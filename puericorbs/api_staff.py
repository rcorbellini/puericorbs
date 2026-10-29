"""A API da equipe: o pediatra (tudo da prática dele) e a atendente (agenda, cadastro, dinheiro; nada clínico).

A atendente pode atender mais de uma prática da mesma clínica: os pedidos dela levam `practice_id` e cada prática é
aberta no banco dela (`ctx.open_practice`), sempre depois de conferir que ela é membro (`staff_practices`).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from . import care, catalog, files, finance, fiscal, growth, invites, plans, practices, protocols, scheduling, views
from .context import Ctx, clinician, dep, staff, staff_practices
from .db import insert, many, now_iso, one, transaction, update

router = APIRouter(prefix="/api/staff")


# ---- ajudantes -----------------------------------------------------------------------------------------------------

def _date(text: str | None, default: date) -> date:
    if not text:
        return default
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(400, "Data inválida. Use AAAA-MM-DD.") from exc


def _practice(ctx: Ctx, practice_id: int | None):
    """A prática do pedido (a deste site, ou outra que a pessoa atende na mesma clínica) e o banco dela."""
    staff(ctx)
    pid = practice_id or ctx.practice_id
    allowed = {p["id"]: p for p in staff_practices(ctx)}
    if pid not in allowed:
        raise HTTPException(404, "Consultório não encontrado.")
    return allowed[pid], ctx.open_practice(pid)


def _get(conn, table: str, row_id: int, what: str) -> dict:
    row = one(conn, f"SELECT * FROM {table} WHERE id = ?", (row_id,))
    if not row:
        raise HTTPException(404, f"{what} não encontrado.")
    return row


def add_months(d: date, n: int) -> date:
    import calendar
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


# ---- hoje (o painel do pediatra) ------------------------------------------------------------------------------------

@router.get("/today")
def today(ctx: Ctx = Depends(dep)):
    clinician(ctx)
    conn, day = ctx.conn, ctx.today
    appts = views.day_appointments(conn, day, ctx.now, staff=True)
    waiting = sorted([a for a in appts if a["status"] == "chegou"], key=lambda a: a["arrived_at"] or "")
    current = next((a for a in appts if a["status"] == "em_atendimento"), None)
    upcoming = [a for a in appts if a["status"] in ("agendado", "confirmado") and a["start_at"] >= ctx.now.strftime("%Y-%m-%dT%H:%M")]
    focus = current or (waiting[0] if waiting else (upcoming[0] if upcoming else None))
    focus_info = None
    if focus:
        pt = one(conn, "SELECT * FROM patients WHERE id = ?", (focus["patient"]["id"],))
        focus_info = {"appointment": focus, "patient": views.patient_brief(conn, pt, day, clinical=True)}
    review = many(conn, """SELECT f.id, f.kind, f.title, f.note, f.created_at, f.uploader_name, p.name AS patient,
                                  p.birth_date FROM files f LEFT JOIN patients p ON p.id = f.patient_id
                           WHERE f.needs_review = 1 AND f.reviewed_at IS NULL ORDER BY f.created_at DESC""")
    for r in review:
        if r["birth_date"]:
            r["age_short"] = care.age_short(date.fromisoformat(r["birth_date"]), day)
    patients = many(conn, "SELECT * FROM patients")
    late_visits = 0
    late_vaccines = 0
    for p in patients:
        nv = care.next_visit_state(conn, p, day)
        if nv and nv["status"] == "atrasado":
            late_visits += 1
        if care.overdue_vaccines(conn, p, day):
            late_vaccines += 1
    old_exams = one(conn, """SELECT COUNT(*) AS n FROM care_items WHERE kind = 'exame' AND status = 'pendente'
                             AND file_id IS NULL AND created_at < ?""", ((day - timedelta(days=15)).isoformat(),))["n"]
    received = one(conn, "SELECT COALESCE(SUM(amount_cents), 0) AS s FROM charges WHERE status = 'paga' AND paid_on = ?",
                   (day.isoformat(),))["s"]
    expected = sum(a["price_cents"] for a in appts if not a["covered"] and a["status"] != "faltou")
    return {
        "date": day.isoformat(), "now": ctx.now.strftime("%H:%M"),
        "focus": focus_info, "waiting": waiting, "appointments": appts,
        "reserved_free": views.free_reserved(conn, day),
        "counts": {"total": len(appts), "squeeze": sum(1 for a in appts if a["kind"] == "encaixe"),
                   "covered": sum(1 for a in appts if a["covered"])},
        "review": review[:6], "review_count": len(review),
        "care": {"late_visits": late_visits, "late_vaccines": late_vaccines, "old_exams": old_exams},
        "money": {"expected": expected, "received": received},
    }


# ---- agenda ---------------------------------------------------------------------------------------------------------

@router.get("/agenda")
def agenda(day_: str | None = Query(None, alias="date"), scope: str | None = None, ctx: Ctx = Depends(dep)):
    staff(ctx)
    day = _date(day_, ctx.today)
    scope = scope or ("clinic" if ctx.role == "receptionist" else "me")
    pracs = staff_practices(ctx) if scope == "clinic" else [p for p in staff_practices(ctx) if p["id"] == ctx.practice_id]
    columns = []
    for p in pracs:
        conn = ctx.open_practice(p["id"])
        columns.append({
            "practice": {"id": p["id"], "name": p["name"], "slug": p["slug"], "accent": p["accent"]},
            "windows": [[s, e] for s, e in scheduling.windows(conn, day)],
            "closure": views.closure_view(scheduling.closure(conn, day)),
            "reserved_free": views.free_reserved(conn, day),
            "appointments": views.day_appointments(conn, day, ctx.now, practice=p, staff=True),
        })
    return {"date": day.isoformat(), "today": ctx.today.isoformat(), "now": ctx.now.strftime("%H:%M"),
            "columns": columns}


@router.get("/slots")
def slots(service_id: int, day_: str | None = Query(None, alias="date"), practice_id: int | None = None,
          ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, practice_id)
    svc = _get(conn, "services", service_id, "Serviço")
    day = _date(day_, ctx.today)
    return {"date": day.isoformat(), "times": scheduling.free_times(conn, svc, day, ctx.now, for_family=False)}


# ---- horários: a grade da semana (a pediatra) e a agenda fechada (a equipe) --------------------------------------------

def _staff_rows(ctx: Ctx, conn, practice: dict, rows: list[dict]) -> list[dict]:
    return [views.appointment_row(conn, r, ctx.now, practice=practice, staff=True) for r in rows]


@router.get("/schedule")
def schedule(practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, practice_id)
    closures = []
    for c in many(conn, """SELECT * FROM schedule_exceptions WHERE COALESCE(end_day, day) >= ? ORDER BY day, id""",
                  (ctx.today.isoformat(),)):
        view = views.closure_view(c)
        by = one(ctx.pconn, "SELECT name FROM users WHERE id = ?", (c["created_by"],)) if c["created_by"] else None
        view["by"] = by["name"] if by else None
        view["appointments"] = _staff_rows(ctx, conn, practice, scheduling.in_days(
            conn, date.fromisoformat(view["start"]), date.fromisoformat(view["end"])))
        closures.append(view)
    reserved = many(conn, "SELECT weekday, start_min, duration_min FROM reserved_slots ORDER BY weekday, start_min")
    return {
        "practice": {"id": practice["id"], "name": practice["name"]}, "today": ctx.today.isoformat(),
        "can_edit_hours": practice["role"] == "clinician",
        "periods": [{"weekday": r["weekday"], "start": scheduling.hhmm(r["start_min"]), "end": scheduling.hhmm(r["end_min"])}
                    for r in many(conn, "SELECT * FROM availability ORDER BY weekday, start_min")],
        "sick_slots": bool(reserved), "sick_duration": scheduling.sick_duration(conn),
        "reserved": [{"weekday": r["weekday"], "time": scheduling.hhmm(r["start_min"]), "duration_min": r["duration_min"]}
                     for r in reserved],
        "closures": closures,
    }


class Hours(BaseModel):
    periods: list[dict] = Field(default_factory=list)
    sick_slots: bool = True
    practice_id: int | None = None


@router.put("/schedule")
def save_hours(body: Hours, ctx: Ctx = Depends(dep)):
    """A grade nova vale daqui para a frente. O que já estava marcado fora dela continua marcado: a resposta diz o quê,
    para a recepção avisar a família."""
    practice, conn = _practice(ctx, body.practice_id)
    if practice["role"] != "clinician":
        raise HTTPException(403, "Só a pediatra muda os dias e os horários de atendimento.")
    periods = scheduling.parse_periods(body.periods)
    with transaction(conn):
        scheduling.set_hours(conn, periods, body.sick_slots)
    return {"ok": True, "outside": _staff_rows(ctx, conn, practice, scheduling.outside_hours(conn, ctx.today))}


class Closure(BaseModel):
    start: str
    end: str | None = None
    reason: str | None = None
    practice_id: int | None = None


@router.post("/closures")
def close_days(body: Closure, ctx: Ctx = Depends(dep)):
    """Fecha a agenda de um dia (ou de vários): ninguém mais marca neles, nem a família pelo app. As consultas que já
    estavam marcadas continuam, e voltam na resposta para a recepção avisar."""
    practice, conn = _practice(ctx, body.practice_id)
    first = _date(body.start, ctx.today)
    last = _date(body.end, first) if body.end else first
    if last < first:
        raise HTTPException(400, "O último dia vem antes do primeiro. Confira as datas.")
    if last < ctx.today:
        raise HTTPException(400, "Esses dias já passaram. Escolha a partir de hoje.")
    if (last - first).days > 366:
        raise HTTPException(400, "Feche no máximo um ano de cada vez.")
    reason = (body.reason or "").strip()[:80] or None
    cid = insert(conn, "schedule_exceptions", {"day": first.isoformat(), "end_day": last.isoformat(), "reason": reason,
                                               "created_by": ctx.user["id"], "created_at": now_iso()})
    return {"id": cid, "affected": _staff_rows(ctx, conn, practice, scheduling.in_days(conn, first, last))}


@router.delete("/closures/{closure_id}")
def reopen_days(closure_id: int, practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, practice_id)
    _get(conn, "schedule_exceptions", closure_id, "Fechamento")
    conn.execute("DELETE FROM schedule_exceptions WHERE id = ?", (closure_id,))
    return {"ok": True}


class NewAppointment(BaseModel):
    patient_id: int
    service_id: int
    date: str
    time: str
    kind: str = "normal"
    notes: str | None = None
    practice_id: int | None = None


@router.post("/appointments")
def new_appointment(body: NewAppointment, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, body.practice_id)
    patient = _get(conn, "patients", body.patient_id, "Paciente")
    svc = _get(conn, "services", body.service_id, "Serviço")
    try:
        start = datetime.fromisoformat(f"{body.date}T{body.time}")
    except ValueError as exc:
        raise HTTPException(400, "Data ou horário inválido.") from exc
    kind = "encaixe" if body.kind == "encaixe" else "normal"
    with transaction(conn):
        aid = scheduling.book(conn, patient=patient, service=svc, start=start, now=ctx.now,
                              source="pediatra" if practice["role"] == "clinician" else "recepcao", kind=kind,
                              user_id=ctx.user["id"], notes=body.notes)
    return {"id": aid}


class Action(BaseModel):
    action: str
    practice_id: int | None = None


@router.post("/appointments/{appt_id}/action")
def appointment_action(appt_id: int, body: Action, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, body.practice_id)
    if body.action in ("iniciar", "finalizar") and practice["role"] != "clinician":
        raise HTTPException(403, "Só o pediatra começa e finaliza a consulta.")
    appt = _get(conn, "appointments", appt_id, "Agendamento")
    with transaction(conn):
        status = scheduling.transition(conn, appt, body.action, ctx.now)
        encounter_id = None
        if body.action == "iniciar":
            encounter_id = _open_encounter(ctx, conn, appt)
    return {"status": status, "encounter_id": encounter_id}


class Asked(BaseModel):
    practice_id: int | None = None


@router.post("/appointments/{appt_id}/asked")
def appointment_asked(appt_id: int, body: Asked, ctx: Ctx = Depends(dep)):
    """A recepção abriu o WhatsApp para pedir a confirmação: a lista mostra que o pedido já foi."""
    practice, conn = _practice(ctx, body.practice_id)
    _get(conn, "appointments", appt_id, "Agendamento")
    asked = ctx.now.strftime("%Y-%m-%dT%H:%M:%S")
    update(conn, "appointments", appt_id, {"confirm_asked_at": asked})
    return {"confirm_asked_at": asked}


class Receive(BaseModel):
    method: str
    amount_cents: int | None = None
    practice_id: int | None = None


@router.post("/appointments/{appt_id}/receive")
def appointment_receive(appt_id: int, body: Receive, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, body.practice_id)
    if body.method not in finance.METHODS:
        raise HTTPException(400, "Forma de pagamento desconhecida.")
    appt = _get(conn, "appointments", appt_id, "Agendamento")
    with transaction(conn):
        cid = finance.receive_appointment(conn, appt, body.method, ctx.today, body.amount_cents)
    return {"charge_id": cid}


# ---- pacientes e famílias ---------------------------------------------------------------------------------------------

@router.get("/patients")
def patients(q: str = "", practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, practice_id)
    clinical = practice["role"] == "clinician"
    term = f"%{q.strip()}%"
    rows = many(conn, """SELECT DISTINCT p.* FROM patients p JOIN families f ON f.id = p.family_id
                         LEFT JOIN guardians g ON g.family_id = f.id
                         WHERE p.name LIKE ? OR f.name LIKE ? OR g.name LIKE ? OR g.phone LIKE ?
                         ORDER BY p.name LIMIT 200""", (term, term, term, term))
    out = []
    for r in rows:
        b = views.patient_brief(conn, r, ctx.today, clinical=False)
        nv = care.next_visit_state(conn, r, ctx.today)
        b["next_visit"] = {"title": nv["title"], "status": nv["status"], "detail": nv["detail"]} if nv else None
        if clinical:
            b["allergies"] = r["allergies"]
        out.append(b)
    return {"patients": out, "practice": {"id": practice["id"], "name": practice["name"]}}


class Guardian(BaseModel):
    name: str
    relation: str = "mãe"
    phone: str | None = None
    email: str | None = None
    cpf: str | None = None


class Child(BaseModel):
    name: str
    sex: str
    birth_date: str
    gestational_weeks: int | None = None


class NewFamily(BaseModel):
    guardian: Guardian
    child: Child
    family_name: str | None = None
    practice_id: int | None = None


@router.post("/families")
def new_family(body: NewFamily, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, body.practice_id)
    if body.child.sex not in ("F", "M"):
        raise HTTPException(400, "Escolha o sexo da criança (F ou M): as curvas da OMS são separadas.")
    birth = _date(body.child.birth_date, ctx.today)
    if birth > ctx.today:
        raise HTTPException(400, "A data de nascimento está no futuro.")
    cpf = fiscal.clean_cpf(body.guardian.cpf, "do responsável")
    surname = body.child.name.strip().split()[-1] if len(body.child.name.split()) > 1 else body.guardian.name.split()[-1]
    with transaction(conn):
        fid = insert(conn, "families", {"name": body.family_name or f"Família {surname}", "created_at": now_iso()})
        # o responsável nasce sem conta: ela só se liga a ele pelo convite da família, com a senha de quem a tem
        # (o e-mail digitado aqui não prova nada; ligar direto entregaria a conta de outra pessoa)
        insert(conn, "guardians", {"family_id": fid, "user_id": None, "name": body.guardian.name.strip(),
                                   "relation": body.guardian.relation, "phone": body.guardian.phone,
                                   "email": (body.guardian.email or "").strip().lower() or None, "cpf": cpf,
                                   "is_legal": 1, "is_financial": 1, "created_at": now_iso()})
        pid = insert(conn, "patients", {"family_id": fid, "name": body.child.name.strip(), "sex": body.child.sex,
                                        "birth_date": birth.isoformat(), "gestational_weeks": body.child.gestational_weeks,
                                        "created_at": now_iso()})
    return {"patient_id": pid, "family_id": fid}


@router.get("/patients/{patient_id}")
def patient(patient_id: int, practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, practice_id)
    row = _get(conn, "patients", patient_id, "Paciente")
    clinical = practice["role"] == "clinician"
    ctx.audit("ver_paciente" if clinical else "ver_cadastro", "patient", patient_id, conn=conn)
    out = {"patient": views.patient_brief(conn, row, ctx.today, clinical=clinical), "clinical": clinical}
    appts = many(conn, "SELECT * FROM appointments WHERE patient_id = ? ORDER BY start_at DESC", (patient_id,))
    out["appointments"] = [views.appointment_row(conn, a, ctx.now) for a in appts]
    vis = None if clinical else "admin"
    file_rows = many(conn, "SELECT * FROM files WHERE patient_id = ? OR (patient_id IS NULL AND family_id = ?) ORDER BY created_at DESC",
                     (patient_id, row["family_id"]))
    out["files"] = [_file_view(f) for f in file_rows if vis is None or f["visibility"] == vis]
    if clinical:
        out["timeline"] = care.timeline(conn, row, ctx.today, audience="clinician")
        out["vaccines"] = care.vaccine_card(conn, row, ctx.today)
        out["milestones"] = care.milestones_view(conn, row, ctx.today)
        out["measurements"] = many(conn, "SELECT * FROM measurements WHERE patient_id = ? ORDER BY taken_on DESC", (patient_id,))
        out["encounters"] = many(conn, """SELECT e.id, e.started_at, e.finished_at, e.status, e.cid, e.conduct,
                                                 e.family_summary, e.summary_released, s.name AS service
                                          FROM encounters e LEFT JOIN services s ON s.id = e.service_id
                                          WHERE e.patient_id = ? ORDER BY e.started_at DESC""", (patient_id,))
        out["care_items"] = many(conn, "SELECT * FROM care_items WHERE patient_id = ? ORDER BY created_at DESC", (patient_id,))
    else:
        out["timeline"] = care.timeline(conn, row, ctx.today, audience="reception")
    out["charges"] = many(conn, "SELECT * FROM charges WHERE patient_id = ? ORDER BY due_on DESC LIMIT 20", (patient_id,))
    out["family_access"] = invites.family_access(ctx.pconn, conn, practice["id"], row["family_id"])
    return out


class PatientEdit(BaseModel):
    allergies: str | None = None
    conditions: str | None = None
    gestational_weeks: int | None = None
    birth_weight_g: int | None = None
    birth_length_cm: float | None = None
    birth_head_cm: float | None = None
    birth_type: str | None = None


@router.put("/patients/{patient_id}")
def patient_edit(patient_id: int, body: PatientEdit, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    _get(ctx.conn, "patients", patient_id, "Paciente")
    update(ctx.conn, "patients", patient_id, body.model_dump(exclude_unset=True))
    return {"ok": True}


class Immunization(BaseModel):
    code: str
    applied_on: str
    lot: str | None = None
    place: str | None = None


@router.post("/patients/{patient_id}/immunizations")
def add_immunization(patient_id: int, body: Immunization, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    _get(ctx.conn, "patients", patient_id, "Paciente")
    if body.code not in protocols.VACCINE_BY_CODE:
        raise HTTPException(400, "Vacina desconhecida.")
    on = _date(body.applied_on, ctx.today)
    ctx.conn.execute("""INSERT INTO immunizations (patient_id, code, applied_on, lot, place, source)
                        VALUES (?, ?, ?, ?, ?, 'consultorio')
                        ON CONFLICT (patient_id, code) DO UPDATE SET applied_on = excluded.applied_on,
                        lot = excluded.lot, place = excluded.place""",
                     (patient_id, body.code, on.isoformat(), body.lot, body.place))
    return {"ok": True}


@router.delete("/patients/{patient_id}/immunizations/{code}")
def remove_immunization(patient_id: int, code: str, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    ctx.conn.execute("DELETE FROM immunizations WHERE patient_id = ? AND code = ?", (patient_id, code))
    return {"ok": True}


class Measurement(BaseModel):
    taken_on: str | None = None
    weight: float | None = None
    length: float | None = None
    head: float | None = None


@router.post("/patients/{patient_id}/measurements")
def add_measurement(patient_id: int, body: Measurement, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    _get(ctx.conn, "patients", patient_id, "Paciente")
    if not (body.weight or body.length or body.head):
        raise HTTPException(400, "Informe ao menos uma medida.")
    mid = insert(ctx.conn, "measurements", {"patient_id": patient_id, "taken_on": _date(body.taken_on, ctx.today).isoformat(),
                                            "weight_kg": body.weight, "length_cm": body.length, "head_cm": body.head,
                                            "source": "consulta"})
    return {"id": mid}


class MilestoneMark(BaseModel):
    code: str
    checked: bool = True
    on: str | None = None


@router.post("/patients/{patient_id}/milestones")
def mark_milestone(patient_id: int, body: MilestoneMark, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    _get(ctx.conn, "patients", patient_id, "Paciente")
    _set_milestone(ctx.conn, patient_id, body.code, body.checked, _date(body.on, ctx.today), "pediatra", ctx.user["name"])
    return {"ok": True}


def _set_milestone(conn, patient_id: int, code: str, checked: bool, on: date, by: str, name: str) -> None:
    if code not in protocols.MILESTONE_BY_CODE:
        raise HTTPException(400, "Marco desconhecido.")
    if checked:
        conn.execute("""INSERT INTO milestone_checks (patient_id, code, achieved_on, marked_by, marker_name)
                        VALUES (?, ?, ?, ?, ?) ON CONFLICT (patient_id, code) DO NOTHING""",
                     (patient_id, code, on.isoformat(), by, name))
    else:
        conn.execute("DELETE FROM milestone_checks WHERE patient_id = ? AND code = ?", (patient_id, code))


class CareItem(BaseModel):
    kind: str
    title: str
    detail: str | None = None
    due_to: str | None = None
    owner: str = "familia"
    visibility: str = "family"
    encounter_id: int | None = None


@router.post("/patients/{patient_id}/care-items")
def add_care_item(patient_id: int, body: CareItem, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    _get(ctx.conn, "patients", patient_id, "Paciente")
    if body.kind not in ("exame", "tarefa", "orientacao", "retorno"):
        raise HTTPException(400, "Tipo de item desconhecido.")
    if not body.title.strip():
        raise HTTPException(400, "Escreva o que precisa ser feito.")
    iid = insert(ctx.conn, "care_items", {
        "patient_id": patient_id, "kind": body.kind, "title": body.title.strip(), "detail": body.detail,
        "due_to": _date(body.due_to, ctx.today).isoformat() if body.due_to else None,
        "owner": body.owner if body.owner in ("familia", "consultorio") else "familia",
        "visibility": "internal" if body.visibility == "internal" else "family",
        "encounter_id": body.encounter_id, "created_at": now_iso()})
    return {"id": iid}


class CareStatus(BaseModel):
    status: str


@router.post("/care-items/{item_id}")
def care_item_status(item_id: int, body: CareStatus, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    _get(ctx.conn, "care_items", item_id, "Item")
    if body.status not in ("pendente", "feito", "dispensado"):
        raise HTTPException(400, "Estado desconhecido.")
    update(ctx.conn, "care_items", item_id, {"status": body.status,
                                             "done_at": now_iso() if body.status == "feito" else None})
    return {"ok": True}


@router.get("/patients/{patient_id}/chart")
def chart(patient_id: int, indicator: str = "wfa", ctx: Ctx = Depends(dep)):
    clinician(ctx)
    row = _get(ctx.conn, "patients", patient_id, "Paciente")
    if indicator not in growth.INDICATORS or indicator == "bfa":
        raise HTTPException(400, "Indicador desconhecido.")
    return views.growth_chart(ctx.conn, row, indicator, ctx.today)


@router.get("/growth")
def growth_assess(patient_id: int, weight: float | None = None, length: float | None = None,
                  head: float | None = None, on: str | None = None, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    row = _get(ctx.conn, "patients", patient_id, "Paciente")
    day = _date(on, ctx.today)
    return growth.assess(row["sex"], date.fromisoformat(row["birth_date"]), day, row["gestational_weeks"],
                         weight_kg=weight, length_cm=length, head_cm=head)


# ---- a consulta ------------------------------------------------------------------------------------------------------

def _open_encounter(ctx: Ctx, conn, appt: dict) -> int:
    existing = one(conn, "SELECT id FROM encounters WHERE appointment_id = ?", (appt["id"],))
    if existing:
        return existing["id"]
    return insert(conn, "encounters", {"appointment_id": appt["id"], "patient_id": appt["patient_id"],
                                       "service_id": appt["service_id"], "status": "aberta",
                                       "started_at": now_iso(), "notes": "{}", "clinician_id": ctx.user["id"]})


@router.post("/appointments/{appt_id}/encounter")
def start_encounter(appt_id: int, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    appt = _get(ctx.conn, "appointments", appt_id, "Agendamento")
    with transaction(ctx.conn):
        if appt["status"] in ("agendado", "confirmado", "chegou"):
            scheduling.transition(ctx.conn, appt, "iniciar", ctx.now)
        eid = _open_encounter(ctx, ctx.conn, appt)
    return {"encounter_id": eid}


@router.get("/encounters/{enc_id}")
def encounter(enc_id: int, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    conn = ctx.conn
    enc = _get(conn, "encounters", enc_id, "Consulta")
    pt = _get(conn, "patients", enc["patient_id"], "Paciente")
    svc = one(conn, "SELECT * FROM services WHERE id = ?", (enc["service_id"],)) if enc["service_id"] else None
    template = catalog.template_of(svc) if svc else catalog.TEMPLATES["livre"]
    appt = one(conn, "SELECT * FROM appointments WHERE id = ?", (enc["appointment_id"],)) if enc["appointment_id"] else None
    ctx.audit("abrir_consulta", "encounter", enc_id)
    measure = one(conn, "SELECT * FROM measurements WHERE encounter_id = ?", (enc_id,))
    last = one(conn, "SELECT * FROM measurements WHERE patient_id = ? AND (encounter_id IS NULL OR encounter_id != ?) "
                     "ORDER BY taken_on DESC LIMIT 1", (pt["id"], enc_id))
    prev = one(conn, """SELECT e.finished_at, e.conduct, e.family_summary, s.name AS service FROM encounters e
                        LEFT JOIN services s ON s.id = e.service_id
                        WHERE e.patient_id = ? AND e.status = 'finalizada' AND e.id != ? ORDER BY e.finished_at DESC LIMIT 1""",
                (pt["id"], enc_id))
    rows, _ = care._visits(date.fromisoformat(pt["birth_date"]), many(conn, """
        SELECT a.id, a.start_at, a.status, s.kind FROM appointments a JOIN services s ON s.id = a.service_id
        WHERE a.patient_id = ? AND a.status != 'cancelado' ORDER BY a.start_at""", (pt["id"],)), ctx.today)
    visit = next((r["visit"].title for r in rows if r["match"] and appt and r["match"]["id"] == appt["id"]), None)
    timeline = care.timeline(conn, pt, ctx.today, audience="clinician")
    return {
        "encounter": {**enc, "notes": care.load_json(enc["notes"], {})},
        "title": visit or (svc["name"] if svc else "Consulta"),
        "template": template, "template_key": catalog.config_of(svc)["template"] if svc else "livre",
        "patient": views.patient_brief(conn, pt, ctx.today, clinical=True),
        "appointment": views.appointment_row(conn, appt, ctx.now) if appt else None,
        "measurement": measure, "last_measurement": last, "previous": prev,
        "milestones": care.milestones_view(conn, pt, ctx.today),
        "care_items": many(conn, "SELECT * FROM care_items WHERE encounter_id = ? ORDER BY id", (enc_id,)),
        "todo": [t for t in timeline["todo"] if t["type"] in ("consulta", "vacina")][:4],
        "vaccines_due": [v for v in care.vaccine_card(conn, pt, ctx.today) if v["status"] in ("pendente", "atrasado")],
    }


class EncounterSave(BaseModel):
    notes: dict = Field(default_factory=dict)
    cid: str | None = None
    conduct: str | None = None
    family_summary: str | None = None
    summary_released: bool = False
    weight: float | None = None
    length: float | None = None
    head: float | None = None
    milestones: list[str] | None = None


def _save_encounter(ctx: Ctx, enc: dict, body: EncounterSave) -> None:
    conn = ctx.conn
    update(conn, "encounters", enc["id"], {
        "notes": json.dumps(body.notes, ensure_ascii=False), "cid": body.cid, "conduct": body.conduct,
        "family_summary": body.family_summary, "summary_released": 1 if body.summary_released else 0})
    if body.weight or body.length or body.head:
        row = one(conn, "SELECT id FROM measurements WHERE encounter_id = ?", (enc["id"],))
        values = {"weight_kg": body.weight, "length_cm": body.length, "head_cm": body.head}
        if row:
            update(conn, "measurements", row["id"], values)
        else:
            insert(conn, "measurements", {"patient_id": enc["patient_id"], "encounter_id": enc["id"],
                                          "taken_on": ctx.today.isoformat(), "source": "consulta", **values})
    if body.milestones is not None:
        band = protocols.milestone_band((ctx.today - date.fromisoformat(
            one(conn, "SELECT birth_date FROM patients WHERE id = ?", (enc["patient_id"],))["birth_date"])).days)
        codes = [m.code for m in band.items] if band else []
        for code in codes:
            _set_milestone(conn, enc["patient_id"], code, code in body.milestones, ctx.today, "pediatra", ctx.user["name"])


@router.put("/encounters/{enc_id}")
def save_encounter(enc_id: int, body: EncounterSave, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    enc = _get(ctx.conn, "encounters", enc_id, "Consulta")
    with transaction(ctx.conn):
        _save_encounter(ctx, enc, body)
    return {"ok": True}


@router.post("/encounters/{enc_id}/finish")
def finish_encounter(enc_id: int, body: EncounterSave, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    enc = _get(ctx.conn, "encounters", enc_id, "Consulta")
    with transaction(ctx.conn):
        _save_encounter(ctx, enc, body)
        update(ctx.conn, "encounters", enc_id, {"status": "finalizada", "finished_at": now_iso()})
        if enc["appointment_id"]:
            appt = one(ctx.conn, "SELECT * FROM appointments WHERE id = ?", (enc["appointment_id"],))
            if appt and appt["status"] != "atendido":
                scheduling.transition(ctx.conn, appt, "finalizar", ctx.now)
    return {"ok": True}


# ---- a caixa de revisão e os arquivos ----------------------------------------------------------------------------

def _file_view(f: dict) -> dict:
    return {k: f[k] for k in ("id", "kind", "title", "note", "mime", "size", "visibility", "uploader_role",
                              "uploader_name", "needs_review", "reviewed_at", "review_note", "created_at",
                              "patient_id", "care_item_id")} | {"kind_label": files.KINDS.get(f["kind"], f["kind"])}


@router.get("/review")
def review(ctx: Ctx = Depends(dep)):
    clinician(ctx)
    rows = many(ctx.conn, """SELECT f.*, p.name AS patient, p.birth_date FROM files f LEFT JOIN patients p ON p.id = f.patient_id
                             WHERE f.needs_review = 1 ORDER BY f.reviewed_at IS NOT NULL, f.created_at DESC LIMIT 60""")
    out = []
    for r in rows:
        v = _file_view(r)
        v["patient"] = r["patient"]
        v["age_short"] = care.age_short(date.fromisoformat(r["birth_date"]), ctx.today) if r["birth_date"] else None
        out.append(v)
    return {"files": out}


class ReviewNote(BaseModel):
    note: str = ""


@router.post("/files/{file_id}/review")
def review_file(file_id: int, body: ReviewNote, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    f = _get(ctx.conn, "files", file_id, "Arquivo")
    with transaction(ctx.conn):
        update(ctx.conn, "files", file_id, {"reviewed_at": now_iso(), "review_note": body.note.strip() or None})
        if f["care_item_id"]:
            update(ctx.conn, "care_items", f["care_item_id"], {"status": "feito", "done_at": now_iso(), "file_id": file_id})
    return {"ok": True}


@router.post("/files")
async def staff_upload(patient_id: int = Form(...), kind: str = Form(...), title: str = Form(...),
                       visibility: str = Form("family"), upload: UploadFile = File(...), ctx: Ctx = Depends(dep)):
    staff(ctx)
    if kind not in files.KINDS:
        raise HTTPException(400, "Tipo de arquivo desconhecido.")
    if ctx.role == "receptionist" and kind not in files.ADMIN:
        raise HTTPException(403, "A recepção envia só papelada: nota, recibo, comprovante e documento.")
    pt = _get(ctx.conn, "patients", patient_id, "Paciente")
    content = await upload.read()
    stored = files.store(ctx.settings.data_dir, ctx.practice_id, content, ctx.settings.max_upload_mb)
    vis = "admin" if kind in files.ADMIN else ("internal" if visibility == "internal" else "family")
    fid = insert(ctx.conn, "files", {
        "family_id": pt["family_id"], "patient_id": patient_id, "kind": kind, "title": title.strip() or files.KINDS[kind],
        "original_name": upload.filename, **stored, "visibility": vis, "uploaded_by": ctx.user["id"],
        "uploader_role": "pediatra" if ctx.role == "clinician" else "atendente", "uploader_name": ctx.user["name"],
        "needs_review": 0, "created_at": now_iso()})
    return {"id": fid}


# ---- serviços ---------------------------------------------------------------------------------------------------------

@router.get("/services")
def services(practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, practice_id)
    rows = many(conn, "SELECT * FROM services ORDER BY position, id")
    return {"services": [catalog.as_dict(r) for r in rows], "kinds": catalog.KINDS, "categories": catalog.CATEGORIES,
            "templates": {k: v["label"] for k, v in catalog.TEMPLATES.items()},
            "schedule": {"availability": many(conn, "SELECT * FROM availability ORDER BY weekday, start_min"),
                         "reserved": many(conn, "SELECT * FROM reserved_slots ORDER BY weekday, start_min")}}


class ServiceBody(BaseModel):
    name: str
    category: str = "consulta"
    kind: str = "well_child"
    duration_min: int = 30
    price_cents: int = 0
    active: bool = True
    config: dict = Field(default_factory=dict)


def _service_values(body: ServiceBody) -> dict:
    if not body.name.strip():
        raise HTTPException(400, "Dê um nome ao serviço.")
    if body.kind not in catalog.KINDS or body.category not in catalog.CATEGORIES:
        raise HTTPException(400, "Tipo ou categoria desconhecidos.")
    if not 5 <= body.duration_min <= 240:
        raise HTTPException(400, "A duração vai de 5 a 240 minutos.")
    if body.price_cents < 0:
        raise HTTPException(400, "O preço não pode ser negativo.")
    known = set(catalog.DEFAULT_CONFIG)
    cfg = {k: v for k, v in body.config.items() if k in known}
    return {"name": body.name.strip(), "category": body.category, "kind": body.kind, "duration_min": body.duration_min,
            "price_cents": body.price_cents, "active": 1 if body.active else 0,
            "config": json.dumps(cfg, ensure_ascii=False), "updated_at": now_iso()}


@router.post("/services")
def create_service(body: ServiceBody, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    values = _service_values(body)
    pos = one(ctx.conn, "SELECT COALESCE(MAX(position), 0) + 1 AS p FROM services")["p"]
    return {"id": insert(ctx.conn, "services", {**values, "position": pos})}


@router.put("/services/{service_id}")
def edit_service(service_id: int, body: ServiceBody, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    old = _get(ctx.conn, "services", service_id, "Serviço")
    values = _service_values(body)
    changed = any(str(old[k]) != str(values[k]) for k in ("duration_min", "price_cents", "config"))
    if changed:
        values["version"] = old["version"] + 1
    update(ctx.conn, "services", service_id, values)
    return {"ok": True, "version": values.get("version", old["version"])}


# ---- planos ----------------------------------------------------------------------------------------------------------

@router.get("/plans")
def plans_view(ctx: Ctx = Depends(dep)):
    staff(ctx)
    conn = ctx.conn
    finance.ensure_plan_charges(conn, ctx.today)
    st = plans.stats(conn, ctx.today)
    members = []
    for m in many(conn, """SELECT m.*, pt.name AS patient, pt.family_id, f.name AS family FROM memberships m
                           JOIN patients pt ON pt.id = m.patient_id JOIN families f ON f.id = pt.family_id
                           ORDER BY m.status = 'cancelado', pt.name"""):
        view = plans.membership_view(conn, m)
        g = one(conn, "SELECT name FROM guardians WHERE family_id = ? AND is_financial = 1 ORDER BY id LIMIT 1", (m["family_id"],))
        late = one(conn, "SELECT due_on FROM charges WHERE membership_id = ? AND status = 'aberta' AND due_on < ? ORDER BY due_on LIMIT 1",
                   (m["id"], ctx.today.isoformat()))
        view.update({"patient": m["patient"], "patient_id": m["patient_id"], "guardian": g["name"] if g else m["family"],
                     "late_days": (ctx.today - date.fromisoformat(late["due_on"])).days if late else 0,
                     "renews_today": m["ends_on"] == ctx.today.isoformat()})
        members.append(view)
    overdue = one(conn, """SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents), 0) AS s FROM charges
                           WHERE membership_id IS NOT NULL AND status = 'aberta' AND due_on < ?""", (ctx.today.isoformat(),))
    cancelled = one(conn, "SELECT COUNT(*) AS n FROM memberships WHERE status = 'cancelado'")["n"]
    services_rows = many(conn, "SELECT id, name FROM services ORDER BY position")
    return {**st, "members": members, "overdue": overdue, "cancelled": cancelled, "services": services_rows,
            "billing": plans.BILLING}


class PlanBody(BaseModel):
    name: str
    description: str | None = None
    price_cents: int
    months: int = 12
    entry_rule: str | None = None
    max_entry_age_m: int | None = None
    auto_renew: bool = True
    sibling_discount_pct: int = 0
    discount_pct: int = 0
    benefits: list[dict] = Field(default_factory=list)
    perks: list[str] = Field(default_factory=list)
    active: bool = True


def _plan_values(body: PlanBody) -> dict:
    if not body.name.strip():
        raise HTTPException(400, "Dê um nome ao plano.")
    if body.price_cents <= 0:
        raise HTTPException(400, "O plano precisa de um preço por mês.")
    benefits = [{"service_id": int(b["service_id"]), "qty": int(b["qty"]), **({"label": b["label"]} if b.get("label") else {})}
                for b in body.benefits if int(b.get("qty", 0)) > 0]
    return {"name": body.name.strip(), "description": body.description, "price_cents": body.price_cents,
            "months": body.months, "entry_rule": body.entry_rule, "max_entry_age_m": body.max_entry_age_m,
            "auto_renew": 1 if body.auto_renew else 0, "sibling_discount_pct": body.sibling_discount_pct,
            "discount_pct": body.discount_pct, "benefits": json.dumps(benefits, ensure_ascii=False),
            "perks": json.dumps([p for p in body.perks if p.strip()], ensure_ascii=False), "active": 1 if body.active else 0}


@router.post("/plans")
def create_plan(body: PlanBody, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    return {"id": insert(ctx.conn, "plans", {**_plan_values(body), "created_at": now_iso()})}


@router.put("/plans/{plan_id}")
def edit_plan(plan_id: int, body: PlanBody, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    _get(ctx.conn, "plans", plan_id, "Plano")
    update(ctx.conn, "plans", plan_id, _plan_values(body))
    return {"ok": True}


class MembershipBody(BaseModel):
    patient_id: int
    plan_id: int
    billing: str = "cartao"
    due_day: int = 10
    started_on: str | None = None


@router.post("/memberships")
def create_membership(body: MembershipBody, ctx: Ctx = Depends(dep)):
    staff(ctx)
    conn = ctx.conn
    pt = _get(conn, "patients", body.patient_id, "Paciente")
    plan = plans.plan_dict(_get(conn, "plans", body.plan_id, "Plano"))
    if body.billing not in plans.BILLING:
        raise HTTPException(400, "Forma de cobrança desconhecida.")
    start = _date(body.started_on, ctx.today)
    if plans.active_membership(conn, pt["id"], start):
        raise HTTPException(409, f"{pt['name'].split()[0]} já tem um plano ativo.")
    ends = add_months(start, plan["months"]) - timedelta(days=1)
    siblings = one(conn, """SELECT COUNT(*) AS n FROM memberships m JOIN patients p ON p.id = m.patient_id
                            WHERE p.family_id = ? AND m.status = 'ativo' AND m.patient_id != ?""", (pt["family_id"], pt["id"]))["n"]
    price = plan["price_cents"]
    if siblings and plan["sibling_discount_pct"]:
        price = round(price * (100 - plan["sibling_discount_pct"]) / 100)
    with transaction(conn):
        mid = insert(conn, "memberships", {"plan_id": plan["id"], "patient_id": pt["id"], "started_on": start.isoformat(),
                                           "ends_on": ends.isoformat(), "billing": body.billing,
                                           "due_day": max(1, min(28, body.due_day)), "status": "ativo",
                                           "price_cents": price, "created_at": now_iso()})
        finance.ensure_plan_charges(conn, ctx.today)
    return {"id": mid}


class MembershipStatus(BaseModel):
    status: str
    paused_until: str | None = None


@router.post("/memberships/{membership_id}/status")
def membership_status(membership_id: int, body: MembershipStatus, ctx: Ctx = Depends(dep)):
    staff(ctx)
    _get(ctx.conn, "memberships", membership_id, "Adesão")
    if body.status not in ("ativo", "pausado", "cancelado"):
        raise HTTPException(400, "Estado desconhecido.")
    update(ctx.conn, "memberships", membership_id, {
        "status": body.status, "paused_until": _date(body.paused_until, ctx.today).isoformat() if body.paused_until else None})
    return {"ok": True}


# ---- dinheiro ------------------------------------------------------------------------------------------------------

@router.get("/finance")
def finance_view(month: str | None = None, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    finance.ensure_plan_charges(ctx.conn, ctx.today)
    ym = month or ctx.today.isoformat()[:7]
    if len(ym) != 7:
        raise HTTPException(400, "Mês inválido. Use AAAA-MM.")
    out = finance.summary(ctx.conn, ym, ctx.today)
    out["methods"] = finance.METHODS
    out["invoice_labels"] = finance.INVOICE
    out["document"] = fiscal.profile(ctx.practice)["document"]
    return out


@router.get("/finance/export")
def finance_export(month: str | None = None, ctx: Ctx = Depends(dep)):
    """O mês para o contador: o que entrou (com a nota) e o que saiu, num CSV que abre no Excel."""
    import csv
    import io
    from fastapi.responses import Response
    clinician(ctx)
    ym = month or ctx.today.isoformat()[:7]
    first, last = finance.month_range(ym)
    buf = io.StringIO()
    out = csv.writer(buf, delimiter=";")
    out.writerow(["tipo", "data", "familia", "crianca", "descricao", "forma", "valor", "nota"])
    for c in many(ctx.conn, """SELECT c.*, f.name AS family, p.name AS patient FROM charges c JOIN families f ON f.id = c.family_id
                               LEFT JOIN patients p ON p.id = c.patient_id
                               WHERE c.status = 'paga' AND c.paid_on BETWEEN ? AND ? ORDER BY c.paid_on""",
                  (first.isoformat(), last.isoformat())):
        out.writerow(["entrada", c["paid_on"], c["family"], c["patient"] or "", c["description"],
                      finance.METHODS.get(c["method"] or "", c["method"] or ""), f"{c['amount_cents'] / 100:.2f}".replace(".", ","),
                      finance.INVOICE.get(c["invoice"], c["invoice"])])
    for e in many(ctx.conn, "SELECT * FROM expenses WHERE spent_on BETWEEN ? AND ? ORDER BY spent_on",
                  (first.isoformat(), last.isoformat())):
        out.writerow(["saida", e["spent_on"], "", "", e["description"], "", f"-{e['amount_cents'] / 100:.2f}".replace(".", ","), ""])
    ctx.audit("exportar_financeiro", "finance", None)
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="financeiro-{ym}.csv"'})


class Pay(BaseModel):
    method: str


@router.post("/charges/{charge_id}/pay")
def pay_charge(charge_id: int, body: Pay, practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, practice_id)
    ch = _get(conn, "charges", charge_id, "Cobrança")
    if ch["status"] != "aberta":
        raise HTTPException(409, "Esta cobrança não está em aberto.")
    if body.method not in finance.METHODS:
        raise HTTPException(400, "Forma de pagamento desconhecida.")
    update(conn, "charges", charge_id, {"status": "paga", "method": body.method, "paid_on": ctx.today.isoformat()})
    return {"ok": True}


class InvoiceState(BaseModel):
    status: str


@router.post("/charges/{charge_id}/invoice")
def invoice_state(charge_id: int, body: InvoiceState, practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    practice, conn = _practice(ctx, practice_id)
    _get(conn, "charges", charge_id, "Cobrança")
    if body.status not in finance.INVOICE:
        raise HTTPException(400, "Estado de nota desconhecido.")
    update(conn, "charges", charge_id, {"invoice": body.status})
    return {"ok": True}


class Expense(BaseModel):
    description: str
    amount_cents: int
    spent_on: str | None = None
    category: str | None = None


@router.post("/expenses")
def add_expense(body: Expense, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    if not body.description.strip() or body.amount_cents <= 0:
        raise HTTPException(400, "Escreva a despesa e um valor maior que zero.")
    return {"id": insert(ctx.conn, "expenses", {"description": body.description.strip(), "category": body.category,
                                                "amount_cents": body.amount_cents,
                                                "spent_on": _date(body.spent_on, ctx.today).isoformat(),
                                                "created_at": now_iso()})}


@router.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    ctx.conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    return {"ok": True}


# ---- recepção ---------------------------------------------------------------------------------------------------------

def _confirm_day(conn, today: date) -> date:
    """O dia a confirmar: o próximo com consulta marcada, até uma semana à frente (na sexta, a segunda)."""
    row = one(conn, """SELECT substr(start_at, 1, 10) AS d FROM appointments WHERE substr(start_at, 1, 10) BETWEEN ? AND ?
                       AND status IN ('agendado', 'confirmado') ORDER BY start_at LIMIT 1""",
              ((today + timedelta(days=1)).isoformat(), (today + timedelta(days=7)).isoformat()))
    return date.fromisoformat(row["d"]) if row else today + timedelta(days=1)


@router.get("/reception")
def reception(ctx: Ctx = Depends(dep)):
    """As tarefas do dia, de todas as práticas que quem pede atende."""
    staff(ctx)
    out = {"date": ctx.today.isoformat(), "practices": []}
    for p in staff_practices(ctx):
        conn = ctx.open_practice(p["id"])
        finance.ensure_plan_charges(conn, ctx.today)
        day = _confirm_day(conn, ctx.today)
        confirm = [views.appointment_row(conn, a, ctx.now, practice=p, staff=True) for a in many(
            conn, "SELECT * FROM appointments WHERE substr(start_at, 1, 10) = ? AND status IN ('agendado', 'confirmado') ORDER BY start_at",
            (day.isoformat(),))]
        arrivals = [a for a in views.day_appointments(conn, ctx.today, ctx.now, practice=p, staff=True) if a["status"] == "chegou"]
        outreach = []
        for pt in many(conn, "SELECT * FROM patients ORDER BY name"):
            nv = care.next_visit_state(conn, pt, ctx.today)
            if nv and nv["status"] == "atrasado":
                g = one(conn, "SELECT name, phone FROM guardians WHERE family_id = ? ORDER BY id LIMIT 1", (pt["family_id"],))
                outreach.append({"patient_id": pt["id"], "patient": pt["name"],
                                 "age_short": care.age_short(date.fromisoformat(pt["birth_date"]), ctx.today),
                                 "visit": nv["title"], "detail": nv["detail"], "guardian": g["name"] if g else None,
                                 "phone": g["phone"] if g else None})
        invoices = many(conn, """SELECT c.*, f.name AS family, pt.name AS patient FROM charges c JOIN families f ON f.id = c.family_id
                                 LEFT JOIN patients pt ON pt.id = c.patient_id
                                 WHERE c.status = 'paga' AND c.invoice = 'emitir' AND c.amount_cents > 0 ORDER BY c.paid_on""")
        overdue = many(conn, """SELECT c.*, f.name AS family, pt.name AS patient FROM charges c JOIN families f ON f.id = c.family_id
                                LEFT JOIN patients pt ON pt.id = c.patient_id
                                WHERE c.status = 'aberta' AND c.due_on < ? ORDER BY c.due_on""", (ctx.today.isoformat(),))
        to_receive = [a for a in views.day_appointments(conn, ctx.today, ctx.now, practice=p, staff=True)
                      if a["status"] in ("atendido", "em_atendimento", "chegou") and not a["covered"] and not a["paid"] and a["price_cents"] > 0]
        out["practices"].append({
            "practice": {"id": p["id"], "name": p["name"], "slug": p["slug"], "billing_mode": p.get("billing_mode")},
            "confirm_date": day.isoformat(), "confirm": confirm,
            "confirmed": sum(1 for a in confirm if a["status"] == "confirmado"),
            "arrivals": arrivals, "outreach": outreach, "invoices": invoices, "overdue": overdue,
            "to_receive": to_receive,
        })
    return out


# ---- o consultório (como ele aparece no site) -------------------------------------------------------------------------

class PracticeProfile(BaseModel):
    name: str
    title: str = "Pediatra"
    registry: str | None = None
    bio: str | None = None
    address: str | None = None
    phone: str | None = None
    accent: str = "agua"


def _profile(ctx: Ctx) -> dict:
    p = one(ctx.pconn, "SELECT * FROM practices WHERE id = ?", (ctx.practice_id,))
    domains = [d["host"] for d in many(ctx.pconn, "SELECT host FROM domains WHERE practice_id = ? ORDER BY created_at, host",
                                       (ctx.practice_id,))]
    return {"practice": {k: p[k] for k in ("id", "slug", "name", "title", "registry", "bio", "address", "phone", "accent")},
            "domains": domains, "accents": list(practices.ACCENTS)}


@router.get("/practice")
def practice_profile(ctx: Ctx = Depends(dep)):
    """Só a pediatra muda o próprio site, e só pelo domínio dele."""
    clinician(ctx)
    return _profile(ctx)


@router.put("/practice")
def save_practice_profile(body: PracticeProfile, ctx: Ctx = Depends(dep)):
    clinician(ctx)
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "O nome do consultório não pode ficar em branco: é o título do site.")
    if body.accent not in practices.ACCENTS:
        raise HTTPException(400, "Escolha uma das cores da lista.")

    def clean(value: str | None, size: int) -> str | None:
        return (value or "").strip()[:size] or None

    update(ctx.pconn, "practices", ctx.practice_id, {
        "name": name[:80], "title": clean(body.title, 40) or "Pediatra", "registry": clean(body.registry, 80),
        "bio": clean(body.bio, 600), "address": clean(body.address, 160), "phone": clean(body.phone, 40),
        "accent": body.accent})
    return _profile(ctx)

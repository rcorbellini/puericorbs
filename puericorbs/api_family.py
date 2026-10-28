"""A API da família: só as crianças dela, só o que foi liberado para ela.

Toda rota passa por `family_patient` (a criança é desta família?) e responde 404 para o resto: a família nunca descobre
que outra criança existe.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import care, catalog, files, growth, plans, protocols, scheduling, views
from .context import Ctx, dep, family, family_patient
from .db import insert, many, now_iso, one, transaction, update

router = APIRouter(prefix="/api/family")


def _children(ctx: Ctx) -> list[dict]:
    ids = sorted(ctx.family_ids)
    if not ids:
        return []
    rows = many(ctx.conn, f"SELECT * FROM patients WHERE family_id IN ({', '.join('?' for _ in ids)}) ORDER BY birth_date DESC",
                tuple(ids))
    return rows


def _guardian_name(ctx: Ctx) -> str:
    return ctx.guardians[0]["name"] if ctx.guardians else ctx.user["name"]


@router.get("/home")
def home(child: int | None = None, ctx: Ctx = Depends(dep)):
    family(ctx)
    kids = _children(ctx)
    if not kids:
        return {"children": [], "child": None}
    row = next((k for k in kids if k["id"] == child), kids[0])
    tl = care.timeline(ctx.conn, row, ctx.today, audience="family")
    upcoming = [views.appointment_row(ctx.conn, a, ctx.now) for a in many(
        ctx.conn, """SELECT * FROM appointments WHERE patient_id = ? AND status IN ('agendado', 'confirmado', 'chegou', 'em_atendimento')
                     AND start_at >= ? ORDER BY start_at""", (row["id"], ctx.today.isoformat()))]
    return {
        "children": [views.patient_brief(ctx.conn, k, ctx.today, clinical=False) | {"allergies": k["allergies"]} for k in kids],
        "child": row["id"],
        "next": tl["next"], "todo": tl["todo"], "done": tl["done"][:8], "upcoming": upcoming,
        "guardian": _guardian_name(ctx),
    }


@router.get("/children/{child_id}/summary/{encounter_id}")
def summary(child_id: int, encounter_id: int, ctx: Ctx = Depends(dep)):
    row = family_patient(ctx, child_id)
    enc = one(ctx.conn, """SELECT e.family_summary, e.finished_at, e.summary_released, s.name AS service
                           FROM encounters e LEFT JOIN services s ON s.id = e.service_id
                           WHERE e.id = ? AND e.patient_id = ?""", (encounter_id, row["id"]))
    if not enc or not enc["summary_released"]:
        raise HTTPException(404, "Resumo não encontrado.")
    return {"summary": enc["family_summary"], "date": enc["finished_at"], "service": enc["service"]}


@router.get("/children/{child_id}/health")
def health(child_id: int, indicator: str = "wfa", ctx: Ctx = Depends(dep)):
    row = family_patient(ctx, child_id)
    if indicator not in ("wfa", "lhfa", "hcfa"):
        raise HTTPException(400, "Medida desconhecida.")
    return {
        "child": views.patient_brief(ctx.conn, row, ctx.today, clinical=False),
        "chart": views.growth_chart(ctx.conn, row, indicator, ctx.today),
        "vaccines": care.vaccine_card(ctx.conn, row, ctx.today),
        "milestones": care.milestones_view(ctx.conn, row, ctx.today),
    }


class Mark(BaseModel):
    code: str
    checked: bool = True


@router.post("/children/{child_id}/milestones")
def mark(child_id: int, body: Mark, ctx: Ctx = Depends(dep)):
    row = family_patient(ctx, child_id)
    if body.code not in protocols.MILESTONE_BY_CODE:
        raise HTTPException(400, "Marco desconhecido.")
    if body.checked:
        name = _guardian_name(ctx).split()[0]
        relation = ctx.guardians[0]["relation"] if ctx.guardians else ""
        ctx.conn.execute("""INSERT INTO milestone_checks (patient_id, code, achieved_on, marked_by, marker_name)
                            VALUES (?, ?, ?, 'familia', ?) ON CONFLICT (patient_id, code) DO NOTHING""",
                         (row["id"], body.code, ctx.today.isoformat(), f"{name}, {relation}" if relation else name))
    else:
        ctx.conn.execute("DELETE FROM milestone_checks WHERE patient_id = ? AND code = ? AND marked_by = 'familia'",
                         (row["id"], body.code))
    return {"ok": True}


# ---- agendar -----------------------------------------------------------------------------------------------------

def _bookable(ctx: Ctx, row: dict) -> list[dict]:
    age = (ctx.today - date.fromisoformat(row["birth_date"])).days
    out = []
    for s in many(ctx.conn, "SELECT * FROM services WHERE active = 1 ORDER BY position, id"):
        cfg = catalog.config_of(s)
        if cfg["booking"]["family"] and catalog.fits_age(s, age):
            out.append(s)
    return out


@router.get("/children/{child_id}/services")
def bookable(child_id: int, ctx: Ctx = Depends(dep)):
    row = family_patient(ctx, child_id)
    nxt = care.next_visit_state(ctx.conn, row, ctx.today)
    out = []
    for s in _bookable(ctx, row):
        item = views.service_public(ctx.conn, s, row, ctx.today)
        if s["kind"] in care.WELL_KINDS and nxt and nxt["status"] != "agendado":
            item["display"] = nxt["title"]
            item["window"] = {"from": nxt["refs"].get("from"), "to": nxt["refs"].get("to")}
        out.append(item)
    return {"services": out, "next_visit": nxt}


def _service_for(ctx: Ctx, row: dict, service_id: int) -> dict:
    svc = next((s for s in _bookable(ctx, row) if s["id"] == service_id), None)
    if not svc:
        raise HTTPException(404, "Este serviço não está disponível para marcar pelo app.")
    return svc


@router.get("/children/{child_id}/days")
def days(child_id: int, service_id: int, ctx: Ctx = Depends(dep)):
    """Os próximos dias com horário livre. A puericultura começa pela janela do protocolo da criança."""
    row = family_patient(ctx, child_id)
    svc = _service_for(ctx, row, service_id)
    cfg = catalog.config_of(svc)
    start = ctx.today
    window = None
    if svc["kind"] in care.WELL_KINDS:
        nxt = care.next_visit_state(ctx.conn, row, ctx.today)
        if nxt and nxt["status"] != "agendado" and nxt["refs"].get("from"):
            lo, hi = date.fromisoformat(nxt["refs"]["from"]), date.fromisoformat(nxt["refs"]["to"])
            window = {"from": lo.isoformat(), "to": hi.isoformat(), "title": nxt["title"]}
            start = max(ctx.today, lo)
    out = []
    limit = ctx.today + timedelta(days=cfg["booking"]["max_days"])
    d = start
    while d <= limit and len(out) < 10:
        times = scheduling.free_times(ctx.conn, svc, d, ctx.now, for_family=True)
        if times:
            out.append({"date": d.isoformat(), "weekday": care.WEEKDAYS[d.weekday()][:3], "day": d.day,
                        "month": d.month, "count": len(times),
                        "in_window": bool(window and window["from"] <= d.isoformat() <= window["to"])})
        d += timedelta(days=1)
    return {"days": out, "window": window}


@router.get("/children/{child_id}/slots")
def slots(child_id: int, service_id: int, date: str, ctx: Ctx = Depends(dep)):
    row = family_patient(ctx, child_id)
    svc = _service_for(ctx, row, service_id)
    try:
        day = datetime.fromisoformat(date).date()
    except ValueError as exc:
        raise HTTPException(400, "Data inválida.") from exc
    cov = plans.cover(ctx.conn, row["id"], svc, day)
    return {"times": scheduling.free_times(ctx.conn, svc, day, ctx.now, for_family=True), "cover": cov,
            "cancel_hours": catalog.config_of(svc)["cancel_hours"], "questions": catalog.config_of(svc)["questions"]}


class Book(BaseModel):
    service_id: int
    date: str
    time: str


@router.post("/children/{child_id}/appointments")
def book(child_id: int, body: Book, ctx: Ctx = Depends(dep)):
    row = family_patient(ctx, child_id)
    svc = _service_for(ctx, row, body.service_id)
    try:
        start = datetime.fromisoformat(f"{body.date}T{body.time}")
    except ValueError as exc:
        raise HTTPException(400, "Data ou horário inválido.") from exc
    with transaction(ctx.conn):
        aid = scheduling.book(ctx.conn, patient=row, service=svc, start=start, now=ctx.now, source="familia",
                              user_id=ctx.user["id"])
    return {"id": aid}


@router.get("/appointments")
def appointments(ctx: Ctx = Depends(dep)):
    family(ctx)
    kids = {k["id"]: k for k in _children(ctx)}
    if not kids:
        return {"upcoming": [], "past": []}
    marks = ", ".join("?" for _ in kids)
    rows = many(ctx.conn, f"SELECT * FROM appointments WHERE patient_id IN ({marks}) AND status != 'cancelado' ORDER BY start_at",
                tuple(kids))
    now = ctx.now.strftime("%Y-%m-%dT%H:%M")
    upcoming = [views.appointment_row(ctx.conn, r, ctx.now) for r in rows
                if r["start_at"] >= now[:10] and r["status"] in ("agendado", "confirmado", "chegou", "em_atendimento")]
    past = [views.appointment_row(ctx.conn, r, ctx.now) for r in reversed(rows) if r["status"] in ("atendido", "faltou")][:10]
    for a in upcoming:
        svc = one(ctx.conn, "SELECT * FROM services WHERE id = ?", (a["service_id"],))
        hours = catalog.config_of(svc)["cancel_hours"]
        a["can_cancel"] = (datetime.fromisoformat(a["start_at"]) - ctx.now) >= timedelta(hours=hours) or svc["kind"] == "sick_visit"
        a["cancel_hours"] = hours
    return {"upcoming": upcoming, "past": past}


@router.post("/appointments/{appt_id}/cancel")
def cancel(appt_id: int, ctx: Ctx = Depends(dep)):
    family(ctx)
    appt = one(ctx.conn, "SELECT * FROM appointments WHERE id = ?", (appt_id,))
    if not appt:
        raise HTTPException(404, "Consulta não encontrada.")
    family_patient(ctx, appt["patient_id"])
    svc = one(ctx.conn, "SELECT * FROM services WHERE id = ?", (appt["service_id"],))
    hours = catalog.config_of(svc)["cancel_hours"]
    if svc["kind"] != "sick_visit" and datetime.fromisoformat(appt["start_at"]) - ctx.now < timedelta(hours=hours):
        raise HTTPException(409, f"Faltam menos de {hours} h para a consulta. Para cancelar, fale com o consultório.")
    with transaction(ctx.conn):
        scheduling.transition(ctx.conn, appt, "cancelar", ctx.now)
    return {"ok": True}


# ---- arquivos -----------------------------------------------------------------------------------------------------

@router.get("/files")
def list_files(filter: str = "todos", ctx: Ctx = Depends(dep)):
    family(ctx)
    ids = sorted(ctx.family_ids)
    marks = ", ".join("?" for _ in ids)
    rows = many(ctx.conn, f"""SELECT f.*, p.name AS patient FROM files f LEFT JOIN patients p ON p.id = f.patient_id
                              WHERE f.family_id IN ({marks}) AND f.visibility IN ('family', 'admin')
                              ORDER BY f.created_at DESC""", tuple(ids))
    kinds = files.FILTERS.get(filter)
    out = []
    for r in rows:
        if kinds and r["kind"] not in kinds:
            continue
        out.append({"id": r["id"], "kind": r["kind"], "kind_label": files.KINDS.get(r["kind"], r["kind"]),
                    "title": r["title"], "note": r["note"], "patient": r["patient"], "patient_id": r["patient_id"],
                    "created_at": r["created_at"], "uploader_role": r["uploader_role"], "uploader_name": r["uploader_name"],
                    "needs_review": bool(r["needs_review"]), "reviewed_at": r["reviewed_at"],
                    "review_note": r["review_note"], "mime": r["mime"]})
    waiting = []
    for k in _children(ctx):
        for ci in many(ctx.conn, """SELECT * FROM care_items WHERE patient_id = ? AND kind = 'exame' AND status = 'pendente'
                                    AND visibility = 'family' AND file_id IS NULL ORDER BY created_at""", (k["id"],)):
            waiting.append({"care_item_id": ci["id"], "title": ci["title"], "detail": ci["detail"], "patient_id": k["id"],
                            "patient": k["name"], "created_at": ci["created_at"], "due_to": ci["due_to"]})
    return {"files": out, "waiting": waiting, "filters": {"todos": "Todos", "exames": "Exames",
                                                          "receitas": "Receitas e atestados", "notas": "Notas e recibos",
                                                          "fotos": "Fotos"}}


@router.post("/files")
async def upload(child_id: int = Form(...), kind: str = Form(...), title: str = Form(""), note: str = Form(""),
                 care_item_id: int | None = Form(None), upload: UploadFile = File(...), ctx: Ctx = Depends(dep)):
    row = family_patient(ctx, child_id)
    if kind not in ("exame", "foto", "video", "caderneta", "comprovante", "documento"):
        raise HTTPException(400, "Escolha o que você está mandando.")
    item = None
    if care_item_id:
        item = one(ctx.conn, "SELECT * FROM care_items WHERE id = ? AND patient_id = ?", (care_item_id, row["id"]))
        if not item:
            raise HTTPException(404, "Pedido não encontrado.")
    content = await upload.read()
    stored = files.store(ctx.settings.data_dir, ctx.practice_id, content, ctx.settings.max_upload_mb)
    with transaction(ctx.conn):
        fid = insert(ctx.conn, "files", {
            "family_id": row["family_id"], "patient_id": row["id"], "kind": kind,
            "title": title.strip() or (item["title"] if item else files.KINDS[kind]), "note": note.strip() or None,
            "original_name": upload.filename, **stored, "visibility": files.visibility_for(kind, "familia"),
            "uploaded_by": ctx.user["id"], "uploader_role": "familia",
            "uploader_name": f"{_guardian_name(ctx).split()[0]}, {ctx.guardians[0]['relation']}" if ctx.guardians else ctx.user["name"],
            "care_item_id": item["id"] if item else None, "needs_review": 1 if kind in files.REVIEW else 0,
            "created_at": now_iso()})
        if item:
            update(ctx.conn, "care_items", item["id"], {"file_id": fid})
    return {"id": fid}

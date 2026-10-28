"""A linha do cuidado: o que já foi feito e o que vem pela frente, para uma criança.

Tudo o que deve acontecer é um item do cuidado. Os itens dos protocolos (consultas da puericultura, vacinas e marcos)
são calculados pela idade e pelo que já está registrado; os da conduta (exame pedido, tarefa, orientação, retorno)
ficam gravados em `care_items`. Esta função junta os dois e é a única fonte do feito e do a fazer: a tela da família,
os lembretes, a busca ativa e os alertas do pediatra leem daqui.
"""

from __future__ import annotations

import json
import sqlite3
from collections import OrderedDict
from datetime import date, timedelta

from . import protocols
from .db import many

ACTIVE = ("agendado", "confirmado", "chegou", "em_atendimento")
WELL_KINDS = ("well_child", "newborn")


def _d(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _fmt(d: date) -> str:
    return d.strftime("%d/%m")


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " e " + parts[-1]


def age_text(birth: date, on: date) -> str:
    """"4 meses e 12 dias", "3 anos e 2 meses", "15 dias"."""
    days = (on - birth).days
    if days < 0:
        return "ainda não nasceu"
    if days < 31:
        return "1 dia" if days == 1 else f"{days} dias"
    months = (on.year - birth.year) * 12 + on.month - birth.month - (1 if on.day < birth.day else 0)
    if months < 24:
        anchor_month = birth.month + months
        anchor = date(birth.year + (anchor_month - 1) // 12, (anchor_month - 1) % 12 + 1, 1)
        try:
            anchor = anchor.replace(day=birth.day)
        except ValueError:
            anchor = anchor.replace(day=28)
        rest = (on - anchor).days
        base = "1 mês" if months == 1 else f"{months} meses"
        return base if rest <= 0 else f"{base} e {rest} dia{'s' if rest > 1 else ''}"
    years, months = divmod(months, 12)
    base = "1 ano" if years == 1 else f"{years} anos"
    return base if not months else f"{base} e {months} {'mês' if months == 1 else 'meses'}"


def age_short(birth: date, on: date) -> str:
    """"4 meses", "3 anos", "15 dias": o que cabe numa lista."""
    days = (on - birth).days
    if days < 31:
        return "1 dia" if days == 1 else f"{max(days, 0)} dias"
    months = (on.year - birth.year) * 12 + on.month - birth.month - (1 if on.day < birth.day else 0)
    if months < 24:
        return "1 mês" if months == 1 else f"{months} meses"
    years = months // 12
    return "1 ano" if years == 1 else f"{years} anos"


def _item(**kw) -> dict:
    base = {"type": None, "title": "", "detail": "", "date": None, "status": "pendente", "owner": "familia",
            "action": None, "refs": {}}
    base.update(kw)
    if isinstance(base["date"], date):
        base["date"] = base["date"].isoformat()
    return base


def _visits(birth: date, appts: list[dict], today: date):
    """Casa cada consulta do protocolo com o agendamento que a cumpre."""
    used: set[int] = set()
    rows = []
    for v in protocols.WELL_CHILD:
        target = birth + timedelta(days=v.day)
        lo, hi = target - timedelta(days=v.before), target + timedelta(days=v.after)
        match = None
        for a in appts:
            if a["id"] in used or a["kind"] not in WELL_KINDS or a["status"] in ("faltou", "cancelado"):
                continue
            if lo - timedelta(days=21) <= _d(a["start_at"]) <= hi + timedelta(days=45):
                match = a
                break
        if match:
            used.add(match["id"])
        if match and match["status"] == "atendido":
            state = "feito"
        elif match:
            state = "agendado"
        elif today > hi:
            state = "perdida"
        elif today >= lo - timedelta(days=21):
            state = "aberta"
        else:
            state = "futura"
        rows.append({"visit": v, "lo": lo, "hi": hi, "match": match, "state": state})
    return rows, used


def _next_visit(rows: list[dict], today: date) -> dict | None:
    scheduled = [r for r in rows if r["state"] == "agendado"]
    if scheduled:
        r = scheduled[0]
        when = r["match"]["start_at"]
        return _item(type="consulta", title=r["visit"].title, date=_d(when), status="agendado",
                     detail=f"{_weekday(_d(when))}, {_fmt(_d(when))}, às {when[11:16]}",
                     refs={"appointment_id": r["match"]["id"], "visit": r["visit"].code})
    last = max((i for i, r in enumerate(rows) if r["state"] == "feito"), default=-1)
    after = rows[last + 1:]
    opened = [r for r in after if r["state"] in ("aberta", "futura")]
    missed = [r for r in after if r["state"] == "perdida" and r["hi"] >= today - timedelta(days=60)]
    pick, status = None, "pendente"
    if opened and opened[0]["state"] == "aberta":
        pick = opened[0]
    elif missed:
        pick, status = missed[-1], "atrasado"
    elif opened:
        pick = opened[0]
    if not pick:
        return None
    lo, hi = pick["lo"], pick["hi"]
    detail = f"agende entre {_fmt(lo)} e {_fmt(hi)}" if status != "atrasado" else f"era entre {_fmt(lo)} e {_fmt(hi)}"
    return _item(type="consulta", title=pick["visit"].title, date=lo, status=status, detail=detail, action="agendar",
                 refs={"visit": pick["visit"].code, "from": lo.isoformat(), "to": hi.isoformat()})


WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _weekday(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def _dose_names(doses: list[protocols.Dose]) -> str:
    parts = []
    for d in doses:
        label = d.vaccine if d.dose in ("dose única", "ao nascer") else f"{d.vaccine} ({d.dose})"
        parts.append(label)
    return _join(parts)


def timeline(conn: sqlite3.Connection, patient: dict, today: date, audience: str = "family") -> dict:
    """O feito e o a fazer. `audience`: 'clinician' (tudo), 'family' (o que é dela) ou 'reception' (só agenda)."""
    pid = patient["id"]
    birth = _d(patient["birth_date"])
    age = (today - birth).days
    appts = many(conn, """
        SELECT a.id, a.start_at, a.status, a.kind AS akind, s.kind, s.name AS service
        FROM appointments a JOIN services s ON s.id = a.service_id
        WHERE a.patient_id = ? AND a.status != 'cancelado' ORDER BY a.start_at""", (pid,))
    encounters = {e["appointment_id"]: e for e in many(conn, """
        SELECT id, appointment_id, family_summary, summary_released, finished_at FROM encounters
        WHERE patient_id = ? AND status = 'finalizada'""", (pid,))}
    todo: list[dict] = []
    done: list[dict] = []

    # as consultas: as do protocolo pelo nome da idade, as outras pelo nome do serviço
    rows, _ = _visits(birth, appts, today)
    visit_by_appt = {r["match"]["id"]: r["visit"] for r in rows if r["match"]}
    for a in appts:
        if a["status"] != "atendido":
            continue
        enc = encounters.get(a["id"])
        summary = ""
        if enc and enc["family_summary"] and (enc["summary_released"] or audience == "clinician"):
            summary = enc["family_summary"]
        visit = visit_by_appt.get(a["id"])
        done.append(_item(type="consulta", title=visit.title if visit else a["service"], date=_d(a["start_at"]),
                          status="feito", detail=summary, action="resumo" if summary else None,
                          refs={"appointment_id": a["id"], "encounter_id": enc["id"] if enc else None}))
    nxt = _next_visit(rows, today)
    if nxt:
        todo.append(nxt)
    if audience == "reception":
        for a in appts:
            if a["status"] in ACTIVE and _d(a["start_at"]) >= today and not (nxt and nxt["refs"].get("appointment_id") == a["id"]):
                todo.append(_item(type="consulta", title=a["service"], date=_d(a["start_at"]), status="agendado",
                                  detail=f"{_fmt(_d(a['start_at']))} às {a['start_at'][11:16]}",
                                  refs={"appointment_id": a["id"]}))
        return _finish(todo, done, nxt)

    # outras consultas já marcadas (por doença, retorno…)
    for a in appts:
        if a["status"] in ACTIVE and a["kind"] not in WELL_KINDS and _d(a["start_at"]) >= today:
            todo.append(_item(type="consulta", title=a["service"], date=_d(a["start_at"]), status="agendado",
                              detail=f"{_weekday(_d(a['start_at']))}, {_fmt(_d(a['start_at']))}, às {a['start_at'][11:16]}",
                              refs={"appointment_id": a["id"]}))

    # vacinas: as feitas agrupadas pelo dia; as que faltam agrupadas pela idade
    applied = {r["code"]: r for r in many(conn, "SELECT code, applied_on FROM immunizations WHERE patient_id = ?", (pid,))}
    by_day: OrderedDict[str, list] = OrderedDict()
    pending: OrderedDict[tuple, list] = OrderedDict()
    old_missing = 0
    for dose in protocols.VACCINES:
        due = birth + timedelta(days=dose.day)
        if dose.code in applied:
            by_day.setdefault(applied[dose.code]["applied_on"], []).append(dose)
            continue
        if today > due + timedelta(days=30):
            if due >= today - timedelta(days=180):
                pending.setdefault((dose.group, "atrasado", due), []).append(dose)
            else:
                old_missing += 1
        elif (due - today).days <= 45:
            pending.setdefault((dose.group, "pendente", due), []).append(dose)
    for day, doses in sorted(by_day.items(), reverse=True):
        groups = {d.group for d in doses}
        if len(doses) == 1:
            title = f"Vacina · {doses[0].vaccine}"
        elif len(groups) == 1:
            title = f"Vacinas {doses[0].group}"
        else:
            title = f"Vacinas de {_fmt(_d(day))}"
        detail = doses[0].dose if len(doses) == 1 else _dose_names(doses)
        done.append(_item(type="vacina", title=title, date=_d(day), status="feito", detail=detail,
                          refs={"codes": [d.code for d in doses]}))
    for (group, status, due), doses in pending.items():
        title = f"{doses[0].vaccine} · {doses[0].dose}" if len(doses) == 1 else f"Vacinas {group}"
        when = f"a partir de {_fmt(due)}" if due > today else (f"desde {_fmt(due)}" if status == "pendente" else f"era em {_fmt(due)}")
        detail = when if len(doses) == 1 else f"{_dose_names(doses)} · {when}"
        todo.append(_item(type="vacina", title=title, date=due, status=status, detail=detail,
                          refs={"codes": [d.code for d in doses]}))
    if old_missing:
        todo.append(_item(type="vacina", title="Vacinas antigas sem registro", status="pendente", action="enviar",
                          detail=f"{old_missing} dose{'s' if old_missing > 1 else ''} · mande a foto da caderneta",
                          date=today, refs={"caderneta": True}))

    # marcos: os marcados vão para o feito; os da faixa atual ficam para marcar, sem nunca virar "atrasado"
    checks = {r["code"]: r for r in many(conn, "SELECT code, achieved_on, marked_by, marker_name FROM milestone_checks WHERE patient_id = ?", (pid,))}
    for code, row in checks.items():
        m = protocols.MILESTONE_BY_CODE.get(code)
        if m:
            if row["marker_name"]:
                detail = f"marcado por {row['marker_name']}"
            else:
                detail = "conferido na consulta" if row["marked_by"] == "pediatra" else "marcado pela família"
            done.append(_item(type="marco", title=m.label, date=_d(row["achieved_on"]), status="feito",
                              detail=detail, refs={"milestone": code}))
    band = protocols.milestone_band(age)
    if band:
        for m in band.items:
            if m.code not in checks:
                todo.append(_item(type="marco", title=m.label, status="pendente", action="marcar", date=None,
                                  detail=f"costuma vir entre {round(m.day_from / 30.44)} e {round(m.day_to / 30.44)} meses",
                                  refs={"milestone": m.code}))

    # o que o pediatra pediu: exames, tarefas, orientações, retornos
    vis = "" if audience == "clinician" else " AND visibility = 'family'"
    for ci in many(conn, f"SELECT * FROM care_items WHERE patient_id = ?{vis} ORDER BY id", (pid,)):
        if ci["status"] == "dispensado":
            continue
        due = _d(ci["due_to"]) if ci["due_to"] else None
        if ci["status"] == "feito":
            done.append(_item(type=ci["kind"], title=ci["title"], date=_d(ci["done_at"] or ci["created_at"]),
                              status="feito", detail=ci["detail"] or "", owner=ci["owner"],
                              refs={"care_item_id": ci["id"], "file_id": ci["file_id"]}))
            continue
        status = "atrasado" if due and due < today else "pendente"
        action = "enviar" if ci["kind"] in ("exame",) or (ci["kind"] == "tarefa" and "foto" in ci["title"].lower()) else None
        if ci["kind"] == "retorno":
            action = "agendar"
        detail = ci["detail"] or ""
        if due:
            detail = (detail + " · " if detail else "") + f"até {_fmt(due)}"
        if ci["file_id"]:
            # a família já mandou: espera a revisão do pediatra, sem cobrar de novo
            status, action, detail = "pendente", None, "enviado · esperando a revisão"
        todo.append(_item(type=ci["kind"], title=ci["title"], date=due or _d(ci["created_at"]), status=status,
                          detail=detail, owner=ci["owner"], action=action,
                          refs={"care_item_id": ci["id"], "visibility": ci["visibility"]}))
    return _finish(todo, done, nxt)


def _finish(todo: list[dict], done: list[dict], nxt: dict | None) -> dict:
    rank = {"atrasado": 0, "agendado": 1, "pendente": 2}
    todo.sort(key=lambda i: (rank.get(i["status"], 3), i["type"] == "marco", i["date"] or "9999"))
    done.sort(key=lambda i: i["date"] or "", reverse=True)
    return {"todo": todo, "done": done, "next": nxt or (todo[0] if todo else None)}


def next_visit_state(conn: sqlite3.Connection, patient: dict, today: date) -> dict | None:
    """Só a próxima consulta do protocolo (para a busca ativa e os painéis)."""
    birth = _d(patient["birth_date"])
    appts = many(conn, """
        SELECT a.id, a.start_at, a.status, s.kind FROM appointments a JOIN services s ON s.id = a.service_id
        WHERE a.patient_id = ? AND a.status != 'cancelado' ORDER BY a.start_at""", (patient["id"],))
    rows, _ = _visits(birth, appts, today)
    return _next_visit(rows, today)


def overdue_vaccines(conn: sqlite3.Connection, patient: dict, today: date) -> int:
    birth = _d(patient["birth_date"])
    applied = {r["code"] for r in many(conn, "SELECT code FROM immunizations WHERE patient_id = ?", (patient["id"],))}
    n = 0
    for dose in protocols.VACCINES:
        due = birth + timedelta(days=dose.day)
        if dose.code not in applied and today > due + timedelta(days=30) and due >= today - timedelta(days=180):
            n += 1
    return n


def vaccine_card(conn: sqlite3.Connection, patient: dict, today: date) -> list[dict]:
    """A caderneta inteira, dose a dose (para o pediatra e para a família)."""
    birth = _d(patient["birth_date"])
    applied = {r["code"]: r for r in many(conn, "SELECT * FROM immunizations WHERE patient_id = ?", (patient["id"],))}
    out = []
    for dose in protocols.VACCINES:
        due = birth + timedelta(days=dose.day)
        row = applied.get(dose.code)
        if row:
            status = "feito"
        elif today > due + timedelta(days=30):
            status = "atrasado"
        elif (due - today).days <= 45:
            status = "pendente"
        else:
            status = "futura"
        out.append({"code": dose.code, "vaccine": dose.vaccine, "dose": dose.dose, "group": dose.group,
                    "due": due.isoformat(), "status": status, "applied_on": row["applied_on"] if row else None,
                    "lot": row["lot"] if row else None, "place": row["place"] if row else None})
    return out


def milestones_view(conn: sqlite3.Connection, patient: dict, today: date) -> dict:
    birth = _d(patient["birth_date"])
    age = (today - birth).days
    checks = {r["code"]: r for r in many(conn, "SELECT * FROM milestone_checks WHERE patient_id = ?", (patient["id"],))}
    band = protocols.milestone_band(age)
    bands = []
    for b in protocols.MILESTONES:
        if b.day_from > age + 31:
            break
        bands.append({"title": b.title, "current": b is band, "items": [
            {"code": m.code, "label": m.label, "checked": m.code in checks,
             "achieved_on": checks[m.code]["achieved_on"] if m.code in checks else None,
             "marked_by": checks[m.code]["marker_name"] if m.code in checks else None} for m in b.items]})
    return {"bands": bands, "current": band.title if band else None}


def load_json(text: str | None, default):
    try:
        return json.loads(text) if text else default
    except ValueError:
        return default

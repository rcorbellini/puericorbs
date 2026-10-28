"""A agenda: os horários livres de um serviço num dia, marcar e as mudanças de estado de um agendamento.

A grade (`availability`) diz os turnos de cada dia da semana. As vagas protegidas (`reserved_slots`) ficam fechadas
para tudo, menos para a consulta por doença no próprio dia: é a vaga da criança que adoeceu hoje. O encaixe (só da
recepção e do pediatra) passa por cima da grade e de quem já está marcado.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from fastapi import HTTPException

from . import catalog, plans
from .db import insert, many, now_iso, one

STEP = 10
NOON = 12 * 60
OPEN = ("agendado", "confirmado", "chegou", "em_atendimento", "atendido")

# a ação, de onde ela pode partir e para onde vai
TRANSITIONS = {
    "confirmar": (("agendado",), "confirmado"),
    "chegou": (("agendado", "confirmado"), "chegou"),
    "iniciar": (("agendado", "confirmado", "chegou"), "em_atendimento"),
    "finalizar": (("agendado", "confirmado", "chegou", "em_atendimento"), "atendido"),
    "faltou": (("agendado", "confirmado"), "faltou"),
    "cancelar": (("agendado", "confirmado", "chegou"), "cancelado"),
    "reabrir": (("faltou", "cancelado"), "agendado"),
}
STATUS_LABEL = {
    "agendado": "Agendada", "confirmado": "Confirmada", "chegou": "Na espera", "em_atendimento": "Em atendimento",
    "atendido": "Atendido", "faltou": "Faltou", "cancelado": "Cancelada",
}


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def minutes(text: str) -> int:
    """"2026-10-28T10:40" ou "10:40" viram 640."""
    clock = text.split("T")[1][:5] if "T" in text else text[:5]
    h, m = clock.split(":")
    return int(h) * 60 + int(m)


def windows(conn: sqlite3.Connection, day: date) -> list[tuple[int, int]]:
    if one(conn, "SELECT id FROM schedule_exceptions WHERE day = ?", (day.isoformat(),)):
        return []
    return [(r["start_min"], r["end_min"]) for r in many(
        conn, "SELECT start_min, end_min FROM availability WHERE weekday = ? ORDER BY start_min", (day.weekday(),))]


def reserved(conn: sqlite3.Connection, day: date) -> list[tuple[int, int]]:
    return [(r["start_min"], r["start_min"] + r["duration_min"]) for r in many(
        conn, "SELECT start_min, duration_min FROM reserved_slots WHERE weekday = ? ORDER BY start_min",
        (day.weekday(),))]


def busy(conn: sqlite3.Connection, day: date, ignore_id: int | None = None) -> list[tuple[int, int]]:
    rows = many(conn, f"""SELECT id, start_at, end_at FROM appointments
                          WHERE substr(start_at, 1, 10) = ? AND status IN ({', '.join('?' for _ in OPEN)})""",
                (day.isoformat(), *OPEN))
    return [(minutes(r["start_at"]), minutes(r["end_at"])) for r in rows if r["id"] != ignore_id]


def _overlaps(a: int, b: int, spans: list[tuple[int, int]]) -> bool:
    return any(a < e and s < b for s, e in spans)


def _shift_windows(wins: list[tuple[int, int]], shifts: list[str]) -> list[tuple[int, int]]:
    out = []
    for s, e in wins:
        if "manha" in shifts and s < NOON:
            out.append((s, min(e, NOON)))
        if "tarde" in shifts and e > NOON:
            out.append((max(s, NOON), e))
    return out


def free_times(conn: sqlite3.Connection, service: dict, day: date, now: datetime, *, for_family: bool) -> list[dict]:
    """Os horários em que o serviço cabe no dia, já arrumados para mostrar (sem um a cada 10 minutos)."""
    cfg = catalog.config_of(service)
    today = now.date()
    if day < today:
        return []
    if for_family and (day - today).days > cfg["booking"]["max_days"]:
        return []
    dur = service["duration_min"]
    acute = service["kind"] == "sick_visit"
    wins = _shift_windows(windows(conn, day), cfg["shifts"])
    res = reserved(conn, day)
    taken = busy(conn, day)
    earliest = -1
    if day == today:
        earliest = now.hour * 60 + now.minute + int(cfg["booking"]["min_notice_h"] * 60 if for_family else 0)
    ends = {e for _, e in taken}
    starts_res = {s for s, _ in res}
    out = []
    for ws, we in wins:
        t = ws
        while t + dur <= we:
            ok = t >= earliest and not _overlaps(t, t + dur, taken)
            in_res = _overlaps(t, t + dur, res)
            if in_res and not (acute and day == today):
                ok = False
            tidy = (t - ws) % dur == 0 or t in ends or t in starts_res
            if ok and tidy:
                out.append({"time": hhmm(t), "reserved": in_res})
            t += STEP
    return out


def book(conn: sqlite3.Connection, *, patient: dict, service: dict, start: datetime, now: datetime, source: str,
         kind: str = "normal", user_id: int | None = None, notes: str | None = None) -> int:
    """Marca. A família só no que o serviço deixa; o encaixe (equipe) ignora a grade e quem já está marcado."""
    cfg = catalog.config_of(service)
    day = start.date()
    if not service["active"]:
        raise HTTPException(409, "Este serviço está desligado. Ligue-o em Serviços antes de marcar.")
    if start < now - timedelta(minutes=5) and source == "familia":
        raise HTTPException(409, "Esse horário já passou. Escolha outro.")
    if source == "familia":
        if not cfg["booking"]["family"]:
            raise HTTPException(403, "Este serviço é marcado pela recepção. Fale com o consultório.")
        age = (day - date.fromisoformat(patient["birth_date"])).days
        if not catalog.fits_age(service, age):
            raise HTTPException(409, "Este serviço não é para a idade da criança.")
    dur = service["duration_min"]
    s = start.hour * 60 + start.minute
    if kind != "encaixe":
        free = {f["time"] for f in free_times(conn, service, day, now, for_family=source == "familia")}
        if hhmm(s) not in free:
            # a equipe pode marcar qualquer horário livre da grade, mesmo fora da lista arrumada
            fits = any(ws <= s and s + dur <= we for ws, we in _shift_windows(windows(conn, day), ["manha", "tarde"]))
            clash = _overlaps(s, s + dur, busy(conn, day))
            if source == "familia" or not fits or clash:
                raise HTTPException(409, "Esse horário não está mais livre. Escolha outro.")
        if _overlaps(s, s + dur, reserved(conn, day)) and service["kind"] == "sick_visit":
            kind = "agudo"
    cov = plans.cover(conn, patient["id"], service, day)
    end = start + timedelta(minutes=dur)
    return insert(conn, "appointments", {
        "patient_id": patient["id"], "service_id": service["id"], "service_version": service["version"],
        "start_at": start.strftime("%Y-%m-%dT%H:%M"), "end_at": end.strftime("%Y-%m-%dT%H:%M"),
        "status": "confirmado" if source == "familia" else "agendado", "kind": kind, "source": source,
        "price_cents": cov["price_cents"], "membership_id": cov["membership_id"], "notes": notes,
        "created_at": now_iso(), "created_by": user_id,
    })


def transition(conn: sqlite3.Connection, appt: dict, action: str, now: datetime) -> str:
    if action not in TRANSITIONS:
        raise HTTPException(400, "Ação desconhecida.")
    allowed, target = TRANSITIONS[action]
    if appt["status"] not in allowed:
        verb = {"chegou": "marcar a chegada de", "iniciar": "começar", "faltou": "marcar falta em"}.get(action, action)
        raise HTTPException(409, f"Não dá para {verb} uma consulta que está como “{STATUS_LABEL[appt['status']].lower()}”.")
    values: dict = {"status": target}
    if target == "chegou":
        values["arrived_at"] = now.strftime("%Y-%m-%dT%H:%M:%S")
    sets = ", ".join(f"{k} = ?" for k in values)
    conn.execute(f"UPDATE appointments SET {sets} WHERE id = ?", (*values.values(), appt["id"]))
    return target

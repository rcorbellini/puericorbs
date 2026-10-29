"""A agenda: os horários livres de um serviço num dia, marcar e as mudanças de estado de um agendamento.

A grade (`availability`) diz os períodos de cada dia da semana, e a pediatra a muda em Horários (`set_hours`). A agenda
fechada (`schedule_exceptions`: férias, congresso, folga) tira dias inteiros da grade; o que já estava marcado neles
continua marcado, para a recepção avisar a família. As vagas protegidas (`reserved_slots`) ficam fechadas para tudo,
menos para a consulta por doença no próprio dia: é a vaga da criança que adoeceu hoje. Elas nascem da grade, uma no fim
de cada período. O encaixe (só da recepção e do pediatra) passa por cima da grade e de quem já está marcado.
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


def closure(conn: sqlite3.Connection, day: date) -> dict | None:
    """O fechamento que cobre o dia, se houver (o que começou primeiro)."""
    iso = day.isoformat()
    return one(conn, """SELECT * FROM schedule_exceptions WHERE day <= ? AND COALESCE(end_day, day) >= ?
                        ORDER BY day, id LIMIT 1""", (iso, iso))


def hours(conn: sqlite3.Connection, day: date) -> list[tuple[int, int]]:
    """Os períodos da grade no dia da semana, sem olhar se a agenda está fechada."""
    return [(r["start_min"], r["end_min"]) for r in many(
        conn, "SELECT start_min, end_min FROM availability WHERE weekday = ? ORDER BY start_min", (day.weekday(),))]


def windows(conn: sqlite3.Connection, day: date) -> list[tuple[int, int]]:
    """Os períodos em que se marca no dia: a grade, a não ser que a agenda esteja fechada."""
    return [] if closure(conn, day) else hours(conn, day)


def reserved(conn: sqlite3.Connection, day: date) -> list[tuple[int, int]]:
    """As vagas protegidas do dia que caem dentro da grade (num dia fechado, nenhuma)."""
    wins = windows(conn, day)
    return [(s, e) for s, e in ((r["start_min"], r["start_min"] + r["duration_min"]) for r in many(
        conn, "SELECT start_min, duration_min FROM reserved_slots WHERE weekday = ? ORDER BY start_min",
        (day.weekday(),))) if any(ws <= s and e <= we for ws, we in wins)]


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
    closed = closure(conn, day)
    if closed and kind != "encaixe":
        if source == "familia":
            raise HTTPException(409, "Este dia não tem horário. Escolha outro.")
        why = f" ({closed['reason']})" if closed["reason"] else ""
        raise HTTPException(409, f"A agenda está fechada neste dia{why}. Para marcar mesmo assim, use o encaixe.")
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


# ---- os horários da pediatra --------------------------------------------------------------------------------------------

WEEKDAYS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
MAX_PERIODS = 6


def parse_periods(items: list[dict]) -> list[tuple[int, int, int]]:
    """[{weekday, start: "08:00", end: "12:00"}] → [(dia, começo, fim)], conferidos: o fim depois do começo, de 5 em 5
    minutos e sem dois períodos do mesmo dia se cruzando."""
    out: list[tuple[int, int, int]] = []
    for it in items:
        wd = it.get("weekday")
        if not isinstance(wd, int) or not 0 <= wd <= 6:
            raise HTTPException(400, "Dia da semana inválido.")
        name = WEEKDAYS[wd].capitalize()
        try:
            s, e = minutes(str(it.get("start", ""))), minutes(str(it.get("end", "")))
        except (ValueError, IndexError) as exc:
            raise HTTPException(400, f"{name}: escreva o horário como 08:00.") from exc
        if not (0 <= s < 24 * 60 and 0 < e <= 24 * 60):
            raise HTTPException(400, f"{name}: o horário vai de 00:00 a 23:59.")
        if s % 5 or e % 5:
            raise HTTPException(400, f"{name}: use horários de 5 em 5 minutos (08:00, 08:05…).")
        if e - s < 15:
            raise HTTPException(400, f"{name}: o fim ({hhmm(e)}) precisa vir pelo menos 15 minutos depois do começo ({hhmm(s)}).")
        out.append((wd, s, e))
    out.sort()
    for (wa, sa, ea), (wb, sb, eb) in zip(out, out[1:]):
        if wa == wb and sb < ea:
            raise HTTPException(400, f"{WEEKDAYS[wa].capitalize()}: os períodos {hhmm(sa)}–{hhmm(ea)} e {hhmm(sb)}–{hhmm(eb)} se cruzam.")
    for wd in range(7):
        if sum(1 for w, _, _ in out if w == wd) > MAX_PERIODS:
            raise HTTPException(400, f"{WEEKDAYS[wd].capitalize()}: são no máximo {MAX_PERIODS} períodos por dia.")
    return out


def sick_duration(conn: sqlite3.Connection) -> int:
    row = one(conn, "SELECT duration_min FROM services WHERE kind = 'sick_visit' AND active = 1 ORDER BY position, id LIMIT 1")
    return row["duration_min"] if row else 30


def set_hours(conn: sqlite3.Connection, periods: list[tuple[int, int, int]], sick_slots: bool) -> None:
    """Troca a grade inteira. Com `sick_slots`, o fim de cada período (do tamanho da consulta por doença) vira a vaga
    protegida da criança que adoece no dia; período curto demais para ela fica sem."""
    dur = sick_duration(conn)
    conn.execute("DELETE FROM availability")
    conn.execute("DELETE FROM reserved_slots")
    for wd, s, e in periods:
        insert(conn, "availability", {"weekday": wd, "start_min": s, "end_min": e})
        if sick_slots and e - s > dur:
            insert(conn, "reserved_slots", {"weekday": wd, "start_min": e - dur, "duration_min": dur})


def outside_hours(conn: sqlite3.Connection, today: date) -> list[dict]:
    """As consultas marcadas daqui para a frente que ficaram fora da grade (o encaixe já nasce fora dela)."""
    rows = many(conn, """SELECT * FROM appointments WHERE substr(start_at, 1, 10) >= ? AND status IN ('agendado', 'confirmado')
                         AND kind != 'encaixe' ORDER BY start_at""", (today.isoformat(),))
    out = []
    for r in rows:
        s, e = minutes(r["start_at"]), minutes(r["end_at"])
        if not any(ws <= s and e <= we for ws, we in hours(conn, date.fromisoformat(r["start_at"][:10]))):
            out.append(r)
    return out


def in_days(conn: sqlite3.Connection, first: date, last: date) -> list[dict]:
    """As consultas marcadas entre dois dias (os dois inclusive): as que um fechamento deixa para remarcar."""
    return many(conn, """SELECT * FROM appointments WHERE substr(start_at, 1, 10) BETWEEN ? AND ?
                         AND status IN ('agendado', 'confirmado') ORDER BY start_at""", (first.isoformat(), last.isoformat()))

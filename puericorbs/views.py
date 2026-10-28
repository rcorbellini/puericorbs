"""O formato do que a API devolve: a criança, o agendamento, o gráfico. Um lugar só, para a recepção nunca receber
um campo clínico por descuido (`patient_brief(..., clinical=False)`)."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from . import care, catalog, growth, plans
from .db import many, one
from .scheduling import STATUS_LABEL, minutes


def guardians_of(conn: sqlite3.Connection, family_id: int) -> list[dict]:
    return many(conn, "SELECT id, name, relation, phone, email, is_legal, is_financial, user_id FROM guardians "
                      "WHERE family_id = ? ORDER BY id", (family_id,))


def patient_brief(conn: sqlite3.Connection, row: dict, today: date, *, clinical: bool) -> dict:
    birth = date.fromisoformat(row["birth_date"])
    fam = one(conn, "SELECT name FROM families WHERE id = ?", (row["family_id"],))
    out = {
        "id": row["id"], "name": row["name"], "first_name": row["name"].split()[0], "sex": row["sex"],
        "birth_date": row["birth_date"], "age": care.age_text(birth, today), "age_short": care.age_short(birth, today),
        "family_id": row["family_id"], "family": fam["name"] if fam else "",
        "guardians": [{"name": g["name"], "relation": g["relation"], "phone": g["phone"], "email": g["email"]}
                      for g in guardians_of(conn, row["family_id"])],
    }
    m = plans.active_membership(conn, row["id"], today)
    out["plan"] = plans.membership_view(conn, m) if m else None
    if clinical:
        out.update({
            "allergies": row["allergies"], "conditions": row["conditions"],
            "gestational_weeks": row["gestational_weeks"], "birth_weight_g": row["birth_weight_g"],
            "birth_length_cm": row["birth_length_cm"], "birth_head_cm": row["birth_head_cm"],
            "birth_type": row["birth_type"],
        })
    return out


def appointment_row(conn: sqlite3.Connection, row: dict, now: datetime, *, practice: dict | None = None) -> dict:
    svc = one(conn, "SELECT name, kind FROM services WHERE id = ?", (row["service_id"],))
    pt = one(conn, "SELECT id, name, birth_date, family_id FROM patients WHERE id = ?", (row["patient_id"],))
    birth = date.fromisoformat(pt["birth_date"])
    wait = None
    if row["status"] == "chegou" and row["arrived_at"]:
        wait = max(0, int((now - datetime.fromisoformat(row["arrived_at"])).total_seconds() // 60))
    out = {
        "id": row["id"], "start_at": row["start_at"], "end_at": row["end_at"], "time": row["start_at"][11:16],
        "date": row["start_at"][:10], "status": row["status"], "status_label": STATUS_LABEL[row["status"]],
        "kind": row["kind"], "source": row["source"], "service": svc["name"], "service_kind": svc["kind"],
        "service_id": row["service_id"], "covered": bool(row["membership_id"]), "price_cents": row["price_cents"],
        "wait_min": wait, "arrived_at": row["arrived_at"],
        "patient": {"id": pt["id"], "name": pt["name"], "first_name": pt["name"].split()[0],
                    "age_short": care.age_short(birth, now.date()), "family_id": pt["family_id"]},
        "duration_min": minutes(row["end_at"]) - minutes(row["start_at"]),
    }
    paid = one(conn, "SELECT id, method, invoice FROM charges WHERE appointment_id = ? AND status = 'paga'", (row["id"],))
    out["paid"] = bool(paid)
    if practice:
        out["practice"] = {"id": practice["id"], "name": practice["name"], "slug": practice["slug"]}
    return out


def day_appointments(conn: sqlite3.Connection, day: date, now: datetime, *, practice: dict | None = None,
                     include_cancelled: bool = False) -> list[dict]:
    rows = many(conn, "SELECT * FROM appointments WHERE substr(start_at, 1, 10) = ? ORDER BY start_at, id",
                (day.isoformat(),))
    if not include_cancelled:
        rows = [r for r in rows if r["status"] != "cancelado"]
    return [appointment_row(conn, r, now, practice=practice) for r in rows]


def free_reserved(conn: sqlite3.Connection, day: date) -> list[dict]:
    """As vagas protegidas do dia que ninguém ocupou."""
    from .scheduling import busy, hhmm, reserved
    taken = busy(conn, day)
    out = []
    for s, e in reserved(conn, day):
        if not any(s < b and a < e for a, b in taken):
            out.append({"time": hhmm(s), "end": hhmm(e), "duration_min": e - s})
    return out


def growth_chart(conn: sqlite3.Connection, patient: dict, indicator: str, today: date) -> dict:
    birth = date.fromisoformat(patient["birth_date"])
    ga = patient.get("gestational_weeks")
    age_now, corrected = growth.corrected_days(birth, today, ga)
    field = growth.INDICATORS[indicator]["field"]
    points = []
    birth_value = {"wfa": (patient.get("birth_weight_g") or 0) / 1000 or None, "lhfa": patient.get("birth_length_cm"),
                   "hcfa": patient.get("birth_head_cm")}.get(indicator)
    if birth_value:
        points.append({"date": patient["birth_date"], "value": birth_value, "label": "Nascimento"})
    for m in many(conn, "SELECT * FROM measurements WHERE patient_id = ? ORDER BY taken_on", (patient["id"],)):
        value = m[field] if field else None
        if value:
            points.append({"date": m["taken_on"], "value": value, "label": care.age_text(birth, date.fromisoformat(m["taken_on"]))})
    for p in points:
        d = date.fromisoformat(p["date"])
        day, _ = growth.corrected_days(birth, d, ga)
        p["day"] = day
        if day <= growth.MAX_DAY:
            z = growth.z_score(indicator, patient["sex"], day, p["value"])
            p["z"] = round(z, 2)
            p["pct"] = growth.pct_label(z)
            p["reading"] = growth.reading(z)
    span = max(age_now + 45, 183) if age_now < 365 else (max(age_now + 120, 730) if age_now < 730 else age_now + 365)
    span = min(growth.MAX_DAY, span)
    return {
        "indicator": indicator, "label": growth.INDICATORS[indicator]["label"], "unit": growth.INDICATORS[indicator]["unit"],
        "sex": patient["sex"], "corrected": corrected, "span_days": span,
        "curves": growth.curves(indicator, patient["sex"], span, points=48),
        "points": [p for p in points if p["day"] <= span],
        "latest": points[-1] if points else None,
    }


def service_public(conn: sqlite3.Connection, row: dict, patient: dict | None, today: date) -> dict:
    out = catalog.as_dict(row)
    cfg = out["config"]
    out = {"id": out["id"], "name": out["name"], "kind": out["kind"], "kind_label": out["kind_label"],
           "duration_min": out["duration_min"], "price_cents": out["price_cents"], "text": cfg["family_text"],
           "category": out["category"]}
    if patient:
        cov = plans.cover(conn, patient["id"], row, today)
        out["covered"] = cov["covered"]
        out["final_cents"] = cov["price_cents"]
        out["cover_label"] = cov["label"]
    return out


def week_dates(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]

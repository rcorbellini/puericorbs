"""Os planos de acompanhamento: o que cada plano dá, quanto já foi usado e se um agendamento entra na cota.

O plano é um pacote dos serviços do próprio pediatra (nunca plano de saúde): `benefits` lista os serviços com cota na
vigência, `discount_pct` é o desconto nos serviços fora da cota e `perks` são os textos do que mais vem junto
(mensagens, visita). A cota é contada pelos agendamentos ligados à adesão (`appointments.membership_id`).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from . import catalog
from .db import many, one

COUNTS = ("agendado", "confirmado", "chegou", "em_atendimento", "atendido")
BILLING = {"cartao": "Cartão", "pix_automatico": "PIX Automático", "boleto": "Boleto", "pix": "PIX"}


def _json(text: str | None, default):
    try:
        return json.loads(text) if text else default
    except ValueError:
        return default


def _covered_ids(conn: sqlite3.Connection, svc: dict) -> list[int]:
    """Os serviços que gastam a cota de um benefício: a cota de puericultura também cobre a primeira consulta do
    recém-nascido, que é a puericultura da primeira semana."""
    ids = [svc["id"]]
    if svc["kind"] == "well_child":
        ids += [r["id"] for r in many(conn, "SELECT id FROM services WHERE kind = 'newborn'")]
    return ids


def plan_dict(row: dict) -> dict:
    out = dict(row)
    out["benefits"] = _json(row["benefits"], [])
    out["perks"] = _json(row["perks"], [])
    out["auto_renew"] = bool(row["auto_renew"])
    out["active"] = bool(row["active"])
    return out


def active_membership(conn: sqlite3.Connection, patient_id: int, on: date) -> dict | None:
    return one(conn, """
        SELECT m.*, p.name AS plan_name FROM memberships m JOIN plans p ON p.id = m.plan_id
        WHERE m.patient_id = ? AND m.status IN ('ativo', 'pausado') AND m.started_on <= ? AND m.ends_on >= ?
        ORDER BY m.started_on DESC LIMIT 1""", (patient_id, on.isoformat(), on.isoformat()))


def usage(conn: sqlite3.Connection, membership: dict) -> list[dict]:
    plan = plan_dict(one(conn, "SELECT * FROM plans WHERE id = ?", (membership["plan_id"],)))
    out = []
    for b in plan["benefits"]:
        svc = one(conn, "SELECT id, name, kind FROM services WHERE id = ?", (b["service_id"],))
        if not svc:
            continue
        ids = _covered_ids(conn, svc)
        rows = many(conn, f"""SELECT status FROM appointments WHERE membership_id = ? AND service_id IN ({', '.join('?' for _ in ids)})
                              AND status IN ({', '.join('?' for _ in COUNTS)})""", (membership["id"], *ids, *COUNTS))
        used = sum(1 for r in rows if r["status"] == "atendido")
        out.append({"service_id": svc["id"], "service": svc["name"], "label": b.get("label") or svc["name"],
                    "qty": b["qty"], "used": used, "booked": len(rows) - used})
    return out


def membership_view(conn: sqlite3.Connection, membership: dict) -> dict:
    plan = plan_dict(one(conn, "SELECT * FROM plans WHERE id = ?", (membership["plan_id"],)))
    uses = usage(conn, membership)
    main = uses[0] if uses else None
    return {
        "id": membership["id"], "plan_id": plan["id"], "plan": plan["name"], "status": membership["status"],
        "started_on": membership["started_on"], "ends_on": membership["ends_on"],
        "paused_until": membership["paused_until"], "billing": membership["billing"],
        "billing_label": BILLING.get(membership["billing"], membership["billing"]), "due_day": membership["due_day"],
        "price_cents": membership["price_cents"], "usage": uses, "perks": plan["perks"],
        "summary": f"{main['used']} de {main['qty']} {main['label'].lower()}" if main else "",
    }


def cover(conn: sqlite3.Connection, patient_id: int, service: dict, on: date) -> dict:
    """Se o agendamento entra no plano: a adesão, o preço e a frase para a família."""
    price = service["price_cents"]
    cfg = catalog.config_of(service)
    out = {"membership_id": None, "price_cents": price, "covered": False, "plan": None, "label": ""}
    m = active_membership(conn, patient_id, on)
    if not m or m["status"] != "ativo" or cfg["plan_mode"] == "fora":
        return out
    plan = plan_dict(one(conn, "SELECT * FROM plans WHERE id = ?", (m["plan_id"],)))
    out["plan"] = plan["name"]
    if cfg["plan_mode"] == "cota":
        for u in usage(conn, m):
            ids = _covered_ids(conn, one(conn, "SELECT id, kind FROM services WHERE id = ?", (u["service_id"],)))
            if service["id"] in ids and u["used"] + u["booked"] < u["qty"]:
                nth = u["used"] + u["booked"] + 1
                out.update(membership_id=m["id"], price_cents=0, covered=True,
                           label=f"Incluída no plano: será a {nth}ª de {u['qty']}.")
                return out
    if plan["discount_pct"] and price:
        out["price_cents"] = round(price * (100 - plan["discount_pct"]) / 100)
        out["label"] = f"{plan['discount_pct']}% de desconto do plano {plan['name']}."
    return out


def stats(conn: sqlite3.Connection, today: date) -> dict:
    plans = [plan_dict(r) for r in many(conn, "SELECT * FROM plans ORDER BY id")]
    members = many(conn, """SELECT m.*, pt.name AS patient, pt.family_id FROM memberships m
                            JOIN patients pt ON pt.id = m.patient_id WHERE m.status != 'cancelado'""")
    for p in plans:
        mine = [m for m in members if m["plan_id"] == p["id"] and m["status"] == "ativo"]
        p["subscribers"] = len(mine)
        rates = []
        for m in mine:
            for u in usage(conn, m)[:1]:
                if u["qty"]:
                    rates.append(u["used"] / u["qty"])
        p["usage_pct"] = round(100 * sum(rates) / len(rates)) if rates else 0
    active = [m for m in members if m["status"] == "ativo"]
    return {
        "plans": plans,
        "subscribers": len(active),
        "mrr_cents": sum(m["price_cents"] for m in active),
        "new_this_month": sum(1 for m in active if m["started_on"][:7] == today.isoformat()[:7]),
    }

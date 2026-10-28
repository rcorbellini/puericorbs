"""O dinheiro da prática: cobranças (o que entra, pago ou a receber) e despesas (o que sai).

Uma cobrança paga é um recebimento. A consulta avulsa vira cobrança paga na hora em que a recepção recebe; a do plano
nasce aberta no dia de vencimento de cada mês (`ensure_plan_charges`) e fica paga quando o pagamento entra.
"""

from __future__ import annotations

import calendar
import sqlite3
from datetime import date

from .db import insert, many, now_iso, one

MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MONTHS_FULL = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
               "Novembro", "Dezembro"]
METHODS = {"pix": "PIX", "cartao": "Cartão", "dinheiro": "Dinheiro", "pix_automatico": "PIX Automático",
           "boleto": "Boleto", "cortesia": "Cortesia"}
INVOICE = {"emitir": "Emitir", "emitida": "Emitida", "sem_nota": "Sem nota"}


def month_range(ym: str) -> tuple[date, date]:
    y, m = int(ym[:4]), int(ym[5:7])
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def shift_month(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7]) - 1 + n
    y, m = y + m // 12, m % 12 + 1
    return f"{y:04d}-{m:02d}"


def ensure_plan_charges(conn: sqlite3.Connection, today: date) -> int:
    """A cobrança do mês de cada adesão ativa, criada uma vez só. Devolve quantas criou."""
    ym = today.isoformat()[:7]
    first, last = month_range(ym)
    made = 0
    rows = many(conn, """
        SELECT m.*, p.name AS plan, pt.family_id FROM memberships m JOIN plans p ON p.id = m.plan_id
        JOIN patients pt ON pt.id = m.patient_id
        WHERE m.status = 'ativo' AND m.started_on <= ? AND m.ends_on >= ?""", (last.isoformat(), first.isoformat()))
    for m in rows:
        if one(conn, "SELECT id FROM charges WHERE membership_id = ? AND substr(due_on, 1, 7) = ?", (m["id"], ym)):
            continue
        due = date(first.year, first.month, min(m["due_day"], last.day))
        insert(conn, "charges", {
            "family_id": m["family_id"], "patient_id": m["patient_id"], "membership_id": m["id"],
            "description": f"Plano {m['plan']} · {MONTHS_FULL[first.month - 1].lower()}",
            "amount_cents": m["price_cents"], "due_on": due.isoformat(), "status": "aberta",
            "method": m["billing"], "invoice": "emitir", "created_at": now_iso(),
        })
        made += 1
    return made


def _charge_rows(conn: sqlite3.Connection, where: str, args: tuple) -> list[dict]:
    return many(conn, f"""
        SELECT c.*, f.name AS family, pt.name AS patient FROM charges c
        JOIN families f ON f.id = c.family_id LEFT JOIN patients pt ON pt.id = c.patient_id
        WHERE {where}""", args)


def summary(conn: sqlite3.Connection, ym: str, today: date) -> dict:
    first, last = month_range(ym)
    paid = _charge_rows(conn, "c.status = 'paga' AND c.paid_on BETWEEN ? AND ? ORDER BY c.paid_on DESC, c.id DESC",
                        (first.isoformat(), last.isoformat()))
    prev_first, prev_last = month_range(shift_month(ym, -1))
    prev = one(conn, "SELECT COALESCE(SUM(amount_cents), 0) AS s FROM charges WHERE status = 'paga' AND paid_on BETWEEN ? AND ?",
               (prev_first.isoformat(), prev_last.isoformat()))["s"]
    open_rows = _charge_rows(conn, "c.status = 'aberta' AND c.due_on <= ? ORDER BY c.due_on", (last.isoformat(),))
    overdue = [c for c in open_rows if c["due_on"] < today.isoformat()]
    expenses = many(conn, "SELECT * FROM expenses WHERE spent_on BETWEEN ? AND ? ORDER BY amount_cents DESC",
                    (first.isoformat(), last.isoformat()))
    received = sum(c["amount_cents"] for c in paid)
    spent = sum(e["amount_cents"] for e in expenses)
    series = []
    for n in range(-5, 1):
        mym = shift_month(ym, n)
        a, b = month_range(mym)
        row = one(conn, """SELECT
                COALESCE(SUM(CASE WHEN membership_id IS NOT NULL THEN amount_cents END), 0) AS plans,
                COALESCE(SUM(CASE WHEN membership_id IS NULL THEN amount_cents END), 0) AS visits
            FROM charges WHERE status = 'paga' AND paid_on BETWEEN ? AND ?""", (a.isoformat(), b.isoformat()))
        series.append({"ym": mym, "label": MONTHS[a.month - 1], "full": MONTHS_FULL[a.month - 1],
                       "plans": row["plans"], "visits": row["visits"]})
    return {
        "ym": ym, "label": f"{MONTHS_FULL[first.month - 1]} de {first.year}",
        "received": received, "received_prev": prev,
        "delta_pct": round(100 * (received - prev) / prev, 1) if prev else None,
        "receivable": sum(c["amount_cents"] for c in open_rows),
        "overdue": sum(c["amount_cents"] for c in overdue), "overdue_count": len(overdue),
        "spent": spent, "result": received - spent,
        "series": series,
        "recent": paid[:12],
        "open": open_rows,
        "invoices_pending": sum(1 for c in paid if c["invoice"] == "emitir" and c["amount_cents"] > 0),
        "invoices_done": sum(1 for c in paid if c["invoice"] == "emitida"),
        "expenses": expenses,
    }


def receive_appointment(conn: sqlite3.Connection, appt: dict, method: str, today: date, amount_cents: int | None = None) -> int:
    """A recepção recebe a consulta avulsa: vira uma cobrança paga, com a nota a emitir."""
    existing = one(conn, "SELECT id FROM charges WHERE appointment_id = ? AND status = 'paga'", (appt["id"],))
    if existing:
        return existing["id"]
    pt = one(conn, "SELECT family_id FROM patients WHERE id = ?", (appt["patient_id"],))
    svc = one(conn, "SELECT name FROM services WHERE id = ?", (appt["service_id"],))
    amount = appt["price_cents"] if amount_cents is None else amount_cents
    return insert(conn, "charges", {
        "family_id": pt["family_id"], "patient_id": appt["patient_id"], "appointment_id": appt["id"],
        "description": svc["name"], "amount_cents": amount, "due_on": today.isoformat(), "status": "paga",
        "method": method, "paid_on": today.isoformat(), "invoice": "emitir" if amount else "sem_nota",
        "created_at": now_iso(),
    })

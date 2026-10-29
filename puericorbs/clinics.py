"""O consultório (a clínica): o lugar e a equipe que uma ou mais pediatras dividem.

Cada pediatra tem a prática dela (os pacientes, o prontuário, a agenda, o dinheiro), e cada uma só vê os seus. O
consultório junta as práticas e a equipe que atende todas elas: a atendente e a administração do consultório
(`clinic_members`), que faz o que a atendente faz e cuida da equipe e dos convites. Nada clínico para as duas. Quem cria
o consultório (a primeira pediatra) já nasce na administração dele.

Pediatra sem domínio próprio trabalha pelo domínio de outra pediatra do mesmo consultório: quem entra é levado à
prática dele (`context.py`).
"""

from __future__ import annotations

import sqlite3

from .db import connect_practice, insert, many, now_iso, one

ROLES = ("receptionist", "manager")


def create(pconn: sqlite3.Connection, name: str) -> int:
    return insert(pconn, "clinics", {"name": name.strip()[:80] or "Consultório", "created_at": now_iso()})


def practices(pconn: sqlite3.Connection, clinic_id: int | None) -> list[dict]:
    """As práticas (as pediatras) do consultório, da mais antiga para a mais nova."""
    if not clinic_id:
        return []
    return many(pconn, "SELECT * FROM practices WHERE clinic_id = ? ORDER BY id", (clinic_id,))


def member(pconn: sqlite3.Connection, clinic_id: int | None, user_id: int) -> dict | None:
    """O papel de alguém na equipe do consultório (atendente ou administração), se tiver."""
    if not clinic_id:
        return None
    return one(pconn, "SELECT * FROM clinic_members WHERE clinic_id = ? AND user_id = ?", (clinic_id, user_id))


def add(pconn: sqlite3.Connection, clinic_id: int, user_id: int, role: str) -> None:
    """Entra na equipe. Quem já é administração não volta a ser só atendente (o convite não rebaixa ninguém)."""
    if role not in ROLES:
        raise ValueError(f"papel desconhecido no consultório: {role}")
    current = member(pconn, clinic_id, user_id)
    if current and (current["role"] == "manager" or current["role"] == role):
        return
    pconn.execute("INSERT OR REPLACE INTO clinic_members (clinic_id, user_id, role, created_at) VALUES (?, ?, ?, ?)",
                  (clinic_id, user_id, role, now_iso()))


def own_practice(pconn: sqlite3.Connection, clinic_id: int | None, user_id: int) -> dict | None:
    """A prática em que a pessoa é a pediatra, dentro do consultório."""
    if not clinic_id:
        return None
    return one(pconn, """SELECT p.* FROM memberships m JOIN practices p ON p.id = m.practice_id
                         WHERE m.user_id = ? AND m.role = 'clinician' AND p.clinic_id = ? ORDER BY p.id LIMIT 1""",
               (user_id, clinic_id))


def guardian_practice(pconn: sqlite3.Connection, data_dir, clinic_id: int | None, user_id: int,
                      skip: int | None = None) -> dict | None:
    """A prática do consultório em que a pessoa é responsável de uma família (a primeira, se for de mais de uma)."""
    for p in practices(pconn, clinic_id):
        if p["id"] == skip:
            continue
        conn = connect_practice(data_dir, p["id"])
        try:
            if one(conn, "SELECT id FROM guardians WHERE user_id = ? LIMIT 1", (user_id,)):
                return p
        finally:
            conn.close()
    return None


def team(pconn: sqlite3.Connection, clinic_id: int) -> list[dict]:
    """Quem trabalha no consultório: as pediatras (com a prática de cada uma) e a equipe, com a última entrada."""
    last = "(SELECT MAX(s.created_at) FROM sessions s WHERE s.user_id = u.id)"
    doctors = many(pconn, f"""SELECT u.id, u.name, u.email, 'clinician' AS role, p.id AS practice_id, p.name AS practice,
                                     {last} AS last_login
                              FROM memberships m JOIN users u ON u.id = m.user_id JOIN practices p ON p.id = m.practice_id
                              WHERE p.clinic_id = ? AND m.role = 'clinician' ORDER BY p.id, u.name""", (clinic_id,))
    staff = many(pconn, f"""SELECT u.id, u.name, u.email, c.role, NULL AS practice_id, NULL AS practice, {last} AS last_login
                            FROM clinic_members c JOIN users u ON u.id = c.user_id WHERE c.clinic_id = ?
                            ORDER BY c.role = 'receptionist', u.name""", (clinic_id,))
    managers = {s["id"] for s in staff if s["role"] == "manager"}
    for d in doctors:
        d["manager"] = d["id"] in managers
    return doctors + [s for s in staff if s["id"] not in {d["id"] for d in doctors}]


def domains(pconn: sqlite3.Connection, clinic_id: int | None) -> list[str]:
    """Os domínios das pediatras do consultório: qualquer um deles abre o consultório para a equipe."""
    if not clinic_id:
        return []
    return [r["host"] for r in many(pconn, """SELECT d.host FROM domains d JOIN practices p ON p.id = d.practice_id
                                             WHERE p.clinic_id = ? ORDER BY p.id, d.created_at, d.host""", (clinic_id,))]

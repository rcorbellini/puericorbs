"""O convite: o link de primeiro acesso de quem vai trabalhar num consultório.

A plataforma gera um link de uso único (`puericorbs invite SLUG`) e manda para a pediatra ou para a atendente. Ele só
abre no domínio do próprio consultório, e ali a pessoa cria a conta com o e-mail e a senha dela: nenhuma senha passa
por terceiros. O banco guarda só o hash do token, como nas sessões.
"""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta

from .auth import token_hash
from .db import insert, many, now_iso, one

ROLES = ("clinician", "receptionist")


def create(pconn: sqlite3.Connection, practice_id: int, role: str = "clinician", days: int = 7) -> str:
    if role not in ROLES:
        raise ValueError(f"papel desconhecido: {role}")
    token = secrets.token_urlsafe(24)
    now = datetime.now().replace(microsecond=0)
    insert(pconn, "invites", {"token_hash": token_hash(token), "practice_id": practice_id, "role": role,
                              "created_at": now.isoformat(), "expires_at": (now + timedelta(days=days)).isoformat()})
    return token


def find(pconn: sqlite3.Connection, token: str, practice_id: int | None) -> dict | None:
    """O convite que ainda vale neste consultório. Usado, vencido ou de outro consultório é como se não existisse."""
    row = one(pconn, "SELECT * FROM invites WHERE token_hash = ?", (token_hash(token or ""),))
    if not row or row["practice_id"] != practice_id or row["used_at"] or row["expires_at"] < now_iso():
        return None
    return row


def use(pconn: sqlite3.Connection, row: dict, user_id: int) -> bool:
    """Gasta o convite. Falso se outro pedido o gastou antes (dois cliques ao mesmo tempo)."""
    cur = pconn.execute("UPDATE invites SET used_at = ?, used_by = ? WHERE token_hash = ? AND used_at IS NULL",
                        (now_iso(), user_id, row["token_hash"]))
    return cur.rowcount == 1


def link(pconn: sqlite3.Connection, practice: dict, token: str, base_domains: tuple[str, ...], port: int) -> str:
    """O endereço do convite: o domínio do consultório; sem ele, o subdomínio da plataforma; no computador, o local."""
    domains = many(pconn, "SELECT host FROM domains WHERE practice_id = ? ORDER BY created_at, host", (practice["id"],))
    if domains:
        return f"https://{domains[0]['host']}/#/convite/{token}"
    base = next((b for b in base_domains if b != "localhost"), None)
    if base:
        return f"https://{practice['slug']}.{base}/#/convite/{token}"
    return f"http://{practice['slug']}.localhost:{port}/#/convite/{token}"

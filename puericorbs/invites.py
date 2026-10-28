"""O convite: um link de uso único para alguém entrar no Puericorbs com a própria senha.

Quatro tipos:

- `staff`: a equipe de um consultório (a pediatra, criada pela plataforma; a atendente, pela pediatra);
- `family`: um responsável já cadastrado na ficha, que cria a senha do app da família (pela pediatra ou pela recepção);
- `practice`: um colega pediatra, que ganha o próprio consultório, separado do de quem convidou;
- `admin`: alguém da administração da plataforma.

O de equipe e o de família só abrem no domínio do próprio consultório. O de colega e o de administração abrem em
qualquer endereço do Puericorbs (ainda não há domínio da plataforma). Ninguém escolhe a senha de ninguém, e o banco
guarda só o hash do token, como nas sessões.
"""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta

from .auth import token_hash
from .db import insert, many, now_iso, one

KINDS = ("staff", "family", "practice", "admin")
ROLES = ("clinician", "receptionist")
LABEL = {"staff": "Equipe", "family": "Família", "practice": "Consultório próprio", "admin": "Administração"}


def create(pconn: sqlite3.Connection, *, kind: str = "staff", practice_id: int | None = None, role: str | None = None,
           guardian_id: int | None = None, label: str | None = None, created_by: int | None = None,
           days: int = 7) -> tuple[str, int]:
    """O token (que só aparece agora, no link) e o id do convite."""
    if kind not in KINDS:
        raise ValueError(f"tipo de convite desconhecido: {kind}")
    if kind == "staff" and role not in ROLES:
        raise ValueError(f"papel desconhecido: {role}")
    if kind in ("staff", "family") and not practice_id:
        raise ValueError("o convite de equipe e o de família são de um consultório")
    token = secrets.token_urlsafe(24)
    now = datetime.now().replace(microsecond=0)
    invite_id = insert(pconn, "invites", {
        "token_hash": token_hash(token), "kind": kind, "practice_id": practice_id,
        "role": role if kind == "staff" else None, "guardian_id": guardian_id if kind == "family" else None,
        "label": (label or "").strip()[:80] or None, "created_by": created_by,
        "created_at": now.isoformat(), "expires_at": (now + timedelta(days=days)).isoformat()})
    return token, invite_id


def valid(row: dict | None) -> bool:
    return bool(row) and not row["used_at"] and not row["revoked_at"] and row["expires_at"] >= now_iso()


def find(pconn: sqlite3.Connection, token: str) -> dict | None:
    """O convite que ainda vale (não usado, não cancelado, não vencido), de qualquer tipo."""
    row = one(pconn, "SELECT * FROM invites WHERE token_hash = ?", (token_hash(token or ""),))
    return row if valid(row) else None


def opens_here(row: dict, site) -> bool:
    """Equipe e família: só no domínio do consultório do convite. Colega e administração: em qualquer site nosso."""
    if row["kind"] in ("staff", "family"):
        return site.kind == "practice" and site.practice["id"] == row["practice_id"]
    return site.kind in ("practice", "platform")


def use(pconn: sqlite3.Connection, row: dict, user_id: int, new_practice_id: int | None = None) -> bool:
    """Gasta o convite. Falso se outro pedido o gastou antes (dois cliques ao mesmo tempo)."""
    cur = pconn.execute("""UPDATE invites SET used_at = ?, used_by = ?, new_practice_id = ?
                           WHERE id = ? AND used_at IS NULL AND revoked_at IS NULL""",
                        (now_iso(), user_id, new_practice_id, row["id"]))
    return cur.rowcount == 1


def revoke(pconn: sqlite3.Connection, invite_id: int) -> None:
    pconn.execute("UPDATE invites SET revoked_at = ? WHERE id = ? AND used_at IS NULL AND revoked_at IS NULL",
                  (now_iso(), invite_id))


def status(row: dict) -> str:
    if row["used_at"]:
        return "aceito"
    if row["revoked_at"]:
        return "cancelado"
    return "vencido" if row["expires_at"] < now_iso() else "pendente"


def view(row: dict) -> dict:
    return {"id": row["id"], "kind": row["kind"], "kind_label": LABEL[row["kind"]], "role": row["role"],
            "label": row["label"], "created_at": row["created_at"], "expires_at": row["expires_at"],
            "used_at": row["used_at"], "status": status(row), "practice_id": row["practice_id"],
            "new_practice_id": row["new_practice_id"]}


def page_link(host: str, scheme: str, token: str) -> str:
    """O link no endereço onde ele foi gerado (o domínio do consultório, quando quem gera está nele)."""
    return f"{scheme}://{host}/#/convite/{token}"


def link(pconn: sqlite3.Connection, practice: dict | None, token: str, base_domains: tuple[str, ...], port: int) -> str:
    """O link fora de um pedido (a linha de comando): o domínio do consultório; sem ele, o subdomínio da plataforma; no
    computador, o local. O convite de colega e o de administração usam o primeiro domínio cadastrado."""
    if practice:
        rows = many(pconn, "SELECT host FROM domains WHERE practice_id = ? ORDER BY created_at, host", (practice["id"],))
    else:
        rows = many(pconn, "SELECT host FROM domains ORDER BY created_at, host LIMIT 1")
    if rows:
        return page_link(rows[0]["host"], "https", token)
    base = next((b for b in base_domains if b != "localhost"), None)
    if practice and base:
        return page_link(f"{practice['slug']}.{base}", "https", token)
    return page_link(f"{practice['slug']}.localhost:{port}" if practice else f"localhost:{port}", "http", token)


def log(pconn: sqlite3.Connection, action: str, *, user_id: int | None = None, practice_id: int | None = None,
        detail: str | None = None, ip: str | None = None) -> None:
    """O registro da plataforma: o que a administração acompanha."""
    insert(pconn, "platform_log", {"at": now_iso(), "user_id": user_id, "practice_id": practice_id, "action": action,
                                   "detail": (detail or "")[:300] or None, "ip": ip})


def family_access(pconn: sqlite3.Connection, conn: sqlite3.Connection, practice_id: int, family_id: int) -> list[dict]:
    """Quem da família já entra no app: com conta e senha (ativo), com o link mandado e ainda valendo (convite) ou
    sem nada (sem)."""
    out = []
    for g in many(conn, "SELECT id, name, relation, phone, email, user_id FROM guardians WHERE family_id = ? ORDER BY id",
                  (family_id,)):
        user = one(pconn, "SELECT email, password_hash FROM users WHERE id = ?", (g["user_id"],)) if g["user_id"] else None
        pending = one(pconn, """SELECT * FROM invites WHERE kind = 'family' AND practice_id = ? AND guardian_id = ?
                                AND used_at IS NULL AND revoked_at IS NULL AND expires_at >= ?
                                ORDER BY created_at DESC LIMIT 1""", (practice_id, g["id"], now_iso()))
        state = "ativo" if user and user["password_hash"] else "convite" if pending else "sem"
        out.append({"id": g["id"], "name": g["name"], "relation": g["relation"], "phone": g["phone"],
                    "email": user["email"] if user else g["email"], "state": state,
                    "invite": view(pending) if pending else None})
    return out

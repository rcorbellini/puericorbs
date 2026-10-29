"""O convite: um link de uso único para alguém entrar no Puericorbs com a própria senha. Todo começo é um convite.

Quatro tipos:

- `practice`: a pediatra que cria o próprio consultório (só a plataforma gera); ela nasce na administração dele;
- `staff`: a equipe de um consultório (`clinic_id`), pela administração dele: uma pediatra que entra com os pacientes
  dela (`clinician`), a atendente de todas as pediatras (`receptionist`) ou mais alguém da administração (`manager`). O
  convite de pediatra com `practice_id` é o da plataforma para um consultório criado vazio;
- `family`: um responsável, pela pediatra ou pela recepção. Ou de quem já está na ficha (`guardian_id`), que só cria
  a senha, ou de uma família nova: quem convida escreve o que sabe (no banco da prática, `invite_prefill`), e a
  família completa o resto. O convite da família não leva nome nenhum para o banco da plataforma;
- `admin`: alguém da administração da plataforma.

O de equipe e o de família abrem em qualquer domínio do consultório deles; o de consultório próprio e o de
administração, em qualquer endereço do Puericorbs (ainda não há domínio da plataforma). Ninguém escolhe a senha de
ninguém, e o banco guarda só o hash do token, como nas sessões.
"""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta

import segno

from .auth import token_hash
from . import clinics
from .db import insert, many, now_iso, one

KINDS = ("staff", "family", "practice", "admin")
ROLES = ("clinician", "receptionist", "manager")
LABEL = {"staff": "Equipe", "family": "Família", "practice": "Consultório próprio", "admin": "Administração"}
ROLE_LABEL = {"clinician": "Pediatra", "receptionist": "Atendente", "manager": "Administração do consultório"}


def create(pconn: sqlite3.Connection, *, kind: str = "staff", practice_id: int | None = None, role: str | None = None,
           guardian_id: int | None = None, label: str | None = None, created_by: int | None = None,
           days: int = 7, clinic_id: int | None = None) -> tuple[str, int]:
    """O token (que só aparece agora, no link) e o id do convite."""
    if kind not in KINDS:
        raise ValueError(f"tipo de convite desconhecido: {kind}")
    if kind == "staff" and role not in ROLES:
        raise ValueError(f"papel desconhecido: {role}")
    if kind == "family" and not practice_id:
        raise ValueError("o convite da família é de uma pediatra")
    if kind == "staff" and not (practice_id or clinic_id):
        raise ValueError("o convite de equipe é de um consultório")
    if kind == "staff" and not clinic_id:
        clinic_id = one(pconn, "SELECT clinic_id FROM practices WHERE id = ?", (practice_id,))["clinic_id"]
    token = secrets.token_urlsafe(24)
    now = datetime.now().replace(microsecond=0)
    invite_id = insert(pconn, "invites", {
        "token_hash": token_hash(token), "kind": kind, "practice_id": practice_id,
        "role": role if kind == "staff" else None, "guardian_id": guardian_id if kind == "family" else None,
        "label": None if kind == "family" else (label or "").strip()[:80] or None, "created_by": created_by,
        "created_at": now.isoformat(), "expires_at": (now + timedelta(days=days)).isoformat(),
        "clinic_id": clinic_id if kind == "staff" else None})
    return token, invite_id


def clinic_of(pconn: sqlite3.Connection, row: dict) -> int | None:
    """O consultório do convite: o dele, ou o da pediatra (o da família e o de um consultório criado vazio)."""
    if row["clinic_id"]:
        return row["clinic_id"]
    if row["practice_id"]:
        p = one(pconn, "SELECT clinic_id FROM practices WHERE id = ?", (row["practice_id"],))
        return p["clinic_id"] if p else None
    return None


def valid(row: dict | None) -> bool:
    return bool(row) and not row["used_at"] and not row["revoked_at"] and row["expires_at"] >= now_iso()


def find(pconn: sqlite3.Connection, token: str) -> dict | None:
    """O convite que ainda vale (não usado, não cancelado, não vencido), de qualquer tipo."""
    row = one(pconn, "SELECT * FROM invites WHERE token_hash = ?", (token_hash(token or ""),))
    return row if valid(row) else None


def opens_here(pconn: sqlite3.Connection, row: dict, site) -> bool:
    """Equipe e família: em qualquer domínio do consultório do convite. Consultório próprio e administração: em
    qualquer site nosso."""
    if row["kind"] in ("staff", "family"):
        return site.kind == "practice" and site.practice["clinic_id"] == clinic_of(pconn, row)
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
            "role_label": ROLE_LABEL.get(row["role"] or ""), "label": row["label"], "created_at": row["created_at"],
            "expires_at": row["expires_at"], "used_at": row["used_at"], "status": status(row),
            "practice_id": row["practice_id"], "new_practice_id": row["new_practice_id"], "clinic_id": row["clinic_id"]}


def qr_svg(link: str) -> str:
    """O QR code do link, em SVG (escuro no fundo branco, com a margem que a câmera precisa): a pessoa aponta o
    celular para a tela da recepção, ou o QR vai impresso. Feito aqui, sem nada de fora."""
    return segno.make(link, error="m").svg_inline(scale=1, border=4, dark="#1c2b3a", light="#ffffff", omitsize=True)


def page_link(host: str, scheme: str, token: str) -> str:
    """O link no endereço onde ele foi gerado (o domínio do consultório, quando quem gera está nele)."""
    return f"{scheme}://{host}/#/convite/{token}"


def link(pconn: sqlite3.Connection, practice: dict | None, token: str, base_domains: tuple[str, ...], port: int) -> str:
    """O link fora de um pedido (a linha de comando, a recepção de outra pediatra): o domínio da pediatra; sem ele, o
    de outra pediatra do mesmo consultório; depois, o subdomínio da plataforma; no computador, o local. O convite de
    consultório próprio e o de administração usam o primeiro domínio cadastrado."""
    if practice:
        rows = many(pconn, "SELECT host FROM domains WHERE practice_id = ? ORDER BY created_at, host", (practice["id"],))
        rows = rows or [{"host": h} for h in clinics.domains(pconn, practice["clinic_id"])]
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

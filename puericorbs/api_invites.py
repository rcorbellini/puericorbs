"""Os convites na API: abrir e aceitar (quem foi convidado) e gerar (a pediatra e a recepção). Os tipos e onde cada
um abre estão em `invites.py`; o que a administração gera está em `api_admin.py`.

Regra de ouro: uma conta que já existe só se liga a um consultório, a uma família ou à administração com a senha
dela. O convite cria a senha de quem ainda não tem conta; nunca escolhe a senha de uma conta alheia.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from . import auth, invites, practices, tenancy
from .api_public import login_user, password_ok, practice_public
from .api_staff import _practice
from .context import ROLE_LABEL, Ctx, clinician, dep
from .db import connect_practice, insert, many, now_iso, one, transaction, update

router = APIRouter(prefix="/api")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HOST = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


def request_link(request: Request, token: str) -> str:
    """O link no endereço deste pedido: quem gera está no domínio do consultório (ou no painel da plataforma)."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    return invites.page_link(request.headers.get("host", "localhost"), scheme, token)


def clean_host(text: str | None) -> str | None:
    """O domínio como a pessoa escreve (com https://, www., barra no fim) vira só o nome; inválido é recusado."""
    if not (text or "").strip():
        return None
    host = re.sub(r"^https?://", "", text.strip().lower()).split("/")[0]
    host = tenancy.normalize_host(host.removeprefix("www."))
    if not HOST.match(host):
        raise HTTPException(400, "Confira o domínio: ele é algo como drnome.com.br, sem espaço.")
    return host


# ---- abrir e aceitar --------------------------------------------------------------------------------------------------

def _open(ctx: Ctx, token: str) -> dict:
    row = invites.find(ctx.pconn, token)
    if not row or not invites.opens_here(row, ctx.site):
        raise HTTPException(404, "Este convite não vale mais: ele já foi usado, foi cancelado ou venceu. "
                                 "Peça um novo a quem mandou.")
    return row


def _guardian(ctx: Ctx, row: dict) -> dict:
    """O responsável no banco do consultório do convite (o id só vale dentro dele)."""
    g = one(ctx.open_practice(row["practice_id"]), "SELECT * FROM guardians WHERE id = ?", (row["guardian_id"],))
    if not g:
        raise HTTPException(404, "Este responsável não está mais no cadastro. Peça um novo convite ao consultório.")
    return g


def _keeps_password(ctx: Ctx, user: dict, practice_id: int | None) -> bool:
    """A conta que o convite da família não pode trocar a senha: a da equipe, a da administração e a de quem também é
    responsável em outro consultório (lá, quem cuida da conta é a própria pessoa)."""
    if user["is_platform_admin"] or one(ctx.pconn, "SELECT 1 AS ok FROM memberships WHERE user_id = ?", (user["id"],)):
        return True
    for p in many(ctx.pconn, "SELECT id FROM practices WHERE id != ?", (practice_id,)):
        conn = connect_practice(ctx.settings.data_dir, p["id"])
        try:
            if one(conn, "SELECT id FROM guardians WHERE user_id = ?", (user["id"],)):
                return True
        finally:
            conn.close()
    return False


@router.get("/invite/{token}")
def invite_info(token: str, ctx: Ctx = Depends(dep)):
    row = _open(ctx, token)
    out = {"kind": row["kind"], "expires_at": row["expires_at"]}
    if row["kind"] in ("staff", "family"):
        out["practice"] = practice_public(ctx.site.practice)
    if row["kind"] == "staff":
        out.update(role=row["role"], role_label=ROLE_LABEL[row["role"]])
    elif row["kind"] == "family":
        g = _guardian(ctx, row)
        user = one(ctx.pconn, "SELECT * FROM users WHERE id = ?", (g["user_id"],)) if g["user_id"] else None
        out["guardian"] = {"name": g["name"], "relation": g["relation"], "email": g["email"]}
        out["account"] = {"email": user["email"], "keeps_password": _keeps_password(ctx, user, row["practice_id"])} \
            if user else None
    elif row["kind"] == "practice":
        who = one(ctx.pconn, "SELECT name FROM users WHERE id = ?", (row["created_by"],)) if row["created_by"] else None
        out["inviter"] = who["name"] if who else None
    return out


class InviteAccept(BaseModel):
    password: str
    name: str | None = None
    email: str | None = None
    practice_name: str | None = None
    registry: str | None = None
    domain: str | None = None


def _email(text: str | None) -> str:
    email = (text or "").strip().lower()
    if not EMAIL.match(email):
        raise HTTPException(400, "Confira o e-mail: é com ele que você vai entrar.")
    return email


def _name(text: str | None) -> str:
    name = (text or "").strip()[:80]
    if not name:
        raise HTTPException(400, "Escreva o seu nome.")
    return name


def _new_password(text: str, size: int = 8) -> None:
    if len(text) < size:
        raise HTTPException(400, f"A senha precisa de pelo menos {size} caracteres.")


def _account_for(ctx: Ctx, email: str, name: str, password: str, *, admin: bool = False) -> int:
    """A conta deste e-mail: a que já existe, com a senha dela, ou uma nova com a senha escolhida agora."""
    user = one(ctx.pconn, "SELECT * FROM users WHERE email = ?", (email,))
    if user:
        if not password_ok(ctx, email, password, user["password_hash"]):
            raise HTTPException(409, "Já existe uma conta com este e-mail. Para aceitar o convite com ela, use a senha "
                                     "dela.")
        return user["id"]
    return insert(ctx.pconn, "users", {"email": email, "name": name, "password_hash": auth.hash_password(password),
                                       "is_platform_admin": 1 if admin else 0, "created_at": now_iso()})


def _spend(ctx: Ctx, row: dict, user_id: int, new_practice_id: int | None = None) -> None:
    if not invites.use(ctx.pconn, row, user_id, new_practice_id):
        raise HTTPException(404, "Este convite acabou de ser usado. Peça um novo a quem mandou.")


def _accept_staff(ctx: Ctx, row: dict, body: InviteAccept) -> dict:
    name, email = _name(body.name), _email(body.email)
    _new_password(body.password)
    uid = _account_for(ctx, email, name, body.password)
    _spend(ctx, row, uid)
    # quem já é da equipe deste consultório continua com o papel que tem (o convite não rebaixa ninguém)
    ctx.pconn.execute("INSERT OR IGNORE INTO memberships (user_id, practice_id, role) VALUES (?, ?, ?)",
                      (uid, row["practice_id"], row["role"]))
    if row["role"] == "clinician":
        changes = {}
        if (body.practice_name or "").strip():
            changes["name"] = body.practice_name.strip()[:80]
        if body.registry is not None:
            changes["registry"] = body.registry.strip()[:80] or None
        update(ctx.pconn, "practices", row["practice_id"], changes)
    invites.log(ctx.pconn, "convite_aceito", user_id=uid, practice_id=row["practice_id"],
                detail=f"equipe ({ROLE_LABEL[row['role']].lower()}): {name}", ip=ctx.ip)
    return {"login": uid}


def _accept_family(ctx: Ctx, row: dict, body: InviteAccept) -> dict:
    g = _guardian(ctx, row)
    _new_password(body.password)
    user = one(ctx.pconn, "SELECT * FROM users WHERE id = ?", (g["user_id"],)) if g["user_id"] else None
    if user:
        if _keeps_password(ctx, user, row["practice_id"]):
            if not password_ok(ctx, user["email"], body.password, user["password_hash"]):
                raise HTTPException(409, "Esta conta já entra em outro lugar do Puericorbs: use a senha que você já tem.")
        else:
            # a conta é só desta família, neste consultório: o link novo serve para criar outra senha
            update(ctx.pconn, "users", user["id"], {"password_hash": auth.hash_password(body.password)})
        uid = user["id"]
    else:
        uid = _account_for(ctx, _email(body.email or g["email"]), g["name"], body.password)
    _spend(ctx, row, uid)
    email = one(ctx.pconn, "SELECT email FROM users WHERE id = ?", (uid,))["email"]
    conn = ctx.open_practice(row["practice_id"])
    update(conn, "guardians", g["id"], {"user_id": uid, "email": g["email"] or email})
    insert(conn, "audit_log", {"at": now_iso(), "user_id": uid, "role": "guardian", "action": "familia_entrou",
                                   "entity": "guardian", "entity_id": g["id"], "ip": ctx.ip})
    invites.log(ctx.pconn, "convite_aceito", user_id=uid, practice_id=row["practice_id"], detail="família", ip=ctx.ip)
    return {"login": uid}


def _accept_practice(ctx: Ctx, row: dict, body: InviteAccept) -> dict:
    name, email = _name(body.name), _email(body.email)
    _new_password(body.password)
    site_name = (body.practice_name or "").strip()[:80] or name
    requested = clean_host(body.domain)
    uid = _account_for(ctx, email, name, body.password)
    _spend(ctx, row, uid)  # antes de criar o consultório: dois cliques ao mesmo tempo não criam dois
    slug = practices.free_slug(ctx.pconn, site_name)
    pid = practices.create_practice(ctx.pconn, ctx.settings.data_dir, name=site_name, slug=slug,
                                    registry=(body.registry or "").strip()[:80] or None, requested_domain=requested)
    ctx.pconn.execute("INSERT INTO memberships (user_id, practice_id, role) VALUES (?, ?, 'clinician')", (uid, pid))
    ctx.pconn.execute("UPDATE invites SET new_practice_id = ? WHERE id = ?", (pid, row["id"]))
    invites.log(ctx.pconn, "consultorio_criado", user_id=uid, practice_id=pid,
                detail=f"{site_name}, pelo convite de colega; domínio pedido: {requested or 'nenhum'}", ip=ctx.ip)
    return {"practice": {"name": site_name, "slug": slug}, "requested_domain": requested}


def _accept_admin(ctx: Ctx, row: dict, body: InviteAccept) -> dict:
    name, email = _name(body.name), _email(body.email)
    _new_password(body.password, 12)
    uid = _account_for(ctx, email, name, body.password, admin=True)
    ctx.pconn.execute("UPDATE users SET is_platform_admin = 1 WHERE id = ?", (uid,))
    _spend(ctx, row, uid)
    invites.log(ctx.pconn, "admin_entrou", user_id=uid, detail=name, ip=ctx.ip)
    return {"login": uid}


ACCEPT = {"staff": _accept_staff, "family": _accept_family, "practice": _accept_practice, "admin": _accept_admin}


@router.post("/invite/{token}")
def invite_accept(token: str, body: InviteAccept, request: Request, response: Response, ctx: Ctx = Depends(dep)):
    row = _open(ctx, token)
    with transaction(ctx.pconn):
        result = ACCEPT[row["kind"]](ctx, row, body)
    uid = result.pop("login", None)
    if uid:
        return login_user(ctx, request, response, one(ctx.pconn, "SELECT * FROM users WHERE id = ?", (uid,)))
    return {"ok": True, **result}


# ---- a pediatra: a equipe e os colegas --------------------------------------------------------------------------------

@router.get("/staff/team")
def team(ctx: Ctx = Depends(dep)):
    clinician(ctx)
    members = many(ctx.pconn, """
        SELECT u.id, u.name, u.email, m.role, (SELECT MAX(s.created_at) FROM sessions s WHERE s.user_id = u.id) AS last_login
        FROM memberships m JOIN users u ON u.id = m.user_id WHERE m.practice_id = ? ORDER BY m.role, u.name""",
                   (ctx.practice_id,))
    rows = many(ctx.pconn, """SELECT i.*, p.name AS new_practice FROM invites i
                              LEFT JOIN practices p ON p.id = i.new_practice_id
                              WHERE i.practice_id = ? AND i.kind IN ('staff', 'practice')
                              ORDER BY i.created_at DESC LIMIT 30""", (ctx.practice_id,))
    return {"members": [{**m, "role_label": ROLE_LABEL[m["role"]], "me": m["id"] == ctx.user["id"]} for m in members],
            "invites": [{**invites.view(r), "new_practice": r["new_practice"]} for r in rows]}


class StaffInvite(BaseModel):
    kind: str
    label: str | None = None


@router.post("/staff/invites")
def staff_invite(body: StaffInvite, request: Request, ctx: Ctx = Depends(dep)):
    """A atendente deste consultório, ou um colega que vai ter o consultório dele (e não vê nada deste)."""
    clinician(ctx)
    if body.kind not in ("receptionist", "colleague"):
        raise HTTPException(400, "Escolha o convite: atendente ou colega.")
    with transaction(ctx.pconn):
        if body.kind == "receptionist":
            token, iid = invites.create(ctx.pconn, kind="staff", practice_id=ctx.practice_id, role="receptionist",
                                        label=body.label, created_by=ctx.user["id"])
        else:
            token, iid = invites.create(ctx.pconn, kind="practice", practice_id=ctx.practice_id, label=body.label,
                                        created_by=ctx.user["id"])
        invites.log(ctx.pconn, "convite_gerado", user_id=ctx.user["id"], practice_id=ctx.practice_id,
                    detail=("atendente" if body.kind == "receptionist" else "colega") + (f": {body.label}" if body.label else ""),
                    ip=ctx.ip)
    return {"link": request_link(request, token),
            "invite": invites.view(one(ctx.pconn, "SELECT * FROM invites WHERE id = ?", (iid,)))}


@router.post("/staff/invites/{invite_id}/revoke")
def staff_revoke(invite_id: int, ctx: Ctx = Depends(dep)):
    row = one(ctx.pconn, "SELECT * FROM invites WHERE id = ? AND practice_id = ?", (invite_id, ctx.practice_id))
    if row and row["kind"] == "family":
        _practice(ctx, None)  # a família: a pediatra ou a recepção
    else:
        clinician(ctx)
    if not row:
        raise HTTPException(404, "Convite não encontrado.")
    invites.revoke(ctx.pconn, invite_id)
    invites.log(ctx.pconn, "convite_cancelado", user_id=ctx.user["id"], practice_id=ctx.practice_id,
                detail=invites.LABEL[row["kind"]], ip=ctx.ip)
    return {"ok": True}


@router.delete("/staff/team/{user_id}")
def remove_member(user_id: int, ctx: Ctx = Depends(dep)):
    """Tirar o acesso da atendente que saiu. A pediatra não sai por aqui."""
    clinician(ctx)
    m = one(ctx.pconn, "SELECT role FROM memberships WHERE user_id = ? AND practice_id = ?", (user_id, ctx.practice_id))
    if not m:
        raise HTTPException(404, "Esta pessoa não é da equipe deste consultório.")
    if m["role"] != "receptionist":
        raise HTTPException(400, "Só o acesso da atendente sai por aqui.")
    ctx.pconn.execute("DELETE FROM memberships WHERE user_id = ? AND practice_id = ?", (user_id, ctx.practice_id))
    who = one(ctx.pconn, "SELECT name FROM users WHERE id = ?", (user_id,))
    invites.log(ctx.pconn, "equipe_removida", user_id=ctx.user["id"], practice_id=ctx.practice_id,
                detail=who["name"] if who else None, ip=ctx.ip)
    return {"ok": True}


# ---- a pediatra e a recepção: o acesso da família ------------------------------------------------------------------

@router.post("/staff/guardians/{guardian_id}/invite")
def guardian_invite(guardian_id: int, request: Request, practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    """O link para o responsável criar a senha do app. Um link por vez: o novo cancela o anterior."""
    practice, conn = _practice(ctx, practice_id)
    g = one(conn, "SELECT * FROM guardians WHERE id = ?", (guardian_id,))
    if not g:
        raise HTTPException(404, "Responsável não encontrado.")
    with transaction(ctx.pconn):
        ctx.pconn.execute("""UPDATE invites SET revoked_at = ? WHERE kind = 'family' AND practice_id = ? AND guardian_id = ?
                             AND used_at IS NULL AND revoked_at IS NULL""", (now_iso(), practice["id"], g["id"]))
        token, iid = invites.create(ctx.pconn, kind="family", practice_id=practice["id"], guardian_id=g["id"],
                                    label=g["name"], created_by=ctx.user["id"])
    insert(conn, "audit_log", {"at": now_iso(), "user_id": ctx.user["id"], "role": practice["role"],
                               "action": "convite_familia", "entity": "guardian", "entity_id": g["id"], "ip": ctx.ip})
    # o link abre no domínio do consultório da família (a atendente pode estar no site de outro pediatra da clínica)
    link = request_link(request, token) if practice["id"] == ctx.practice_id else invites.link(
        ctx.pconn, practice, token, ctx.settings.base_domains, ctx.settings.port)
    row = one(ctx.pconn, "SELECT * FROM invites WHERE id = ?", (iid,))
    first = g["name"].split()[0]
    text = (f"Olá, {first}! Este é o seu acesso ao app de {practice['name']}: lá você acompanha a saúde e a agenda, "
            f"marca consultas e manda exames. Crie a sua senha por este link (vale 7 dias): {link}")
    return {"link": link, "text": text, "phone": g["phone"], "invite": invites.view(row)}

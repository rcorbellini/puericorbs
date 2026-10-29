"""Os convites na API: abrir e aceitar (quem foi convidado) e gerar (a administração do consultório, a pediatra e a
recepção). Os tipos e onde cada um abre estão em `invites.py`; o que a plataforma gera está em `api_admin.py`.

Regra de ouro: uma conta que já existe só se liga a um consultório, a uma família ou à administração com a senha
dela. O convite cria a senha de quem ainda não tem conta; nunca escolhe a senha de uma conta alheia.
"""

from __future__ import annotations

import json
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from . import auth, clinics, invites, practices, tenancy
from .api_public import login_user, password_ok, practice_public
from .api_staff import _practice
from .context import ROLE_LABEL, Ctx, dep, manager, staff
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
    if not row or not invites.opens_here(ctx.pconn, row, ctx.site):
        raise HTTPException(404, "Este convite não vale mais: ele já foi usado, foi cancelado ou venceu. "
                                 "Peça um novo a quem mandou.")
    return row


def _prefill(ctx: Ctx, row: dict) -> dict:
    """O que quem convidou a família nova já sabia (no banco da prática): o responsável e a criança."""
    found = one(ctx.open_practice(row["practice_id"]), "SELECT data FROM invite_prefill WHERE invite_id = ?", (row["id"],))
    data = json.loads(found["data"]) if found else {}
    return {"guardian": data.get("guardian") or {}, "child": data.get("child") or {}}


def _guardian(ctx: Ctx, row: dict) -> dict:
    """O responsável no banco do consultório do convite (o id só vale dentro dele)."""
    g = one(ctx.open_practice(row["practice_id"]), "SELECT * FROM guardians WHERE id = ?", (row["guardian_id"],))
    if not g:
        raise HTTPException(404, "Este responsável não está mais no cadastro. Peça um novo convite ao consultório.")
    return g


def _keeps_password(ctx: Ctx, user: dict, practice_id: int | None) -> bool:
    """A conta que o convite da família não pode trocar a senha: a da equipe, a da administração e a de quem também é
    responsável em outro consultório (lá, quem cuida da conta é a própria pessoa)."""
    if user["is_platform_admin"] or one(ctx.pconn, "SELECT 1 AS ok FROM memberships WHERE user_id = ?", (user["id"],)) \
            or one(ctx.pconn, "SELECT 1 AS ok FROM clinic_members WHERE user_id = ?", (user["id"],)):
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
    if row["kind"] == "family" or (row["kind"] == "staff" and row["practice_id"]):
        p = one(ctx.pconn, "SELECT * FROM practices WHERE id = ?", (row["practice_id"],))
        out["practice"] = practice_public(p)
    if row["kind"] == "staff":
        clinic = one(ctx.pconn, "SELECT name FROM clinics WHERE id = ?", (invites.clinic_of(ctx.pconn, row),))
        others = clinics.practices(ctx.pconn, invites.clinic_of(ctx.pconn, row))
        out.update(role=row["role"], role_label=invites.ROLE_LABEL[row["role"]], clinic=clinic["name"] if clinic else None,
                   doctors=[p["name"] for p in others], label=row["label"])
    elif row["kind"] == "family" and not row["guardian_id"]:
        out["prefill"] = _prefill(ctx, row)
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
    clinic_name: str | None = None
    registry: str | None = None
    domain: str | None = None
    # a família nova (o convite pré-preenchido): o responsável e a criança
    relation: str | None = None
    phone: str | None = None
    child_name: str | None = None
    child_sex: str | None = None
    child_birth: str | None = None
    child_weeks: int | None = None


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
    """A equipe do consultório. A pediatra entra com a prática dela (os pacientes só dela), no consultório de quem
    convidou; a atendente e a administração entram no consultório inteiro. O convite de pediatra com `practice_id` é
    o da plataforma para um consultório criado vazio: ela vira a pediatra dele."""
    name, email = _name(body.name), _email(body.email)
    _new_password(body.password)
    clinic_id = invites.clinic_of(ctx.pconn, row)
    uid = _account_for(ctx, email, name, body.password)
    _spend(ctx, row, uid)
    practice_id = row["practice_id"]
    if row["role"] == "clinician" and practice_id:
        ctx.pconn.execute("INSERT OR IGNORE INTO memberships (user_id, practice_id, role) VALUES (?, ?, 'clinician')",
                          (uid, practice_id))
        changes = {}
        if (body.practice_name or "").strip():
            changes["name"] = body.practice_name.strip()[:80]
        if body.registry is not None:
            changes["registry"] = body.registry.strip()[:80] or None
        update(ctx.pconn, "practices", practice_id, changes)
        if not one(ctx.pconn, "SELECT 1 AS ok FROM clinic_members WHERE clinic_id = ? AND role = 'manager'", (clinic_id,)):
            clinics.add(ctx.pconn, clinic_id, uid, "manager")  # a primeira pediatra cuida do consultório
    elif row["role"] == "clinician":
        if clinics.own_practice(ctx.pconn, clinic_id, uid):
            raise HTTPException(409, "Esta conta já é pediatra neste consultório. Entre com ela.")
        site_name = (body.practice_name or "").strip()[:80] or name
        practice_id = practices.create_practice(
            ctx.pconn, ctx.settings.data_dir, name=site_name, slug=practices.free_slug(ctx.pconn, site_name),
            registry=(body.registry or "").strip()[:80] or None, clinic_id=clinic_id)
        ctx.pconn.execute("INSERT INTO memberships (user_id, practice_id, role) VALUES (?, ?, 'clinician')",
                          (uid, practice_id))
        ctx.pconn.execute("UPDATE invites SET new_practice_id = ? WHERE id = ?", (practice_id, row["id"]))
    else:
        clinics.add(ctx.pconn, clinic_id, uid, row["role"])
    invites.log(ctx.pconn, "convite_aceito", user_id=uid, practice_id=practice_id,
                detail=f"equipe ({invites.ROLE_LABEL[row['role']].lower()}): {name}", ip=ctx.ip)
    return {"login": uid}


RELATIONS = ("mãe", "pai", "avó", "avô", "responsável")


def _child(name: str | None, sex: str | None, birth: str | None, weeks: int | None, today: date) -> dict:
    """A criança como a família (ou a recepção) escreveu, conferida."""
    name = " ".join((name or "").split())[:80]
    if not name:
        raise HTTPException(400, "Escreva o nome da criança.")
    if sex not in ("F", "M"):
        raise HTTPException(400, "Escolha menina ou menino: as curvas de crescimento da OMS são separadas.")
    try:
        born = date.fromisoformat(birth or "")
    except ValueError as exc:
        raise HTTPException(400, "Confira a data de nascimento da criança.") from exc
    if born > today or (today - born).days > 18 * 366:
        raise HTTPException(400, "Confira a data de nascimento da criança.")
    if weeks is not None and not 22 <= weeks <= 42:
        raise HTTPException(400, "As semanas de gestação vão de 22 a 42 (deixe em branco se nasceu no tempo certo).")
    return {"name": name, "sex": sex, "birth_date": born.isoformat(), "gestational_weeks": weeks}


def _accept_new_family(ctx: Ctx, row: dict, body: InviteAccept) -> dict:
    """A família nova: o responsável confere o que a recepção escreveu, completa o resto e cria a senha. A ficha nasce
    agora, no banco da prática. Quem já é responsável nesta prática (outro filho) ganha a criança na mesma família."""
    name, email = _name(body.name), _email(body.email)
    _new_password(body.password)
    relation = body.relation if body.relation in RELATIONS else "responsável"
    phone = (body.phone or "").strip()[:40]
    if len(re.sub(r"\D", "", phone)) < 10:
        raise HTTPException(400, "Escreva o celular com o DDD: é por ele que o consultório fala com você.")
    child = _child(body.child_name, body.child_sex, body.child_birth, body.child_weeks, ctx.today)
    uid = _account_for(ctx, email, name, body.password)
    _spend(ctx, row, uid)
    conn = ctx.open_practice(row["practice_id"])
    with transaction(conn):
        mine = one(conn, "SELECT * FROM guardians WHERE user_id = ? ORDER BY id LIMIT 1", (uid,))
        if mine:
            fid, gid = mine["family_id"], mine["id"]
        else:
            surname = child["name"].split()[-1] if len(child["name"].split()) > 1 else name.split()[-1]
            fid = insert(conn, "families", {"name": f"Família {surname}", "created_at": now_iso()})
            gid = insert(conn, "guardians", {"family_id": fid, "user_id": uid, "name": name, "relation": relation,
                                             "phone": phone, "email": email, "is_legal": 1, "is_financial": 1,
                                             "created_at": now_iso()})
        pid = insert(conn, "patients", {"family_id": fid, **child, "created_at": now_iso()})
        conn.execute("DELETE FROM invite_prefill WHERE invite_id = ?", (row["id"],))
        insert(conn, "audit_log", {"at": now_iso(), "user_id": uid, "role": "guardian", "action": "familia_cadastrou",
                                   "entity": "patient", "entity_id": pid, "ip": ctx.ip})
    invites.log(ctx.pconn, "convite_aceito", user_id=uid, practice_id=row["practice_id"], detail="família nova", ip=ctx.ip)
    return {"login": uid}


def _accept_family(ctx: Ctx, row: dict, body: InviteAccept) -> dict:
    if not row["guardian_id"]:
        return _accept_new_family(ctx, row, body)
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
    """A pediatra que cria o próprio consultório: ele nasce com a prática dela, e ela na administração dele."""
    name, email = _name(body.name), _email(body.email)
    _new_password(body.password)
    site_name = (body.practice_name or "").strip()[:80] or name
    requested = clean_host(body.domain)
    uid = _account_for(ctx, email, name, body.password)
    _spend(ctx, row, uid)  # antes de criar o consultório: dois cliques ao mesmo tempo não criam dois
    slug = practices.free_slug(ctx.pconn, site_name)
    pid = practices.create_practice(ctx.pconn, ctx.settings.data_dir, name=site_name, slug=slug,
                                    registry=(body.registry or "").strip()[:80] or None, requested_domain=requested,
                                    clinic_name=(body.clinic_name or "").strip()[:80] or site_name)
    clinic_id = one(ctx.pconn, "SELECT clinic_id FROM practices WHERE id = ?", (pid,))["clinic_id"]
    ctx.pconn.execute("INSERT INTO memberships (user_id, practice_id, role) VALUES (?, ?, 'clinician')", (uid, pid))
    clinics.add(ctx.pconn, clinic_id, uid, "manager")
    ctx.pconn.execute("UPDATE invites SET new_practice_id = ? WHERE id = ?", (pid, row["id"]))
    invites.log(ctx.pconn, "consultorio_criado", user_id=uid, practice_id=pid,
                detail=f"{site_name}, pelo convite da plataforma; domínio pedido: {requested or 'nenhum'}", ip=ctx.ip)
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


# ---- a equipe do consultório: a administração convida e tira; quem é da equipe vê --------------------------------------

@router.get("/staff/team")
def team(ctx: Ctx = Depends(dep)):
    staff(ctx)
    clinic = one(ctx.pconn, "SELECT * FROM clinics WHERE id = ?", (ctx.clinic_id,))
    rows = many(ctx.pconn, """SELECT i.*, p.name AS new_practice FROM invites i
                              LEFT JOIN practices p ON p.id = i.new_practice_id
                              WHERE i.kind = 'staff' AND i.clinic_id = ? ORDER BY i.created_at DESC LIMIT 30""",
                (ctx.clinic_id,))
    members = clinics.team(ctx.pconn, ctx.clinic_id)
    for m in members:
        m["role_label"] = ROLE_LABEL["manager"] if m["role"] == "manager" else ROLE_LABEL[m["role"]]
        m["me"] = m["id"] == ctx.user["id"]
    return {"clinic": {"id": clinic["id"], "name": clinic["name"]}, "members": members, "can_manage": ctx.manages,
            "invites": [{**invites.view(r), "new_practice": r["new_practice"]} for r in rows] if ctx.manages else []}


class StaffInvite(BaseModel):
    role: str
    label: str | None = None


def invite_text(role: str, label: str | None, clinic: str, link: str) -> str:
    """A mensagem pronta para mandar com o link (WhatsApp, e-mail, o que for)."""
    hi = f"Olá, {label.split()[0]}!" if label else "Olá!"
    what = {"clinician": "atender pelo Puericorbs, com a sua agenda e os seus pacientes, só seus",
            "receptionist": "cuidar da agenda, do cadastro e do dinheiro pelo Puericorbs",
            "manager": "cuidar da equipe e da recepção pelo Puericorbs"}[role]
    return f"{hi} {clinic} convidou você para {what}. Crie a sua senha por este link (vale 7 dias): {link}"


@router.post("/staff/invites")
def staff_invite(body: StaffInvite, request: Request, ctx: Ctx = Depends(dep)):
    """Uma pediatra (que entra com os pacientes dela), uma atendente (de todas as pediatras) ou mais alguém da
    administração, para este consultório."""
    manager(ctx)
    if body.role not in invites.ROLES:
        raise HTTPException(400, "Escolha quem você convida: pediatra, atendente ou administração.")
    clinic = one(ctx.pconn, "SELECT * FROM clinics WHERE id = ?", (ctx.clinic_id,))
    with transaction(ctx.pconn):
        token, iid = invites.create(ctx.pconn, kind="staff", clinic_id=ctx.clinic_id, role=body.role,
                                    label=body.label, created_by=ctx.user["id"])
        invites.log(ctx.pconn, "convite_gerado", user_id=ctx.user["id"], practice_id=ctx.practice_id,
                    detail=invites.ROLE_LABEL[body.role].lower() + (f": {body.label}" if body.label else ""), ip=ctx.ip)
    link = request_link(request, token)
    return {"link": link, "qr": invites.qr_svg(link), "text": invite_text(body.role, body.label, clinic["name"], link),
            "invite": invites.view(one(ctx.pconn, "SELECT * FROM invites WHERE id = ?", (iid,)))}


@router.post("/staff/invites/{invite_id}/revoke")
def staff_revoke(invite_id: int, ctx: Ctx = Depends(dep)):
    row = one(ctx.pconn, "SELECT * FROM invites WHERE id = ?", (invite_id,))
    if row and row["kind"] == "family":
        _practice(ctx, row["practice_id"])  # a família: a pediatra dela ou a recepção do consultório
    else:
        manager(ctx)
        if row and row["clinic_id"] != ctx.clinic_id:
            row = None
    if not row:
        raise HTTPException(404, "Convite não encontrado.")
    invites.revoke(ctx.pconn, invite_id)
    if row["kind"] == "family" and not row["guardian_id"]:  # o que a recepção escreveu da família nova vai junto
        ctx.open_practice(row["practice_id"]).execute("DELETE FROM invite_prefill WHERE invite_id = ?", (invite_id,))
    invites.log(ctx.pconn, "convite_cancelado", user_id=ctx.user["id"], practice_id=ctx.practice_id,
                detail=invites.LABEL[row["kind"]], ip=ctx.ip)
    return {"ok": True}


@router.delete("/staff/team/{user_id}")
def remove_member(user_id: int, ctx: Ctx = Depends(dep)):
    """Tirar o acesso de quem saiu da equipe (atendente ou administração). A pediatra não sai por aqui: os pacientes
    são dela, e a saída dela do consultório passa pela plataforma."""
    manager(ctx)
    m = clinics.member(ctx.pconn, ctx.clinic_id, user_id)
    if not m:
        if clinics.own_practice(ctx.pconn, ctx.clinic_id, user_id):
            raise HTTPException(400, "A pediatra não sai por aqui: os pacientes são dela. Fale com a plataforma.")
        raise HTTPException(404, "Esta pessoa não é da equipe deste consultório.")
    others = ctx.pconn.execute("SELECT COUNT(*) FROM clinic_members WHERE clinic_id = ? AND role = 'manager' AND user_id != ?",
                               (ctx.clinic_id, user_id)).fetchone()[0]
    if m["role"] == "manager" and not others:
        raise HTTPException(400, "O consultório precisa de alguém na administração. Convide outra pessoa antes.")
    ctx.pconn.execute("DELETE FROM clinic_members WHERE clinic_id = ? AND user_id = ?", (ctx.clinic_id, user_id))
    who = one(ctx.pconn, "SELECT name FROM users WHERE id = ?", (user_id,))
    invites.log(ctx.pconn, "equipe_removida", user_id=ctx.user["id"], practice_id=ctx.practice_id,
                detail=who["name"] if who else None, ip=ctx.ip)
    return {"ok": True}


# ---- a pediatra e a recepção: o acesso da família ------------------------------------------------------------------

class FamilyInvite(BaseModel):
    """O que quem convida já sabe da família nova; tudo opcional: a família completa o resto."""
    practice_id: int | None = None
    name: str | None = None
    relation: str | None = None
    phone: str | None = None
    email: str | None = None
    child_name: str | None = None
    child_sex: str | None = None
    child_birth: str | None = None


def _clean_prefill(body: FamilyInvite, today: date) -> dict:
    g = {"name": " ".join((body.name or "").split())[:80], "relation": body.relation if body.relation in RELATIONS else "",
         "phone": (body.phone or "").strip()[:40], "email": (body.email or "").strip().lower()[:120]}
    if g["email"] and not EMAIL.match(g["email"]):
        raise HTTPException(400, "Confira o e-mail do responsável (ou deixe em branco: a família escreve).")
    c = {"name": " ".join((body.child_name or "").split())[:80], "sex": body.child_sex if body.child_sex in ("F", "M") else "",
         "birth_date": ""}
    if body.child_birth:
        try:
            born = date.fromisoformat(body.child_birth)
        except ValueError as exc:
            raise HTTPException(400, "Confira a data de nascimento (ou deixe em branco: a família escreve).") from exc
        if born > today:
            raise HTTPException(400, "A data de nascimento está no futuro.")
        c["birth_date"] = born.isoformat()
    return {"guardian": {k: v for k, v in g.items() if v}, "child": {k: v for k, v in c.items() if v}}


@router.post("/staff/family-invites")
def family_invite(body: FamilyInvite, request: Request, ctx: Ctx = Depends(dep)):
    """O convite de uma família que ainda não está no cadastro. Quem convida escreve o que já sabe (pode ser nada), e
    a família confere e completa no próprio celular; a ficha nasce no aceite. O que foi escrito fica no banco da
    prática; no da plataforma, só o convite, sem nome."""
    practice, conn = _practice(ctx, body.practice_id)
    data = _clean_prefill(body, ctx.today)
    with transaction(ctx.pconn):
        token, iid = invites.create(ctx.pconn, kind="family", practice_id=practice["id"], created_by=ctx.user["id"])
    insert(conn, "invite_prefill", {"invite_id": iid, "data": json.dumps(data, ensure_ascii=False),
                                    "created_by": ctx.user["id"], "created_at": now_iso()})
    ctx.audit("convite_familia_nova", "invite", iid, conn=conn)
    link = request_link(request, token) if practice["id"] == ctx.practice_id else invites.link(
        ctx.pconn, practice, token, ctx.settings.base_domains, ctx.settings.port)
    first = (data["guardian"].get("name") or "").split()
    hi = f"Olá, {first[0]}!" if first else "Olá!"
    text = (f"{hi} Este é o convite para o app de {practice['name']}: lá você acompanha a saúde e a agenda da criança, "
            f"marca consultas e manda exames. Confira os dados, complete o que faltar e crie a sua senha por este link "
            f"(vale 7 dias): {link}")
    return {"link": link, "qr": invites.qr_svg(link), "text": text, "phone": data["guardian"].get("phone"),
            "invite": invites.view(one(ctx.pconn, "SELECT * FROM invites WHERE id = ?", (iid,)))}


@router.get("/staff/family-invites")
def family_invites(practice_id: int | None = None, ctx: Ctx = Depends(dep)):
    """Os convites de família nova ainda à espera, desta pediatra: para lembrar quem não respondeu, ou cancelar."""
    practice, conn = _practice(ctx, practice_id)
    out = []
    for r in many(conn, "SELECT * FROM invite_prefill ORDER BY created_at DESC"):
        inv = one(ctx.pconn, "SELECT * FROM invites WHERE id = ? AND kind = 'family' AND practice_id = ?",
                  (r["invite_id"], practice["id"]))
        if inv and invites.status(inv) == "pendente":
            data = json.loads(r["data"])
            out.append({"id": inv["id"], "expires_at": inv["expires_at"], "created_at": inv["created_at"],
                        "guardian": data.get("guardian") or {}, "child": data.get("child") or {}})
    return {"invites": out}

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
                                    created_by=ctx.user["id"])
    insert(conn, "audit_log", {"at": now_iso(), "user_id": ctx.user["id"], "role": practice["role"],
                               "action": "convite_familia", "entity": "guardian", "entity_id": g["id"], "ip": ctx.ip})
    # o link abre no domínio do consultório da família (a atendente pode estar no site de outro pediatra da clínica)
    link = request_link(request, token) if practice["id"] == ctx.practice_id else invites.link(
        ctx.pconn, practice, token, ctx.settings.base_domains, ctx.settings.port)
    row = one(ctx.pconn, "SELECT * FROM invites WHERE id = ?", (iid,))
    first = g["name"].split()[0]
    text = (f"Olá, {first}! Este é o seu acesso ao app de {practice['name']}: lá você acompanha a saúde e a agenda, "
            f"marca consultas e manda exames. Crie a sua senha por este link (vale 7 dias): {link}")
    return {"link": link, "qr": invites.qr_svg(link), "text": text, "phone": g["phone"], "invite": invites.view(row)}

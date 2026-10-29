"""O painel da administração da plataforma: acompanhar os consultórios, gerar os convites que só a plataforma gera e
entrar em qualquer consultório vendo como alguém dele.

O painel mostra números (famílias, crianças, consultas), a equipe de cada consultório, os convites e o registro da
plataforma. A ficha, a agenda e o app da família, a administração vê do jeito de quem usa: entrando como a pediatra, a
atendente ou uma família ("vendo como"), com a faixa no topo da página, e cada pedido dela vai para o registro do
consultório (`context.py`). Ela entra por qualquer site nosso (ainda não há domínio da plataforma) e o painel fica em
#/admin.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from . import auth, clinics, invites, practices, tenancy
from .api_invites import clean_host, request_link
from .api_public import practice_public, set_cookie
from .context import ROLE_LABEL, Ctx, dep, need_user
from .db import connect_practice, insert, many, now_iso, one, transaction

router = APIRouter(prefix="/api/admin")


def admin(ctx: Ctx) -> None:
    need_user(ctx)
    # vendo como alguém, quem pede é a administração por trás dele
    if not (ctx.actor or ctx.user)["is_platform_admin"] or ctx.site.kind == "unknown":
        raise HTTPException(403, "Só a administração da plataforma vê esta página.")


def _origin(ctx: Ctx, request: Request, practice: dict) -> str | None:
    """Onde a prática abre, visto daqui: este mesmo endereço (""), se ela é deste consultório; na máquina (demonstração
    e testes), o subdomínio local na mesma porta; senão, o domínio dela ou o de outra pediatra do mesmo consultório.
    Sem nenhum, não há onde entrar (None)."""
    if practice["id"] == ctx.practice_id or (ctx.clinic_id and practice["clinic_id"] == ctx.clinic_id):
        return ""
    raw = request.headers.get("host", "")
    host = tenancy.normalize_host(raw)
    for base in ctx.settings.base_domains:
        if host == base or host.endswith("." + base):
            port = raw[len(host):] if raw.lower().startswith(host) else ""
            return f"{request.url.scheme}://{practice['slug']}.{base}{port}"
    row = one(ctx.pconn, "SELECT host FROM domains WHERE practice_id = ? ORDER BY created_at, host", (practice["id"],))
    hosts = [row["host"]] if row else clinics.domains(ctx.pconn, practice["clinic_id"])
    return f"https://{hosts[0]}" if hosts else None


def _metrics(ctx: Ctx, practice_id: int) -> dict:
    """Só contagens: o painel nunca carrega um nome de paciente."""
    conn = connect_practice(ctx.settings.data_dir, practice_id)
    try:
        since = (ctx.today - timedelta(days=30)).isoformat()
        start, end = ctx.today.isoformat(), (ctx.today + timedelta(days=8)).isoformat()
        count = lambda sql, args=(): conn.execute(sql, args).fetchone()[0]  # noqa: E731
        return {
            "families": count("SELECT COUNT(*) FROM families"),
            "patients": count("SELECT COUNT(*) FROM patients"),
            "family_accounts": count("SELECT COUNT(DISTINCT user_id) FROM guardians WHERE user_id IS NOT NULL"),
            "visits_30d": count("SELECT COUNT(*) FROM appointments WHERE status = 'atendido' AND start_at >= ?", (since,)),
            "next_7d": count("""SELECT COUNT(*) FROM appointments WHERE status IN ('agendado', 'confirmado')
                                AND start_at >= ? AND start_at < ?""", (start, end)),
        }
    finally:
        conn.close()


@router.get("/overview")
def overview(request: Request, ctx: Ctx = Depends(dep)):
    admin(ctx)
    out = []
    for p in many(ctx.pconn, """SELECT p.*, c.name AS clinic FROM practices p LEFT JOIN clinics c ON c.id = p.clinic_id
                                ORDER BY p.clinic_id, p.created_at, p.id"""):
        last = "(SELECT MAX(s.created_at) FROM sessions s WHERE s.user_id = u.id)"
        # a pediatra da prática e a equipe do consultório dela (a atendente e a administração atendem todas)
        members = many(ctx.pconn, f"""
            SELECT u.id, u.name, u.email, m.role, {last} AS last_login FROM memberships m JOIN users u ON u.id = m.user_id
            WHERE m.practice_id = ? ORDER BY m.role, u.name""", (p["id"],))
        members += many(ctx.pconn, f"""
            SELECT u.id, u.name, u.email, c.role, {last} AS last_login FROM clinic_members c JOIN users u ON u.id = c.user_id
            WHERE c.clinic_id = ? AND u.id NOT IN (SELECT user_id FROM memberships WHERE role = 'clinician')
            ORDER BY c.role DESC, u.name""", (p["clinic_id"],))  # a pediatra que cuida do consultório fica no cartão dela
        pending = ctx.pconn.execute("""SELECT COUNT(*) FROM invites WHERE practice_id = ? AND kind != 'family'
                                       AND used_at IS NULL AND revoked_at IS NULL AND expires_at >= ?""",
                                    (p["id"], now_iso())).fetchone()[0]
        out.append({**practice_public(p), "clinic": p["clinic"], "clinic_id": p["clinic_id"],
                    "created_at": p["created_at"], "requested_domain": p["requested_domain"],
                    "domains": [d["host"] for d in many(ctx.pconn, "SELECT host FROM domains WHERE practice_id = ? ORDER BY created_at, host", (p["id"],))],
                    "members": [{**m, "role_label": ROLE_LABEL[m["role"]]} for m in members],
                    "has_clinician": any(m["role"] == "clinician" for m in members),
                    "last_access": max((m["last_login"] for m in members if m["last_login"]), default=None),
                    "pending_invites": pending, "metrics": _metrics(ctx, p["id"]),
                    "can_enter": _origin(ctx, request, p) is not None})
    rows = many(ctx.pconn, """
        SELECT i.*, p.name AS practice, np.name AS new_practice, u.name AS created_by_name, uu.name AS used_by_name,
               c.name AS clinic
        FROM invites i LEFT JOIN practices p ON p.id = i.practice_id LEFT JOIN practices np ON np.id = i.new_practice_id
        LEFT JOIN clinics c ON c.id = COALESCE(i.clinic_id, p.clinic_id)
        LEFT JOIN users u ON u.id = i.created_by LEFT JOIN users uu ON uu.id = i.used_by
        WHERE i.kind != 'family'  -- o convite da família leva o nome do responsável: fica com o consultório
        ORDER BY (i.used_at IS NULL AND i.revoked_at IS NULL AND i.expires_at >= ?) DESC, i.created_at DESC LIMIT 40""",
                (now_iso(),))
    log = many(ctx.pconn, """SELECT l.at, l.action, l.detail, u.name AS user, p.name AS practice FROM platform_log l
                             LEFT JOIN users u ON u.id = l.user_id LEFT JOIN practices p ON p.id = l.practice_id
                             ORDER BY l.id DESC LIMIT 40""")
    totals = {k: sum(p["metrics"][k] for p in out) for k in ("families", "patients", "visits_30d", "next_7d")}
    totals.update(practices=len(out), clinicians=sum(1 for p in out if p["has_clinician"]))
    return {
        "practices": out, "totals": totals, "log": log,
        "invites": [{**invites.view(r), "practice": r["practice"], "new_practice": r["new_practice"], "clinic": r["clinic"],
                     "created_by": r["created_by_name"], "used_by": r["used_by_name"]} for r in rows],
        "admins": many(ctx.pconn, "SELECT name, email FROM users WHERE is_platform_admin = 1 ORDER BY name"),
        "tunnel_target": ctx.settings.extra.get("tunnel_target"),
    }


class AdminInvite(BaseModel):
    kind: str
    practice_id: int | None = None
    label: str | None = None


@router.post("/invites")
def admin_invite(body: AdminInvite, request: Request, ctx: Ctx = Depends(dep)):
    """Os convites da plataforma: um pediatra novo com o consultório dele (practice), a pediatra de um consultório
    que ainda não tem ninguém (clinician) e outra pessoa da administração (admin)."""
    admin(ctx)
    warning = None
    with transaction(ctx.pconn):
        if body.kind == "clinician":
            p = one(ctx.pconn, "SELECT * FROM practices WHERE id = ?", (body.practice_id,))
            if not p:
                raise HTTPException(404, "Consultório não encontrado.")
            if one(ctx.pconn, "SELECT 1 AS ok FROM memberships WHERE practice_id = ? AND role = 'clinician'", (p["id"],)):
                # a plataforma não põe ninguém dentro de um consultório que já tem dona: a equipe é ela quem convida
                raise HTTPException(409, "Este consultório já tem pediatra. A equipe dele é a pediatra quem convida.")
            token, iid = invites.create(ctx.pconn, kind="staff", practice_id=p["id"], role="clinician",
                                        label=body.label, created_by=ctx.user["id"])
            link = invites.link(ctx.pconn, p, token, ctx.settings.base_domains, ctx.settings.port)
            if not one(ctx.pconn, "SELECT host FROM domains WHERE practice_id = ?", (p["id"],)):
                warning = "Este consultório ainda não tem domínio: o link só abre depois de ligar um."
            detail = f"pediatra de {p['name']}"
        elif body.kind in ("practice", "admin"):
            token, iid = invites.create(ctx.pconn, kind=body.kind, label=body.label, created_by=ctx.user["id"])
            link = request_link(request, token)
            detail = "pediatra com consultório próprio" if body.kind == "practice" else "administração"
        else:
            raise HTTPException(400, "Escolha o convite: pediatra com consultório próprio, pediatra de um consultório "
                                     "ou administração.")
        if body.label:
            detail += f": {body.label}"
        invites.log(ctx.pconn, "convite_gerado", user_id=ctx.user["id"], practice_id=body.practice_id, detail=detail,
                    ip=ctx.ip)
    return {"link": link, "warning": warning,
            "invite": invites.view(one(ctx.pconn, "SELECT * FROM invites WHERE id = ?", (iid,)))}


@router.post("/invites/{invite_id}/revoke")
def admin_revoke(invite_id: int, ctx: Ctx = Depends(dep)):
    admin(ctx)
    row = one(ctx.pconn, "SELECT * FROM invites WHERE id = ?", (invite_id,))
    if not row:
        raise HTTPException(404, "Convite não encontrado.")
    invites.revoke(ctx.pconn, invite_id)
    invites.log(ctx.pconn, "convite_cancelado", user_id=ctx.user["id"], practice_id=row["practice_id"],
                detail=invites.LABEL[row["kind"]], ip=ctx.ip)
    return {"ok": True}


class NewPractice(BaseModel):
    name: str
    domain: str | None = None


@router.post("/practices")
def new_practice(body: NewPractice, ctx: Ctx = Depends(dep)):
    """Um consultório vazio; a pediatra entra depois, pelo convite."""
    admin(ctx)
    name = body.name.strip()[:80]
    if not name:
        raise HTTPException(400, "Escreva o nome do consultório (como vai aparecer no site).")
    host = clean_host(body.domain)
    slug = practices.free_slug(ctx.pconn, name)
    pid = practices.create_practice(ctx.pconn, ctx.settings.data_dir, name=name, slug=slug, domain=host)
    invites.log(ctx.pconn, "consultorio_criado", user_id=ctx.user["id"], practice_id=pid,
                detail=f"{name}{f', em {host}' if host else ''}", ip=ctx.ip)
    return {"id": pid, "slug": slug}


class NewDomain(BaseModel):
    host: str


@router.post("/practices/{practice_id}/domains")
def add_domain(practice_id: int, body: NewDomain, ctx: Ctx = Depends(dep)):
    """Cadastra o domínio no Puericorbs. O DNS (no Cloudflare) é à parte: o painel mostra o que pôr lá."""
    admin(ctx)
    p = one(ctx.pconn, "SELECT * FROM practices WHERE id = ?", (practice_id,))
    if not p:
        raise HTTPException(404, "Consultório não encontrado.")
    host = clean_host(body.host)
    if not host:
        raise HTTPException(400, "Escreva o domínio, como drnome.com.br.")
    other = one(ctx.pconn, "SELECT practice_id FROM domains WHERE host = ?", (host,))
    if other:
        raise HTTPException(409, f"O domínio {host} já aponta para {'este' if other['practice_id'] == p['id'] else 'outro'} consultório.")
    with transaction(ctx.pconn):
        ctx.pconn.execute("INSERT INTO domains (host, practice_id, created_at) VALUES (?, ?, ?)", (host, p["id"], now_iso()))
        if p["requested_domain"] == host:
            ctx.pconn.execute("UPDATE practices SET requested_domain = NULL WHERE id = ?", (p["id"],))
        invites.log(ctx.pconn, "dominio_ligado", user_id=ctx.user["id"], practice_id=p["id"], detail=host, ip=ctx.ip)
    return {"ok": True, "host": host, "tunnel_target": ctx.settings.extra.get("tunnel_target")}


def _audit(ctx: Ctx, conn, action: str, detail: str | None = None) -> None:
    """O registro de um consultório que a administração consulta pelo painel (de fora dele)."""
    me = ctx.actor or ctx.user
    insert(conn, "audit_log", {"at": now_iso(), "user_id": me["id"], "role": "admin", "action": action,
                               "ip": ctx.ip, "actor_id": me["id"], "detail": detail})


@router.get("/practices/{practice_id}/families")
def families(practice_id: int, q: str = "", ctx: Ctx = Depends(dep)):
    """Os responsáveis de um consultório, para escolher como que família entrar (com conta ou ainda sem)."""
    admin(ctx)
    if not one(ctx.pconn, "SELECT id FROM practices WHERE id = ?", (practice_id,)):
        raise HTTPException(404, "Consultório não encontrado.")
    conn = ctx.open_practice(practice_id)
    like = f"%{q.strip()}%"
    rows = many(conn, """SELECT g.id, g.family_id, g.name, g.relation, g.user_id FROM guardians g
                         WHERE g.name LIKE ? OR EXISTS (SELECT 1 FROM patients p WHERE p.family_id = g.family_id
                                                        AND p.name LIKE ?)
                         ORDER BY g.name, g.id LIMIT 30""", (like, like))
    ids = sorted({r["family_id"] for r in rows})
    kids: dict[int, list[str]] = {}
    if ids:
        for k in many(conn, f"""SELECT family_id, name FROM patients WHERE family_id IN ({",".join("?" * len(ids))})
                                ORDER BY birth_date DESC""", tuple(ids)):
            kids.setdefault(k["family_id"], []).append(k["name"].split()[0])
    _audit(ctx, conn, "administracao_familias", f"busca: {q.strip()}" if q.strip() else None)
    return {"guardians": [{"id": r["id"], "name": r["name"], "relation": r["relation"], "account": bool(r["user_id"]),
                           "children": kids.get(r["family_id"], [])} for r in rows]}


class ViewAs(BaseModel):
    practice_id: int
    user_id: int | None = None
    guardian_id: int | None = None


@router.post("/view-as")
def view_as(body: ViewAs, request: Request, ctx: Ctx = Depends(dep)):
    """Entrar num consultório vendo como alguém dele: a pediatra, a atendente ou uma família. Devolve o link de entrada,
    no endereço do consultório (cada domínio tem a própria sessão); ele vale 2 minutos e uma vez só."""
    admin(ctx)
    p = one(ctx.pconn, "SELECT * FROM practices WHERE id = ?", (body.practice_id,))
    if not p:
        raise HTTPException(404, "Consultório não encontrado.")
    if body.user_id:
        if not one(ctx.pconn, "SELECT 1 AS ok FROM memberships WHERE user_id = ? AND practice_id = ?",
                   (body.user_id, p["id"])) and not clinics.member(ctx.pconn, p["clinic_id"], body.user_id):
            raise HTTPException(404, "Esta pessoa não é da equipe deste consultório.")
    elif not one(ctx.open_practice(p["id"]), "SELECT id FROM guardians WHERE id = ?", (body.guardian_id or 0,)):
        raise HTTPException(404, "Família não encontrada neste consultório.")
    origin = _origin(ctx, request, p)
    if origin is None:
        raise HTTPException(409, "Este consultório ainda não tem domínio: ligue um para entrar nele.")
    token = secrets.token_urlsafe(32)
    insert(ctx.pconn, "handoffs", {
        "token_hash": auth.token_hash(token), "admin_id": (ctx.actor or ctx.user)["id"], "practice_id": p["id"],
        "as_user_id": body.user_id, "as_guardian_id": None if body.user_id else body.guardian_id,
        "created_at": now_iso(), "expires_at": (datetime.now() + timedelta(minutes=2)).replace(microsecond=0).isoformat()})
    return {"url": f"{origin}/api/admin/entrar/{token}"}


@router.get("/entrar/{token}")
def enter(token: str, request: Request, ctx: Ctx = Depends(dep)):
    """O link de entrada, já no endereço do consultório: liga o "vendo como" na sessão da administração daqui (ou abre
    uma, se ainda não houver) e leva à página de quem ela está vendo. Vencido, gasto ou de outro consultório, volta
    ao painel com o aviso."""
    row = one(ctx.pconn, "SELECT * FROM handoffs WHERE token_hash = ?", (auth.token_hash(token),))
    boss = one(ctx.pconn, "SELECT * FROM users WHERE id = ? AND is_platform_admin = 1", (row["admin_id"],)) if row else None
    # gastar é um UPDATE só: de dois cliques ao mesmo tempo, um entra e o outro volta ao painel
    target = one(ctx.pconn, "SELECT * FROM practices WHERE id = ?", (row["practice_id"],)) if row else None
    # vale no domínio da prática ou no de outra pediatra do mesmo consultório (a prática sem domínio próprio)
    if (not boss or row["expires_at"] < now_iso() or not target or target["clinic_id"] != ctx.clinic_id
            or ctx.pconn.execute("UPDATE handoffs SET used_at = ? WHERE token_hash = ? AND used_at IS NULL",
                                 (now_iso(), row["token_hash"])).rowcount != 1):
        return RedirectResponse("/#/admin/entrada-vencida", status_code=303)
    conn = ctx.open_practice(target["id"])
    response = RedirectResponse("/", status_code=303)
    session = request.cookies.get(auth.COOKIE)
    if not session or (ctx.actor or ctx.user or {}).get("id") != boss["id"]:
        session = auth.new_session(ctx.pconn, boss["id"], request.headers.get("user-agent"), ctx.settings.session_days)
        set_cookie(response, request, auth.COOKIE, session, ctx.settings.session_days)
    auth.set_acting(ctx.pconn, session, row["practice_id"], row["as_user_id"], row["as_guardian_id"])
    if row["as_user_id"]:
        who = one(ctx.pconn, """SELECT u.name, m.role FROM memberships m JOIN users u ON u.id = m.user_id
                                WHERE m.user_id = ? AND m.practice_id = ?""", (row["as_user_id"], row["practice_id"])) \
            or one(ctx.pconn, """SELECT u.name, c.role FROM clinic_members c JOIN users u ON u.id = c.user_id
                                 WHERE c.user_id = ? AND c.clinic_id = ?""", (row["as_user_id"], target["clinic_id"]))
        role, label = (who["role"], f"{ROLE_LABEL[who['role']]}: {who['name']}") if who else (None, "alguém da equipe")
        audit_label, target_user = label, row["as_user_id"]
    else:
        g = one(conn, "SELECT name, relation, user_id FROM guardians WHERE id = ?", (row["as_guardian_id"],))
        role, label = "guardian", "uma família"  # o nome da família não sai do banco do consultório
        audit_label = f"Família: {g['name']} ({g['relation']})" if g else label
        target_user = g["user_id"] if g else None
    insert(conn, "audit_log", {
        "at": now_iso(), "user_id": target_user, "role": role, "action": "administracao_entrou",
        "entity": "user" if row["as_user_id"] else "guardian", "entity_id": row["as_user_id"] or row["as_guardian_id"],
        "ip": ctx.ip, "actor_id": boss["id"], "detail": f"vendo como {audit_label}"})
    invites.log(ctx.pconn, "vendo_como", user_id=boss["id"], practice_id=row["practice_id"], detail=label, ip=ctx.ip)
    return response


@router.post("/view-as/stop")
def stop_view_as(request: Request, ctx: Ctx = Depends(dep)):
    """Voltar ao painel: a sessão deixa de ver como alguém e volta a ser só da administração."""
    admin(ctx)
    if ctx.actor:
        auth.set_acting(ctx.pconn, request.cookies.get(auth.COOKIE))
        ctx.audit("administracao_saiu")
    return {"ok": True}

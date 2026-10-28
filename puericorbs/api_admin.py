"""O painel da administração da plataforma: acompanhar os consultórios e gerar os convites que só a plataforma gera.

A administração vê números (famílias, crianças, consultas), a equipe de cada consultório, os convites e o registro da
plataforma; nunca um nome de criança, uma ficha ou um arquivo. Ela entra por qualquer site nosso (ainda não há
domínio da plataforma) e o painel fica em #/admin.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import invites, practices
from .api_invites import clean_host, request_link
from .api_public import practice_public
from .context import ROLE_LABEL, Ctx, dep, need_user
from .db import connect_practice, many, now_iso, one, transaction

router = APIRouter(prefix="/api/admin")


def admin(ctx: Ctx) -> None:
    need_user(ctx)
    if not ctx.user["is_platform_admin"] or ctx.site.kind == "unknown":
        raise HTTPException(403, "Só a administração da plataforma vê esta página.")


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
def overview(ctx: Ctx = Depends(dep)):
    admin(ctx)
    out = []
    for p in many(ctx.pconn, "SELECT * FROM practices ORDER BY created_at, id"):
        members = many(ctx.pconn, """
            SELECT u.id, u.name, u.email, m.role, (SELECT MAX(s.created_at) FROM sessions s WHERE s.user_id = u.id) AS last_login
            FROM memberships m JOIN users u ON u.id = m.user_id WHERE m.practice_id = ? ORDER BY m.role, u.name""", (p["id"],))
        pending = ctx.pconn.execute("""SELECT COUNT(*) FROM invites WHERE practice_id = ? AND kind != 'family'
                                       AND used_at IS NULL AND revoked_at IS NULL AND expires_at >= ?""",
                                    (p["id"], now_iso())).fetchone()[0]
        out.append({**practice_public(p), "created_at": p["created_at"], "requested_domain": p["requested_domain"],
                    "domains": [d["host"] for d in many(ctx.pconn, "SELECT host FROM domains WHERE practice_id = ? ORDER BY created_at, host", (p["id"],))],
                    "members": [{**m, "role_label": ROLE_LABEL[m["role"]]} for m in members],
                    "has_clinician": any(m["role"] == "clinician" for m in members),
                    "last_access": max((m["last_login"] for m in members if m["last_login"]), default=None),
                    "pending_invites": pending, "metrics": _metrics(ctx, p["id"])})
    rows = many(ctx.pconn, """
        SELECT i.*, p.name AS practice, np.name AS new_practice, u.name AS created_by_name, uu.name AS used_by_name
        FROM invites i LEFT JOIN practices p ON p.id = i.practice_id LEFT JOIN practices np ON np.id = i.new_practice_id
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
        "invites": [{**invites.view(r), "practice": r["practice"], "new_practice": r["new_practice"],
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

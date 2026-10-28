"""O contexto de cada pedido: o site (qual prática), quem está entrando e com que papel nela.

O papel vem da prática, não do usuário: a mesma conta pode ser a pediatra num domínio e não ter nada em outro. A
atendente é membro de cada prática que atende; o responsável é um `guardian` com a conta dele na prática.

A administração pode entrar num consultório vendo como alguém dele (`api_admin.py`): `user` e `role` passam a ser os
dessa pessoa, para a tela e as regras serem as dela, e `actor` guarda quem está de fato, que vai para o `audit_log`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime

from fastapi import HTTPException, Request

from . import auth, tenancy
from .config import Settings
from .db import connect_platform, connect_practice, insert, many, now_iso, one

ROLE_LABEL = {"clinician": "Pediatra", "receptionist": "Atendente", "guardian": "Família", "admin": "Plataforma"}


@dataclass
class Ctx:
    settings: Settings
    site: tenancy.Site
    pconn: sqlite3.Connection
    conn: sqlite3.Connection | None = None
    user: dict | None = None
    role: str | None = None
    guardians: list[dict] = field(default_factory=list)
    actor: dict | None = None  # a administração, quando está vendo como `user`
    ip: str = ""
    now: datetime = field(default_factory=datetime.now)
    _extra: dict = field(default_factory=dict)

    @property
    def today(self) -> date:
        return self.now.date()

    @property
    def practice(self) -> dict | None:
        return self.site.practice

    @property
    def practice_id(self) -> int | None:
        return self.site.practice["id"] if self.site.practice else None

    @property
    def family_ids(self) -> set[int]:
        return {g["family_id"] for g in self.guardians}

    def open_practice(self, practice_id: int) -> sqlite3.Connection:
        """Outra prática (a atendente que atende dois pediatras). Fecha junto com o pedido."""
        if practice_id == self.practice_id and self.conn:
            return self.conn
        key = f"p{practice_id}"
        if key not in self._extra:
            self._extra[key] = connect_practice(self.settings.data_dir, practice_id)
        return self._extra[key]

    def close(self) -> None:
        for conn in [self.conn, self.pconn, *self._extra.values()]:
            if conn:
                conn.close()

    def audit(self, action: str, entity: str | None = None, entity_id: int | None = None,
              detail: str | None = None) -> None:
        if self.conn:
            insert(self.conn, "audit_log", {"at": now_iso(), "user_id": self.user["id"] if self.user else None,
                                            "role": self.role, "action": action, "entity": entity,
                                            "entity_id": entity_id, "ip": self.ip,
                                            "actor_id": self.actor["id"] if self.actor else None, "detail": detail})


def _act_as(ctx: Ctx, acting: dict) -> None:
    """A administração vendo como alguém deste consultório. Se a pessoa saiu da equipe (ou o responsável foi apagado),
    não vale mais, e a sessão volta a ser só da administração."""
    if acting["as_user_id"]:
        target = one(ctx.pconn, """SELECT u.*, m.role AS member_role FROM memberships m JOIN users u ON u.id = m.user_id
                                   WHERE m.user_id = ? AND m.practice_id = ?""", (acting["as_user_id"], ctx.practice_id))
        if target:
            target.pop("password_hash", None)
            ctx.actor, ctx.role, ctx.user = ctx.user, target.pop("member_role"), target
        return
    g = one(ctx.conn, "SELECT * FROM guardians WHERE id = ?", (acting["as_guardian_id"] or 0,))
    if not g:
        return
    account = one(ctx.pconn, "SELECT * FROM users WHERE id = ?", (g["user_id"],)) if g["user_id"] else None
    ctx.actor, ctx.role = ctx.user, "guardian"
    if account:
        account.pop("password_hash", None)
        ctx.user = account
        ctx.guardians = many(ctx.conn, "SELECT * FROM guardians WHERE user_id = ?", (account["id"],))
    else:
        # ainda sem conta: a tela é a que a família vai ver; o que for feito aqui fica no nome de quem age
        ctx.user = {**ctx.actor, "name": g["name"], "email": g["email"] or "", "is_platform_admin": 0}
        ctx.guardians = [g]


def build(request: Request, settings: Settings) -> Ctx:
    pconn = connect_platform(settings.data_dir)
    site = tenancy.resolve(settings, pconn, request.headers.get("host"), request.cookies.get(tenancy.SITE_COOKIE))
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    ctx = Ctx(settings=settings, site=site, pconn=pconn, ip=ip, now=datetime.now(settings.tz).replace(tzinfo=None))
    ctx.user = auth.session_user(pconn, request.cookies.get(auth.COOKIE))
    acting = ctx.user.pop("acting") if ctx.user else None
    if site.practice:
        ctx.conn = connect_practice(settings.data_dir, site.practice["id"])
        if acting and acting["as_practice_id"] == site.practice["id"] and ctx.user["is_platform_admin"]:
            _act_as(ctx, acting)
        if ctx.user and not ctx.actor:
            member = one(pconn, "SELECT role FROM memberships WHERE user_id = ? AND practice_id = ?",
                         (ctx.user["id"], site.practice["id"]))
            if member:
                ctx.role = member["role"]
            else:
                ctx.guardians = many(ctx.conn, "SELECT * FROM guardians WHERE user_id = ?", (ctx.user["id"],))
                if ctx.guardians:
                    ctx.role = "guardian"
    elif ctx.user and ctx.user["is_platform_admin"]:
        ctx.role = "admin"
    return ctx


def dep(request: Request):
    """A dependência do FastAPI: abre o contexto e fecha os bancos no fim do pedido. Com a administração vendo como
    alguém, cada pedido vai para o registro do consultório (menos os dois que a página faz ao abrir)."""
    ctx = build(request, request.app.state.settings)
    try:
        if ctx.actor and request.url.path not in ("/api/site", "/api/me"):
            ctx.audit("administracao", detail=f"{request.method} {request.url.path}")
        yield ctx
    finally:
        ctx.close()


def need_user(ctx: Ctx) -> None:
    if not ctx.user:
        raise HTTPException(401, "Entre na sua conta para continuar.")


def need_role(ctx: Ctx, *roles: str) -> None:
    need_user(ctx)
    if ctx.site.kind != "practice":
        raise HTTPException(404, "Este endereço não é de um consultório.")
    if ctx.role not in roles:
        if ctx.role is None:
            raise HTTPException(403, "Sua conta não tem acesso a este consultório.")
        raise HTTPException(403, "Isso não está disponível para o seu perfil.")


def staff(ctx: Ctx) -> None:
    need_role(ctx, "clinician", "receptionist")


def clinician(ctx: Ctx) -> None:
    need_role(ctx, "clinician")


def family(ctx: Ctx) -> None:
    need_role(ctx, "guardian")


def family_patient(ctx: Ctx, patient_id: int) -> dict:
    """A criança, se for da família de quem pede; senão, 404 (nunca diz que existe)."""
    family(ctx)
    row = one(ctx.conn, "SELECT * FROM patients WHERE id = ?", (patient_id,))
    if not row or row["family_id"] not in ctx.family_ids:
        raise HTTPException(404, "Criança não encontrada.")
    return row


def staff_practices(ctx: Ctx) -> list[dict]:
    """As práticas em que quem pede trabalha, na mesma clínica da prática deste site (a recepção compartilhada)."""
    staff(ctx)
    rows = many(ctx.pconn, """
        SELECT p.*, m.role FROM memberships m JOIN practices p ON p.id = m.practice_id
        WHERE m.user_id = ? ORDER BY p.name""", (ctx.user["id"],))
    clinic = ctx.practice["clinic_id"]
    mine = [r for r in rows if r["id"] == ctx.practice_id or (clinic and r["clinic_id"] == clinic)]
    return sorted(mine, key=lambda r: (r["id"] != ctx.practice_id, r["name"]))  # o consultório deste site primeiro

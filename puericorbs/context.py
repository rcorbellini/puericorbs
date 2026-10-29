"""O contexto de cada pedido: o site (qual prática), quem está entrando e com que papel nela.

O papel vem da prática, não do usuário: a mesma conta pode ser a pediatra num domínio e não ter nada em outro. A
pediatra é membro da prática dela; a atendente e a administração do consultório são da equipe do consultório inteiro
(`clinics.py`) e atendem todas as pediatras dele; o responsável é um `guardian` com a conta dele na prática.

O domínio abre a prática dele, mas quem é do mesmo consultório entra por qualquer domínio do consultório e é levado à
prática que é sua (a pediatra sem domínio próprio, a família dela): `site.practice` passa a ser essa, e o banco aberto
é o dela. Nunca para uma prática de outro consultório, nunca para uma em que a pessoa não tem papel.

A administração da plataforma pode entrar num consultório vendo como alguém dele (`api_admin.py`): `user` e `role`
passam a ser os dessa pessoa, para a tela e as regras serem as dela, e `actor` guarda quem está de fato, que vai para o
`audit_log`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, replace
from datetime import date, datetime

from fastapi import HTTPException, Request

from . import auth, clinics, tenancy
from .config import Settings
from .db import connect_platform, connect_practice, insert, many, now_iso, one

ROLE_LABEL = {"clinician": "Pediatra", "receptionist": "Atendente", "manager": "Administração do consultório",
              "guardian": "Família", "admin": "Plataforma"}


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
    manages: bool = False      # é da administração do consultório (a pediatra que o criou, ou quem foi convidado)
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
    def clinic_id(self) -> int | None:
        return self.site.practice["clinic_id"] if self.site.practice else None

    def switch(self, practice: dict) -> None:
        """Passa o pedido para outra prática do mesmo consultório (a de quem entrou por um domínio que não é o dela)."""
        if practice["clinic_id"] != self.clinic_id:
            raise ValueError("só dentro do mesmo consultório")
        if self.conn:
            self.conn.close()
        self.site = replace(self.site, practice=practice)
        self.conn = connect_practice(self.settings.data_dir, practice["id"])

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
              detail: str | None = None, conn: sqlite3.Connection | None = None) -> None:
        """No registro desta prática ou, com `conn`, no de outra do consultório (a recepção atende todas)."""
        conn = conn or self.conn
        if conn:
            insert(conn, "audit_log", {"at": now_iso(), "user_id": self.user["id"] if self.user else None,
                                       "role": self.role, "action": action, "entity": entity,
                                       "entity_id": entity_id, "ip": self.ip,
                                       "actor_id": self.actor["id"] if self.actor else None, "detail": detail})


def _act_as(ctx: Ctx, acting: dict) -> None:
    """A administração vendo como alguém deste consultório. Se a pessoa saiu da equipe (ou o responsável foi apagado),
    não vale mais, e a sessão volta a ser só da administração."""
    if acting["as_user_id"]:
        target = one(ctx.pconn, """SELECT u.*, m.role AS member_role FROM memberships m JOIN users u ON u.id = m.user_id
                                   WHERE m.user_id = ? AND m.practice_id = ?""", (acting["as_user_id"], ctx.practice_id))
        team = clinics.member(ctx.pconn, ctx.clinic_id, acting["as_user_id"])
        if not target and team:  # a atendente ou a administração do consultório
            target = one(ctx.pconn, "SELECT * FROM users WHERE id = ?", (acting["as_user_id"],))
            target["member_role"] = "receptionist"
        if target:
            target.pop("password_hash", None)
            ctx.actor, ctx.role, ctx.user = ctx.user, target.pop("member_role"), target
            ctx.manages = bool(team and team["role"] == "manager")
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


def _role(ctx: Ctx) -> None:
    """O papel de quem entrou, e a prática em que ele fica. Pela ordem: a pediatra desta prática; a pediatra de outra
    prática do consultório (vai para a dela); a equipe do consultório (fica nesta); o responsável de uma família desta
    prática; o de outra prática do consultório (vai para a dela)."""
    uid = ctx.user["id"]
    team = clinics.member(ctx.pconn, ctx.clinic_id, uid)
    ctx.manages = bool(team and team["role"] == "manager")
    member = one(ctx.pconn, "SELECT role FROM memberships WHERE user_id = ? AND practice_id = ?", (uid, ctx.practice_id))
    if member:
        ctx.role = member["role"]
        return
    own = clinics.own_practice(ctx.pconn, ctx.clinic_id, uid)
    if own:
        ctx.switch(own)
        ctx.role = "clinician"
        return
    if team:
        ctx.role = "receptionist"
        return
    ctx.guardians = many(ctx.conn, "SELECT * FROM guardians WHERE user_id = ?", (uid,))
    if not ctx.guardians:
        other = clinics.guardian_practice(ctx.pconn, ctx.settings.data_dir, ctx.clinic_id, uid, skip=ctx.practice_id)
        if other:
            ctx.switch(other)
            ctx.guardians = many(ctx.conn, "SELECT * FROM guardians WHERE user_id = ?", (uid,))
    if ctx.guardians:
        ctx.role = "guardian"


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
        if acting and ctx.user["is_platform_admin"]:
            # a entrada vale neste consultório: na prática deste domínio ou noutra do mesmo consultório (a sem domínio)
            target = one(pconn, "SELECT * FROM practices WHERE id = ?", (acting["as_practice_id"],))
            if target and target["clinic_id"] == ctx.clinic_id:
                if target["id"] != ctx.practice_id:
                    ctx.switch(target)
                _act_as(ctx, acting)
        if ctx.user and not ctx.actor:
            _role(ctx)
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
    """As práticas em que quem pede trabalha, no consultório deste site. A pediatra: só a dela, mesmo quando cuida do
    consultório (cada pediatra vê só os seus pacientes). A atendente e a administração que não é pediatra: todas as
    pediatras do consultório, sem nada clínico (`receptionist`)."""
    staff(ctx)
    rows = many(ctx.pconn, """
        SELECT p.*, m.role FROM memberships m JOIN practices p ON p.id = m.practice_id
        WHERE m.user_id = ? AND (p.id = ? OR p.clinic_id = ?)""", (ctx.user["id"], ctx.practice_id, ctx.clinic_id))
    mine = {r["id"]: r for r in rows}
    doctor = any(r["role"] == "clinician" for r in rows)
    if not doctor and clinics.member(ctx.pconn, ctx.clinic_id, ctx.user["id"]):
        for p in clinics.practices(ctx.pconn, ctx.clinic_id):
            mine.setdefault(p["id"], {**p, "role": "receptionist"})
    return sorted(mine.values(), key=lambda r: (r["id"] != ctx.practice_id, r["name"]))  # a deste site primeiro


def manager(ctx: Ctx) -> None:
    """A equipe e os convites do consultório: só a administração dele."""
    staff(ctx)
    if not ctx.manages:
        raise HTTPException(403, "Só a administração do consultório cuida da equipe e dos convites.")

"""O site (qual consultório este endereço abre), a entrada e a plataforma."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import auth, files, practices, tenancy, views
from .context import ROLE_LABEL, Ctx, dep, need_user, staff_practices
from .db import many, one

router = APIRouter(prefix="/api")


def practice_public(p: dict) -> dict:
    return {k: p.get(k) for k in ("id", "slug", "name", "title", "registry", "bio", "address", "phone", "accent")}


def me_payload(ctx: Ctx) -> dict | None:
    if not ctx.user:
        return None
    out = {"id": ctx.user["id"], "name": ctx.user["name"], "email": ctx.user["email"], "role": ctx.role,
           "role_label": ROLE_LABEL.get(ctx.role or "", ""), "is_platform_admin": bool(ctx.user["is_platform_admin"])}
    if ctx.role in ("clinician", "receptionist"):
        out["practices"] = [{"id": p["id"], "name": p["name"], "slug": p["slug"], "role": p["role"]}
                            for p in staff_practices(ctx)]
    if ctx.role == "guardian":
        out["guardian"] = {"name": ctx.guardians[0]["name"], "relation": ctx.guardians[0]["relation"]}
    return out


def _cookie(response: Response, request: Request, name: str, value: str | None, days: int) -> None:
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    if value is None:
        response.delete_cookie(name, path="/")
    else:
        response.set_cookie(name, value, max_age=days * 86400, httponly=True, samesite="lax", secure=secure, path="/")


def _demo_accounts(ctx: Ctx) -> list[dict]:
    """Quem dá para "ser" na demonstração: a equipe e os responsáveis com conta nesta prática."""
    if not ctx.settings.demo or not ctx.site.practice:
        return []
    out = []
    for m in many(ctx.pconn, """SELECT u.id, u.name, u.email, m.role FROM memberships m JOIN users u ON u.id = m.user_id
                                WHERE m.practice_id = ? ORDER BY m.role, u.name""", (ctx.practice_id,)):
        out.append({"email": m["email"], "name": m["name"], "role": m["role"], "label": ROLE_LABEL[m["role"]]})
    seen = set()
    for g in many(ctx.conn, """SELECT g.user_id, g.name, g.relation, f.name AS family FROM guardians g
                               JOIN families f ON f.id = g.family_id WHERE g.user_id IS NOT NULL ORDER BY g.id"""):
        if g["user_id"] in seen:
            continue
        seen.add(g["user_id"])
        user = one(ctx.pconn, "SELECT email FROM users WHERE id = ?", (g["user_id"],))
        if user:
            kids = many(ctx.conn, """SELECT p.name FROM patients p JOIN guardians gg ON gg.family_id = p.family_id
                                     WHERE gg.user_id = ? ORDER BY p.birth_date DESC""", (g["user_id"],))
            names = [k["name"].split()[0] for k in kids]
            label = f"{g['relation'].capitalize()} de {' e '.join(names)}" if names else "Família"
            out.append({"email": user["email"], "name": g["name"], "role": "guardian", "label": label})
    return out[:12]


@router.get("/site")
def site(ctx: Ctx = Depends(dep)):
    out = {"kind": ctx.site.kind, "host": ctx.site.host, "simulated": ctx.site.simulated,
           "demo": ctx.settings.demo, "today": ctx.today.isoformat(), "now": ctx.now.strftime("%H:%M")}
    if ctx.site.practice:
        p = ctx.site.practice
        out["practice"] = practice_public(p)
        out["domains"] = [d["host"] for d in many(ctx.pconn, "SELECT host FROM domains WHERE practice_id = ?", (p["id"],))]
        clinic = one(ctx.pconn, "SELECT name FROM clinics WHERE id = ?", (p["clinic_id"],)) if p["clinic_id"] else None
        out["clinic"] = clinic["name"] if clinic else None
        out["services"] = [views.service_public(ctx.conn, s, None, ctx.today) for s in many(
            ctx.conn, "SELECT * FROM services WHERE active = 1 ORDER BY position, id")]
        out["demo_accounts"] = _demo_accounts(ctx)
    out["me"] = me_payload(ctx)
    return out


class Login(BaseModel):
    email: str
    password: str = ""


def _can_enter(ctx: Ctx, user_id: int) -> bool:
    if ctx.site.kind == "practice":
        if one(ctx.pconn, "SELECT 1 AS ok FROM memberships WHERE user_id = ? AND practice_id = ?", (user_id, ctx.practice_id)):
            return True
        return bool(one(ctx.conn, "SELECT id FROM guardians WHERE user_id = ?", (user_id,)))
    user = one(ctx.pconn, "SELECT is_platform_admin FROM users WHERE id = ?", (user_id,))
    return bool(user and user["is_platform_admin"])


def _login(ctx: Ctx, request: Request, response: Response, user: dict) -> dict:
    if not _can_enter(ctx, user["id"]):
        if ctx.site.kind == "practice":
            raise HTTPException(403, "Esta conta não tem acesso a este consultório.")
        raise HTTPException(403, "Entre pelo endereço do seu consultório.")
    token = auth.new_session(ctx.pconn, user["id"], request.headers.get("user-agent"), ctx.settings.session_days)
    _cookie(response, request, auth.COOKIE, token, ctx.settings.session_days)
    return {"ok": True}


@router.post("/auth/login")
def login(body: Login, request: Request, response: Response, ctx: Ctx = Depends(dep)):
    user = one(ctx.pconn, "SELECT * FROM users WHERE email = ?", (body.email.strip().lower(),))
    if not user or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "E-mail ou senha não conferem.")
    return _login(ctx, request, response, user)


@router.post("/auth/demo")
def demo_login(body: Login, request: Request, response: Response, ctx: Ctx = Depends(dep)):
    if not ctx.settings.demo:
        raise HTTPException(404, "Não encontrado.")
    user = one(ctx.pconn, "SELECT * FROM users WHERE email = ?", (body.email.strip().lower(),))
    if not user:
        raise HTTPException(404, "Conta de demonstração não encontrada.")
    return _login(ctx, request, response, user)


@router.post("/auth/logout")
def logout(request: Request, response: Response, ctx: Ctx = Depends(dep)):
    auth.end_session(ctx.pconn, request.cookies.get(auth.COOKIE))
    _cookie(response, request, auth.COOKIE, None, 0)
    return {"ok": True}


@router.get("/me")
def me(ctx: Ctx = Depends(dep)):
    return {"me": me_payload(ctx)}


class SitePick(BaseModel):
    slug: str | None = None


@router.post("/demo/site")
def pick_site(body: SitePick, request: Request, response: Response, ctx: Ctx = Depends(dep)):
    """Na demonstração, "visitar" o site de um pediatra a partir do endereço da plataforma (o ngrok dá um só)."""
    if not ctx.settings.demo:
        raise HTTPException(404, "Não encontrado.")
    if body.slug and not one(ctx.pconn, "SELECT id FROM practices WHERE slug = ?", (body.slug,)):
        raise HTTPException(404, "Consultório não encontrado.")
    # trocar de site é trocar de consultório: a sessão de um não vale no outro
    auth.end_session(ctx.pconn, request.cookies.get(auth.COOKIE))
    _cookie(response, request, auth.COOKIE, None, 0)
    _cookie(response, request, tenancy.SITE_COOKIE, body.slug, 30)
    return {"ok": True}


@router.get("/platform")
def platform(ctx: Ctx = Depends(dep)):
    if ctx.site.kind == "practice" and not ctx.site.simulated:
        raise HTTPException(404, "Este endereço é de um consultório.")
    if not ctx.settings.demo and ctx.role != "admin":
        need_user(ctx)
        raise HTTPException(403, "Só a administração da plataforma vê esta página.")
    rows = many(ctx.pconn, """SELECT p.*, c.name AS clinic FROM practices p LEFT JOIN clinics c ON c.id = p.clinic_id
                              ORDER BY p.id""")
    out = []
    for p in rows:
        out.append({**practice_public(p), "clinic": p["clinic"],
                    "domains": [d["host"] for d in many(ctx.pconn, "SELECT host FROM domains WHERE practice_id = ?", (p["id"],))],
                    "subdomain": f"{p['slug']}.{ctx.settings.base_domains[0]}" if ctx.settings.base_domains else None})
    return {"practices": out, "demo": ctx.settings.demo, "me": me_payload(ctx)}


class NewPractice(BaseModel):
    name: str
    slug: str
    domain: str | None = None
    accent: str = "agua"
    registry: str | None = None
    clinician_name: str
    clinician_email: str
    password: str


@router.post("/platform/practices")
def new_practice(body: NewPractice, ctx: Ctx = Depends(dep)):
    need_user(ctx)
    if not ctx.user["is_platform_admin"]:
        raise HTTPException(403, "Só a administração da plataforma cria consultórios.")
    if len(body.password) < 8:
        raise HTTPException(400, "A senha precisa de pelo menos 8 caracteres.")
    pid = practices.create_practice(ctx.pconn, ctx.settings.data_dir, name=body.name, slug=body.slug,
                                    domain=body.domain, accent=body.accent, registry=body.registry,
                                    clinician_name=body.clinician_name, clinician_email=body.clinician_email,
                                    password=body.password)
    return {"id": pid}


@router.post("/platform/reset")
def reset_demo(request: Request, response: Response, ctx: Ctx = Depends(dep)):
    """Volta a demonstração ao começo (apaga o que foi feito nela)."""
    if not ctx.settings.demo:
        raise HTTPException(404, "Não encontrado.")
    from . import seed
    ctx.close()
    seed.run(ctx.settings, reset=True)
    _cookie(response, request, auth.COOKIE, None, 0)
    return {"ok": True}


@router.get("/files/{file_id}")
def file_content(file_id: int, download: int = 0, ctx: Ctx = Depends(dep)):
    need_user(ctx)
    if ctx.site.kind != "practice" or ctx.role not in ("clinician", "receptionist", "guardian"):
        raise HTTPException(404, "Arquivo não encontrado.")
    row = one(ctx.conn, "SELECT * FROM files WHERE id = ?", (file_id,))
    if not row or not files.can_see(row, ctx.role, ctx.family_ids):
        raise HTTPException(404, "Arquivo não encontrado.")
    if ctx.role != "guardian":
        ctx.audit("abrir_arquivo", "file", file_id)
    path = files.path_of(ctx.settings.data_dir, ctx.practice_id, row["stored_name"])
    if not path.exists():
        raise HTTPException(404, "O arquivo sumiu do disco. Avise o suporte.")
    name = row["original_name"] or (row["title"] + path.suffix)
    return FileResponse(path, media_type=row["mime"], filename=name,
                        content_disposition_type="attachment" if download else "inline",
                        headers={"Cache-Control": "private, max-age=600"})

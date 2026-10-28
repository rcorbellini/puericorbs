"""A aplicação: a API, a página (um PWA sem build) e as regras que valem para todo pedido."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from . import api_admin, api_family, api_invites, api_public, api_staff, config, tenancy
from .config import Settings

WEB = Path(__file__).parent / "web"
FOREVER = "public, max-age=31536000, immutable"


def asset_version() -> str:
    """A versão dos arquivos da página: muda quando qualquer um deles muda (nome, tamanho ou data)."""
    h = hashlib.sha256()
    for f in sorted(p for p in WEB.rglob("*") if p.is_file()):
        st = f.stat()
        h.update(f"{f.relative_to(WEB)}:{st.st_size}:{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:10]


class Assets(StaticFiles):
    """Os arquivos da página, pedidos por /static/v/<versão>/… (o index.html já sai com a versão de agora).

    O Cloudflare manda o navegador guardar .js e .css por 4 horas: num endereço fixo, quem abriu o site antes de uma
    atualização ficava com o JavaScript velho, e a página nova travava em "Carregando…". Com a versão no caminho, cada
    mudança é um endereço novo, e o import relativo (./lib.js) traz o resto dos módulos da mesma versão. O endereço da
    versão de agora fica guardado para sempre; o sem versão (ou de uma versão vencida) é conferido a cada uso.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        parts = path.split(os.sep, 2)
        versioned = len(parts) == 3 and parts[0] == "v"
        response = await super().get_response(parts[2] if versioned else path, scope)
        if response.status_code in (200, 304):
            response.headers["Cache-Control"] = FOREVER if versioned and parts[1] == asset_version() else "no-cache"
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or config.load()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="Puericorbs", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings

    @app.middleware("http")
    async def guard(request: Request, call_next):
        bare = tenancy.bare_domain(settings, tenancy.normalize_host(request.headers.get("host")))
        if bare:
            return RedirectResponse(str(request.url.replace(netloc=bare)), status_code=301)
        # pedido que muda alguma coisa precisa vir da própria página (o cabeçalho X-PC): a proteção contra CSRF
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/") \
                and request.headers.get("x-pc") != "1":
            return JSONResponse({"detail": "Pedido recusado: ele não veio do aplicativo."}, status_code=403)
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=()")
        if request.url.path.startswith("/api/") and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", [])[1:])
        return JSONResponse({"detail": f"Confira o campo {where or 'enviado'}: ele está faltando ou com formato errado."},
                            status_code=422)

    app.include_router(api_public.router)
    app.include_router(api_invites.router)
    app.include_router(api_staff.router)
    app.include_router(api_family.router)
    app.include_router(api_admin.router)
    app.mount("/static", Assets(directory=WEB), name="static")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/healthz", include_in_schema=False)
    def health():
        return {"ok": True}

    @app.get("/{path:path}", include_in_schema=False)
    def page(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Não encontrado."}, status_code=404)
        body = (WEB / "index.html").read_text(encoding="utf-8").replace('"/static/', f'"/static/v/{asset_version()}/')
        return HTMLResponse(body, headers={"Cache-Control": "no-cache"})

    return app


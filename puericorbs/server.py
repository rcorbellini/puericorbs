"""A aplicação: a API, a página (um PWA sem build) e as regras que valem para todo pedido."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from . import api_admin, api_family, api_invites, api_public, api_staff, config, tenancy
from .config import Settings

WEB = Path(__file__).parent / "web"


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
    app.mount("/static", StaticFiles(directory=WEB), name="static")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/healthz", include_in_schema=False)
    def health():
        return {"ok": True}

    @app.get("/{path:path}", include_in_schema=False)
    def page(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Não encontrado."}, status_code=404)
        return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})

    return app


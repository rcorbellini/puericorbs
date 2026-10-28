"""A linha de comando: `puericorbs serve`, `puericorbs seed` e o cadastro de domínio."""

from __future__ import annotations

import argparse

from . import config


def main() -> None:
    parser = argparse.ArgumentParser(prog="puericorbs", description="O consultório pediátrico pequeno.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="sobe a página e a API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int)
    seed = sub.add_parser("seed", help="cria os dados de demonstração (Clínica Girassol, Dra. Marina, Dr. Paulo)")
    seed.add_argument("--reset", action="store_true", help="apaga os dados e começa de novo")
    dom = sub.add_parser("domain", help="aponta um domínio para uma prática")
    dom.add_argument("host")
    dom.add_argument("slug")
    args = parser.parse_args()
    settings = config.load()

    if args.cmd == "serve":
        import uvicorn
        uvicorn.run("puericorbs.server:create_app", factory=True, host=args.host, port=args.port or settings.port,
                    proxy_headers=True, forwarded_allow_ips="*", log_level="info")
    elif args.cmd == "seed":
        from . import seed as seeding
        seeding.run(settings, reset=args.reset)
        print("Demonstração pronta.")
    elif args.cmd == "domain":
        from .db import connect_platform, now_iso, one
        from .tenancy import normalize_host
        pconn = connect_platform(settings.data_dir)
        practice = one(pconn, "SELECT id, name FROM practices WHERE slug = ?", (args.slug,))
        if not practice:
            raise SystemExit(f"Não existe prática com o endereço curto “{args.slug}”.")
        host = normalize_host(args.host)
        pconn.execute("INSERT OR REPLACE INTO domains (host, practice_id, created_at) VALUES (?, ?, ?)",
                      (host, practice["id"], now_iso()))
        print(f"{host} agora abre o consultório de {practice['name']}.")


if __name__ == "__main__":
    main()

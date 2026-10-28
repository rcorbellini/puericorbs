"""A linha de comando: subir o servidor, a demonstração, os consultórios, os domínios e os convites.

`--data PASTA` (ou `PUERICORBS_DATA`) escolhe a pasta de dados: sem nada, é a `data/` da demonstração; a produção mora
em outra pasta, com `demo = false` no `config.toml` dela (veja `docs/dominios.md`).
"""

from __future__ import annotations

import argparse

from . import config


def main() -> None:
    parser = argparse.ArgumentParser(prog="puericorbs", description="O consultório pediátrico pequeno.")
    parser.add_argument("--data", help="a pasta de dados (padrão: data/, a demonstração)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="sobe a página e a API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int)
    seed = sub.add_parser("seed", help="cria os dados de demonstração (Clínica Girassol, Dra. Marina, Dr. Paulo)")
    seed.add_argument("--reset", action="store_true", help="apaga os dados e começa de novo")
    prac = sub.add_parser("practice", help="cria um consultório sem ninguém dentro (a pediatra entra pelo convite)")
    prac.add_argument("slug", help="o endereço curto, como dramarina")
    prac.add_argument("--name", required=True, help="como o consultório aparece no site (ela pode mudar depois)")
    prac.add_argument("--domain", help="o domínio próprio, como dramarina.com.br")
    prac.add_argument("--title", help="o que vem acima do nome no site (padrão: Pediatra)")
    prac.add_argument("--accent", default="agua", help="agua, azul, coral ou lavanda")
    dom = sub.add_parser("domain", help="aponta um domínio para um consultório")
    dom.add_argument("host")
    dom.add_argument("slug")
    inv = sub.add_parser("invite", help="gera o link de primeiro acesso de quem vai trabalhar num consultório")
    inv.add_argument("slug")
    inv.add_argument("--role", choices=("clinician", "receptionist"), default="clinician",
                     help="clinician (a pediatra) ou receptionist (a atendente)")
    inv.add_argument("--days", type=int, default=7, help="por quantos dias o link vale")
    args = parser.parse_args()
    settings = config.load(args.data)

    if args.cmd == "serve":
        import os

        import uvicorn
        os.environ["PUERICORBS_DATA"] = str(settings.data_dir)  # o create_app lê de novo a configuração
        uvicorn.run("puericorbs.server:create_app", factory=True, host=args.host, port=args.port or settings.port,
                    proxy_headers=True, forwarded_allow_ips="*", log_level="info")
        return

    from .db import connect_platform, now_iso, one
    from .tenancy import normalize_host
    if args.cmd == "seed":
        from . import seed as seeding
        try:
            seeding.run(settings, reset=args.reset)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        print("Demonstração pronta.")
        return

    pconn = connect_platform(settings.data_dir)
    if args.cmd == "practice":
        from fastapi import HTTPException

        from .practices import create_practice
        try:
            create_practice(pconn, settings.data_dir, name=args.name, slug=args.slug, domain=args.domain,
                            title=args.title, accent=args.accent)
        except HTTPException as exc:
            raise SystemExit(exc.detail) from exc
        print(f"Consultório “{args.name}” criado em {settings.data_dir}. Agora o convite: puericorbs invite {args.slug}")
        return

    practice = one(pconn, "SELECT * FROM practices WHERE slug = ?", (args.slug,))
    if not practice:
        raise SystemExit(f"Não existe consultório com o endereço curto “{args.slug}” em {settings.data_dir}.")
    if args.cmd == "domain":
        host = normalize_host(args.host)
        pconn.execute("INSERT OR REPLACE INTO domains (host, practice_id, created_at) VALUES (?, ?, ?)",
                      (host, practice["id"], now_iso()))
        print(f"{host} agora abre o consultório de {practice['name']}.")
    elif args.cmd == "invite":
        from . import invites
        token = invites.create(pconn, practice["id"], args.role, args.days)
        who = "a pediatra" if args.role == "clinician" else "a atendente"
        print(f"Convite para {who} de {practice['name']} (vale {args.days} dias e uma vez só):")
        print(invites.link(pconn, practice, token, settings.base_domains, settings.port))


if __name__ == "__main__":
    main()

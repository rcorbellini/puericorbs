"""Qual consultório este endereço abre.

Cada pediatra tem o próprio domínio (dramarina.com.br), e todos apontam para este mesmo servidor: o endereço do
pedido (o cabeçalho Host) diz qual prática responde. A ordem:

1. o domínio cadastrado na tabela `domains` (o domínio próprio do pediatra);
2. o subdomínio `<slug>.<base>` de uma das `base_domains` (dramarina.localhost, ou um subdomínio da plataforma para quem
   ainda não tem domínio);
3. o resto é a plataforma. Na demonstração, a plataforma deixa "visitar" o site de um pediatra por um cookie, porque o
   ngrok dá um endereço só; fora dela, endereço desconhecido responde "domínio não configurado".
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from .config import Settings
from .db import connect_platform, one

SITE_COOKIE = "pc_site"
SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,40}[a-z0-9])?$")


@dataclass
class Site:
    kind: str                      # practice | platform | unknown
    host: str
    practice: dict | None = None
    simulated: bool = False


def normalize_host(raw: str | None) -> str:
    host = (raw or "").strip().lower().rstrip(".")
    if host.startswith("["):  # IPv6 com porta
        return host.split("]")[0] + "]"
    return host.split(":")[0]


def _by_slug(pconn: sqlite3.Connection, slug: str) -> dict | None:
    if not SLUG.match(slug):
        return None
    return one(pconn, "SELECT * FROM practices WHERE slug = ?", (slug,))


def resolve(settings: Settings, pconn: sqlite3.Connection, raw_host: str | None, site_cookie: str | None) -> Site:
    host = normalize_host(raw_host)
    row = one(pconn, "SELECT p.* FROM domains d JOIN practices p ON p.id = d.practice_id WHERE d.host = ?", (host,))
    if row:
        return Site("practice", host, row)
    for base in settings.base_domains:
        if host.endswith("." + base):
            row = _by_slug(pconn, host[: -len(base) - 1])
            if row:
                return Site("practice", host, row)
    if host in settings.platform_hosts or settings.demo:
        if settings.demo and site_cookie:
            row = _by_slug(pconn, site_cookie)
            if row:
                return Site("practice", host, row, simulated=True)
        return Site("platform", host)
    return Site("unknown", host)


def bare_domain(settings: Settings, host: str) -> str | None:
    """O `www.` de um domínio cadastrado vai para o domínio sem ele: a sessão é por endereço, e o site é um só."""
    if not host.startswith("www."):
        return None
    pconn = connect_platform(settings.data_dir)
    try:
        return host[4:] if one(pconn, "SELECT host FROM domains WHERE host = ?", (host[4:],)) else None
    finally:
        pconn.close()

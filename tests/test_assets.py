"""Os arquivos da página saem com a versão no endereço: depois de uma atualização, nenhum cache (o do navegador, o do
Cloudflare) devolve o JavaScript velho. Foi o que travou o convite da administração em "Carregando…" (28/10)."""

from __future__ import annotations

import re
import shutil
from urllib.parse import urljoin

from conftest import client

from puericorbs import server

HOST = "dramarina.localhost"


def version_of(page: str) -> str:
    return re.search(r'src="/static/v/([0-9a-f]+)/js/main\.js"', page).group(1)


def test_a_pagina_pede_tudo_pela_versao_de_agora(settings):
    r = client(settings, HOST).get("/")
    assert r.headers["cache-control"] == "no-cache"
    ver = version_of(r.text)
    assert ver == server.asset_version()
    refs = re.findall(r'(?:src|href)="(/static/[^"]+)"', r.text)
    assert refs and all(u.startswith(f"/static/v/{ver}/") for u in refs), refs


def test_cada_modulo_e_fonte_vem_da_mesma_versao(settings):
    """O import relativo e o url() relativo do CSS herdam a versão de quem os pede; um caminho absoluto
    (/static/js/lib.js) escaparia dela e traria de volta o arquivo velho."""
    c = client(settings, HOST)
    page = c.get("/").text
    ver = version_of(page)
    todo, seen = re.findall(r'(?:src|href)="(/static/[^"]+)"', page), set()
    while todo:
        url = todo.pop()
        if url in seen:
            continue
        seen.add(url)
        assert url.startswith(f"/static/v/{ver}/"), url
        r = c.get(url)
        assert r.status_code == 200, url
        assert r.headers["cache-control"] == server.FOREVER, url
        if url.endswith(".js"):
            todo += [urljoin(url, m) for m in re.findall(r"""(?:from|import)\s*\(?\s*['"]([^'"]+\.js)['"]""", r.text)]
        elif url.endswith(".css"):
            todo += [urljoin(url, m) for m in re.findall(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", r.text)
                     if not m.startswith("data:")]
    assert {f"/static/v/{ver}/{p}" for p in ("js/lib.js", "js/site.js", "js/admin.js", "fonts/figtree-latin.woff2")} <= seen


def test_uma_mudanca_troca_o_endereco_e_o_velho_deixa_de_ser_guardado(settings, tmp_path, monkeypatch):
    web = tmp_path / "web"
    shutil.copytree(server.WEB, web)
    monkeypatch.setattr(server, "WEB", web)
    c = client(settings, HOST)
    old = version_of(c.get("/").text)
    (web / "js" / "site.js").write_text("export const novo = 1;\n", encoding="utf-8")
    new = version_of(c.get("/").text)
    assert new != old
    assert c.get(f"/static/v/{new}/js/site.js").headers["cache-control"] == server.FOREVER
    stale = c.get(f"/static/v/{old}/js/site.js")
    # quem ainda pede pela versão velha recebe o arquivo de agora, sem a promessa de guardá-lo
    assert stale.status_code == 200 and "novo" in stale.text
    assert stale.headers["cache-control"] == "no-cache"
    assert c.get("/static/js/site.js").headers["cache-control"] == "no-cache"

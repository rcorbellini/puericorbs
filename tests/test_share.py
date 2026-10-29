"""O nome do app no celular e a prévia do link: cada consultório com o nome que a pediatra deu a ele. "Puericorbs" é só
o endereço da plataforma. Quem lê o link (o WhatsApp) não roda o JavaScript: tudo precisa sair do servidor."""

from __future__ import annotations

import html
import re
from io import BytesIO

from conftest import H, client
from PIL import Image

from puericorbs import share


def meta(page: str, key: str) -> str | None:
    m = re.search(rf'<meta (?:name|property)="{re.escape(key)}" content="([^"]*)"', page)
    return html.unescape(m.group(1)) if m else None


def head(page: str) -> str:
    return page.split("</head>")[0]


def test_o_site_e_o_app_levam_o_nome_do_consultorio(settings):
    c = client(settings, "dramarina.localhost")
    page = c.get("/").text
    assert "<title>Dra. Marina Alves</title>" in page
    assert meta(page, "og:title") == "Dra. Marina Alves · Pediatra"
    assert meta(page, "og:site_name") == "Dra. Marina Alves"
    assert meta(page, "apple-mobile-web-app-title") == "Marina Alves"
    assert meta(page, "og:description").startswith("Pediatra. Acompanha a criança")
    assert "Puericorbs" not in head(page)
    man = c.get("/manifest.webmanifest")
    assert man.headers["content-type"].startswith("application/manifest+json")
    assert (man.json()["name"], man.json()["short_name"]) == ("Dra. Marina Alves", "Marina Alves")
    # o convite e qualquer tela abrem a mesma página: a prévia do link é a do consultório (o # não chega ao servidor)
    assert meta(c.get("/convite").text, "og:title") == "Dra. Marina Alves · Pediatra"
    # o endereço da plataforma continua Puericorbs
    plat = client(settings, "localhost")
    assert "<title>Puericorbs</title>" in plat.get("/").text
    assert plat.get("/manifest.webmanifest").json()["name"] == "Puericorbs"


def test_a_previa_do_link_tem_a_imagem_do_consultorio(settings):
    c = client(settings, "dramarina.localhost")
    page = c.get("/", headers={"x-forwarded-proto": "https"}).text
    image = meta(page, "og:image")
    assert image.startswith("https://dramarina.localhost/og.png?v=")
    assert meta(page, "og:url") == "https://dramarina.localhost/"
    r = c.get(image.removeprefix("https://dramarina.localhost"))
    assert r.headers["content-type"] == "image/png" and "immutable" in r.headers["cache-control"]
    assert Image.open(BytesIO(r.content)).size == share.CARD
    assert c.get("/og.png?v=velha").headers["cache-control"] == "no-cache"
    other = meta(client(settings, "drpauloreis.localhost").get("/").text, "og:image")
    assert other.split("v=")[1] != image.split("v=")[1]


def test_o_nome_novo_vale_na_hora_e_vai_escapado(fresh):
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    before = meta(marina.get("/").text, "og:image")
    body = {"name": 'Dra. Ana "Bia" <Souza>', "title": "Pediatra", "accent": "coral"}
    assert marina.put("/api/staff/practice", json=body, headers=H).status_code == 200
    page = marina.get("/").text
    assert "<title>Dra. Ana &quot;Bia&quot; &lt;Souza&gt;</title>" in page
    assert "<Souza>" not in page
    assert meta(page, "og:title") == 'Dra. Ana "Bia" <Souza> · Pediatra'
    assert meta(page, "og:image") != before
    assert marina.get("/manifest.webmanifest").json()["name"] == 'Dra. Ana "Bia" <Souza>'


def test_o_nome_curto_cabe_embaixo_do_icone():
    assert share.short_name("Karita Naves") == "Karita Naves"
    assert share.short_name("Dra. Marina Alves") == "Marina Alves"
    assert share.short_name("Dra. Maria Fernanda Albuquerque") == "Dra. Maria"
    assert share.short_name("Pediatria Integrada Sol") == "Pediatria"
    assert all(len(share.short_name(n)) <= share.SHORT for n in (
        "Consultório Pediátrico Infantil", "Dr. Bartolomeu Albuquerque", "Pediatriainfantilintegrada"))

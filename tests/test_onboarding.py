"""A pediatra de verdade: a produção sem nada da demonstração, o convite de primeiro acesso, o `www` e a tela do
consultório. Cada teste tenta uma porta que precisa estar fechada (ou aberta só para quem deve)."""

from __future__ import annotations

import pytest
from conftest import H, client
from fastapi.testclient import TestClient

from puericorbs import config, invites, seed
from puericorbs.db import connect_platform, one
from puericorbs.practices import create_practice
from puericorbs.server import create_app

NOVA = {"name": "Teste Silva", "email": "teste@exemplo.test", "password": "senha-forte-1",
        "practice_name": "Dra. Teste Silva", "registry": "CRM-SP 000001"}


@pytest.fixture()
def prod(tmp_path):
    """Uma produção vazia: demo = false e um consultório sem ninguém dentro, no domínio dele."""
    (tmp_path / "config.toml").write_text("demo = false\n")
    s = config.load(tmp_path)
    pconn = connect_platform(s.data_dir)
    create_practice(pconn, s.data_dir, name="Consultório pediátrico", slug="drateste", domain="drateste.com.br")
    create_practice(pconn, s.data_dir, name="Outro consultório", slug="outro", domain="outro.com.br")
    pconn.close()
    return s


def site(s, host: str = "drateste.com.br") -> TestClient:
    return TestClient(create_app(s), base_url=f"http://{host}")


def convite(s, slug: str = "drateste", role: str = "clinician") -> str:
    pconn = connect_platform(s.data_dir)
    try:
        pid = one(pconn, "SELECT id FROM practices WHERE slug = ?", (slug,))["id"]
        return invites.create(pconn, pid, role)
    finally:
        pconn.close()


def test_a_producao_nao_tem_nada_da_demonstracao(prod):
    c = site(prod)
    info = c.get("/api/site").json()
    assert info["demo"] is False and info["demo_accounts"] == []
    assert c.post("/api/auth/demo", json={"email": "teste@exemplo.test"}, headers=H).status_code == 404
    assert c.post("/api/platform/reset", headers=H).status_code == 404
    assert site(prod, "qualquer.com.br").get("/api/site").json()["kind"] == "unknown"
    with pytest.raises(RuntimeError):
        seed.run(prod, reset=True)
    assert connect_platform(prod.data_dir).execute("SELECT COUNT(*) FROM practices").fetchone()[0] == 2


def test_convite_cria_a_pediatra_e_ela_entra(prod):
    token = convite(prod)
    c = site(prod)
    info = c.get(f"/api/invite/{token}").json()
    assert info["role"] == "clinician" and info["practice"]["name"] == "Consultório pediátrico"
    r = c.post(f"/api/invite/{token}", json=NOVA, headers=H)
    assert r.status_code == 200, r.text
    assert c.get("/api/me").json()["me"]["role"] == "clinician"
    assert c.get("/api/site").json()["practice"]["name"] == "Dra. Teste Silva"
    # o convite gasta: o mesmo link não serve de novo
    assert site(prod).post(f"/api/invite/{token}", json={**NOVA, "email": "outra@exemplo.test"},
                           headers=H).status_code == 404
    # e a senha que ela criou é a que vale
    assert site(prod).post("/api/auth/login", json={"email": NOVA["email"], "password": NOVA["password"]},
                           headers=H).status_code == 200


def test_convite_so_abre_no_proprio_consultorio(prod):
    token = convite(prod)
    assert site(prod, "outro.com.br").get(f"/api/invite/{token}").status_code == 404
    assert site(prod, "outro.com.br").post(f"/api/invite/{token}", json=NOVA, headers=H).status_code == 404
    assert site(prod, "qualquer.com.br").get(f"/api/invite/{token}").status_code == 404
    assert site(prod).get("/api/invite/inventado").status_code == 404


def test_convite_vencido_nao_abre(prod):
    token = convite(prod)
    pconn = connect_platform(prod.data_dir)
    pconn.execute("UPDATE invites SET expires_at = '2000-01-01T00:00:00'")
    pconn.close()
    assert site(prod).get(f"/api/invite/{token}").status_code == 404


def test_conta_que_ja_existe_aceita_com_a_propria_senha(prod):
    assert site(prod).post(f"/api/invite/{convite(prod)}", json=NOVA, headers=H).status_code == 200
    token = convite(prod, "outro", "receptionist")
    errada = {**NOVA, "password": "outra-senha-9"}
    assert site(prod, "outro.com.br").post(f"/api/invite/{token}", json=errada, headers=H).status_code == 409
    c = site(prod, "outro.com.br")
    assert c.post(f"/api/invite/{token}", json=NOVA, headers=H).status_code == 200
    assert c.get("/api/me").json()["me"]["role"] == "receptionist"
    # o convite da atendente não muda o nome do consultório
    assert c.get("/api/site").json()["practice"]["name"] == "Outro consultório"


def test_convite_pede_email_e_senha_de_verdade(prod):
    token = convite(prod)
    c = site(prod)
    assert c.post(f"/api/invite/{token}", json={**NOVA, "email": "sem-arroba"}, headers=H).status_code == 400
    assert c.post(f"/api/invite/{token}", json={**NOVA, "password": "curta"}, headers=H).status_code == 400
    assert c.get(f"/api/invite/{token}").status_code == 200  # o erro não gasta o convite


def test_www_vai_para_o_dominio(prod):
    r = site(prod, "www.drateste.com.br").get("/agenda?x=1", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == "http://drateste.com.br/agenda?x=1"
    # www de um domínio que não é de ninguém não vira nada
    assert site(prod, "www.qualquer.com.br").get("/api/site", follow_redirects=False).json()["kind"] == "unknown"


def test_so_a_pediatra_muda_o_consultorio(fresh):
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    atual = marina.get("/api/staff/practice").json()
    assert atual["domains"] == ["dramarina.com.br"]
    novo = {**atual["practice"], "bio": "Atendo com calma.", "accent": "coral"}
    r = marina.put("/api/staff/practice", json=novo, headers=H)
    assert r.status_code == 200 and r.json()["practice"]["accent"] == "coral"
    assert client(fresh, "dramarina.localhost").get("/api/site").json()["practice"]["bio"] == "Atendo com calma."
    assert marina.put("/api/staff/practice", json={**novo, "name": " "}, headers=H).status_code == 400
    assert marina.put("/api/staff/practice", json={**novo, "accent": "neon"}, headers=H).status_code == 400
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    assert carla.put("/api/staff/practice", json=novo, headers=H).status_code == 403
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    assert ana.get("/api/staff/practice").status_code == 403
    # o Paulo, no domínio dele, muda o dele, nunca o da Marina
    paulo = client(fresh, "drpauloreis.localhost", "paulo@demo.test")
    assert paulo.put("/api/staff/practice", json={**novo, "name": "Dr. Paulo Reis"}, headers=H).status_code == 200
    assert client(fresh, "dramarina.localhost").get("/api/site").json()["practice"]["name"] == "Dra. Marina Alves"

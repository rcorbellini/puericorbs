"""Os convites que a pediatra, a recepção e a administração geram: a família, a atendente, o colega com o consultório
dele e a administração. Cada teste tenta uma porta que precisa estar fechada (ou aberta só para quem deve)."""

from __future__ import annotations

import sqlite3

import pytest
from conftest import H, client, outro_consultorio
from fastapi.testclient import TestClient

from puericorbs import config, invites
from puericorbs.db import PLATFORM_VERSION, connect_platform, connect_practice, one
from puericorbs.server import create_app


def entra(s, host: str, email: str, password: str) -> TestClient:
    c = TestClient(create_app(s), base_url=f"http://{host}")
    r = c.post("/api/auth/login", json={"email": email, "password": password}, headers=H)
    assert r.status_code == 200, r.text
    return c


def token_of(link: str) -> str:
    return link.split("#/convite/")[1]


def nova_familia(c: TestClient, email: str | None, nome: str = "Lara Teixeira") -> tuple[int, int]:
    r = c.post("/api/staff/families", headers=H, json={
        "guardian": {"name": nome, "relation": "mãe", "phone": "(11) 95555-0000", "email": email},
        "child": {"name": "Nina Teixeira", "sex": "F", "birth_date": "2026-03-01"}})
    assert r.status_code == 200, r.text
    pid = r.json()["patient_id"]
    gid = c.get(f"/api/staff/patients/{pid}").json()["family_access"][0]["id"]
    return pid, gid


def admin(s, host: str = "dramarina.localhost") -> TestClient:
    pconn = connect_platform(s.data_dir)
    token, _ = invites.create(pconn, kind="admin")
    pconn.close()
    c = TestClient(create_app(s), base_url=f"http://{host}")
    r = c.post(f"/api/invite/{token}", headers=H,
               json={"name": "Dono", "email": "dono@exemplo.test", "password": "uma-senha-longa"})
    assert r.status_code == 200, r.text
    return c


def test_migracao_mantem_o_convite_que_ja_existia(tmp_path):
    """O banco da plataforma da versão 2 (o convite da primeira pediatra já mandado) passa à atual sem perder o link."""
    s = config.load(tmp_path)
    path = tmp_path / "platform.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL,
          password_hash TEXT, is_platform_admin INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL, user_agent TEXT);
        CREATE TABLE clinics (id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE practices (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
          title TEXT NOT NULL DEFAULT 'Pediatra', registry TEXT, bio TEXT, address TEXT, phone TEXT,
          accent TEXT NOT NULL DEFAULT 'agua', clinic_id INTEGER, created_at TEXT NOT NULL);
        CREATE TABLE domains (host TEXT PRIMARY KEY, practice_id INTEGER NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE memberships (user_id INTEGER NOT NULL, practice_id INTEGER NOT NULL, role TEXT NOT NULL,
          PRIMARY KEY (user_id, practice_id));
        CREATE TABLE invites (token_hash TEXT PRIMARY KEY, practice_id INTEGER NOT NULL, role TEXT NOT NULL,
          created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT, used_by INTEGER);
        INSERT INTO practices (id, slug, name, created_at) VALUES (1, 'drateste', 'Consultório pediátrico', '2026-10-28T13:00:00');
        INSERT INTO domains VALUES ('drateste.com.br', 1, '2026-10-28T13:00:00');
        PRAGMA user_version = 2;""")
    from puericorbs.auth import token_hash
    old.execute("INSERT INTO invites VALUES (?, 1, 'clinician', '2026-10-28T13:00:00', '2099-01-01T00:00:00', NULL, NULL)",
                (token_hash("o-link-dela"),))
    old.commit()
    old.close()
    pconn = connect_platform(s.data_dir)
    assert pconn.execute("PRAGMA user_version").fetchone()[0] == PLATFORM_VERSION
    row = invites.find(pconn, "o-link-dela")
    assert row and row["kind"] == "staff" and row["role"] == "clinician" and row["practice_id"] == 1
    pconn.close()
    info = TestClient(create_app(s), base_url="http://drateste.com.br").get("/api/invite/o-link-dela").json()
    assert info["role"] == "clinician"


def test_familia_cria_a_senha_pelo_link_da_recepcao(fresh):
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    pid, gid = nova_familia(carla, "lara@exemplo.test")
    acesso = carla.get(f"/api/staff/patients/{pid}").json()["family_access"][0]
    assert acesso["state"] == "sem"  # o cadastro não cria conta: só o convite liga a pessoa
    x = carla.post(f"/api/staff/guardians/{gid}/invite", headers=H).json()
    assert x["phone"] == "(11) 95555-0000" and x["link"] in x["text"]
    assert carla.get(f"/api/staff/patients/{pid}").json()["family_access"][0]["state"] == "convite"
    lara = TestClient(create_app(fresh), base_url="http://dramarina.localhost")
    info = lara.get(f"/api/invite/{token_of(x['link'])}").json()
    assert info["kind"] == "family" and info["account"] is None and info["guardian"]["email"] == "lara@exemplo.test"
    r = lara.post(f"/api/invite/{token_of(x['link'])}", json={"email": "lara@exemplo.test", "password": "senha-da-lara"},
                  headers=H)
    assert r.status_code == 200, r.text
    assert lara.get("/api/me").json()["me"]["role"] == "guardian"
    assert [k["name"] for k in lara.get("/api/family/home").json()["children"]] == ["Nina Teixeira"]
    assert carla.get(f"/api/staff/patients/{pid}").json()["family_access"][0]["state"] == "ativo"
    entra(fresh, "dramarina.localhost", "lara@exemplo.test", "senha-da-lara")


def test_so_a_equipe_gera_o_link_da_familia_e_ele_so_abre_no_consultorio(fresh):
    outro_consultorio(fresh)
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    pid, gid = nova_familia(marina, "lara@exemplo.test")
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    assert ana.post(f"/api/staff/guardians/{gid}/invite", headers=H).status_code == 403
    token = token_of(marina.post(f"/api/staff/guardians/{gid}/invite", headers=H).json()["link"])
    fora = TestClient(create_app(fresh), base_url="http://draoutra.localhost")
    assert fora.get(f"/api/invite/{token}").status_code == 404
    # no site do Paulo, que é do mesmo consultório, abre; e o responsável vem do banco da Marina (o id 1 existe nos
    # dois bancos: a Ana aqui, outra pessoa lá)
    ana = token_of(marina.post("/api/staff/guardians/1/invite", headers=H).json()["link"])
    info = TestClient(create_app(fresh), base_url="http://drpauloreis.localhost").get(f"/api/invite/{ana}").json()
    assert info["guardian"]["name"] == "Ana Costa" and info["practice"]["name"] == "Dra. Marina Alves"
    assert fora.post(f"/api/invite/{ana}", json={"password": "qualquer-senha"}, headers=H).status_code == 404
    # o Paulo não alcança o responsável da Marina: o id é de outro banco
    paulo = client(fresh, "drpauloreis.localhost", "paulo@demo.test")
    lins = paulo.get("/api/staff/patients?q=Lins").json()["patients"][0]
    ids_paulo = {g["id"] for g in paulo.get(f"/api/staff/patients/{lins['id']}").json()["family_access"]}
    x = paulo.post(f"/api/staff/guardians/{gid}/invite", headers=H)
    assert x.status_code == 404 or gid in ids_paulo
    # um link novo cancela o anterior
    novo = token_of(marina.post(f"/api/staff/guardians/{gid}/invite", headers=H).json()["link"])
    site = TestClient(create_app(fresh), base_url="http://dramarina.localhost")
    assert site.get(f"/api/invite/{token}").status_code == 404 and site.get(f"/api/invite/{novo}").status_code == 200


def test_link_da_familia_nao_troca_a_senha_de_conta_alheia(fresh):
    """O e-mail digitado na recepção não prova nada: a conta que já existe só se liga com a senha dela, e a conta da
    equipe ou de quem é responsável em outro consultório nunca tem a senha trocada pelo link."""
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    site = TestClient(create_app(fresh), base_url="http://dramarina.localhost")
    # 1) o cadastro com o e-mail do Paulo (equipe de outro consultório)
    _, gid = nova_familia(marina, "paulo@demo.test", "Paulo Reis")
    token = token_of(marina.post(f"/api/staff/guardians/{gid}/invite", headers=H).json()["link"])
    r = site.post(f"/api/invite/{token}", json={"email": "paulo@demo.test", "password": "tomei-a-conta"}, headers=H)
    assert r.status_code == 409
    entra(fresh, "drpauloreis.localhost", "paulo@demo.test", "demo1234")  # a senha dele continua a mesma
    # 2) a Fernanda é responsável no consultório do Paulo; aqui, liga com a senha dela
    _, gid = nova_familia(marina, "fernanda@demo.test", "Fernanda Lins")
    token = token_of(marina.post(f"/api/staff/guardians/{gid}/invite", headers=H).json()["link"])
    assert site.post(f"/api/invite/{token}", json={"email": "fernanda@demo.test", "password": "chute-errado"},
                     headers=H).status_code == 409
    assert site.post(f"/api/invite/{token}", json={"email": "fernanda@demo.test", "password": "demo1234"},
                     headers=H).status_code == 200
    # e um link novo aqui não troca a senha dela (ela também é do outro consultório)
    token = token_of(marina.post(f"/api/staff/guardians/{gid}/invite", headers=H).json()["link"])
    assert site.get(f"/api/invite/{token}").json()["account"]["keeps_password"] is True
    assert site.post(f"/api/invite/{token}", json={"password": "outra-senha-1"}, headers=H).status_code == 409
    entra(fresh, "drpauloreis.localhost", "fernanda@demo.test", "demo1234")


def test_familia_so_deste_consultorio_troca_a_senha_esquecida(fresh):
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    helena = marina.get("/api/staff/patients?q=Helena").json()["patients"][0]
    ana = next(g for g in marina.get(f"/api/staff/patients/{helena['id']}").json()["family_access"] if g["name"] == "Ana Costa")
    assert ana["state"] == "ativo"
    token = token_of(marina.post(f"/api/staff/guardians/{ana['id']}/invite", headers=H).json()["link"])
    site = TestClient(create_app(fresh), base_url="http://dramarina.localhost")
    assert site.get(f"/api/invite/{token}").json()["account"]["keeps_password"] is False
    assert site.post(f"/api/invite/{token}", json={"password": "nova-senha-da-ana"}, headers=H).status_code == 200
    entra(fresh, "dramarina.localhost", "ana@demo.test", "nova-senha-da-ana")
    r = TestClient(create_app(fresh), base_url="http://dramarina.localhost").post(
        "/api/auth/login", json={"email": "ana@demo.test", "password": "demo1234"}, headers=H)
    assert r.status_code == 401


def test_painel_mostra_numeros_e_a_ficha_so_abre_vendo_como(fresh):
    dono = admin(fresh)
    assert dono.get("/api/me").json()["me"]["is_platform_admin"] is True
    texto = dono.get("/api/admin/overview").text
    painel = dono.get("/api/admin/overview").json()
    marina = next(p for p in painel["practices"] if p["slug"] == "dramarina")
    assert marina["metrics"]["patients"] > 5 and marina["has_clinician"]
    for nome in ("Helena", "Theo", "Alice", "Ana Costa"):
        assert nome not in texto
    # sem o "vendo como" (test_view_as.py), a administração não abre ficha nem lista de pacientes
    assert dono.get("/api/staff/patients").status_code == 403
    assert dono.get("/api/family/home").status_code == 403
    # e quem não é da administração não vê o painel
    assert client(fresh, "dramarina.localhost", "marina@demo.test").get("/api/admin/overview").status_code == 403
    assert TestClient(create_app(fresh), base_url="http://dramarina.localhost").get("/api/admin/overview").status_code == 401


def test_administracao_gera_os_convites_da_plataforma(fresh):
    dono = admin(fresh)
    # consultório que já tem pediatra: a plataforma não põe ninguém dentro
    assert dono.post("/api/admin/invites", json={"kind": "clinician", "practice_id": 1}, headers=H).status_code == 409
    novo = dono.post("/api/admin/practices", json={"name": "Dra. Nova Silva"}, headers=H).json()
    x = dono.post("/api/admin/invites", json={"kind": "clinician", "practice_id": novo["id"]}, headers=H).json()
    assert x["warning"] and "#/convite/" in x["link"]
    assert dono.post("/api/admin/practices/" + str(novo["id"]) + "/domains", json={"host": "dramarina.com.br"},
                     headers=H).status_code == 409
    for kind in ("practice", "admin"):
        assert dono.post("/api/admin/invites", json={"kind": kind}, headers=H).status_code == 200
    # a família não aparece no painel
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    _, gid = nova_familia(marina, None)
    marina.post(f"/api/staff/guardians/{gid}/invite", headers=H)
    painel = dono.get("/api/admin/overview").json()
    assert all(i["kind"] != "family" for i in painel["invites"])
    assert "Lara" not in dono.get("/api/admin/overview").text
    # convite de administração pede senha longa
    pconn = connect_platform(fresh.data_dir)
    token, _ = invites.create(pconn, kind="admin")
    pconn.close()
    r = TestClient(create_app(fresh), base_url="http://dramarina.localhost").post(
        f"/api/invite/{token}", json={"name": "X", "email": "x@exemplo.test", "password": "curta123"}, headers=H)
    assert r.status_code == 400


def test_senha_errada_demais_espera(fresh):
    c = TestClient(create_app(fresh), base_url="http://dramarina.localhost")
    for _ in range(10):
        assert c.post("/api/auth/login", json={"email": "marina@demo.test", "password": "errada"}, headers=H).status_code == 401
    r = c.post("/api/auth/login", json={"email": "marina@demo.test", "password": "demo1234"}, headers=H)
    assert r.status_code == 429


def test_cadastro_com_email_de_outra_familia_nao_entrega_a_conta(fresh):
    """A recepção cadastra uma "nova família" com o e-mail da Ana e manda o link para outra pessoa: o link não troca a
    senha da Ana nem abre os filhos dela; só a senha da própria Ana ligaria a conta."""
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    _, gid = nova_familia(carla, "ana@demo.test", "Outra Pessoa")
    token = token_of(carla.post(f"/api/staff/guardians/{gid}/invite", headers=H).json()["link"])
    site = TestClient(create_app(fresh), base_url="http://dramarina.localhost")
    assert site.get(f"/api/invite/{token}").json()["account"] is None
    r = site.post(f"/api/invite/{token}", json={"email": "ana@demo.test", "password": "tomei-a-conta"}, headers=H)
    assert r.status_code == 409
    entra(fresh, "dramarina.localhost", "ana@demo.test", "demo1234")

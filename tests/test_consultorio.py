"""O consultório com várias pediatras: cada uma só vê os seus pacientes; a atendente e a administração do consultório
atendem todas, sem nada clínico; quem é de fora não entra; e tudo começa por convite.

Na demonstração, a Dra. Marina e o Dr. Paulo dividem o Consultório Girassol: a Carla é a atendente das duas práticas, a
Bia e a Dra. Marina são a administração. A "Dra. Outra" é um consultório à parte, criado aqui para cada fronteira."""

from __future__ import annotations

import sqlite3

from conftest import H, client, outro_consultorio
from fastapi.testclient import TestClient

from puericorbs import clinics, config, invites
from puericorbs.auth import token_hash
from puericorbs.db import PLATFORM_VERSION, connect_platform, connect_practice, many, one
from puericorbs.practices import create_practice
from puericorbs.server import create_app

PASSWORD = "demo1234"


def entra(s, host: str, email: str, password: str = PASSWORD) -> TestClient:
    c = TestClient(create_app(s), base_url=f"http://{host}")
    r = c.post("/api/auth/login", json={"email": email, "password": password}, headers=H)
    assert r.status_code == 200, r.text
    return c


def convida(c: TestClient, role: str, label: str | None = None) -> str:
    r = c.post("/api/staff/invites", json={"role": role, "label": label}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()["link"].split("#/convite/")[1]


def aceita(s, host: str, token: str, **body) -> TestClient:
    c = TestClient(create_app(s), base_url=f"http://{host}")
    r = c.post(f"/api/invite/{token}", json=body, headers=H)
    assert r.status_code == 200, r.text
    return c


def familia(c: TestClient, practice_id: int | None = None, nome: str = "Rita Prado") -> int:
    r = c.post("/api/staff/families", headers=H, json={
        "practice_id": practice_id, "guardian": {"name": nome, "relation": "mãe", "phone": "(11) 95555-1000"},
        "child": {"name": "Davi Prado", "sex": "M", "birth_date": "2026-01-10"}})
    assert r.status_code == 200, r.text
    return r.json()["patient_id"]


def test_a_pediatra_convidada_entra_com_os_pacientes_dela(fresh):
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    token = convida(marina, "clinician", "João")
    info = TestClient(create_app(fresh), base_url="http://dramarina.localhost").get(f"/api/invite/{token}").json()
    assert info["role"] == "clinician" and info["clinic"] == "Clínica Girassol" and "Dra. Marina Alves" in info["doctors"]
    # sem domínio próprio, ele entra pelo da Marina e cai na prática dele
    joao = aceita(fresh, "dramarina.localhost", token, name="João Lima", practice_name="Dr. João Lima",
                  registry="CRM-SP 123", email="joao@exemplo.test", password="senha-do-joao")
    site = joao.get("/api/site").json()
    assert site["me"]["role"] == "clinician" and site["practice"]["name"] == "Dr. João Lima"
    jid = site["practice"]["id"]
    pconn = connect_platform(fresh.data_dir)
    assert one(pconn, "SELECT clinic_id FROM practices WHERE id = ?", (jid,))["clinic_id"] == \
        one(pconn, "SELECT clinic_id FROM practices WHERE id = 1")["clinic_id"]
    pconn.close()
    davi = familia(joao)
    assert [p["id"] for p in joao.get("/api/staff/patients").json()["patients"]] == [davi]
    assert connect_practice(fresh.data_dir, jid).execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 1
    assert not one(connect_practice(fresh.data_dir, 1), "SELECT id FROM patients WHERE name = 'Davi Prado'")
    # cada pediatra só vê os seus
    assert joao.get("/api/staff/patients?practice_id=1").status_code == 404
    paulo = client(fresh, "drpauloreis.localhost", "paulo@demo.test")
    assert paulo.get(f"/api/staff/patients?practice_id={jid}").status_code == 404
    # a pediatra que cuida do consultório também só vê os seus; a recepção e a administração atendem todas, sem o
    # prontuário
    assert marina.get(f"/api/staff/patients?practice_id={jid}").status_code == 404
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    bia = client(fresh, "dramarina.localhost", "bia@demo.test")
    for c in (carla, bia):
        assert [p["id"] for p in c.get(f"/api/staff/patients?practice_id={jid}").json()["patients"]] == [davi]
        ficha = c.get(f"/api/staff/patients/{davi}?practice_id={jid}").json()
        assert ficha["clinical"] is False and "allergies" not in ficha["patient"] and "encounters" not in ficha
    # e o acesso fica no registro da prática dele, com quem viu
    vistos = many(connect_practice(fresh.data_dir, jid), "SELECT user_id, action FROM audit_log WHERE entity_id = ?", (davi,))
    assert {v["action"] for v in vistos} >= {"ver_cadastro"} and len({v["user_id"] for v in vistos}) == 2


def test_so_a_administracao_do_consultorio_convida_e_tira_a_equipe(fresh):
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    paulo = client(fresh, "drpauloreis.localhost", "paulo@demo.test")
    for c in (carla, paulo):
        assert c.post("/api/staff/invites", json={"role": "receptionist"}, headers=H).status_code == 403
    assert marina.post("/api/staff/invites", json={"role": "chefe"}, headers=H).status_code == 400
    # a atendente nova atende as duas pediatras, por qualquer domínio do consultório
    lia = aceita(fresh, "drpauloreis.localhost", convida(marina, "receptionist", "Lia"), name="Lia Costa",
                 email="lia@exemplo.test", password="senha-da-lia")
    me = lia.get("/api/me").json()["me"]
    assert me["role"] == "receptionist" and me["manages"] is False and {p["id"] for p in me["practices"]} == {1, 2}
    # a equipe vê quem é quem; os convites (que já existem), só a administração
    assert marina.get("/api/staff/team").json()["invites"] and carla.get("/api/staff/team").json()["invites"] == []
    assert lia.get("/api/staff/patients?practice_id=1").status_code == 200
    assert lia.post("/api/staff/invites", json={"role": "receptionist"}, headers=H).status_code == 403
    # a administração nova faz o que a atendente faz e cuida da equipe
    rui = aceita(fresh, "dramarina.localhost", convida(marina, "manager", "Rui"), name="Rui Lopes",
                 email="rui@exemplo.test", password="senha-do-rui")
    me = rui.get("/api/me").json()["me"]
    assert me["role"] == "receptionist" and me["manages"] is True and me["role_label"] == "Administração do consultório"
    assert rui.get("/api/staff/today").status_code == 403  # o dia clínico é da pediatra
    equipe = rui.get("/api/staff/team").json()
    quem = {m["email"]: m for m in equipe["members"]}
    assert quem["marina@demo.test"]["manager"] and quem["paulo@demo.test"]["practice"] == "Dr. Paulo Reis"
    assert quem["lia@exemplo.test"]["role"] == "receptionist" and quem["rui@exemplo.test"]["role"] == "manager"
    assert any(i["label"] == "Lia" and i["status"] == "aceito" for i in equipe["invites"])
    # tirar: a atendente sai; a pediatra não sai por aqui
    assert rui.delete(f"/api/staff/team/{quem['lia@exemplo.test']['id']}", headers=H).status_code == 200
    assert lia.get("/api/staff/patients").status_code == 403
    assert rui.delete(f"/api/staff/team/{quem['paulo@demo.test']['id']}", headers=H).status_code == 400


def test_o_consultorio_nunca_fica_sem_administracao(fresh):
    outro_consultorio(fresh)
    outra = entra(fresh, "draoutra.localhost", "outra@demo.test")
    me = outra.get("/api/me").json()["me"]
    assert me["role"] == "clinician" and me["manages"] is True  # quem cria o consultório já cuida dele
    r = outra.delete(f"/api/staff/team/{me['id']}", headers=H)
    assert r.status_code == 400 and "administração" in r.json()["detail"]


def test_quem_e_de_outro_consultorio_nao_entra(fresh):
    outro_consultorio(fresh)
    nao = lambda host, email: TestClient(create_app(fresh), base_url=f"http://{host}").post(  # noqa: E731
        "/api/auth/login", json={"email": email, "password": PASSWORD}, headers=H).status_code
    assert nao("dramarina.localhost", "outra@demo.test") == 403
    for email in ("carla@demo.test", "bia@demo.test", "marina@demo.test", "ana@demo.test"):
        assert nao("draoutra.localhost", email) == 403, email
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    token = convida(marina, "receptionist")
    assert TestClient(create_app(fresh), base_url="http://draoutra.localhost").get(f"/api/invite/{token}").status_code == 404
    outra = entra(fresh, "draoutra.localhost", "outra@demo.test")
    assert outra.get("/api/staff/patients?practice_id=1").status_code == 404
    assert outra.get("/api/staff/agenda?scope=clinic").json()["columns"][0]["practice"]["name"] == "Dra. Outra"


def test_cada_um_cai_na_propria_area_por_qualquer_dominio_do_consultorio(fresh):
    em = lambda host, email: client(fresh, host, email).get("/api/site").json()  # noqa: E731
    marina = em("drpauloreis.localhost", "marina@demo.test")
    assert marina["practice"]["id"] == 1 and marina["me"]["role"] == "clinician"
    paulo = em("dramarina.localhost", "paulo@demo.test")
    assert paulo["practice"]["id"] == 2 and paulo["me"]["role"] == "clinician" and paulo["me"]["manages"] is False
    ana = client(fresh, "drpauloreis.localhost", "ana@demo.test")
    assert ana.get("/api/site").json()["practice"]["id"] == 1
    assert {k["first_name"] for k in ana.get("/api/family/home").json()["children"]} == {"Helena", "Theo"}
    # quem não entrou vê o site do domínio, com as colegas do consultório
    publico = TestClient(create_app(fresh), base_url="http://drpauloreis.localhost").get("/api/site").json()
    assert publico["practice"]["id"] == 2 and [c["name"] for c in publico["colleagues"]] == ["Dra. Marina Alves"]


def test_a_plataforma_cria_o_consultorio_e_a_pediatra_cuida_dele(fresh):
    from test_invites import admin
    dono = admin(fresh)
    link = dono.post("/api/admin/invites", json={"kind": "practice", "label": "Clara"}, headers=H).json()["link"]
    r = TestClient(create_app(fresh), base_url="http://dramarina.localhost").post(
        f"/api/invite/{link.split('#/convite/')[1]}", headers=H, json={
            "name": "Clara Nunes", "practice_name": "Dra. Clara Nunes", "clinic_name": "Consultório Lua",
            "email": "clara@exemplo.test", "password": "senha-da-clara", "domain": "draclara.com.br"})
    assert r.status_code == 200, r.text
    pconn = connect_platform(fresh.data_dir)
    p = one(pconn, "SELECT p.*, c.name AS clinic FROM practices p JOIN clinics c ON c.id = p.clinic_id WHERE p.slug = 'draclaranunes'")
    assert p["clinic"] == "Consultório Lua" and p["clinic_id"] != 1
    uid = one(pconn, "SELECT id FROM users WHERE email = 'clara@exemplo.test'")["id"]
    assert clinics.member(pconn, p["clinic_id"], uid)["role"] == "manager"
    pconn.close()


V4_INVITES = """CREATE TABLE invites (
  id INTEGER PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL DEFAULT 'staff' CHECK (kind IN ('staff', 'family', 'practice', 'admin')),
  practice_id INTEGER REFERENCES practices(id) ON DELETE CASCADE,
  role TEXT CHECK (role IN ('clinician', 'receptionist')), guardian_id INTEGER, label TEXT,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
  used_at TEXT, used_by INTEGER REFERENCES users(id) ON DELETE SET NULL, revoked_at TEXT,
  new_practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL)"""


def test_migracao_do_consultorio(tmp_path):
    """A plataforma da versão 4 (sem a equipe do consultório) passa à 5: cada prática ganha consultório, a atendente
    passa a ser do consultório, a pediatra mais antiga cuida dele, e o convite que estava pendente continua valendo."""
    s = config.load(tmp_path)
    pconn = connect_platform(s.data_dir)
    a = create_practice(pconn, s.data_dir, name="Dra. A", slug="draa", clinician_email="a@x.test", password="senha-da-a")
    clinic = one(pconn, "SELECT clinic_id FROM practices WHERE id = ?", (a,))["clinic_id"]
    b = create_practice(pconn, s.data_dir, name="Dr. B", slug="drb", clinician_email="b@x.test", password="senha-do-b",
                        clinic_id=clinic)
    c = create_practice(pconn, s.data_dir, name="Dra. C", slug="drac", clinician_email="c@x.test", password="senha-da-c")
    # o jeito da versão 4: a prática C sem consultório, a atendente como membro de cada prática, sem clinic_members
    pconn.execute("UPDATE practices SET clinic_id = NULL WHERE id = ?", (c,))
    pconn.execute("DELETE FROM clinics WHERE id NOT IN (SELECT clinic_id FROM practices WHERE clinic_id IS NOT NULL)")
    pconn.execute("INSERT INTO users (email, name, created_at) VALUES ('r@x.test', 'R', '2026-10-28T10:00:00')")
    r = one(pconn, "SELECT id FROM users WHERE email = 'r@x.test'")["id"]
    for pid in (a, b):
        pconn.execute("INSERT INTO memberships (user_id, practice_id, role) VALUES (?, ?, 'receptionist')", (r, pid))
    pconn.execute("DROP TABLE clinic_members")
    pconn.execute("DROP TABLE invites")
    pconn.execute(V4_INVITES)
    pconn.execute("""INSERT INTO invites (token_hash, kind, practice_id, role, created_at, expires_at)
                     VALUES (?, 'staff', ?, 'receptionist', '2026-10-28T10:00:00', '2099-01-01T00:00:00')""",
                  (token_hash("pendente"), a))
    for col in ("billing_mode", "tax_id", "legal_name", "municipal_registration", "tax_regime", "iss_rate"):
        pconn.execute(f"ALTER TABLE practices DROP COLUMN {col}")  # o que a versão 6 trouxe (test_fiscal.py)
    pconn.execute("PRAGMA user_version = 4")
    pconn.close()
    pconn = connect_platform(s.data_dir)
    assert pconn.execute("PRAGMA user_version").fetchone()[0] == PLATFORM_VERSION
    nova = one(pconn, "SELECT p.clinic_id, c.name FROM practices p JOIN clinics c ON c.id = p.clinic_id WHERE p.id = ?", (c,))
    assert nova["name"] == "Dra. C"
    assert many(pconn, "SELECT clinic_id, role FROM clinic_members WHERE user_id = ?", (r,)) == \
        [{"clinic_id": clinic, "role": "receptionist"}]
    assert not one(pconn, "SELECT 1 AS x FROM memberships WHERE role = 'receptionist'")
    gestao = {(m["clinic_id"], m["user_id"]) for m in many(pconn, "SELECT * FROM clinic_members WHERE role = 'manager'")}
    a_id, b_id, c_id = (one(pconn, "SELECT id FROM users WHERE email = ?", (e,))["id"] for e in ("a@x.test", "b@x.test", "c@x.test"))
    assert gestao == {(clinic, a_id), (nova["clinic_id"], c_id)}  # a mais antiga do consultório; o Dr. B, não
    pconn.close()
    # o convite pendente abre e faz da pessoa a atendente do consultório
    novo = aceita(s, "draa.localhost", "pendente", name="Rosa", email="rosa@x.test", password="senha-da-rosa")
    assert {p["id"] for p in novo.get("/api/me").json()["me"]["practices"]} == {a, b}
    with sqlite3.connect(s.data_dir / "platform.db") as raw:
        assert raw.execute("SELECT clinic_id FROM invites").fetchone()[0] is None
    assert invites.find(connect_platform(s.data_dir), "pendente") is None

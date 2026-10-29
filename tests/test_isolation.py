"""O invariante número 1: cada pediatra só vê os seus pacientes, a família só vê os filhos e a recepção nunca vê o
prontuário. Cada teste tenta atravessar uma fronteira e precisa ser barrado."""

from __future__ import annotations

from conftest import H, client, outro_consultorio

from puericorbs import config, tenancy
from puericorbs.db import connect_platform


def test_o_dominio_decide_o_consultorio(settings):
    pconn = connect_platform(settings.data_dir)
    assert tenancy.resolve(settings, pconn, "dramarina.com.br", None).practice["slug"] == "dramarina"
    assert tenancy.resolve(settings, pconn, "DRPAULOREIS.com.br:443", None).practice["slug"] == "drpauloreis"
    assert tenancy.resolve(settings, pconn, "dramarina.localhost:8930", None).practice["slug"] == "dramarina"
    assert tenancy.resolve(settings, pconn, "localhost", None).kind == "platform"


def test_dominio_desconhecido_fora_da_demonstracao(settings):
    from dataclasses import replace
    prod = replace(settings, demo=False)
    pconn = connect_platform(settings.data_dir)
    assert tenancy.resolve(prod, pconn, "qualquer.com.br", None).kind == "unknown"
    # o cookie de "visitar um site" só vale na demonstração
    assert tenancy.resolve(prod, pconn, "localhost", "dramarina").kind == "platform"


def test_pediatra_nao_ve_os_pacientes_do_outro(fresh):
    paulo = client(fresh, "drpauloreis.localhost", "paulo@demo.test")
    assert paulo.get("/api/staff/patients?practice_id=1").status_code == 404
    nomes = {p["name"] for p in paulo.get("/api/staff/patients").json()["patients"]}
    assert "Helena Costa" not in nomes and "Davi Nunes" in nomes
    # a Marina cuida do consultório, mas é pediatra: também só vê os dela
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    assert marina.get("/api/staff/patients?practice_id=2").status_code == 404
    # pelo domínio do Paulo (o mesmo consultório), ela cai na prática dela, nunca na dele
    m = client(fresh, "drpauloreis.localhost", "marina@demo.test")
    assert m.get("/api/site").json()["practice"]["id"] == 1
    assert "Davi Nunes" not in {p["name"] for p in m.get("/api/staff/patients").json()["patients"]}
    # e no domínio de outro consultório ela não entra
    outro_consultorio(fresh)
    r = client(fresh, "draoutra.localhost").post("/api/auth/demo", json={"email": "marina@demo.test"}, headers=H)
    assert r.status_code == 403


def test_familia_so_ve_os_proprios_filhos(fresh):
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    kids = {k["name"]: k["id"] for k in ana.get("/api/family/home").json()["children"]}
    assert set(kids) == {"Helena Costa", "Theo Costa"}
    julia = client(fresh, "dramarina.localhost", "julia@demo.test")
    alice = julia.get("/api/family/home").json()["children"][0]["id"]
    assert ana.get(f"/api/family/children/{alice}/health").status_code == 404
    assert ana.get("/api/staff/today").status_code == 403
    # pelo domínio do Paulo (o mesmo consultório), a mãe da Helena só vê os filhos dela
    pelo_paulo = client(fresh, "drpauloreis.localhost", "ana@demo.test")
    assert {k["name"] for k in pelo_paulo.get("/api/family/home").json()["children"]} == {"Helena Costa", "Theo Costa"}
    # e no domínio de outro consultório ela não entra
    outro_consultorio(fresh)
    r = client(fresh, "draoutra.localhost").post("/api/auth/demo", json={"email": "ana@demo.test"}, headers=H)
    assert r.status_code == 403


def test_recepcao_nao_ve_o_prontuario(settings):
    carla = client(settings, "dramarina.localhost", "carla@demo.test")
    pid = carla.get("/api/staff/patients?q=Alice").json()["patients"][0]["id"]
    ficha = carla.get(f"/api/staff/patients/{pid}").json()
    assert ficha["clinical"] is False
    assert "allergies" not in ficha["patient"]
    assert "encounters" not in ficha and "measurements" not in ficha and "vaccines" not in ficha
    assert all(f["visibility"] == "admin" for f in ficha["files"])
    assert {i["type"] for i in ficha["timeline"]["todo"]} <= {"consulta"}
    assert carla.get(f"/api/staff/patients/{pid}/chart").status_code == 403
    assert carla.get("/api/staff/review").status_code == 403
    assert carla.get("/api/staff/finance").status_code == 403
    # mas atende os dois pediatras da clínica
    assert carla.get("/api/staff/patients?practice_id=2").status_code == 200


def test_arquivo_clinico_nao_abre_para_quem_nao_pode(settings):
    marina = client(settings, "dramarina.localhost", "marina@demo.test")
    review = marina.get("/api/staff/review").json()["files"]
    exame = next(f for f in review if f["kind"] == "exame")
    assert marina.get(f"/api/files/{exame['id']}").status_code == 200
    carla = client(settings, "dramarina.localhost", "carla@demo.test")
    assert carla.get(f"/api/files/{exame['id']}").status_code == 404
    ana = client(settings, "dramarina.localhost", "ana@demo.test")  # o exame é da família Pires
    assert ana.get(f"/api/files/{exame['id']}").status_code == 404


def test_pedido_sem_o_cabecalho_do_app_e_recusado(settings):
    c = client(settings, "dramarina.localhost")
    assert c.post("/api/auth/demo", json={"email": "marina@demo.test"}).status_code == 403


def test_senha(settings):
    c = client(settings, "dramarina.localhost")
    assert c.post("/api/auth/login", json={"email": "marina@demo.test", "password": "errada"}, headers=H).status_code == 401
    assert c.post("/api/auth/login", json={"email": "marina@demo.test", "password": "demo1234"}, headers=H).status_code == 200
    assert c.get("/api/me").json()["me"]["role"] == "clinician"


def test_cada_pratica_tem_o_proprio_banco(settings):
    from puericorbs.db import practice_dir
    assert (practice_dir(settings.data_dir, 1) / "practice.db").exists()
    assert (practice_dir(settings.data_dir, 2) / "practice.db").exists()
    assert config.load(settings.data_dir).data_dir == settings.data_dir


def test_horarios_e_agenda_fechada_so_do_proprio_consultorio(fresh):
    """A agenda fechada devolve quem estava marcado (nome e telefone da família): o Paulo nunca abre a da Marina."""
    from datetime import date, timedelta
    amanha = (date.today() + timedelta(days=1)).isoformat()
    paulo = client(fresh, "drpauloreis.localhost", "paulo@demo.test")
    assert paulo.get("/api/staff/schedule?practice_id=1").status_code == 404
    assert paulo.put("/api/staff/schedule", json={"periods": [], "practice_id": 1}, headers=H).status_code == 404
    assert paulo.post("/api/staff/closures", json={"start": amanha, "practice_id": 1}, headers=H).status_code == 404
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    cid = marina.post("/api/staff/closures", json={"start": amanha}, headers=H).json()["id"]
    assert paulo.delete(f"/api/staff/closures/{cid}?practice_id=1", headers=H).status_code == 404
    appt = marina.get(f"/api/staff/agenda?date={amanha}").json()["columns"][0]["appointments"][0]["id"]
    assert paulo.post(f"/api/staff/appointments/{appt}/asked", json={"practice_id": 1}, headers=H).status_code == 404
    # no consultório dele, o mesmo número é outro agendamento (ou nenhum): nada da Marina vaza
    assert all(a["patient"]["name"] != "Helena Costa"
               for c in paulo.get(f"/api/staff/agenda?date={amanha}").json()["columns"] for a in c["appointments"])
    # a Carla atende os dois e fecha a agenda do Paulo pelo site da Marina
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    assert carla.post("/api/staff/closures", json={"start": amanha, "practice_id": 2}, headers=H).status_code == 200
    assert paulo.get("/api/staff/schedule").json()["closures"][0]["start"] == amanha

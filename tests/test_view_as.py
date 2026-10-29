"""A administração entra em qualquer consultório vendo como alguém dele: a tela e as ações são as dessa pessoa, e o
registro do consultório guarda quem estava de fato. Cada teste tenta uma porta que precisa estar fechada (ou aberta
só para quem deve)."""

from __future__ import annotations

from urllib.parse import urlsplit

from conftest import H, client, outro_consultorio
from fastapi.testclient import TestClient

from puericorbs import auth, config
from puericorbs.db import PLATFORM_VERSION, PRACTICE_VERSION, connect_platform, connect_practice, many, one
from puericorbs.server import create_app

ADMIN = "admin@demo.test"
VENCIDA = "/#/admin/entrada-vencida"


def uid(s, email: str) -> int:
    return one(connect_platform(s.data_dir), "SELECT id FROM users WHERE email = ?", (email,))["id"]


def browser(s, host: str) -> TestClient:
    """Um navegador sem ninguém dentro, neste endereço (a sessão é por endereço, como o cookie)."""
    return TestClient(create_app(s), base_url=f"http://{host}")


def entra_como(s, practice_id: int, panel_host: str = "localhost", **who) -> TestClient:
    """Do painel até a página do consultório, vendo como `who`: o link de entrada é aberto no endereço que ele indica,
    com os cookies daquele endereço."""
    panel = client(s, panel_host, ADMIN)
    r = panel.post("/api/admin/view-as", json={"practice_id": practice_id, **who}, headers=H)
    assert r.status_code == 200, r.text
    url = urlsplit(r.json()["url"])
    c = TestClient(create_app(s), base_url=f"{url.scheme}://{url.netloc}") if url.netloc else panel
    r = c.get(url.path, follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, "/"), r.headers.get("location")
    return c


def first_slot(c: TestClient, child_id: int) -> dict:
    for svc in c.get(f"/api/family/children/{child_id}/services").json()["services"]:
        for day in c.get(f"/api/family/children/{child_id}/days?service_id={svc['id']}").json()["days"]:
            times = c.get(f"/api/family/children/{child_id}/slots?service_id={svc['id']}&date={day['date']}").json()["times"]
            if times:
                return {"service_id": svc["id"], "date": day["date"], "time": times[0]["time"]}
    raise AssertionError("nenhum horário livre para a família")


def test_ve_a_pediatra_como_ela_ve_e_age_como_ela(fresh):
    marina_id = uid(fresh, "marina@demo.test")
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    c = entra_como(fresh, 1, user_id=marina_id)
    me = c.get("/api/me").json()["me"]
    assert (me["id"], me["role"], me["is_platform_admin"]) == (marina_id, "clinician", False)
    assert me["acting"] == {"admin": "Administração Puericorbs", "name": me["name"], "role_label": "Pediatra"}
    for path in ("/api/staff/patients", "/api/staff/today", "/api/staff/practice", "/api/staff/team"):
        assert c.get(path).json() == marina.get(path).json(), path
    r = c.post("/api/staff/expenses", json={"description": "Teste da plataforma", "amount_cents": 1000}, headers=H)
    assert r.status_code == 200, r.text
    assert "Teste da plataforma" in marina.get("/api/staff/finance").text


def test_ve_a_familia_com_conta_igual_a_ela(fresh):
    ana_id = uid(fresh, "ana@demo.test")
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    g = one(connect_practice(fresh.data_dir, 1), "SELECT id FROM guardians WHERE user_id = ?", (ana_id,))
    c = entra_como(fresh, 1, guardian_id=g["id"])
    assert c.get("/api/me").json()["me"]["id"] == ana_id
    for path in ("/api/family/home", "/api/family/appointments", "/api/family/files"):
        assert c.get(path).json() == ana.get(path).json(), path


def test_ve_a_familia_ainda_sem_conta_e_o_que_faz_fica_no_nome_da_administracao(fresh):
    conn = connect_practice(fresh.data_dir, 1)
    g = one(conn, "SELECT id, name, family_id FROM guardians WHERE user_id IS NULL ORDER BY id LIMIT 1")
    kids = {k["name"].split()[0] for k in many(conn, "SELECT name FROM patients WHERE family_id = ?", (g["family_id"],))}
    c = entra_como(fresh, 1, guardian_id=g["id"])
    me = c.get("/api/me").json()["me"]
    assert me["role"] == "guardian" and me["acting"]["name"] == g["name"] and me["acting"]["role_label"] == "Família"
    home = c.get("/api/family/home").json()
    assert {k["first_name"] for k in home["children"]} == kids
    child = home["children"][0]["id"]
    r = c.post(f"/api/family/children/{child}/appointments", json=first_slot(c, child), headers=H)
    assert r.status_code == 200, r.text
    assert one(conn, "SELECT created_by FROM appointments WHERE id = ?", (r.json()["id"],))["created_by"] == uid(fresh, ADMIN)


def test_o_registro_do_consultorio_guarda_quem_estava_de_fato(fresh):
    admin_id, marina_id = uid(fresh, ADMIN), uid(fresh, "marina@demo.test")
    c = entra_como(fresh, 1, user_id=marina_id)
    patient = c.get("/api/staff/patients").json()["patients"][0]
    assert c.get(f"/api/staff/patients/{patient['id']}").status_code == 200
    conn = connect_practice(fresh.data_dir, 1)
    rows = many(conn, "SELECT * FROM audit_log WHERE actor_id = ? ORDER BY id", (admin_id,))
    assert any(r["action"] == "administracao_entrou" and r["user_id"] == marina_id and "Pediatra" in r["detail"] for r in rows)
    assert any(r["detail"] == "GET /api/staff/patients" and r["user_id"] == marina_id for r in rows)
    assert any(r["action"] == "ver_paciente" and r["entity_id"] == patient["id"] for r in rows)
    # a pediatra de verdade continua no registro sem ninguém por trás
    client(fresh, "dramarina.localhost", "marina@demo.test").get(f"/api/staff/patients/{patient['id']}")
    last = one(conn, "SELECT user_id, actor_id FROM audit_log ORDER BY id DESC LIMIT 1")
    assert last == {"user_id": marina_id, "actor_id": None}
    # a plataforma registra a entrada; o nome de uma família nunca vai para o banco dela
    g = one(conn, "SELECT id, name FROM guardians WHERE user_id IS NULL ORDER BY id LIMIT 1")
    entra_como(fresh, 1, guardian_id=g["id"])
    log = many(connect_platform(fresh.data_dir), "SELECT detail FROM platform_log WHERE action = 'vendo_como' ORDER BY id")
    assert [x["detail"] for x in log][-2:] == [f"Pediatra: {c.get('/api/me').json()['me']['name']}", "uma família"]
    assert all(g["name"] not in (x["detail"] or "") for x in log)


def test_o_link_de_entrada_vale_uma_vez_so_no_consultorio_e_por_pouco_tempo(fresh):
    outro_consultorio(fresh)
    panel = client(fresh, "localhost", ADMIN)
    body = {"practice_id": 1, "user_id": uid(fresh, "marina@demo.test")}
    url = urlsplit(panel.post("/api/admin/view-as", json=body, headers=H).json()["url"])
    assert url.netloc == "dramarina.localhost"
    fora = browser(fresh, "draoutra.localhost")
    assert fora.get(url.path, follow_redirects=False).headers["location"] == VENCIDA
    assert "pc_session" not in fora.cookies
    assert browser(fresh, "dramarina.localhost").get(url.path, follow_redirects=False).headers["location"] == "/"
    outro = browser(fresh, "dramarina.localhost")
    assert outro.get(url.path, follow_redirects=False).headers["location"] == VENCIDA
    assert outro.get("/api/me").json()["me"] is None
    url = urlsplit(panel.post("/api/admin/view-as", json=body, headers=H).json()["url"])
    connect_platform(fresh.data_dir).execute("UPDATE handoffs SET expires_at = '2000-01-01T00:00:00' WHERE used_at IS NULL")
    assert browser(fresh, "dramarina.localhost").get(url.path, follow_redirects=False).headers["location"] == VENCIDA


def test_so_a_administracao_entra_como_alguem(fresh):
    marina_id, carla_id = uid(fresh, "marina@demo.test"), uid(fresh, "carla@demo.test")
    body = {"practice_id": 1, "user_id": carla_id}
    for who in ("marina@demo.test", "ana@demo.test"):
        assert client(fresh, "dramarina.localhost", who).post("/api/admin/view-as", json=body, headers=H).status_code == 403
    assert browser(fresh, "dramarina.localhost").post("/api/admin/view-as", json=body, headers=H).status_code == 401
    # nem com a sessão forjada: o "vendo como" de quem não é da administração não vale
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    connect_platform(fresh.data_dir).execute("UPDATE sessions SET as_practice_id = 1, as_user_id = ? WHERE user_id = ?",
                                             (carla_id, marina_id))
    me = marina.get("/api/me").json()["me"]
    assert me["id"] == marina_id and me["role"] == "clinician" and "acting" not in me
    # e a administração só entra como quem é do consultório
    panel = client(fresh, "localhost", ADMIN)
    paulo_id = uid(fresh, "paulo@demo.test")
    assert panel.post("/api/admin/view-as", json={"practice_id": 1, "user_id": paulo_id}, headers=H).status_code == 404
    assert panel.post("/api/admin/view-as", json={"practice_id": 1, "guardian_id": 9999}, headers=H).status_code == 404


def test_vendo_como_so_vale_no_consultorio_em_que_entrou(fresh):
    """A sessão levada ao domínio de outro consultório não vê ninguém lá: nem a pediatra, nem a família de mesmo número
    (cada prática numera os responsáveis no próprio banco)."""
    fora = outro_consultorio(fresh)
    g = one(connect_practice(fresh.data_dir, 1), "SELECT id FROM guardians ORDER BY id LIMIT 1")
    conn = connect_practice(fresh.data_dir, fora)
    conn.execute("INSERT INTO families (name, created_at) VALUES ('Família de fora', '2026-10-28T10:00:00')")
    conn.execute("INSERT INTO guardians (id, family_id, name, created_at) VALUES (?, 1, 'Alguém de fora', '2026-10-28T10:00:00')",
                 (g["id"],))
    for who in ({"user_id": uid(fresh, "marina@demo.test")}, {"guardian_id": g["id"]}):
        c = entra_como(fresh, 1, **who)
        other = TestClient(create_app(fresh), base_url="http://draoutra.localhost",
                           cookies={"pc_session": c.cookies.get("pc_session")})
        me = other.get("/api/me").json()["me"]
        assert me["is_platform_admin"] and me["role"] is None and "acting" not in me, who
        assert other.get("/api/staff/patients").status_code == 403
        assert other.get("/api/family/home").status_code == 403


def test_voltar_ao_painel(fresh):
    c = entra_como(fresh, 1, user_id=uid(fresh, "marina@demo.test"))
    assert c.post("/api/admin/view-as/stop", headers=H).json() == {"ok": True}
    me = c.get("/api/me").json()["me"]
    assert me["is_platform_admin"] and "acting" not in me
    assert c.get("/api/staff/patients").status_code == 403
    assert c.get("/api/admin/overview").status_code == 200
    saiu = one(connect_practice(fresh.data_dir, 1), "SELECT actor_id FROM audit_log WHERE action = 'administracao_saiu'")
    assert saiu == {"actor_id": uid(fresh, ADMIN)}


def test_quem_sai_da_equipe_deixa_de_ser_visto(fresh):
    carla_id = uid(fresh, "carla@demo.test")
    c = entra_como(fresh, 1, user_id=carla_id)
    assert c.get("/api/me").json()["me"]["role"] == "receptionist"
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    assert marina.delete(f"/api/staff/team/{carla_id}", headers=H).status_code == 200
    me = c.get("/api/me").json()["me"]
    assert me["is_platform_admin"] and "acting" not in me


def test_do_dominio_de_um_consultorio_a_entrada_vai_pelo_dominio_do_outro(fresh):
    """Na produção, o painel está num domínio de pediatra: a entrada em outro consultório vai pelo domínio dele, e o
    consultório sem domínio não tem onde entrar."""
    fora = outro_consultorio(fresh, domain="draoutra.com.br")
    panel = client(fresh, "dramarina.com.br", ADMIN)
    r = panel.post("/api/admin/view-as", json={"practice_id": fora, "user_id": uid(fresh, "outra@demo.test")}, headers=H)
    assert r.json()["url"].startswith("https://draoutra.com.br/api/admin/entrar/")
    # o Paulo é do mesmo consultório: a entrada vale por este mesmo endereço
    for pid, email in ((1, "marina@demo.test"), (2, "paulo@demo.test")):
        same = panel.post("/api/admin/view-as", json={"practice_id": pid, "user_id": uid(fresh, email)}, headers=H)
        assert same.json()["url"].startswith("/api/admin/entrar/"), email
    pid = panel.post("/api/admin/practices", json={"name": "Dra. Sem Domínio"}, headers=H).json()["id"]
    painel = {p["id"]: p for p in panel.get("/api/admin/overview").json()["practices"]}
    assert painel[1]["can_enter"] and painel[2]["can_enter"] and painel[fora]["can_enter"] and not painel[pid]["can_enter"]
    conn = connect_practice(fresh.data_dir, pid)
    conn.execute("INSERT INTO families (name, created_at) VALUES ('Teste', '2026-10-28T10:00:00')")
    conn.execute("INSERT INTO guardians (family_id, name, created_at) VALUES (1, 'Responsável', '2026-10-28T10:00:00')")
    r = panel.post("/api/admin/view-as", json={"practice_id": pid, "guardian_id": 1}, headers=H)
    assert r.status_code == 409 and "domínio" in r.json()["detail"]


def test_a_lista_de_familias_e_so_da_administracao_e_fica_no_registro(fresh):
    panel = client(fresh, "localhost", ADMIN)
    found = panel.get("/api/admin/practices/1/families?q=Helena").json()["guardians"]
    assert found and all("Helena" in g["children"] for g in found)
    assert any(g["account"] for g in found)
    assert client(fresh, "dramarina.localhost", "marina@demo.test").get("/api/admin/practices/1/families").status_code == 403
    row = one(connect_practice(fresh.data_dir, 1), "SELECT * FROM audit_log WHERE action = 'administracao_familias'")
    assert row["actor_id"] == uid(fresh, ADMIN) and row["detail"] == "busca: Helena"


def test_migracao_mantem_a_sessao_e_o_registro(tmp_path):
    """Os bancos de antes do "vendo como" (plataforma 3, consultório 1) passam aos atuais sem derrubar ninguém."""
    s = config.load(tmp_path)
    pconn = connect_platform(s.data_dir)
    pconn.execute("INSERT INTO users (email, name, created_at) VALUES ('x@exemplo.test', 'X', '2026-10-28T10:00:00')")
    token = auth.new_session(pconn, 1, "teste", 30)
    for col in ("as_practice_id", "as_user_id", "as_guardian_id"):
        pconn.execute(f"ALTER TABLE sessions DROP COLUMN {col}")
    pconn.execute("DROP TABLE handoffs")
    pconn.execute("DROP TABLE clinic_members")  # o que a versão 5 trouxe (test_consultorio.py)
    pconn.execute("PRAGMA user_version = 3")
    pconn.close()
    pconn = connect_platform(s.data_dir)
    assert pconn.execute("PRAGMA user_version").fetchone()[0] == PLATFORM_VERSION
    assert auth.session_user(pconn, token)["name"] == "X"
    conn = connect_practice(s.data_dir, 1)
    conn.execute("INSERT INTO audit_log (at, action) VALUES ('2026-10-28T10:00:00', 'ver_paciente')")
    for col in ("actor_id", "detail"):
        conn.execute(f"ALTER TABLE audit_log DROP COLUMN {col}")
    for col in ("end_day", "created_by", "created_at"):  # o que a versão 3 trouxe (test_schedule.py)
        conn.execute(f"ALTER TABLE schedule_exceptions DROP COLUMN {col}")
    conn.execute("ALTER TABLE appointments DROP COLUMN confirm_asked_at")
    conn.execute("PRAGMA user_version = 1")
    conn.close()
    conn = connect_practice(s.data_dir, 1)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == PRACTICE_VERSION
    assert one(conn, "SELECT action, actor_id, detail FROM audit_log") == {"action": "ver_paciente", "actor_id": None,
                                                                         "detail": None}

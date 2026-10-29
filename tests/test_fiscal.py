"""O recibo e a nota (`fiscal.py`, `api_fiscal.py`): a pediatra diz como recebe (pessoa física ou empresa, por ora em
São Paulo), a recepção vê os dados de cada pagamento prontos para copiar, completa os CPFs e anexa o PDF, que chega à
família pelo app."""

from __future__ import annotations

from conftest import H, client

from puericorbs import config, fiscal
from puericorbs.db import PLATFORM_VERSION, PRACTICE_VERSION, connect_platform, connect_practice, one

CPF = "123.456.789-09"  # o de exemplo dos manuais: só os dígitos fecham
CNPJ = "12.345.678/0001-95"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def pago(s, practice_id: int, family: str) -> dict:
    """Um pagamento já feito de uma família da demonstração."""
    return one(connect_practice(s.data_dir, practice_id), """SELECT c.* FROM charges c JOIN families f ON f.id = c.family_id
        WHERE f.name = ? AND c.status = 'paga' AND c.amount_cents > 0 ORDER BY c.id LIMIT 1""", (family,))


def test_cpf_e_cnpj_conferem_os_digitos():
    assert fiscal.cpf_ok(CPF) and fiscal.cpf_ok("12345678909")
    assert not fiscal.cpf_ok("123.456.789-00") and not fiscal.cpf_ok("111.111.111-11") and not fiscal.cpf_ok("1234567890")
    assert fiscal.cnpj_ok(CNPJ) and not fiscal.cnpj_ok("12.345.678/0001-96") and not fiscal.cnpj_ok("00000000000000")
    assert fiscal.fmt_cpf("12345678909") == CPF and fiscal.fmt_cnpj("12345678000195") == CNPJ
    assert fiscal.clean_cpf(" ", "x") is None and fiscal.clean_cpf(CPF, "x") == "12345678909"


def test_so_a_pediatra_diz_como_recebe(fresh):
    for who in ("carla@demo.test", "bia@demo.test", "ana@demo.test"):
        c = client(fresh, "dramarina.localhost", who)
        assert c.get("/api/staff/fiscal").status_code == 403, who
        assert c.put("/api/staff/fiscal", json={"mode": None}, headers=H).status_code == 403, who
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    f = marina.get("/api/staff/fiscal").json()
    assert f["profile"]["mode"] == "pf" and f["profile"]["document"] == "recibo" and f["city"] == "São Paulo"
    assert f["profile"]["portal"]["name"] == "o e-CAC" and set(f["portals"]) == {"pf", "simples", "presumido"}
    pj = {"mode": "pj", "tax_id": CNPJ, "legal_name": "Marina Alves Pediatria Ltda", "regime": "simples", "iss_rate": 2}
    for bad, word in ((dict(pj, tax_id="12.345.678/0001-96"), "CNPJ"), (dict(pj, legal_name=" "), "razão social"),
                      (dict(pj, regime="mei"), "regime"), (dict(pj, iss_rate=7), "ISS"),
                      ({"mode": "pf", "tax_id": "123.456.789-00"}, "CPF"), ({"mode": "cnpj"}, "pessoa física")):
        r = marina.put("/api/staff/fiscal", json=bad, headers=H)
        assert r.status_code == 400 and word in r.json()["detail"], (bad, r.text)
    p = marina.put("/api/staff/fiscal", json=pj, headers=H).json()["profile"]
    assert p["tax_id"] == CNPJ and p["document"] == "nota" and p["portal"]["name"] == "o Emissor Nacional"
    p = marina.put("/api/staff/fiscal", json=dict(pj, regime="presumido"), headers=H).json()["profile"]
    assert p["portal"]["url"] == "https://nfe.prefeitura.sp.gov.br"
    # só a prática dela muda: o Dr. Paulo, no mesmo consultório, segue como estava
    assert one(connect_platform(fresh.data_dir), "SELECT tax_regime FROM practices WHERE id = 2")["tax_regime"] == "simples"
    # ainda sem decidir também vale, e apaga o que era da empresa
    p = marina.put("/api/staff/fiscal", json={"mode": None}, headers=H).json()["profile"]
    assert p["mode"] is None and p["portal"] is None and p["tax_id"] is None
    row = one(connect_platform(fresh.data_dir), "SELECT * FROM practices WHERE id = 1")
    assert row["legal_name"] is None and row["tax_regime"] is None


def test_a_recepcao_e_o_financeiro_sabem_se_e_recibo_ou_nota(fresh):
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    modes = {p["practice"]["name"]: p["practice"]["billing_mode"] for p in carla.get("/api/staff/reception").json()["practices"]}
    assert modes == {"Dra. Marina Alves": "pf", "Dr. Paulo Reis": "pj"}
    assert client(fresh, "dramarina.localhost", "marina@demo.test").get("/api/staff/finance").json()["document"] == "recibo"
    assert client(fresh, "drpauloreis.localhost", "paulo@demo.test").get("/api/staff/finance").json()["document"] == "nota"


def test_o_documento_de_um_pagamento(fresh):
    ch = pago(fresh, 1, "Família Costa")
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    d = carla.get(f"/api/staff/charges/{ch['id']}/document?practice_id=1").json()
    assert d["payer"]["name"] == "Ana Costa" and d["payer"]["cpf"] is None  # a responsável financeira, não o pai
    assert d["amount_cents"] == ch["amount_cents"] and d["paid_on"] == ch["paid_on"] and d["service"] == ch["description"]
    assert d["profile"]["document"] == "recibo"
    assert d["missing"] == ["o CPF de quem pagou", "o CPF da criança"]
    # quem paga é quem a família marcou como responsável financeiro, seja quem for o primeiro do cadastro
    conn = connect_practice(fresh.data_dir, 1)
    conn.execute("UPDATE guardians SET is_financial = (name = 'Bruno Costa') WHERE family_id = ?", (ch["family_id"],))
    conn.commit()
    assert carla.get(f"/api/staff/charges/{ch['id']}/document?practice_id=1").json()["payer"]["name"] == "Bruno Costa"
    conn.execute("UPDATE guardians SET is_financial = (name = 'Ana Costa') WHERE family_id = ?", (ch["family_id"],))
    conn.commit()
    r = carla.put(f"/api/staff/guardians/{d['payer']['id']}/cpf?practice_id=1", json={"cpf": "123.456.789-00"}, headers=H)
    assert r.status_code == 400 and "do responsável" in r.json()["detail"]
    assert carla.put(f"/api/staff/guardians/{d['payer']['id']}/cpf?practice_id=1", json={"cpf": CPF}, headers=H).status_code == 200
    assert carla.put(f"/api/staff/patients/{d['child']['id']}/cpf?practice_id=1", json={"cpf": "98765432100"}, headers=H).status_code == 200
    d = carla.get(f"/api/staff/charges/{ch['id']}/document?practice_id=1").json()
    assert d["payer"]["cpf"] == CPF and d["child"]["cpf"] == "987.654.321-00" and d["missing"] == []
    assert one(connect_practice(fresh.data_dir, 1), "SELECT cpf FROM guardians WHERE id = ?", (d["payer"]["id"],))["cpf"] == "12345678909"
    # a nota (empresa) sai no nome de quem pagou: o CPF da criança não falta
    paulo = client(fresh, "drpauloreis.localhost", "paulo@demo.test")
    ch2 = pago(fresh, 2, "Família Nunes")
    d2 = paulo.get(f"/api/staff/charges/{ch2['id']}/document").json()
    assert d2["profile"]["document"] == "nota" and d2["missing"] == ["o CPF de quem pagou"]
    assert d2["service_code"] == "04.01"
    # sem saber como a pediatra recebe, a fila diz o que falta
    client(fresh, "dramarina.localhost", "marina@demo.test").put("/api/staff/fiscal", json={"mode": None}, headers=H)
    assert carla.get(f"/api/staff/charges/{ch['id']}/document?practice_id=1").json()["missing"] == \
        ["como a pediatra recebe (Consultório)"]


def test_o_pdf_anexado_chega_a_familia(fresh):
    ch = pago(fresh, 1, "Família Costa")
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    r = carla.post(f"/api/staff/charges/{ch['id']}/document?practice_id=1",
                   files={"upload": ("recibo.pdf", PDF, "application/pdf")}, headers=H)
    assert r.status_code == 200 and r.json()["kind"] == "recibo", r.text
    conn = connect_practice(fresh.data_dir, 1)
    row = one(conn, "SELECT * FROM charges WHERE id = ?", (ch["id"],))
    assert row["invoice"] == "emitida" and row["document_file_id"] == r.json()["file_id"]
    # papelada de dinheiro: a família e a recepção veem, o que é clínico não
    assert one(conn, "SELECT visibility FROM files WHERE id = ?", (row["document_file_id"],))["visibility"] == "admin"
    assert one(conn, "SELECT * FROM audit_log WHERE action = 'documento_fiscal_anexado'")["entity_id"] == ch["id"]
    seen = client(fresh, "dramarina.localhost", "ana@demo.test").get("/api/family/files?filter=notas").json()["files"]
    assert any(f["id"] == r.json()["file_id"] and f["kind_label"] == "Recibo" for f in seen)
    # o PDF da nota (empresa) entra como nota fiscal
    paulo = client(fresh, "drpauloreis.localhost", "paulo@demo.test")
    ch2 = pago(fresh, 2, "Família Nunes")
    assert paulo.post(f"/api/staff/charges/{ch2['id']}/document", files={"upload": ("nota.pdf", PDF, "application/pdf")},
                      headers=H).json()["kind"] == "nota"
    # o que não é PDF nem foto não entra
    assert carla.post(f"/api/staff/charges/{ch['id']}/document?practice_id=1",
                      files={"upload": ("x.exe", b"MZ\x90\x00", "application/octet-stream")}, headers=H).status_code == 415


def test_cadastro_da_familia_confere_o_cpf(fresh):
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    body = {"guardian": {"name": "Lia Prado", "cpf": "123.456.789-00"}, "child": {"name": "Rui Prado", "sex": "M",
                                                                                  "birth_date": "2026-01-10"}}
    r = carla.post("/api/staff/families", json=body, headers=H)
    assert r.status_code == 400 and "CPF do responsável" in r.json()["detail"]
    body["guardian"]["cpf"] = CPF
    fid = carla.post("/api/staff/families", json=body, headers=H).json()["family_id"]
    assert one(connect_practice(fresh.data_dir, 1), "SELECT cpf FROM guardians WHERE family_id = ?", (fid,))["cpf"] == "12345678909"


def test_migracao_fiscal(tmp_path):
    """A plataforma 5 ganha como a pediatra recebe (6); a prática 4, o CPF da criança e o documento da cobrança (5)."""
    s = config.load(tmp_path)
    pconn = connect_platform(s.data_dir)
    for col in ("billing_mode", "tax_id", "legal_name", "municipal_registration", "tax_regime", "iss_rate"):
        pconn.execute(f"ALTER TABLE practices DROP COLUMN {col}")
    pconn.execute("PRAGMA user_version = 5")
    pconn.close()
    pconn = connect_platform(s.data_dir)
    assert pconn.execute("PRAGMA user_version").fetchone()[0] == PLATFORM_VERSION
    assert {"billing_mode", "tax_id", "iss_rate"} <= {r[1] for r in pconn.execute("PRAGMA table_info(practices)")}
    conn = connect_practice(s.data_dir, 1)
    conn.execute("ALTER TABLE patients DROP COLUMN cpf")
    conn.execute("ALTER TABLE charges DROP COLUMN document_file_id")
    conn.execute("PRAGMA user_version = 4")
    conn.close()
    conn = connect_practice(s.data_dir, 1)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == PRACTICE_VERSION
    assert "cpf" in {r[1] for r in conn.execute("PRAGMA table_info(patients)")}
    assert "document_file_id" in {r[1] for r in conn.execute("PRAGMA table_info(charges)")}

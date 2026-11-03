"""CPF ou CNPJ? (`taxes.py`, a rota em `api_fiscal.py`): a conta do mês com as regras de 2026, só para a pediatra, a
partir do Financeiro da prática dela. Os valores esperados foram feitos à mão, pela tabela."""

from __future__ import annotations

from datetime import date

from conftest import client

from puericorbs import finance, taxes
from puericorbs.db import connect_practice, one


def test_imposto_de_renda_com_a_reducao_de_2026():
    # 6.000: 27,5% − 908,73 = 741,27; a redução é 978,62 − 0,133145 × 6.000 = 179,75
    assert round(taxes.income_tax(6000, 6000), 2) == 561.52
    # o salário de 5.000 com o desconto simplificado: a tabela dá 312,89, e a redução zera
    assert taxes.income_tax(5000 - 607.20, 5000) == 0
    # acima de 7.350 não há redução
    assert round(taxes.income_tax(10000, 10000), 2) == round(10000 * 0.275 - 908.73, 2)
    assert taxes.income_tax(2000, 2000) == 0 and taxes.income_tax(-5, 0) == 0


def test_simples_anexo_iii_e_v():
    assert round(taxes.simples_rate(180000, taxes.ANEXO_III), 4) == 0.06
    assert round(taxes.simples_rate(360000, taxes.ANEXO_III), 4) == 0.086  # 11,2% − 9.360 ÷ 360.000
    assert round(taxes.simples_rate(360000, taxes.ANEXO_V), 4) == 0.1675


def test_pessoa_fisica():
    pf = taxes.individual(8000, 2000)
    by = {line["label"]: line["cents"] for line in pf["lines"]}
    assert by["INSS"] == 160000  # 20% de 8.000
    assert by["Imposto de renda"] == 31451  # (8.000 − 2.000 − 1.600) × 22,5% − 675,49
    assert by["ISS"] == 0  # o médico autônomo é isento em São Paulo
    assert pf["kept_cents"] == 800000 - 200000 - 160000 - 31451
    # o INSS para no teto
    assert {x["label"]: x["cents"] for x in taxes.individual(50000, 0)["lines"]}["INSS"] == 169511


def test_empresa_no_simples():
    pj = taxes.company(30000, 6000, 500)
    by = {line["label"]: line["cents"] for line in pj["lines"]}
    assert pj["salary_cents"] == 840000  # 28% para o Fator R
    assert by["Simples Nacional (DAS)"] == 258000  # 8,6% de 30.000
    assert by["INSS do pró-labore"] == 92400
    assert by["Imposto de renda do pró-labore"] == 114717  # (8.400 − 924) × 27,5% − 908,73
    assert pj["kept_cents"] == 3000000 - 600000 - 258000 - 92400 - 114717 - 50000
    # o lucro acima de R$ 50 mil por mês paga 10%; abaixo, não
    assert "Imposto sobre o lucro" not in by
    big = {x["label"]: x["cents"] for x in taxes.company(150000, 10000, 1000)["lines"]}
    assert big["Imposto sobre o lucro"] > 0
    assert taxes.company(500000, 0, 0)["eligible"] is False  # 6 milhões por ano: fora do Simples
    # pró-labore de 5.250: o INSS (577,50) é menor que o desconto simplificado (607,20), que vale mais
    # (5.250 − 607,20) × 22,5% − 675,49 = 369,14; a redução é 978,62 − 0,133145 × 5.250 = 279,61
    mid = {x["label"]: x["cents"] for x in taxes.company(18750, 0, 0)["lines"]}
    assert mid["Imposto de renda do pró-labore"] == 8953


def test_quem_deixa_mais_e_a_partir_de_quanto():
    low = taxes.compare(300000, 50000, 40000)
    assert low["best"] == "pf" and low["diff_year_cents"] == 12 * low["diff_month_cents"]
    high = taxes.compare(3000000, 600000, 50000)
    assert high["best"] == "pj" and high["diff_month_cents"] > 0
    assert 300000 < high["break_even_cents"] < 3000000
    assert not high["notes"]
    assert any("600 mil" in n for n in taxes.compare(6000000, 0, 0)["notes"])
    assert any("Lucro Presumido" in n for n in taxes.compare(20000000, 0, 0)["notes"])
    assert taxes.compare(0, 0, 0)["pf"]["kept_cents"] == 0


def test_so_a_pediatra_faz_a_conta_e_com_o_financeiro_dela(fresh):
    for who in ("carla@demo.test", "bia@demo.test", "ana@demo.test"):
        assert client(fresh, "dramarina.localhost", who).get("/api/staff/fiscal/compare").status_code == 403, who
    for host, email, pid in (("dramarina.localhost", "marina@demo.test", 1), ("drpauloreis.localhost", "paulo@demo.test", 2)):
        r = client(fresh, host, email).get("/api/staff/fiscal/compare")
        assert r.status_code == 200, r.text
        h = r.json()["history"]
        conn = connect_practice(fresh.data_dir, pid)
        today = date.today().isoformat()
        first, last = finance.shift_month(today[:7], -3) + "-01", today[:7] + "-01"
        got = one(conn, "SELECT COALESCE(SUM(amount_cents), 0) AS s FROM charges WHERE status = 'paga' AND paid_on >= ? "
                        "AND paid_on < ?", (first, last))["s"]
        assert h["revenue_cents"] == got // 3 and r.json()["inputs"]["revenue_cents"] == got // 3, email
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    # a cobrança em aberto não é dinheiro recebido: a média não muda
    before = marina.get("/api/staff/fiscal/compare").json()["history"]
    conn = connect_practice(fresh.data_dir, 1)
    conn.execute("""INSERT INTO charges (family_id, description, amount_cents, due_on, paid_on, status, invoice, created_at)
                    SELECT family_id, 'teste', 9000000, ?, ?, 'aberta', 'emitir', created_at FROM charges LIMIT 1""",
                 (finance.shift_month(date.today().isoformat()[:7], -1) + "-10",) * 2)
    conn.commit()
    assert marina.get("/api/staff/fiscal/compare").json()["history"] == before
    r = marina.get("/api/staff/fiscal/compare?revenue_cents=3000000&expenses_cents=600000&accountant_cents=50000").json()
    assert r["best"] == "pj" and r["inputs"]["expenses_cents"] == 600000 and r["year"] == 2026
    bad = marina.get("/api/staff/fiscal/compare?revenue_cents=-1")
    assert bad.status_code == 400 and "por mês" in bad.json()["detail"]

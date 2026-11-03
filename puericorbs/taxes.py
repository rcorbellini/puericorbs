"""CPF ou CNPJ? A conta do mês, para a pediatra decidir como recebe (`fiscal.py`). Por ora, na cidade de São Paulo.

Compara, com o que ela recebe e gasta por mês, quanto fica com ela atendendo como pessoa física (o carnê-leão) e com
uma empresa no Simples Nacional (o Anexo III, com o pró-labore em 28% do faturamento para o Fator R). É uma estimativa
para conversar com o contador, não a apuração: as regras e os números abaixo são os de 2026, cada um com a fonte, e
mudam todo ano (`RULES_YEAR`).

- **Pessoa física:**
  - **INSS:** 20% do que recebe, entre o salário mínimo e o teto (contribuinte individual que atende pessoa física).
  - **Imposto de renda:** a tabela mensal, sobre o que recebe menos o livro-caixa (aluguel, secretária, contador,
    material de consumo) e o INSS, com a redução da Lei 15.270/2025. Aqui a redução entra pelo que ela recebe, antes
    das deduções: assim a conta nunca promete imposto de menos.
  - **ISS:** o médico autônomo em São Paulo é isento (código 4073, Lei 14.864/2008; tabela da Prefeitura de 2026).
- **Empresa no Simples Nacional (Anexo III):**
  - **O DAS:** a alíquota efetiva sobre o faturamento, com o faturamento dos últimos 12 meses igual a 12 vezes o mês.
    Já leva o ISS e o INSS da empresa.
  - **O pró-labore:** 28% do faturamento, nunca menos que o salário mínimo. Abaixo de 28%, a empresa cai no Anexo V,
    bem mais caro. Sobre ele, o INSS de 11% (até o teto) e o imposto de renda na fonte.
  - **O lucro:** o resto sai como lucro, isento até R$ 50 mil por mês da mesma empresa. Acima disso, 10% retidos
    sobre o total (Lei 15.270/2025).
  - **O que a empresa paga:** as despesas do consultório e o contador, que aqui não reduzem imposto (o DAS é sobre o
    faturamento).

Fora da conta, e o contador vê: o Lucro Presumido, o imposto mínimo de quem ganha mais de R$ 600 mil por ano, o ajuste
anual da declaração e a reforma tributária (a CBS e o IBS, que em 2026 só aparecem na nota).
"""

from __future__ import annotations

RULES_YEAR = 2026
MIN_WAGE = 1621.00  # salário mínimo de 2026
INSS_CEILING = 8475.55  # teto do INSS em 2026 (Portaria Interministerial MPS/MF 13/2026)
SIMPLIFIED_DISCOUNT = 607.20  # o desconto simplificado mensal do imposto na fonte, no lugar das deduções
DIVIDEND_FREE = 50000.00  # lucro por mês, da mesma empresa, sem a retenção de 10%
SIMPLES_CEILING = 4800000.00
FACTOR_R = 0.28

# (até, alíquota, parcela a deduzir): a tabela mensal do imposto de renda, a mesma desde maio de 2025
IR_TABLE = [(2428.80, 0.0, 0.0), (2826.65, 0.075, 182.16), (3751.05, 0.15, 394.16), (4664.68, 0.225, 675.49),
            (float("inf"), 0.275, 908.73)]
# (receita bruta em 12 meses até, alíquota nominal, parcela a deduzir): os Anexos III e V da LC 123/2006
ANEXO_III = [(180000, 0.06, 0), (360000, 0.112, 9360), (720000, 0.135, 17640), (1800000, 0.16, 35640),
             (3600000, 0.21, 125640), (4800000, 0.33, 648000)]
ANEXO_V = [(180000, 0.155, 0), (360000, 0.18, 4500), (720000, 0.195, 9900), (1800000, 0.205, 17100),
           (3600000, 0.23, 62100), (4800000, 0.305, 540000)]

SOURCES = [
    ("A tabela do imposto de renda e a redução de 2026 (Lei 15.270/2025)",
     "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/L15270.htm"),
    ("O ISS do médico autônomo em São Paulo: isento (Prefeitura, tabela de 2026)",
     "https://prefeitura.sp.gov.br/documents/d/fazenda/autonomos2026-pdf"),
    ("O Simples Nacional, Anexos III e V (LC 123/2006)",
     "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp123.htm"),
]


def income_tax(base: float, gross: float) -> float:
    """O imposto de renda do mês: a tabela sobre a base, menos a redução de 2026, que é calculada sobre o bruto."""
    if base <= 0:
        return 0.0
    rate, deduct = next((r, d) for top, r, d in IR_TABLE if base <= top)
    tax = max(0.0, base * rate - deduct)
    if gross <= 5000:
        cut = 312.89
    elif gross <= 7350:
        cut = max(0.0, 978.62 - 0.133145 * gross)
    else:
        cut = 0.0
    return round(max(0.0, tax - min(tax, cut)), 2)


def simples_rate(revenue_12m: float, table: list) -> float:
    """A alíquota efetiva do Simples: (receita de 12 meses × nominal − parcela) ÷ receita de 12 meses."""
    if revenue_12m <= 0:
        return table[0][1]
    _, rate, deduct = next(row for row in table if revenue_12m <= row[0])
    return (revenue_12m * rate - deduct) / revenue_12m


def _cents(value: float) -> int:
    return round(value * 100)


def _scenario(lines: list[tuple[str, float, str]], revenue: float, kept: float) -> dict:
    tax = sum(v for _, v, _ in lines)
    return {
        "lines": [{"label": label, "cents": _cents(v), "note": note} for label, v, note in lines],
        "tax_cents": _cents(tax), "kept_cents": _cents(kept),
        "tax_pct": round(100 * tax / revenue, 1) if revenue else 0.0,
    }


def individual(revenue: float, expenses: float) -> dict:
    """Pessoa física: o carnê-leão, o INSS de contribuinte individual e o livro-caixa."""
    inss = 0.20 * min(max(revenue, MIN_WAGE), INSS_CEILING) if revenue > 0 else 0.0
    book = min(expenses, revenue)  # o livro-caixa nunca passa do que entrou no mês
    ir = income_tax(revenue - book - inss, revenue)
    lines = [("INSS", inss, "20%, até o teto"),
             ("Imposto de renda", ir, "carnê-leão, com o livro-caixa"),
             ("ISS", 0.0, "isento em São Paulo")]
    return _scenario(lines, revenue, revenue - expenses - inss - ir)


def company(revenue: float, expenses: float, accountant: float) -> dict:
    """Empresa no Simples Nacional, Anexo III: o DAS, o pró-labore em 28% e o lucro."""
    yearly = revenue * 12
    if yearly > SIMPLES_CEILING:
        return {"eligible": False, "lines": [], "tax_cents": 0, "kept_cents": 0, "tax_pct": 0.0}
    rate = simples_rate(yearly, ANEXO_III)
    das = revenue * rate
    salary = max(MIN_WAGE, FACTOR_R * revenue) if revenue > 0 else 0.0
    inss = 0.11 * min(salary, INSS_CEILING)
    irrf = income_tax(salary - max(inss, SIMPLIFIED_DISCOUNT), salary)
    profit = revenue - das - salary - expenses - accountant
    dividend_tax = 0.10 * profit if profit > DIVIDEND_FREE else 0.0
    lines = [("Simples Nacional (DAS)", das, f"{100 * rate:.2f}%, já com o ISS".replace(".", ",")),
             ("INSS do pró-labore", inss, "11%, até o teto"),
             ("Imposto de renda do pró-labore", irrf, "na fonte"),
             ("Contador", accountant, "a mensalidade")]
    if dividend_tax:
        lines.append(("Imposto sobre o lucro", dividend_tax, "10% retidos, acima de R$ 50 mil no mês; ajuste na declaração"))
    out = _scenario(lines, revenue, revenue - expenses - das - inss - irrf - accountant - dividend_tax)
    out.update(eligible=True, salary_cents=_cents(salary), rate_pct=round(100 * rate, 2),
               rate_v_pct=round(100 * simples_rate(yearly, ANEXO_V), 2))
    return out


def break_even(expense_share: float, accountant: float) -> int | None:
    """O faturamento mensal a partir do qual a empresa deixa mais com a pediatra, com a mesma parte em despesas."""
    for step in range(8, 600):  # de R$ 2.000 a R$ 150.000, de R$ 250 em R$ 250
        revenue = step * 250.0
        expenses = revenue * expense_share
        pj = company(revenue, expenses, accountant)
        if pj["eligible"] and pj["kept_cents"] > individual(revenue, expenses)["kept_cents"]:
            return _cents(revenue)
    return None


def compare(revenue_cents: int, expenses_cents: int, accountant_cents: int) -> dict:
    """As duas contas lado a lado, quem deixa mais por mês e por ano, e a partir de quanto a empresa compensa."""
    revenue, expenses, accountant = revenue_cents / 100, expenses_cents / 100, accountant_cents / 100
    pf, pj = individual(revenue, expenses), company(revenue, expenses, accountant)
    if not pj["eligible"]:
        best = None
    elif pj["kept_cents"] > pf["kept_cents"]:
        best = "pj"
    elif pj["kept_cents"] < pf["kept_cents"]:
        best = "pf"
    else:
        best = None
    diff = abs(pj["kept_cents"] - pf["kept_cents"]) if pj["eligible"] else 0
    notes = []
    if revenue * 12 > 600000:
        notes.append("Acima de R$ 600 mil por ano, entra o imposto mínimo da Lei 15.270/2025, nos dois caminhos: "
                     "o contador faz essa conta na declaração.")
    if revenue * 12 > 1800000:
        notes.append("Acima de R$ 1,8 milhão por ano, o Simples fica caro e o Lucro Presumido, que esta conta não "
                     "faz, costuma deixar mais: leve ao contador antes de decidir pela pessoa física.")
    if not pj["eligible"]:
        notes.append("Acima de R$ 4,8 milhões por ano, a empresa não cabe no Simples Nacional.")
    return {
        "year": RULES_YEAR, "city": "São Paulo",
        "inputs": {"revenue_cents": revenue_cents, "expenses_cents": expenses_cents,
                   "accountant_cents": accountant_cents},
        "pf": pf, "pj": pj, "best": best, "diff_month_cents": diff, "diff_year_cents": diff * 12,
        "break_even_cents": break_even(expenses / revenue if revenue else 0.0, accountant),
        "notes": notes, "sources": [{"label": label, "url": url} for label, url in SOURCES],
    }

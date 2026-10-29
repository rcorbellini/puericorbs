"""Como a pediatra recebe e o documento que a família leva de cada pagamento. Por enquanto, só em São Paulo (capital).

- **Pessoa física:** o recibo do Receita Saúde (obrigatório desde 1º/01/2025, IN RFB 2.240/2024). A Receita não tem
  API: a pediatra emite no app da Receita Federal ou no e-CAC (Carnê-Leão Web), ou a recepção emite por ela, com uma
  procuração eletrônica no e-CAC. O Puericorbs junta os dados de cada pagamento para copiar, e o PDF anexado chega à
  família pelo app.
- **Empresa (CNPJ):** a nota fiscal de serviço (NFS-e). Em São Paulo, o Simples Nacional emite pelo Emissor Nacional
  (desde 1º/11/2026, Resolução CGSN 191/2026), e o Lucro Presumido pela Nota Fiscal Paulistana. Hoje o Puericorbs
  prepara os dados e guarda o PDF; a emissão automática entra quando a empresa tiver o certificado digital
  (`docs/pagamentos.md`).

O que vai no documento sai daqui (`document`): quem pagou (o responsável financeiro), quem foi atendido (a criança),
o valor, a data e o serviço, e o que falta no cadastro para emitir.
"""

from __future__ import annotations

import re
import sqlite3

from fastapi import HTTPException

from . import catalog
from .db import one

MODES = {"pf": "Pessoa física", "pj": "Empresa (CNPJ)"}
REGIMES = {"simples": "Simples Nacional", "presumido": "Lucro Presumido"}
CITY = "São Paulo"
# onde se emite, para a recepção abrir com um toque
PORTALS = {
    "pf": ("o e-CAC", "https://cav.receita.fazenda.gov.br",
           "No app Receita Federal (Receita Saúde) ou no e-CAC, em Carnê-Leão Web."),
    "simples": ("o Emissor Nacional", "https://www.nfse.gov.br/EmissorNacional",
                "Em São Paulo, a empresa do Simples Nacional emite a nota pelo Emissor Nacional."),
    "presumido": ("a Nota Fiscal Paulistana", "https://nfe.prefeitura.sp.gov.br",
                  "Em São Paulo, a empresa do Lucro Presumido emite a nota pela Nota Fiscal Paulistana."),
}


def digits(text: str | None) -> str:
    return re.sub(r"\D", "", text or "")


def _check(numbers: list[int], weights: list[int]) -> int:
    rest = sum(n * w for n, w in zip(numbers, weights)) % 11
    return 0 if rest < 2 else 11 - rest


def cpf_ok(text: str | None) -> bool:
    d = [int(c) for c in digits(text)]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    return d[9] == _check(d[:9], list(range(10, 1, -1))) and d[10] == _check(d[:10], list(range(11, 1, -1)))


def cnpj_ok(text: str | None) -> bool:
    d = [int(c) for c in digits(text)]
    if len(d) != 14 or len(set(d)) == 1:
        return False
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return d[12] == _check(d[:12], w1) and d[13] == _check(d[:13], [6] + w1)


def fmt_cpf(text: str | None) -> str:
    d = digits(text)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else (text or "")


def fmt_cnpj(text: str | None) -> str:
    d = digits(text)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else (text or "")


def clean_cpf(text: str | None, what: str) -> str | None:
    """O CPF guardado só com os números; vazio vira nada; inválido é recusado, dizendo de quem é."""
    if not digits(text):
        return None
    if not cpf_ok(text):
        raise HTTPException(400, f"Confira o CPF {what}: os números não fecham.")
    return digits(text)


def portal(key: str) -> dict:
    name, url, how = PORTALS[key]
    return {"name": name, "url": url, "how": how}


def profile(practice: dict) -> dict:
    """Como a pediatra recebe, para a tela: o modo, o CPF ou o CNPJ formatado e onde se emite."""
    mode = practice.get("billing_mode")
    regime = practice.get("tax_regime")
    where = ("pf" if mode == "pf" else regime) if mode else None
    tax_id = practice.get("tax_id")
    return {
        "mode": mode, "mode_label": MODES.get(mode or ""), "city": CITY,
        "tax_id": fmt_cpf(tax_id) if mode == "pf" else fmt_cnpj(tax_id) if tax_id else None,
        "legal_name": practice.get("legal_name"), "municipal_registration": practice.get("municipal_registration"),
        "regime": regime, "regime_label": REGIMES.get(regime or ""), "iss_rate": practice.get("iss_rate"),
        "document": ("recibo" if mode == "pf" else "nota") if mode else None,
        "portal": portal(where) if where in PORTALS else None,
    }


def document(conn: sqlite3.Connection, practice: dict, charge: dict) -> dict:
    """Tudo o que o recibo (ou a nota) de uma cobrança pede, pronto para copiar, e o que falta no cadastro."""
    fam = charge["family_id"]
    payer = one(conn, """SELECT * FROM guardians WHERE family_id = ? ORDER BY is_financial DESC, is_legal DESC, id
                         LIMIT 1""", (fam,))
    child = one(conn, "SELECT * FROM patients WHERE id = ?", (charge["patient_id"],)) if charge["patient_id"] else None
    service = None
    if charge["appointment_id"]:
        service = one(conn, """SELECT s.* FROM appointments a JOIN services s ON s.id = a.service_id
                               WHERE a.id = ?""", (charge["appointment_id"],))
    prof = profile(practice)
    missing = []
    if not prof["mode"]:
        missing.append("como a pediatra recebe (Consultório)")
    if not payer or not payer["cpf"]:
        missing.append("o CPF de quem pagou")
    if prof["mode"] == "pf" and child and not child["cpf"]:
        missing.append("o CPF da criança")
    description = charge["description"]
    if child:
        description = f"{description} · {child['name']}"
    return {
        "charge_id": charge["id"], "amount_cents": charge["amount_cents"], "paid_on": charge["paid_on"],
        "method": charge["method"], "service": charge["description"], "description": description,
        "service_code": catalog.config_of(service)["invoice"]["code"] if service else "04.01",
        "payer": {"id": payer["id"], "name": payer["name"], "relation": payer["relation"],
                  "cpf": fmt_cpf(payer["cpf"]) if payer["cpf"] else None, "phone": payer["phone"]} if payer else None,
        "child": {"id": child["id"], "name": child["name"],
                  "cpf": fmt_cpf(child["cpf"]) if child["cpf"] else None} if child else None,
        "profile": prof, "missing": missing, "file_id": charge.get("document_file_id"),
    }


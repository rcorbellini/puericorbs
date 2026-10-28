"""O catálogo de serviços: a ficha de cada serviço e os modelos de registro.

O serviço é a unidade de configuração: a agenda pega dele a duração, os turnos e quem pode marcar; o dinheiro, o
preço; o plano, a cota; o prontuário, o modelo de registro; a nota fiscal, o código. As colunas guardam o que a busca
e a agenda precisam; o resto da ficha mora em `config` (JSON), mesclado com DEFAULT_CONFIG.
"""

from __future__ import annotations

import copy
import json

KINDS = {
    "newborn": "Recém-nascido",
    "well_child": "Puericultura",
    "sick_visit": "Por doença",
    "follow_up": "Retorno",
    "prenatal": "Pré-natal pediátrica",
    "home_visit": "Visita domiciliar",
    "telehealth": "Teleconsulta",
    "procedure": "Procedimento",
    "report": "Documento",
}
CATEGORIES = {"consulta": "Consultas", "fora": "Fora do consultório", "procedimento": "Procedimentos e documentos"}

DEFAULT_CONFIG: dict = {
    "family_text": "",
    "age_min_m": None,
    "age_max_m": None,
    "shifts": ["manha", "tarde"],
    "booking": {"reception": True, "family": True, "public": False, "min_notice_h": 2, "max_days": 60,
                "squeeze": True},
    "plan_mode": "cota",          # cota (entra na cota do plano) | desconto (só o desconto do plano) | fora
    "return_free": False,
    "return_days": 15,
    "no_show_fee_cents": 0,
    "prepay": False,
    "cancel_hours": 24,
    "template": "livre",
    "questions": [],
    "after": {"next_by_protocol": False, "guidance": False, "attendance_statement": True, "survey": False},
    "invoice": {"code": "04.01", "description": "", "auto": True},
}

# os modelos de registro: os campos que o pediatra preenche na consulta (o construtor de modelos é o próximo passo)
TEMPLATES: dict[str, dict] = {
    "puericultura": {
        "label": "Puericultura",
        "measures": ["weight", "length", "head"],
        "fields": [
            {"key": "queixas", "label": "Queixas e intercorrências", "type": "textarea"},
            {"key": "alimentacao", "label": "Alimentação", "type": "textarea"},
            {"key": "sono", "label": "Sono e rotina", "type": "textarea"},
            {"key": "desenvolvimento", "label": "Desenvolvimento", "type": "milestones"},
            {"key": "exame", "label": "Exame físico", "type": "textarea"},
        ],
    },
    "recem_nascido": {
        "label": "Recém-nascido",
        "measures": ["weight", "length", "head"],
        "fields": [
            {"key": "gestacao", "label": "Gestação e parto", "type": "textarea"},
            {"key": "alimentacao", "label": "Amamentação", "type": "textarea"},
            {"key": "triagens", "label": "Triagens neonatais", "type": "checks",
             "options": ["Teste do pezinho", "Teste da orelhinha", "Teste do olhinho", "Teste do coraçãozinho",
                         "Teste da linguinha"]},
            {"key": "exame", "label": "Exame físico", "type": "textarea"},
        ],
    },
    "intercorrencia": {
        "label": "Consulta por doença",
        "measures": ["weight"],
        "fields": [
            {"key": "queixa", "label": "Queixa e história", "type": "textarea"},
            {"key": "sinais", "label": "Sinais vitais", "type": "text",
             "placeholder": "temperatura, frequência respiratória, saturação"},
            {"key": "exame", "label": "Exame físico", "type": "textarea"},
        ],
    },
    "retorno": {
        "label": "Retorno",
        "measures": [],
        "fields": [
            {"key": "evolucao", "label": "Evolução", "type": "textarea"},
            {"key": "exame", "label": "Exame físico", "type": "textarea"},
        ],
    },
    "livre": {
        "label": "Livre",
        "measures": [],
        "fields": [{"key": "anotacoes", "label": "Anotações", "type": "textarea"}],
    },
}


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def config_of(row: dict) -> dict:
    try:
        extra = json.loads(row.get("config") or "{}")
    except ValueError:
        extra = {}
    return _merge(DEFAULT_CONFIG, extra)


def template_of(row: dict) -> dict:
    cfg = config_of(row)
    return TEMPLATES.get(cfg["template"], TEMPLATES["livre"])


def as_dict(row: dict) -> dict:
    cfg = config_of(row)
    return {
        "id": row["id"], "name": row["name"], "category": row["category"], "kind": row["kind"],
        "kind_label": KINDS.get(row["kind"], row["kind"]), "duration_min": row["duration_min"],
        "price_cents": row["price_cents"], "active": bool(row["active"]), "version": row["version"],
        "position": row["position"], "config": cfg,
    }


def age_months(age_days: int) -> float:
    return age_days / 30.44


def fits_age(row: dict, age_days: int) -> bool:
    cfg = config_of(row)
    m = age_months(age_days)
    if cfg["age_min_m"] is not None and m < cfg["age_min_m"]:
        return False
    if cfg["age_max_m"] is not None and m > cfg["age_max_m"]:
        return False
    return True


def default_services() -> list[dict]:
    """O catálogo com que toda prática nova começa (o pediatra edita tudo)."""
    def svc(name, category, kind, duration, price, position, **cfg):
        return {"name": name, "category": category, "kind": kind, "duration_min": duration,
                "price_cents": price * 100, "position": position, "config": cfg}
    return [
        svc("Primeira consulta do recém-nascido", "consulta", "newborn", 60, 600, 1, template="recem_nascido",
            age_max_m=1, family_text="A primeira consulta do bebê, de preferência na primeira semana.",
            after={"next_by_protocol": True, "guidance": True}),
        svc("Puericultura", "consulta", "well_child", 40, 450, 2, template="puericultura", age_max_m=144,
            shifts=["manha"], return_free=True, return_days=15, no_show_fee_cents=15000,
            family_text="Acompanhamento do crescimento e do desenvolvimento, com as vacinas em dia.",
            questions=["Como está o sono?", "Como está a alimentação?", "Alguma vacina tomada fora daqui?",
                       "Algo novo no desenvolvimento?", "Alguma dúvida que queira trazer?"],
            after={"next_by_protocol": True, "guidance": True, "survey": True},
            invoice={"description": "Consulta pediátrica de puericultura"}),
        svc("Consulta por doença", "consulta", "sick_visit", 30, 380, 3, template="intercorrencia",
            booking={"min_notice_h": 0, "max_days": 2},
            family_text="Para quando a criança está doente. As vagas do dia abrem às 7h."),
        svc("Retorno", "consulta", "follow_up", 20, 0, 4, template="retorno", plan_mode="fora",
            booking={"family": False}, family_text="A volta depois de uma consulta, sem custo dentro do prazo."),
        svc("Consulta pré-natal pediátrica", "consulta", "prenatal", 40, 400, 5, template="livre",
            booking={"family": False}, family_text="Uma conversa com a gestante antes do bebê nascer."),
        svc("Visita domiciliar", "fora", "home_visit", 60, 650, 6, template="puericultura", shifts=["tarde"],
            booking={"min_notice_h": 48},
            family_text="A consulta na sua casa, nos primeiros dias do bebê."),
        svc("Teleconsulta", "fora", "telehealth", 20, 250, 7, template="livre", booking={"family": False}),
        svc("Teste da linguinha", "procedimento", "procedure", 20, 250, 8, template="livre", age_max_m=3),
        svc("Relatório para a escola", "procedimento", "report", 20, 120, 9, template="livre",
            booking={"family": False}),
    ]

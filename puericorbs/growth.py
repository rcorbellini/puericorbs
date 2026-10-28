"""As curvas de crescimento da OMS: escore-z, percentil e as linhas de referência dos gráficos.

As tabelas (`data/who_lms.json`) vêm do pacote anthro da própria OMS: L, M e S por dia de vida, de 0 a 1826 dias, para
meninos e meninas. O escore-z sai da fórmula LMS; para peso e IMC além de ±3, a OMS manda medir a distância em
unidades do intervalo entre 2 e 3 desvios (o "z restrito"), e é isso que `z_score` faz.
"""

from __future__ import annotations

import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).parent / "data" / "who_lms.json"

INDICATORS = {
    "wfa": {"label": "Peso", "unit": "kg", "field": "weight_kg"},
    "lhfa": {"label": "Comprimento", "unit": "cm", "field": "length_cm"},
    "hcfa": {"label": "Perímetro cefálico", "unit": "cm", "field": "head_cm"},
    "bfa": {"label": "IMC", "unit": "kg/m²", "field": None},
}

# os escores-z das linhas que o gráfico desenha
PCT_Z = {3: -1.880794, 15: -1.036433, 50: 0.0, 85: 1.036433, 97: 1.880794}
MAX_DAY = 1826


@lru_cache(maxsize=1)
def _tables() -> dict:
    return json.loads(DATA.read_text())


def lms(indicator: str, sex: str, day: float) -> tuple[float, float, float]:
    table = _tables()[indicator][sex]
    d = max(0, min(len(table) - 1, int(round(day))))
    l, m, s = table[d]
    return l, m, s


def value_at(indicator: str, sex: str, day: float, z: float) -> float:
    l, m, s = lms(indicator, sex, day)
    if abs(l) < 1e-9:
        return m * math.exp(s * z)
    return m * (1 + l * s * z) ** (1 / l)


def z_score(indicator: str, sex: str, day: float, value: float) -> float:
    l, m, s = lms(indicator, sex, day)
    if value <= 0:
        raise ValueError("a medida precisa ser maior que zero")
    z = math.log(value / m) / s if abs(l) < 1e-9 else ((value / m) ** l - 1) / (l * s)
    if indicator in ("wfa", "bfa") and abs(z) > 3:
        sd3 = value_at(indicator, sex, day, 3 if z > 0 else -3)
        sd2 = value_at(indicator, sex, day, 2 if z > 0 else -2)
        z = (3 if z > 0 else -3) + (value - sd3) / abs(sd3 - sd2)
    return z


def percentile(z: float) -> float:
    return 50 * (1 + math.erf(z / math.sqrt(2)))


def age_days(birth: date, on: date) -> int:
    return (on - birth).days


def corrected_days(birth: date, on: date, gestational_weeks: int | None) -> tuple[int, bool]:
    """A idade usada nas curvas: corrigida para o prematuro (< 37 semanas) até os 2 anos de idade cronológica."""
    days = age_days(birth, on)
    if gestational_weeks and gestational_weeks < 37 and days < 730:
        return max(0, days - (40 - gestational_weeks) * 7), True
    return days, False


def reading(z: float) -> str:
    """A frase para a família: sem número, sem susto."""
    if z < -2:
        return "abaixo do esperado para a idade"
    if z > 2:
        return "acima do esperado para a idade"
    return "dentro do esperado para a idade"


def pct_label(z: float) -> str:
    p = percentile(z)
    if p < 1:
        return "abaixo do P1"
    if p > 99:
        return "acima do P99"
    return f"P{round(p)}"


def assess(sex: str, birth: date, on: date, gestational_weeks: int | None = None, *, weight_kg: float | None = None,
           length_cm: float | None = None, head_cm: float | None = None) -> dict:
    """Percentil e escore-z de cada medida informada, na idade (corrigida, se for o caso) do dia `on`."""
    day, corrected = corrected_days(birth, on, gestational_weeks)
    out: dict = {"age_days": day, "corrected": corrected, "measures": {}}
    if day > MAX_DAY:
        out["out_of_range"] = True
        return out
    for key, value in (("wfa", weight_kg), ("lhfa", length_cm), ("hcfa", head_cm)):
        if value:
            z = z_score(key, sex, day, value)
            out["measures"][key] = {"value": value, "z": round(z, 2), "percentile": round(percentile(z), 1),
                                    "label": pct_label(z), "reading": reading(z)}
    if weight_kg and length_cm:
        bmi = weight_kg / (length_cm / 100) ** 2
        z = z_score("bfa", sex, day, bmi)
        out["measures"]["bfa"] = {"value": round(bmi, 1), "z": round(z, 2), "percentile": round(percentile(z), 1),
                                  "label": pct_label(z), "reading": reading(z)}
    return out


def curves(indicator: str, sex: str, day_to: int, points: int = 60) -> dict[int, list[list[float]]]:
    """As linhas P3, P15, P50, P85 e P97 de 0 até `day_to`, com `points` pontos cada (para o gráfico)."""
    day_to = max(30, min(MAX_DAY, day_to))
    step = day_to / points
    days = [round(i * step) for i in range(points + 1)]
    return {p: [[d, round(value_at(indicator, sex, d, z), 3)] for d in days] for p, z in PCT_Z.items()}

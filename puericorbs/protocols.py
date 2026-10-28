"""Os protocolos que geram o "a fazer" pela idade: as consultas da puericultura, as vacinas e os marcos.

São o modelo inicial de toda prática, para o pediatra revisar: o calendário de consultas segue o mínimo do Ministério
da Saúde (1ª semana, 1, 2, 4, 6, 9, 12, 18 e 24 meses e depois uma por ano), as vacinas seguem o calendário do PNI
até os 4 anos, sem as de campanha, e os marcos são uma versão simples, em linguagem de família, dos da Caderneta da
Criança. Editar por prática é o próximo passo (docs/funcionalidades.md, seção 2).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Visit:
    code: str
    title: str
    day: int        # a idade-alvo, em dias
    before: int     # quantos dias antes a janela abre
    after: int      # quantos dias depois ela fecha


WELL_CHILD = [
    Visit("1sem", "Primeira consulta", 7, 4, 7),
    Visit("1m", "Consulta de 1 mês", 30, 7, 10),
    Visit("2m", "Consulta dos 2 meses", 61, 7, 10),
    Visit("4m", "Consulta dos 4 meses", 122, 7, 14),
    Visit("6m", "Consulta dos 6 meses", 183, 7, 14),
    Visit("9m", "Consulta dos 9 meses", 274, 14, 21),
    Visit("12m", "Consulta de 1 ano", 365, 7, 21),
    Visit("18m", "Consulta de 1 ano e meio", 548, 14, 30),
    Visit("24m", "Consulta de 2 anos", 730, 14, 30),
] + [Visit(f"{y}a", f"Consulta de {y} anos", round(365.25 * y), 30, 60) for y in range(3, 11)]


@dataclass(frozen=True)
class Dose:
    code: str
    vaccine: str
    dose: str
    day: int
    group: str      # o nome do grupo para a família ("Vacinas dos 4 meses")


VACCINES = [
    Dose("bcg", "BCG", "dose única", 0, "ao nascer"),
    Dose("hepb-0", "Hepatite B", "ao nascer", 0, "ao nascer"),
    Dose("penta-1", "Penta", "1ª dose", 61, "dos 2 meses"),
    Dose("vip-1", "VIP (pólio)", "1ª dose", 61, "dos 2 meses"),
    Dose("pneumo-1", "Pneumo 10", "1ª dose", 61, "dos 2 meses"),
    Dose("rota-1", "Rotavírus", "1ª dose", 61, "dos 2 meses"),
    Dose("menc-1", "Meningocócica C", "1ª dose", 91, "dos 3 meses"),
    Dose("penta-2", "Penta", "2ª dose", 122, "dos 4 meses"),
    Dose("vip-2", "VIP (pólio)", "2ª dose", 122, "dos 4 meses"),
    Dose("pneumo-2", "Pneumo 10", "2ª dose", 122, "dos 4 meses"),
    Dose("rota-2", "Rotavírus", "2ª dose", 122, "dos 4 meses"),
    Dose("menc-2", "Meningocócica C", "2ª dose", 152, "dos 5 meses"),
    Dose("penta-3", "Penta", "3ª dose", 183, "dos 6 meses"),
    Dose("vip-3", "VIP (pólio)", "3ª dose", 183, "dos 6 meses"),
    Dose("gripe-1", "Gripe", "1ª dose", 183, "dos 6 meses"),
    Dose("fa-1", "Febre amarela", "1ª dose", 274, "dos 9 meses"),
    Dose("scr-1", "Tríplice viral", "1ª dose", 365, "de 1 ano"),
    Dose("pneumo-r", "Pneumo 10", "reforço", 365, "de 1 ano"),
    Dose("menc-r", "Meningocócica", "reforço", 365, "de 1 ano"),
    Dose("dtp-r1", "DTP", "1º reforço", 456, "dos 15 meses"),
    Dose("vip-r1", "VIP (pólio)", "reforço", 456, "dos 15 meses"),
    Dose("hepa-1", "Hepatite A", "dose única", 456, "dos 15 meses"),
    Dose("tetra-1", "Tetra viral", "dose única", 456, "dos 15 meses"),
    Dose("dtp-r2", "DTP", "2º reforço", 1461, "dos 4 anos"),
    Dose("varic-2", "Varicela", "2ª dose", 1461, "dos 4 anos"),
    Dose("fa-r", "Febre amarela", "reforço", 1461, "dos 4 anos"),
]
VACCINE_BY_CODE = {d.code: d for d in VACCINES}


@dataclass(frozen=True)
class Milestone:
    code: str
    label: str
    day_from: int
    day_to: int


@dataclass(frozen=True)
class MilestoneBand:
    title: str
    day_from: int
    day_to: int
    items: tuple[Milestone, ...]


def _band(title: str, m_from: int, m_to: int, *labels: tuple[str, str]) -> MilestoneBand:
    d_from, d_to = round(m_from * 30.44), round(m_to * 30.44)
    return MilestoneBand(title, d_from, d_to, tuple(Milestone(code, label, d_from, d_to) for code, label in labels))


MILESTONES = [
    _band("Marcos até os 2 meses", 0, 2, ("sorri", "Sorri quando alguém conversa"), ("olhar", "Fixa o olhar no rosto")),
    _band("Marcos dos 2 aos 4 meses", 2, 4, ("cabeca", "Sustenta a cabeça"), ("balbucia", "Ri alto e balbucia"),
          ("segura", "Segura objetos com a mão")),
    _band("Marcos dos 4 aos 6 meses", 4, 6, ("rola", "Rola sozinho"), ("boca", "Pega objetos e leva à boca"),
          ("senta-apoio", "Senta com apoio")),
    _band("Marcos dos 6 aos 9 meses", 6, 9, ("senta", "Senta sem apoio"), ("engatinha", "Engatinha"),
          ("estranha", "Estranha pessoas desconhecidas"), ("silabas", "Repete sílabas (mamã, papá)")),
    _band("Marcos dos 9 aos 12 meses", 9, 12, ("pinca", "Pinça com o polegar e o indicador"),
          ("pe-apoio", "Fica em pé com apoio"), ("tchau", "Dá tchau e bate palmas")),
    _band("Marcos de 1 ano a 1 ano e meio", 12, 18, ("anda", "Anda sozinho"), ("palavras", "Fala as primeiras palavras"),
          ("aponta", "Aponta o que quer")),
    _band("Marcos de 1 ano e meio a 2 anos", 18, 24, ("corre", "Corre"), ("frase", "Junta duas palavras"),
          ("chuta", "Chuta uma bola")),
    _band("Marcos de 2 a 3 anos", 24, 36, ("pula", "Pula com os dois pés"), ("nome", "Diz o próprio nome"),
          ("brinca", "Brinca de faz de conta")),
]
MILESTONE_BY_CODE = {m.code: m for band in MILESTONES for m in band.items}


def milestone_band(age_days: int) -> MilestoneBand | None:
    for band in MILESTONES:
        if band.day_from <= age_days < band.day_to:
            return band
    return None


# as orientações que chegam à família na idade certa (o texto é do pediatra; estes são os títulos do modelo)
GUIDANCE = [
    (0, "Sono seguro: de barriga para cima, no berço, sem travesseiro"),
    (120, "Introdução alimentar: o que esperar a partir dos 6 meses"),
    (240, "Prevenção de acidentes: quando o bebê começa a se mexer"),
    (330, "Desmame da mamadeira e escovação dos dentes"),
]

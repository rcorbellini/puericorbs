"""As curvas da OMS, a linha do cuidado, a agenda e o plano: o que a família e o pediatra veem tem de bater com os
protocolos e com o que está registrado."""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta

from conftest import H, client

from puericorbs import growth, scheduling
from puericorbs.db import connect_practice, one


def test_curva_da_oms_no_meio_e_percentil_50():
    _, m, _ = growth.lms("wfa", "F", 122)
    z = growth.z_score("wfa", "F", 122, m)
    assert abs(z) < 1e-9 and round(growth.percentile(z)) == 50
    # menina de 4 meses com 6,4 kg: perto da mediana; com 4,6 kg, abaixo do esperado
    assert growth.reading(growth.z_score("wfa", "F", 122, 6.4)) == "dentro do esperado para a idade"
    assert growth.reading(growth.z_score("wfa", "F", 122, 4.6)) == "abaixo do esperado para a idade"


def test_idade_corrigida_do_prematuro():
    birth = date(2026, 1, 1)
    day, corrected = growth.corrected_days(birth, birth + timedelta(days=120), 32)
    assert corrected and day == 120 - 8 * 7
    day, corrected = growth.corrected_days(birth, birth + timedelta(days=800), 32)
    assert not corrected and day == 800  # depois dos 2 anos, a idade de verdade


def test_linha_do_cuidado_da_helena(settings):
    ana = client(settings, "dramarina.localhost", "ana@demo.test")
    home = ana.get("/api/family/home").json()
    assert home["next"]["title"] == "Consulta dos 6 meses"
    assert home["next"]["action"] == "agendar"
    titles = [i["title"] for i in home["todo"]]
    assert "Meningocócica C · 2ª dose" in titles
    assert "Mandar a foto da caderneta de vacinação" in titles
    feito = {i["title"]: i for i in home["done"]}
    assert "Consulta dos 4 meses" in feito and "crescendo muito bem" in feito["Consulta dos 4 meses"]["detail"]


def test_vaga_protegida_so_abre_no_dia_e_so_para_doenca(settings):
    conn = connect_practice(settings.data_dir, 1)
    day = date.today() + timedelta(days=7)
    while day.weekday() > 4:
        day += timedelta(days=1)
    sick = one(conn, "SELECT * FROM services WHERE kind = 'sick_visit'")
    well = one(conn, "SELECT * FROM services WHERE kind = 'well_child'")
    early = datetime.combine(day, datetime.min.time()).replace(hour=7)
    no_dia = {t["time"] for t in scheduling.free_times(conn, sick, day, early, for_family=True)}
    assert "11:30" in no_dia  # a vaga do fim da manhã, no próprio dia
    antes = {t["time"] for t in scheduling.free_times(conn, sick, day, early - timedelta(days=1), for_family=False)}
    assert "11:30" not in antes  # na véspera ela ainda está fechada
    puericultura = {t["time"] for t in scheduling.free_times(conn, well, day, early, for_family=True)}
    assert "11:30" not in puericultura


def test_familia_agenda_na_janela_e_entra_no_plano(fresh):
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    helena = next(k for k in ana.get("/api/family/home").json()["children"] if k["first_name"] == "Helena")
    svc = next(s for s in ana.get(f"/api/family/children/{helena['id']}/services").json()["services"] if s["kind"] == "well_child")
    assert svc["covered"] and svc["display"] == "Consulta dos 6 meses"
    days = ana.get(f"/api/family/children/{helena['id']}/days?service_id={svc['id']}").json()
    first = days["days"][0]
    assert days["window"]["from"] <= first["date"] <= days["window"]["to"]
    slot = ana.get(f"/api/family/children/{helena['id']}/slots?service_id={svc['id']}&date={first['date']}").json()
    assert slot["cover"]["covered"]
    body = {"service_id": svc["id"], "date": first["date"], "time": slot["times"][0]["time"]}
    assert ana.post(f"/api/family/children/{helena['id']}/appointments", json=body, headers=H).status_code == 200
    assert ana.post(f"/api/family/children/{helena['id']}/appointments", json=body, headers=H).status_code == 409
    home = ana.get(f"/api/family/home?child={helena['id']}").json()
    assert home["next"]["status"] == "agendado"
    usage = home["children"][0]["plan"]["usage"][0] if home["children"][0]["id"] == helena["id"] else \
        next(c for c in home["children"] if c["id"] == helena["id"])["plan"]["usage"][0]
    assert usage["booked"] == 1


def test_familia_manda_o_exame_e_o_pediatra_revisa(fresh):
    from PIL import Image
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    files = ana.get("/api/family/files").json()
    pedido = files["waiting"][0]
    img = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 120, 90)).save(img, "JPEG")
    r = ana.post("/api/family/files", headers=H, data={"child_id": pedido["patient_id"], "kind": "exame",
                                                      "title": "Hemograma", "care_item_id": pedido["care_item_id"]},
                 files={"upload": ("hemograma.jpg", img.getvalue(), "image/jpeg")})
    assert r.status_code == 200, r.text
    assert not ana.get("/api/family/files").json()["waiting"]
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    novo = next(f for f in marina.get("/api/staff/review").json()["files"] if f["id"] == r.json()["id"])
    assert novo["needs_review"] and not novo["reviewed_at"]
    assert marina.post(f"/api/staff/files/{novo['id']}/review", json={"note": "Normal."}, headers=H).status_code == 200
    item = connect_practice(fresh.data_dir, 1).execute("SELECT status FROM care_items WHERE id = ?", (pedido["care_item_id"],)).fetchone()
    assert item[0] == "feito"


def test_arquivo_que_nao_e_foto_nem_pdf_e_recusado(fresh):
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    kid = ana.get("/api/family/home").json()["child"]
    r = ana.post("/api/family/files", headers=H, data={"child_id": kid, "kind": "documento"},
                 files={"upload": ("x.exe", b"MZ\x90\x00 executavel", "application/octet-stream")})
    assert r.status_code == 415


def test_consulta_do_comeco_ao_fim(fresh):
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    hoje = marina.get("/api/staff/today").json()
    alice = hoje["focus"]["appointment"]
    enc = marina.post(f"/api/staff/appointments/{alice['id']}/encounter", headers=H).json()["encounter_id"]
    tela = marina.get(f"/api/staff/encounters/{enc}").json()
    assert tela["title"] == "Consulta dos 9 meses" and tela["template_key"] == "puericultura"
    pct = marina.get(f"/api/staff/growth?patient_id={alice['patient']['id']}&weight=8.4&length=71").json()
    assert pct["measures"]["wfa"]["label"].startswith("P")
    body = {"notes": {"alimentacao": "aceita bem"}, "family_summary": "Tudo bem com a Alice.", "summary_released": True,
            "weight": 8.4, "length": 71.0, "milestones": ["pinca"]}
    assert marina.post(f"/api/staff/encounters/{enc}/finish", json=body, headers=H).status_code == 200
    julia = client(fresh, "dramarina.localhost", "julia@demo.test")
    done = julia.get("/api/family/home").json()["done"]
    assert any(i["title"] == "Consulta dos 9 meses" and i["detail"] == "Tudo bem com a Alice." for i in done)


def test_financeiro_bate_com_as_cobrancas(settings):
    marina = client(settings, "dramarina.localhost", "marina@demo.test")
    f = marina.get("/api/staff/finance").json()
    assert f["result"] == f["received"] - f["spent"]
    assert f["overdue"] > 0 and f["overdue_count"] == 3
    assert len(f["series"]) == 6
    csv = marina.get("/api/staff/finance/export").text
    assert csv.splitlines()[0].endswith("tipo;data;familia;crianca;descricao;forma;valor;nota")

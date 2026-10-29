"""A agenda da pediatra: os dias e os horários em que ela atende (só ela muda), a agenda fechada (ela e a recepção fecham
e reabrem) e o pedido de confirmação pelo WhatsApp. Nada que já estava marcado é desmarcado sozinho: volta na resposta,
com o telefone da família, para a recepção avisar."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from conftest import H, client

from puericorbs import config, scheduling, views
from puericorbs.api_staff import _confirm_day
from puericorbs.db import PRACTICE_VERSION, connect_practice, insert, one

SEG_A_QUA = [{"weekday": wd, "start": "08:00", "end": "16:00"} for wd in (0, 1, 2)]


def next_weekday(wd: int, after: int = 3) -> date:
    d = date.today() + timedelta(days=after)
    while d.weekday() != wd:
        d += timedelta(days=1)
    return d


def service_id(conn, kind: str) -> int:
    return one(conn, "SELECT id FROM services WHERE kind = ? ORDER BY position LIMIT 1", (kind,))["id"]


def test_a_pediatra_atende_seg_ter_e_qua_das_8_as_16(fresh):
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    r = marina.put("/api/staff/schedule", json={"periods": SEG_A_QUA, "sick_slots": True}, headers=H)
    assert r.status_code == 200, r.text
    s = marina.get("/api/staff/schedule").json()
    assert s["can_edit_hours"] is True
    assert s["periods"] == SEG_A_QUA
    # a vaga da criança doente vai para o fim do período novo (16:00 menos a consulta por doença de 30 min)
    assert {(x["weekday"], x["time"]) for x in s["reserved"]} == {(0, "15:30"), (1, "15:30"), (2, "15:30")}
    conn = connect_practice(fresh.data_dir, 1)
    well = one(conn, "SELECT * FROM services WHERE kind = 'well_child'")
    seg, qui = next_weekday(0), next_weekday(3)
    early = datetime.combine(seg - timedelta(days=1), datetime.min.time()).replace(hour=7)
    times = [t["time"] for t in scheduling.free_times(conn, well, seg, early, for_family=False)]
    assert times[0] == "08:00" and scheduling.minutes(times[-1]) + well["duration_min"] <= 16 * 60
    assert scheduling.free_times(conn, well, qui, early, for_family=False) == []
    # e a família, pelo app, só vê segunda, terça e quarta, em todo serviço que ela marca
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    theo = next(k for k in ana.get("/api/family/home").json()["children"] if k["first_name"] == "Theo")
    seen = []
    for svc in ana.get(f"/api/family/children/{theo['id']}/services").json()["services"]:
        seen += ana.get(f"/api/family/children/{theo['id']}/days?service_id={svc['id']}").json()["days"]
    assert seen and all(date.fromisoformat(d["date"]).weekday() in (0, 1, 2) for d in seen)


def test_sem_a_vaga_da_crianca_doente(fresh):
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    marina.put("/api/staff/schedule", json={"periods": SEG_A_QUA, "sick_slots": False}, headers=H)
    s = marina.get("/api/staff/schedule").json()
    assert s["sick_slots"] is False and s["reserved"] == []


def test_so_a_pediatra_muda_os_horarios(fresh):
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    assert carla.get("/api/staff/schedule").json()["can_edit_hours"] is False
    assert carla.put("/api/staff/schedule", json={"periods": SEG_A_QUA}, headers=H).status_code == 403
    assert carla.put("/api/staff/schedule", json={"periods": SEG_A_QUA, "practice_id": 2}, headers=H).status_code == 403
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    assert ana.get("/api/staff/schedule").status_code == 403
    assert ana.put("/api/staff/schedule", json={"periods": SEG_A_QUA}, headers=H).status_code == 403
    conn = connect_practice(fresh.data_dir, 1)
    assert one(conn, "SELECT COUNT(*) AS n FROM availability")["n"] == 10  # a grade de segunda a sexta, intacta


def test_horario_que_nao_fecha_diz_o_que_corrigir(fresh):
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    cases = [
        ([{"weekday": 0, "start": "12:00", "end": "08:00"}], "Segunda: o fim (08:00)"),
        ([{"weekday": 1, "start": "08:00", "end": "12:00"}, {"weekday": 1, "start": "11:00", "end": "13:00"}],
         "Terça: os períodos 08:00–12:00 e 11:00–13:00 se cruzam"),
        ([{"weekday": 2, "start": "8h", "end": "12:00"}], "Quarta: escreva o horário como 08:00"),
        ([{"weekday": 3, "start": "08:03", "end": "12:00"}], "de 5 em 5 minutos"),
        ([{"weekday": 4, "start": "25:00", "end": "26:00"}], "de 00:00 a 23:59"),
        ([{"weekday": 7, "start": "08:00", "end": "12:00"}], "Dia da semana inválido"),
    ]
    for periods, message in cases:
        r = marina.put("/api/staff/schedule", json={"periods": periods}, headers=H)
        assert r.status_code == 400 and message in r.json()["detail"], (periods, r.text)
    conn = connect_practice(fresh.data_dir, 1)
    assert one(conn, "SELECT COUNT(*) AS n FROM availability")["n"] == 10


def test_consulta_fora_do_horario_novo_continua_marcada_e_volta_na_resposta(fresh):
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    conn = connect_practice(fresh.data_dir, 1)
    qui = next_weekday(3, after=22)
    well = service_id(conn, "well_child")
    free = carla.get(f"/api/staff/slots?service_id={well}&date={qui}").json()["times"]
    alice = carla.get("/api/staff/patients?q=Alice").json()["patients"][0]["id"]
    aid = carla.post("/api/staff/appointments", json={"patient_id": alice, "service_id": well, "date": qui.isoformat(),
                                                      "time": free[0]["time"]}, headers=H).json()["id"]
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    out = marina.put("/api/staff/schedule", json={"periods": SEG_A_QUA, "sick_slots": True}, headers=H).json()["outside"]
    row = next(a for a in out if a["id"] == aid)
    assert row["contacts"] and row["contacts"][0]["phone"]  # o aviso de remarcar sai pronto
    for a in out:  # só volta o que de fato saiu da grade nova
        inside = date.fromisoformat(a["date"]).weekday() in (0, 1, 2) and \
            8 * 60 <= scheduling.minutes(a["start_at"]) and scheduling.minutes(a["end_at"]) <= 16 * 60
        assert not inside, a
    assert one(conn, "SELECT status FROM appointments WHERE id = ?", (aid,))["status"] == "agendado"


def test_fechar_um_dia_ninguem_marca_e_quem_estava_marcado_volta(fresh):
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")  # a recepção também fecha
    conn = connect_practice(fresh.data_dir, 1)
    amanha = date.today() + timedelta(days=1)
    col = carla.get(f"/api/staff/agenda?date={amanha}&scope=me").json()["columns"][0]
    marcadas = sorted(a["id"] for a in col["appointments"] if a["status"] in ("agendado", "confirmado"))
    assert marcadas  # a demonstração tem consultas amanhã
    r = carla.post("/api/staff/closures", json={"start": amanha.isoformat(), "reason": "Doença"}, headers=H)
    assert r.status_code == 200, r.text
    assert sorted(a["id"] for a in r.json()["affected"]) == marcadas
    assert all(a["contacts"] for a in r.json()["affected"])
    col = carla.get(f"/api/staff/agenda?date={amanha}&scope=me").json()["columns"][0]
    assert col["closure"]["reason"] == "Doença" and col["windows"] == [] and col["reserved_free"] == []
    assert sorted(a["id"] for a in col["appointments"] if a["status"] in ("agendado", "confirmado")) == marcadas
    sick = service_id(conn, "sick_visit")
    assert carla.get(f"/api/staff/slots?service_id={sick}&date={amanha}").json()["times"] == []
    pedro = carla.get("/api/staff/patients?q=Pedro").json()["patients"][0]["id"]
    body = {"patient_id": pedro, "service_id": sick, "date": amanha.isoformat(), "time": "15:00"}
    r = carla.post("/api/staff/appointments", json=body, headers=H)
    assert r.status_code == 409 and "fechada neste dia (Doença)" in r.json()["detail"]
    assert carla.post("/api/staff/appointments", json={**body, "kind": "encaixe"}, headers=H).status_code == 200
    # a família não vê o dia e, se tentar mesmo assim, não marca (nem fica sabendo o motivo)
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    theo = next(k for k in ana.get("/api/family/home").json()["children"] if k["first_name"] == "Theo")
    days = ana.get(f"/api/family/children/{theo['id']}/days?service_id={sick}").json()["days"]
    assert amanha.isoformat() not in {d["date"] for d in days}
    r = ana.post(f"/api/family/children/{theo['id']}/appointments",
                 json={"service_id": sick, "date": amanha.isoformat(), "time": "16:00"}, headers=H)
    assert r.status_code == 409 and "Doença" not in r.json()["detail"]
    # reabrir devolve os horários
    cid = carla.get("/api/staff/schedule").json()["closures"][0]["id"]
    assert carla.delete(f"/api/staff/closures/{cid}", headers=H).status_code == 200
    assert carla.get(f"/api/staff/slots?service_id={sick}&date={amanha}").json()["times"]


def test_fechar_varios_dias_e_conferir_as_datas(fresh):
    marina = client(fresh, "dramarina.localhost", "marina@demo.test")
    hoje = date.today()

    def close(start, end=None):
        return marina.post("/api/staff/closures", json={"start": str(start), "end": str(end) if end else None,
                                                        "reason": "Férias"}, headers=H)

    assert close(hoje + timedelta(days=5), hoje + timedelta(days=3)).status_code == 400
    assert close(hoje - timedelta(days=10), hoje - timedelta(days=3)).status_code == 400
    assert close(hoje, hoje + timedelta(days=400)).status_code == 400
    assert close("amanhã").status_code == 400
    ferias = (hoje + timedelta(days=40), hoje + timedelta(days=54))
    assert close(*ferias).status_code == 200
    conn = connect_practice(fresh.data_dir, 1)
    for k in range(15):
        assert scheduling.windows(conn, ferias[0] + timedelta(days=k)) == []
    assert scheduling.windows(conn, ferias[1] + timedelta(days=1)) or (ferias[1] + timedelta(days=1)).weekday() > 4
    c = next(x for x in marina.get("/api/staff/schedule").json()["closures"] if x["reason"] == "Férias")
    assert (c["start"], c["end"], c["by"]) == (ferias[0].isoformat(), ferias[1].isoformat(), "Dra. Marina Alves")


def test_vaga_protegida_so_aparece_dentro_da_grade(fresh):
    conn = connect_practice(fresh.data_dir, 1)
    seg = next_weekday(0)
    assert (16 * 60 + 50, 17 * 60 + 20) in scheduling.reserved(conn, seg)
    conn.execute("DELETE FROM availability WHERE weekday = 0 AND start_min >= 720")  # segunda só de manhã
    assert all(e <= 720 for _, e in scheduling.reserved(conn, seg))
    assert "16:50" not in {v["time"] for v in views.free_reserved(conn, seg)}


def test_pedido_de_confirmacao_fica_na_lista_da_recepcao(fresh):
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    p = carla.get("/api/staff/reception").json()["practices"][0]
    pend = next(a for a in p["confirm"] if a["status"] == "agendado")
    assert pend["contacts"] and pend["confirm_asked_at"] is None and pend["patient"]["sex"] in ("F", "M")
    r = carla.post(f"/api/staff/appointments/{pend['id']}/asked", json={"practice_id": p["practice"]["id"]}, headers=H)
    assert r.status_code == 200
    again = next(a for a in carla.get("/api/staff/reception").json()["practices"][0]["confirm"] if a["id"] == pend["id"])
    assert again["confirm_asked_at"] == r.json()["confirm_asked_at"]
    # a família não marca o pedido, e as consultas dela não trazem o telefone de ninguém
    ana = client(fresh, "dramarina.localhost", "ana@demo.test")
    assert ana.post(f"/api/staff/appointments/{pend['id']}/asked", json={}, headers=H).status_code == 403
    assert all("contacts" not in a for a in ana.get("/api/family/appointments").json()["upcoming"])


def test_a_recepcao_confirma_o_proximo_dia_com_consulta(fresh):
    """Na sexta, o cartão de confirmar mostra a segunda: o próximo dia com consulta marcada, até uma semana."""
    conn = connect_practice(fresh.data_dir, 1)
    hoje = date.today()
    conn.execute("DELETE FROM appointments WHERE substr(start_at, 1, 10) > ?", (hoje.isoformat(),))
    assert _confirm_day(conn, hoje) == hoje + timedelta(days=1)  # nada marcado: amanhã, vazio
    segunda = hoje + timedelta(days=3)
    patient = one(conn, "SELECT id FROM patients LIMIT 1")["id"]
    insert(conn, "appointments", {"patient_id": patient, "service_id": service_id(conn, "follow_up"),
                                  "start_at": f"{segunda}T09:00", "end_at": f"{segunda}T09:20", "status": "agendado",
                                  "created_at": f"{hoje}T08:00:00"})
    assert _confirm_day(conn, hoje) == segunda
    carla = client(fresh, "dramarina.localhost", "carla@demo.test")
    p = carla.get("/api/staff/reception").json()["practices"][0]
    assert p["confirm_date"] == segunda.isoformat() and len(p["confirm"]) == 1


def test_migracao_da_agenda_fechada(tmp_path):
    """Um banco da versão 2 (o fechamento de um dia só, sem quem fechou) passa à 3 com o dia ainda fechado."""
    s = config.load(tmp_path)
    conn = connect_practice(s.data_dir, 1)
    for col in ("end_day", "created_by", "created_at"):
        conn.execute(f"ALTER TABLE schedule_exceptions DROP COLUMN {col}")
    conn.execute("ALTER TABLE appointments DROP COLUMN confirm_asked_at")
    conn.execute("DROP TABLE invite_prefill")  # o que a versão 4 trouxe (test_invites.py)
    conn.execute("INSERT INTO schedule_exceptions (day, reason) VALUES ('2031-03-03', 'Feriado')")
    conn.execute("PRAGMA user_version = 2")
    conn.close()
    conn = connect_practice(s.data_dir, 1)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == PRACTICE_VERSION
    assert scheduling.closure(conn, date(2031, 3, 3))["reason"] == "Feriado"
    assert scheduling.closure(conn, date(2031, 3, 4)) is None
    assert "confirm_asked_at" in {r[1] for r in conn.execute("PRAGMA table_info(appointments)")}

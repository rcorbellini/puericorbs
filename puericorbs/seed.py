"""A demonstração: a Clínica Girassol, a Dra. Marina e o Dr. Paulo, a recepção da Carla e as famílias do protótipo.

Tudo é fictício e tudo é relativo ao dia de hoje: a Helena tem sempre 4 meses e 12 dias. Cada criança ganha o
histórico do protocolo (consultas, medidas pela curva da OMS com um desvio próprio, vacinas), seis meses de dinheiro
(consultas avulsas, mensalidades dos planos, despesas) e o dia de hoje montado como no protótipo.
"""

from __future__ import annotations

import io
import json
import shutil
from datetime import date, datetime, timedelta

from . import auth, catalog, files, growth, protocols
from .config import Settings
from .db import connect_platform, connect_practice, insert, many, now_iso, one, platform_path, transaction
from .finance import MONTHS_FULL
from .practices import create_practice

PASSWORD = "demo1234"


# ---- arquivos de exemplo (um PDF de uma página e uma imagem neutra) ----------------------------------------------------

def tiny_pdf(title: str, lines: list[str]) -> bytes:
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    body = ["BT", "/F1 17 Tf", "56 776 Td", f"({esc(title)}) Tj", "/F1 11 Tf", "0 -30 Td"]
    for line in lines:
        body += [f"({esc(line)}) Tj", "0 -17 Td"]
    body.append("ET")
    stream = "\n".join(body).encode("cp1252", "replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


def soft_image(label: str, hue: tuple[int, int, int]) -> bytes:
    from PIL import Image, ImageDraw
    w, h = 900, 680
    img = Image.new("RGB", (w, h), (246, 248, 251))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=tuple(int(c * (1 - t) + 246 * t) for c in hue))
    draw.ellipse([w * 0.32, h * 0.22, w * 0.68, h * 0.70], fill=tuple(min(255, c + 25) for c in hue))
    draw.text((40, h - 60), label, fill=(28, 43, 58))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# ---- ajudantes de data ----------------------------------------------------------------------------------------------

def months_ago(d: date, months: int, days: int = 0) -> date:
    y, m = divmod(d.month - 1 - months, 12)
    year, month = d.year + y, m + 1
    import calendar
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1])) - timedelta(days=days)


def weekday_on_or_before(d: date) -> date:
    while d.weekday() > 4:
        d -= timedelta(days=1)
    return d


def at(d: date, hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{d.isoformat()}T{hhmm}")


class Practice:
    """O que a semente faz numa prática: famílias, crianças, histórico e o dia de hoje."""

    def __init__(self, settings: Settings, pconn, practice_id: int, today: date, now: datetime):
        self.settings, self.pconn, self.pid = settings, pconn, practice_id
        self.conn = connect_practice(settings.data_dir, practice_id)
        self.today, self.now = today, now
        self.svc = {s["kind"]: s for s in many(self.conn, "SELECT * FROM services")}
        self.plans: dict[str, int] = {}
        self.slot_seq = 0

    # -- cadastro --
    def family(self, name: str, guardians: list[dict]) -> int:
        fid = insert(self.conn, "families", {"name": name, "created_at": now_iso()})
        for i, g in enumerate(guardians):
            user_id = None
            if g.get("email"):
                u = one(self.pconn, "SELECT id FROM users WHERE email = ?", (g["email"],))
                user_id = u["id"] if u else insert(self.pconn, "users", {
                    "email": g["email"], "name": g["name"], "password_hash": auth.hash_password(PASSWORD),
                    "created_at": now_iso()})
            insert(self.conn, "guardians", {"family_id": fid, "user_id": user_id, "name": g["name"],
                                            "relation": g["relation"], "phone": g.get("phone"), "email": g.get("email"),
                                            "is_legal": 1, "is_financial": 1 if i == 0 else 0, "created_at": now_iso()})
        return fid

    def child(self, family_id: int, name: str, sex: str, birth: date, z: float = 0.0, **extra) -> dict:
        day0 = 0
        values = {"family_id": family_id, "name": name, "sex": sex, "birth_date": birth.isoformat(),
                  "gestational_weeks": extra.pop("ga", 39), "created_at": now_iso(),
                  "birth_weight_g": round(growth.value_at("wfa", sex, day0, z) * 1000 / 10) * 10,
                  "birth_length_cm": round(growth.value_at("lhfa", sex, day0, z), 1),
                  "birth_head_cm": round(growth.value_at("hcfa", sex, day0, z), 1),
                  "birth_type": extra.pop("birth_type", "parto normal"), **extra}
        pid = insert(self.conn, "patients", values)
        return {**values, "id": pid, "z": z}

    def plan(self, key: str, **values) -> int:
        benefits = [{"service_id": self.svc[k]["id"], "qty": q, "label": label} for k, q, label in values.pop("benefits")]
        pid = insert(self.conn, "plans", {**values, "benefits": json.dumps(benefits, ensure_ascii=False),
                                          "perks": json.dumps(values.pop("perks", []), ensure_ascii=False)
                                          if "perks" in values else "[]", "created_at": now_iso()})
        self.plans[key] = pid
        return pid

    def join(self, patient: dict, plan_key: str, started: date, billing: str, due_day: int, *, months: int = 12,
             status: str = "ativo", paused_until: date | None = None, sibling: bool = False) -> int:
        plan = one(self.conn, "SELECT * FROM plans WHERE id = ?", (self.plans[plan_key],))
        price = plan["price_cents"]
        if sibling and plan["sibling_discount_pct"]:
            price = round(price * (100 - plan["sibling_discount_pct"]) / 100)
        ends = months_ago(started, -months) - timedelta(days=1)
        return insert(self.conn, "memberships", {
            "plan_id": plan["id"], "patient_id": patient["id"], "started_on": started.isoformat(),
            "ends_on": ends.isoformat(), "billing": billing, "due_day": due_day, "status": status,
            "paused_until": paused_until.isoformat() if paused_until else None, "price_cents": price,
            "created_at": now_iso()})

    # -- agenda e prontuário --
    def appointment(self, patient: dict, kind: str, when: datetime, status: str, *, akind: str = "normal",
                    membership_id: int | None = None, source: str = "recepcao", arrived: datetime | None = None,
                    price: int | None = None) -> int:
        svc = self.svc[kind]
        end = when + timedelta(minutes=svc["duration_min"])
        return insert(self.conn, "appointments", {
            "patient_id": patient["id"], "service_id": svc["id"], "service_version": 1,
            "start_at": when.strftime("%Y-%m-%dT%H:%M"), "end_at": end.strftime("%Y-%m-%dT%H:%M"), "status": status,
            "kind": akind, "source": source, "price_cents": 0 if membership_id else (svc["price_cents"] if price is None else price),
            "membership_id": membership_id, "arrived_at": arrived.strftime("%Y-%m-%dT%H:%M:%S") if arrived else None,
            "created_at": now_iso()})

    def measure(self, patient: dict, on: date, encounter_id: int | None = None) -> None:
        day = (on - date.fromisoformat(patient["birth_date"])).days
        if day > growth.MAX_DAY:
            return
        z = patient["z"]
        insert(self.conn, "measurements", {
            "patient_id": patient["id"], "encounter_id": encounter_id, "taken_on": on.isoformat(),
            "weight_kg": round(growth.value_at("wfa", patient["sex"], day, z + 0.05), 2),
            "length_cm": round(growth.value_at("lhfa", patient["sex"], day, z), 1),
            "head_cm": round(growth.value_at("hcfa", patient["sex"], day, z - 0.05), 1) if day <= 730 else None,
            "source": "consulta"})

    def encounter(self, patient: dict, appt_id: int, when: datetime, summary: str, conduct: str = "",
                  cid: str = "Z00.1 · Exame de rotina de saúde da criança", notes: dict | None = None) -> int:
        svc = one(self.conn, "SELECT service_id FROM appointments WHERE id = ?", (appt_id,))
        return insert(self.conn, "encounters", {
            "appointment_id": appt_id, "patient_id": patient["id"], "service_id": svc["service_id"],
            "status": "finalizada", "started_at": when.strftime("%Y-%m-%dT%H:%M:%S"),
            "finished_at": (when + timedelta(minutes=35)).strftime("%Y-%m-%dT%H:%M:%S"),
            "notes": json.dumps(notes or {}, ensure_ascii=False), "cid": cid, "conduct": conduct,
            "family_summary": summary, "summary_released": 1, "clinician_id": None})

    def history(self, patient: dict, *, until: date, skip: tuple[str, ...] = (), membership_id: int | None = None,
                vaccines_until: date | None = None, skip_vaccines: tuple[str, ...] = (), paid: bool = True) -> None:
        """As consultas do protocolo que já passaram, com medidas, e as vacinas até `vaccines_until`."""
        birth = date.fromisoformat(patient["birth_date"])
        for v in protocols.WELL_CHILD:
            target = birth + timedelta(days=v.day)
            if target >= until or v.code in skip:
                continue
            d = weekday_on_or_before(target)
            self.slot_seq += 1
            when = at(d, f"{8 + self.slot_seq % 4:02d}:{(self.slot_seq * 20) % 60:02d}")
            kind = "newborn" if v.code == "1sem" else "well_child"
            aid = self.appointment(patient, kind, when, "atendido", membership_id=membership_id)
            self.measure(patient, d)
            if paid and not membership_id:
                self.paid(patient, aid, kind, d, "pix" if self.slot_seq % 3 else "cartao", invoice="emitida")
        limit = vaccines_until or (until - timedelta(days=1))
        for dose in protocols.VACCINES:
            due = birth + timedelta(days=dose.day)
            if due <= limit and dose.code not in skip_vaccines:
                self.conn.execute("INSERT OR IGNORE INTO immunizations (patient_id, code, applied_on, place, source) "
                                  "VALUES (?, ?, ?, ?, 'consultorio')",
                                  (patient["id"], dose.code, weekday_on_or_before(due + timedelta(days=1)).isoformat(),
                                   "Clínica Girassol" if dose.day else "Maternidade"))

    def milestones(self, patient: dict, codes: list[tuple[str, int, str]]) -> None:
        birth = date.fromisoformat(patient["birth_date"])
        for code, day, who in codes:
            self.conn.execute("""INSERT OR IGNORE INTO milestone_checks (patient_id, code, achieved_on, marked_by, marker_name)
                                 VALUES (?, ?, ?, ?, ?)""",
                              (patient["id"], code, (birth + timedelta(days=day)).isoformat(),
                               "pediatra" if who == "pediatra" else "familia", None if who == "pediatra" else who))

    # -- dinheiro --
    def paid(self, patient: dict, appt_id: int | None, kind: str, on: date, method: str, invoice: str = "emitida",
             amount: int | None = None, description: str | None = None) -> None:
        svc = self.svc[kind]
        insert(self.conn, "charges", {
            "family_id": patient["family_id"], "patient_id": patient["id"], "appointment_id": appt_id,
            "description": description or svc["name"], "amount_cents": svc["price_cents"] if amount is None else amount,
            "due_on": on.isoformat(), "status": "paga", "method": method, "paid_on": on.isoformat(),
            "invoice": invoice, "created_at": now_iso()})

    def plan_charges(self, months_back: int = 6, late: dict[int, int] | None = None) -> None:
        """As mensalidades dos últimos meses: pagas no vencimento, menos as que estão em atraso agora."""
        late = late or {}
        from .finance import MONTHS_FULL, month_range, shift_month
        ym_now = self.today.isoformat()[:7]
        for m in many(self.conn, """SELECT m.*, p.name AS plan, pt.family_id FROM memberships m
                                    JOIN plans p ON p.id = m.plan_id JOIN patients pt ON pt.id = m.patient_id"""):
            for n in range(-months_back, 1):
                ym = shift_month(ym_now, n)
                first, last = month_range(ym)
                due = date(first.year, first.month, min(m["due_day"], last.day))
                if due < date.fromisoformat(m["started_on"]) or due > date.fromisoformat(m["ends_on"]):
                    continue
                if m["status"] == "pausado" and n >= -1:
                    continue
                if due > self.today:
                    continue
                is_late = m["id"] in late and ym == ym_now
                insert(self.conn, "charges", {
                    "family_id": m["family_id"], "patient_id": m["patient_id"], "membership_id": m["id"],
                    "description": f"Plano {m['plan']} · {MONTHS_FULL[first.month - 1].lower()}",
                    "amount_cents": m["price_cents"], "due_on": due.isoformat(),
                    "status": "aberta" if is_late else "paga", "method": m["billing"],
                    "paid_on": None if is_late else due.isoformat(), "invoice": "emitir" if is_late else "emitida",
                    "created_at": now_iso()})

    def sick_visits(self, kids: list[dict], months_back: int = 6) -> None:
        """Consultas por doença no passado, mais no inverno (maio a julho), pagas na hora."""
        start = months_ago(self.today, months_back).replace(day=1)
        d, i = start, 0
        while d < self.today - timedelta(days=1):
            if d.weekday() < 5:
                winter = d.month in (5, 6, 7)
                per_day = (3 if d.day % 2 == 0 else 2) if winter else (2 if (d.day + d.month) % 3 else 1)
                for k in range(per_day):
                    kid = kids[(i + k) % len(kids)]
                    when = at(d, ["11:30", "16:50", "15:40"][k % 3])
                    aid = self.appointment(kid, "sick_visit", when, "atendido", akind="agudo")
                    self.paid(kid, aid, "sick_visit", d, ["pix", "cartao", "pix", "dinheiro"][(i + k) % 4])
                i += per_day + 1
            d += timedelta(days=1)

    def expenses(self, items: list[tuple[str, str, int]], months_back: int = 6) -> None:
        from .finance import month_range, shift_month
        for n in range(-months_back, 1):
            first, _ = month_range(shift_month(self.today.isoformat()[:7], n))
            for desc, cat, cents in items:
                insert(self.conn, "expenses", {"description": desc, "category": cat,
                                               "amount_cents": cents + (n * 1700 if cat == "material" else 0),
                                               "spent_on": (first + timedelta(days=4)).isoformat(), "created_at": now_iso()})

    def file(self, patient: dict, kind: str, title: str, content: bytes, *, by: str, by_name: str | None,
             created: datetime, visibility: str | None = None, note: str | None = None, review: str | None = None,
             care_item_id: int | None = None, needs_review: bool | None = None) -> int:
        stored = files.store(self.settings.data_dir, self.pid, content, 25)
        nr = (kind in files.REVIEW and by == "familia") if needs_review is None else needs_review
        fid = insert(self.conn, "files", {
            "family_id": patient["family_id"], "patient_id": patient["id"], "kind": kind, "title": title, "note": note,
            "original_name": None, **stored, "visibility": visibility or files.visibility_for(kind, by),
            "uploaded_by": None, "uploader_role": by, "uploader_name": by_name, "care_item_id": care_item_id,
            "needs_review": 1 if nr else 0, "reviewed_at": created.strftime("%Y-%m-%dT%H:%M:%S") if review is not None else None,
            "review_note": review or None, "created_at": created.strftime("%Y-%m-%dT%H:%M:%S")})
        if care_item_id:
            self.conn.execute("UPDATE care_items SET file_id = ? WHERE id = ?", (fid, care_item_id))
        return fid

    def care_item(self, patient: dict, kind: str, title: str, *, created: date, due: date | None = None,
                  detail: str | None = None, owner: str = "familia", status: str = "pendente") -> int:
        return insert(self.conn, "care_items", {
            "patient_id": patient["id"], "kind": kind, "title": title, "detail": detail, "owner": owner,
            "due_to": due.isoformat() if due else None, "status": status, "visibility": "family",
            "created_at": f"{created.isoformat()}T10:00:00", "done_at": f"{created.isoformat()}T10:00:00" if status == "feito" else None})


def _reset(settings: Settings) -> None:
    data = settings.data_dir.resolve()
    for p in (platform_path(data), platform_path(data).with_suffix(".db-wal"), platform_path(data).with_suffix(".db-shm")):
        if p.exists():
            p.unlink()
    practices_dir = data / "practices"
    if practices_dir.exists() and practices_dir.parent == data:
        shutil.rmtree(practices_dir)


def run(settings: Settings, reset: bool = False) -> None:
    if not settings.demo:
        # a produção nunca recebe a demonstração, e o --reset apagaria os consultórios de verdade
        raise RuntimeError("Esta pasta é de produção (demo = false): a demonstração não entra nela.")
    if reset:
        _reset(settings)
    pconn = connect_platform(settings.data_dir)
    if one(pconn, "SELECT id FROM users LIMIT 1"):
        pconn.close()
        return
    now = datetime.now(settings.tz).replace(tzinfo=None, second=0, microsecond=0)
    today = now.date()
    with transaction(pconn):
        insert(pconn, "users", {"email": "admin@demo.test", "name": "Administração Puericorbs",
                                "password_hash": auth.hash_password(PASSWORD), "is_platform_admin": 1, "created_at": now_iso()})
        clinic = insert(pconn, "clinics", {"name": "Clínica Girassol", "created_at": now_iso()})
    marina_id = create_practice(pconn, settings.data_dir, name="Dra. Marina Alves", slug="dramarina",
                                domain="dramarina.com.br", accent="agua", clinic_id=clinic,
                                registry="CRM-SP 000000 · RQE 00000",
                                bio="Pediatra. Acompanha a criança desde a gestação, com o foco nos primeiros anos.",
                                address="Clínica Girassol, sala 2", clinician_name="Dra. Marina Alves",
                                clinician_email="marina@demo.test", password=PASSWORD)
    paulo_id = create_practice(pconn, settings.data_dir, name="Dr. Paulo Reis", slug="drpauloreis",
                               domain="drpauloreis.com.br", accent="azul", clinic_id=clinic,
                               registry="CRM-SP 000000 · RQE 00000",
                               bio="Pediatra geral e de urgência. Atende na Clínica Girassol de manhã.",
                               address="Clínica Girassol, sala 3", clinician_name="Dr. Paulo Reis",
                               clinician_email="paulo@demo.test", password=PASSWORD)
    with transaction(pconn):
        carla = insert(pconn, "users", {"email": "carla@demo.test", "name": "Carla Souza",
                                        "password_hash": auth.hash_password(PASSWORD), "created_at": now_iso()})
        for pid in (marina_id, paulo_id):
            insert(pconn, "memberships", {"user_id": carla, "practice_id": pid, "role": "receptionist"})
    _marina(settings, pconn, marina_id, today, now)
    _paulo(settings, pconn, paulo_id, today, now)
    pconn.close()


def _marina(settings: Settings, pconn, practice_id: int, today: date, now: datetime) -> None:
    s = Practice(settings, pconn, practice_id, today, now)
    c = s.conn
    with transaction(c), transaction(pconn):
        s.plan("primeiro", name="Primeiro Ano", description="O primeiro ano de vida, mês a mês.", price_cents=69000,
               months=12, entry_rule="entrada até os 3 meses", max_entry_age_m=3, discount_pct=15, sibling_discount_pct=10,
               benefits=[("well_child", 12, "consultas de puericultura"), ("sick_visit", 2, "consultas por doença"),
                         ("home_visit", 1, "visita em casa")],
               perks=["Mensagens em horário comercial, resposta em até 4 h", "1 visita em casa na primeira semana",
                      "15% de desconto nos outros serviços"])
        s.plan("acompanhamento", name="Acompanhamento", description="Da criança de 1 a 6 anos.", price_cents=39000,
               months=12, entry_rule="de 1 a 6 anos", discount_pct=15, sibling_discount_pct=10,
               benefits=[("well_child", 4, "consultas de rotina"), ("sick_visit", 3, "consultas por doença")],
               perks=["Mensagens, resposta no mesmo dia útil", "15% de desconto nos outros serviços",
                      "Irmãos: 10% de desconto por criança"])
        s.plan("gestante", name="Gestante e bebê", description="Da gestação ao primeiro ano.", price_cents=72000,
               months=15, entry_rule="a partir do 7º mês de gestação", discount_pct=15,
               benefits=[("prenatal", 1, "consulta pré-natal"), ("well_child", 12, "consultas de puericultura"),
                         ("sick_visit", 2, "consultas por doença"), ("home_visit", 1, "visita em casa")],
               perks=["Visita na maternidade ou em casa", "Depois do nascimento, tudo do Primeiro Ano"])

        # Família Costa: a Helena (4 meses, no plano) e o Theo (3 anos)
        costa = s.family("Família Costa", [{"name": "Ana Costa", "relation": "mãe", "email": "ana@demo.test", "phone": "(11) 90000-0001"},
                                           {"name": "Bruno Costa", "relation": "pai", "phone": "(11) 90000-0002"}])
        helena = s.child(costa, "Helena Costa", "F", months_ago(today, 4, 12), z=-0.12)
        hb = date.fromisoformat(helena["birth_date"])
        mh = s.join(helena, "primeiro", hb + timedelta(days=5), "cartao", 5)
        s.history(helena, until=today, membership_id=mh, vaccines_until=hb + timedelta(days=125))
        last = one(c, "SELECT * FROM appointments WHERE patient_id = ? ORDER BY start_at DESC LIMIT 1", (helena["id"],))
        enc = s.encounter(helena, last["id"], datetime.fromisoformat(last["start_at"]),
                          "A Helena está crescendo muito bem e está dentro do esperado para a idade. Hoje ela tomou as "
                          "vacinas dos 4 meses. Continue o leite materno e a vitamina D todos os dias. A próxima consulta "
                          "é a dos 6 meses.", conduct="Manter aleitamento materno exclusivo. Vitamina D 400 UI/dia.")
        s.milestones(helena, [("sorri", 48, "Ana, mãe"), ("olhar", 40, "Ana, mãe"), ("cabeca", 118, "Ana, mãe"),
                              ("balbucia", 122, "pediatra")])
        foto_item = s.care_item(helena, "tarefa", "Mandar a foto da caderneta de vacinação",
                                created=date.fromisoformat(last["start_at"][:10]), due=today - timedelta(days=1),
                                detail="para completar a caderneta digital")
        c.execute("UPDATE care_items SET encounter_id = ? WHERE id = ?", (enc, foto_item))
        rx = s.file(helena, "receita", "Receita · vitamina D", tiny_pdf("Receita", [
            "Paciente: Helena Costa", "", "Vitamina D 400 UI/gota", "Dar 1 gota por dia, por via oral, até novo pedido.", "",
            "Dra. Marina Alves · CRM-SP 000000 (documento de demonstração)"]),
            by="pediatra", by_name="Dra. Marina Alves", created=datetime.fromisoformat(last["start_at"]) + timedelta(minutes=40))
        s.file(helena, "foto", "Foto: manchinha no braço", soft_image("Foto de exemplo", (255, 205, 184)),
               by="familia", by_name="Ana, mãe", created=now - timedelta(days=14, hours=3), note="Apareceu ontem, não coça.",
               review="É uma dermatite leve. Hidrate duas vezes ao dia e me mande outra foto em uma semana.")

        theo = s.child(costa, "Theo Costa", "M", months_ago(today, 38), z=0.35, ga=40)
        s.history(theo, until=today - timedelta(days=40), skip=("3a",))
        t3 = s.appointment(theo, "well_child", at(weekday_on_or_before(today + timedelta(days=12)), "10:00"), "confirmado", source="familia")
        sick = s.appointment(theo, "sick_visit", at(weekday_on_or_before(today - timedelta(days=23)), "11:30"), "atendido", akind="agudo")
        s.paid(theo, sick, "sick_visit", weekday_on_or_before(today - timedelta(days=23)), "pix", invoice="emitida")
        s.encounter(theo, sick, at(weekday_on_or_before(today - timedelta(days=23)), "11:30"),
                    "O Theo está com uma virose. Pode dar o antitérmico se tiver febre acima de 37,8 °C e oferecer muito "
                    "líquido. Se a febre passar de 3 dias, me avise.", cid="B34.9 · Infecção viral não especificada",
                    conduct="Sintomáticos. Reavaliar se febre > 72 h.")
        exam = s.care_item(theo, "exame", "Hemograma e ferritina", created=today - timedelta(days=6),
                           due=date.fromisoformat(one(c, "SELECT start_at FROM appointments WHERE id = ?", (t3,))["start_at"][:10]),
                           detail="antes da consulta de 3 anos")
        s.file(theo, "atestado", "Atestado para a escola", tiny_pdf("Atestado", [
            "Atesto que Theo Costa esteve em consulta pediátrica e deve se afastar", "das atividades escolares por 2 dias.", "",
            "Dra. Marina Alves · CRM-SP 000000 (documento de demonstração)"]),
            by="pediatra", by_name="Dra. Marina Alves", created=at(weekday_on_or_before(today - timedelta(days=23)), "12:05"))
        s.file(theo, "recibo", "Recibo · consulta por doença", tiny_pdf("Recibo", [
            "Recebi de Ana Costa (CPF de demonstração) a quantia de R$ 380,00", "referente à consulta por doença de Theo Costa.", "",
            "Dra. Marina Alves · CRM-SP 000000 (documento de demonstração)"]),
            by="atendente", by_name="Carla Souza", created=at(weekday_on_or_before(today - timedelta(days=23)), "12:10"))
        s.file(theo, "exame", "Urina tipo 1", tiny_pdf("Urina tipo 1 (exemplo)", ["Resultado de demonstração: sem alterações."]),
               by="familia", by_name="Ana, mãe", created=now - timedelta(days=21), review="Normal. Não precisa de mais nada.")

        # Família Moreira: a Alice, 9 meses, chega hoje às 10h (está na espera)
        moreira = s.family("Família Moreira", [{"name": "Júlia Moreira", "relation": "mãe", "email": "julia@demo.test", "phone": "(11) 90000-0003"},
                                               {"name": "Caio Moreira", "relation": "pai"}])
        alice = s.child(moreira, "Alice Moreira", "F", months_ago(today, 9, 1), z=0.22,
                        allergies="Alergia à proteína do leite de vaca (APLV)")
        ab = date.fromisoformat(alice["birth_date"])
        ma = s.join(alice, "primeiro", ab + timedelta(days=6), "pix_automatico", 10)
        s.history(alice, until=today - timedelta(days=7), membership_id=ma, vaccines_until=ab + timedelta(days=200))
        for extra in (91, 152):  # as consultas a mais que a Dra. Marina faz nos 3 e 5 meses
            s.appointment(alice, "well_child", at(weekday_on_or_before(ab + timedelta(days=extra)), "09:20"), "atendido", membership_id=ma)
        s.milestones(alice, [("sorri", 45, "Júlia, mãe"), ("cabeca", 100, "Júlia, mãe"), ("rola", 150, "Júlia, mãe"),
                             ("boca", 160, "pediatra"), ("senta", 240, "Júlia, mãe"), ("engatinha", 262, "Júlia, mãe")])
        s.appointment(alice, "well_child", at(today, "10:10"), "chegou", membership_id=ma, arrived=now - timedelta(minutes=12))

        # Bento, 3 anos, no plano Acompanhamento: veio hoje às 9h20 por doença
        ribeiro = s.family("Família Ribeiro", [{"name": "Marcos Ribeiro", "relation": "pai", "email": "marcos@demo.test", "phone": "(11) 90000-0004"}])
        bento = s.child(ribeiro, "Bento Ribeiro", "M", months_ago(today, 37), z=0.1, ga=38)
        mb = s.join(bento, "acompanhamento", months_ago(today, 7), "cartao", 3)
        s.history(bento, until=today, membership_id=None)
        bt = s.appointment(bento, "sick_visit", at(today, "09:00"), "atendido", membership_id=mb)
        s.encounter(bento, bt, at(today, "09:02"), "O Bento está com otite. Use o antibiótico da receita por 7 dias e "
                    "volte se a febre não passar em 48 h.", cid="H66.9 · Otite média", conduct="Amoxicilina 7 dias.")

        # o resto da agenda de hoje
        gael_f = s.family("Família Souza", [{"name": "Patrícia Souza", "relation": "mãe", "phone": "(11) 90000-0005"}])
        gael = s.child(gael_f, "Gael Souza", "M", today - timedelta(days=7), z=-0.3)
        g = s.appointment(gael, "newborn", at(today, "08:00"), "atendido")
        s.paid(gael, g, "newborn", today, "cartao", invoice="emitir")
        s.measure(gael, today)
        laura_f = s.family("Família Mendes", [{"name": "Camila Mendes", "relation": "mãe", "phone": "(11) 90000-0006"}])
        laura = s.child(laura_f, "Laura Mendes", "F", months_ago(today, 2, 2), z=0.4)
        s.history(laura, until=today)
        lt = s.appointment(laura, "well_child", at(today, "09:30"), "atendido")
        s.paid(laura, lt, "well_child", today, "pix", invoice="emitida")
        lima = s.family("Família Lima", [{"name": "Rodrigo Lima", "relation": "pai", "phone": "(11) 90000-0007"}])
        pedro = s.child(lima, "Pedro Lima", "M", months_ago(today, 62), z=-0.2)
        s.history(pedro, until=today, paid=False)
        s.appointment(pedro, "sick_visit", at(today, "10:30"), "chegou", akind="encaixe", arrived=now - timedelta(minutes=4))
        prado = s.family("Família Prado", [{"name": "Rui Prado", "relation": "pai", "phone": "(11) 90000-0008"}])
        malu = s.child(prado, "Maria Luiza Prado", "F", months_ago(today, 12, -3), z=0.05)
        mm = s.join(malu, "primeiro", months_ago(today, 12) + timedelta(days=1), "cartao", 28)  # renova hoje
        s.history(malu, until=today - timedelta(days=20), membership_id=mm)
        s.appointment(malu, "well_child", at(today, "10:50"), "confirmado", membership_id=mm)
        campos = s.family("Família Campos", [{"name": "Bruna Campos", "relation": "mãe", "email": "bruna@demo.test", "phone": "(11) 90000-0009"}])
        heitor = s.child(campos, "Heitor Campos", "M", months_ago(today, 4, 5), z=0.6)
        mhc = s.join(heitor, "primeiro", date.fromisoformat(heitor["birth_date"]) + timedelta(days=8), "boleto", 15)
        s.history(heitor, until=today - timedelta(days=10), membership_id=mhc, skip=("4m",))
        s.appointment(heitor, "well_child", at(today, "14:00"), "confirmado", membership_id=mhc)
        s.file(heitor, "foto", "Foto: assadura", soft_image("Foto de exemplo", (255, 220, 200)), by="familia",
               by_name="Bruna, mãe", created=now - timedelta(hours=19), note="Piorou desde ontem.")
        rocha = s.family("Família Rocha", [{"name": "Sílvia Rocha", "relation": "mãe", "phone": "(11) 90000-0010"}])
        valentina = s.child(rocha, "Valentina Rocha", "F", months_ago(today, 74), z=0.0)
        s.history(valentina, until=today, paid=False)
        vs = s.appointment(valentina, "sick_visit", at(weekday_on_or_before(today - timedelta(days=9)), "16:50"), "atendido", akind="agudo")
        s.paid(valentina, vs, "sick_visit", weekday_on_or_before(today - timedelta(days=9)), "cartao")
        s.appointment(valentina, "follow_up", at(today, "14:40"), "agendado")
        tx = s.family("Família Teixeira", [{"name": "Paula Teixeira", "relation": "mãe", "phone": "(11) 90000-0011"}])
        joaquim = s.child(tx, "Joaquim Teixeira", "M", months_ago(today, 24, -2), z=-0.4)
        s.history(joaquim, until=today - timedelta(days=5), skip=("24m",))
        s.appointment(joaquim, "well_child", at(today, "15:00"), "confirmado")
        du = s.family("Família Duarte", [{"name": "Renan Duarte", "relation": "pai", "phone": "(11) 90000-0012"}])
        cecilia = s.child(du, "Cecília Duarte", "F", today - timedelta(days=15), z=0.1)
        s.appointment(cecilia, "newborn", at(today, "15:40"), "confirmado")
        pires = s.family("Família Pires", [{"name": "Diego Pires", "relation": "pai", "phone": "(11) 90000-0013"}])
        lara = s.child(pires, "Lara Pires", "F", months_ago(today, 63), z=0.3)
        s.history(lara, until=today, paid=False)
        lexam = s.care_item(lara, "exame", "Urina tipo 1 e urocultura", created=today - timedelta(days=3),
                            due=today + timedelta(days=4), detail="depois do antibiótico")
        s.file(lara, "exame", "Urina tipo 1 e urocultura", tiny_pdf("Urina tipo 1 e urocultura (exemplo)",
               ["Resultado de demonstração.", "Leucócitos: 3.000/mL · Urocultura: negativa"]),
               by="familia", by_name="Diego, pai", created=now - timedelta(hours=2), care_item_id=lexam)

        # quem está com a puericultura atrasada (a busca ativa da recepção)
        martins = s.family("Família Martins", [{"name": "Tatiane Martins", "relation": "mãe", "phone": "(11) 90000-0014"}])
        enzo = s.child(martins, "Enzo Martins", "M", months_ago(today, 25, 10), z=0.2)
        s.history(enzo, until=today, skip=("24m",))
        nunes = s.family("Família Nunes", [{"name": "Juliana Nunes", "relation": "mãe", "phone": "(11) 90000-0015"}])
        sophia = s.child(nunes, "Sophia Nunes", "F", months_ago(today, 9, 28), z=-0.5)
        s.history(sophia, until=today, skip=("9m",), skip_vaccines=("fa-1",))
        lopes = s.family("Família Lopes", [{"name": "Marta Lopes", "relation": "mãe", "phone": "(11) 90000-0016"}])
        bernardo = s.child(lopes, "Bernardo Lopes", "M", months_ago(today, 13, 5), z=0.15)
        mbl = s.join(bernardo, "acompanhamento", months_ago(today, 1, 2), "boleto", 26)
        s.history(bernardo, until=today, skip=("12m",))
        gomes = s.family("Família Gomes", [{"name": "Lucas Gomes", "relation": "pai", "phone": "(11) 90000-0017"}])
        livia = s.child(gomes, "Lívia Gomes", "F", months_ago(today, 19, 10), z=0.0)
        mlg = s.join(livia, "acompanhamento", months_ago(today, 5), "cartao", 25)
        s.history(livia, until=today, skip=("18m",))

        # irmãos com o plano pausado
        andrade = s.family("Família Andrade", [{"name": "Renata Andrade", "relation": "mãe", "email": "renata@demo.test", "phone": "(11) 90000-0018"}])
        lis = s.child(andrade, "Lis Andrade", "F", months_ago(today, 40), z=0.1)
        tomas = s.child(andrade, "Tomás Andrade", "M", months_ago(today, 63), z=-0.1)
        nxt = months_ago(today, -1)
        s.join(lis, "acompanhamento", months_ago(today, 9), "pix_automatico", 1, status="pausado", paused_until=nxt)
        s.join(tomas, "acompanhamento", months_ago(today, 9), "pix_automatico", 1, status="pausado", paused_until=nxt, sibling=True)
        s.history(lis, until=today, paid=False)
        s.history(tomas, until=today, paid=False)
        freitas = s.family("Família Freitas", [{"name": "Gustavo Freitas", "relation": "pai", "phone": "(11) 90000-0019"}])
        miguel = s.child(freitas, "Miguel Freitas", "M", months_ago(today, 50), z=0.25)
        s.history(miguel, until=today, paid=False)

        # amanhã: a agenda que a recepção confirma (algumas famílias já confirmaram pelo app)
        tomorrow = today + timedelta(days=1)
        s.appointment(lis, "well_child", at(tomorrow, "08:00"), "agendado")
        s.appointment(tomas, "well_child", at(tomorrow, "08:40"), "confirmado", source="familia")
        s.appointment(miguel, "follow_up", at(tomorrow, "09:20"), "agendado")
        s.appointment(lara, "follow_up", at(tomorrow, "09:40"), "confirmado", source="familia")
        s.appointment(laura, "sick_visit", at(tomorrow, "11:00"), "agendado")

        # dinheiro: as mensalidades (três em atraso agora), as consultas por doença dos últimos meses e as despesas
        late_ids = {mhc: 6, mbl: 2, mlg: 3}
        s.plan_charges()
        for mid, days_late in late_ids.items():
            # a mensalidade deste mês fica em aberto, vencida há `days_late` dias, seja qual for o dia de hoje
            m = one(c, """SELECT m.*, p.name AS plan, pt.family_id FROM memberships m JOIN plans p ON p.id = m.plan_id
                          JOIN patients pt ON pt.id = m.patient_id WHERE m.id = ?""", (mid,))
            c.execute("DELETE FROM charges WHERE membership_id = ? AND substr(due_on, 1, 7) = ?", (mid, today.isoformat()[:7]))
            due = today - timedelta(days=days_late)
            insert(c, "charges", {"family_id": m["family_id"], "patient_id": m["patient_id"], "membership_id": mid,
                                  "description": f"Plano {m['plan']} · {MONTHS_FULL[due.month - 1].lower()}", "amount_cents": m["price_cents"],
                                  "due_on": due.isoformat(), "status": "aberta", "method": m["billing"], "invoice": "emitir",
                                  "created_at": now_iso()})
        s.sick_visits([theo, pedro, valentina, lara, enzo, miguel, joaquim, lis, tomas, laura])
        s.expenses([("Aluguel da sala · Clínica Girassol", "aluguel", 240000), ("Atendente · a sua parte", "equipe", 145000),
                    ("Vacinas e insumos", "material", 70000), ("Materiais e impressos", "material", 48000),
                    ("Contador", "servicos", 56000)])
        s.file(helena, "nota", "Nota fiscal · plano de " + ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
               "agosto", "setembro", "outubro", "novembro", "dezembro"][today.month - 1],
               tiny_pdf("Nota fiscal de serviço (exemplo)", ["Plano Primeiro Ano · R$ 690,00", "Documento de demonstração, sem valor fiscal."]),
               by="atendente", by_name="Carla Souza", created=now - timedelta(days=max(1, today.day - 5)))
    s.conn.close()


def _paulo(settings: Settings, pconn, practice_id: int, today: date, now: datetime) -> None:
    s = Practice(settings, pconn, practice_id, today, now)
    c = s.conn
    with transaction(c), transaction(pconn):
        c.execute("DELETE FROM reserved_slots")
        for wd in range(5):
            insert(c, "reserved_slots", {"weekday": wd, "start_min": 11 * 60, "duration_min": 30})
            insert(c, "reserved_slots", {"weekday": wd, "start_min": 11 * 60 + 30, "duration_min": 30})
        s.plan("primeiro", name="Primeiro Ano", description="O primeiro ano de vida.", price_cents=65000, months=12,
               entry_rule="entrada até os 3 meses", max_entry_age_m=3, discount_pct=10,
               benefits=[("well_child", 11, "consultas de puericultura"), ("sick_visit", 3, "consultas por doença")],
               perks=["Mensagens em horário comercial", "10% de desconto nos outros serviços"])
        nunes = s.family("Família Nunes", [{"name": "Carolina Nunes", "relation": "mãe", "phone": "(11) 90000-0101"}])
        davi = s.child(nunes, "Davi Nunes", "M", months_ago(today, 50), z=0.1)
        s.history(davi, until=today, paid=False)
        d1 = s.appointment(davi, "sick_visit", at(today, "08:00"), "atendido", akind="agudo")
        s.paid(davi, d1, "sick_visit", today, "pix", invoice="emitir")
        lins = s.family("Família Lins", [{"name": "Fernanda Lins", "relation": "mãe", "email": "fernanda@demo.test", "phone": "(11) 90000-0102"}])
        sofia = s.child(lins, "Sofia Lins", "F", months_ago(today, 6, 1), z=0.3)
        ms = s.join(sofia, "primeiro", date.fromisoformat(sofia["birth_date"]) + timedelta(days=7), "cartao", 12)
        s.history(sofia, until=today - timedelta(days=3), membership_id=ms)
        s.appointment(sofia, "well_child", at(today, "09:00"), "atendido", membership_id=ms)
        s.measure(sofia, today)
        prates = s.family("Família Prates", [{"name": "Helena Prates", "relation": "mãe", "phone": "(11) 90000-0103"}])
        lucas = s.child(prates, "Lucas Prates", "M", months_ago(today, 98), z=0.0)
        s.history(lucas, until=today, paid=False)
        s.appointment(lucas, "follow_up", at(today, "09:40"), "faltou")
        vieira = s.family("Família Vieira", [{"name": "Otávio Vieira", "relation": "pai", "phone": "(11) 90000-0104"}])
        isis = s.child(vieira, "Isis Vieira", "F", months_ago(today, 25), z=-0.2)
        s.history(isis, until=today, paid=False)
        s.appointment(isis, "sick_visit", at(today, "10:10"), "em_atendimento", arrived=now - timedelta(minutes=25))
        castro = s.family("Família Castro", [{"name": "Beatriz Castro", "relation": "mãe", "phone": "(11) 90000-0105"}])
        nina = s.child(castro, "Nina Castro", "F", today - timedelta(days=15), z=0.2)
        s.appointment(nina, "newborn", at(today, "10:40"), "chegou", arrived=now - timedelta(minutes=7))
        nog = s.family("Família Nogueira", [{"name": "Priscila Nogueira", "relation": "mãe", "phone": "(11) 90000-0106"}])
        livia = s.child(nog, "Lívia Nogueira", "F", months_ago(today, 6, 10), z=0.0)
        s.history(livia, until=today, skip=("6m",))
        s.plan_charges()
        s.sick_visits([davi, lucas, isis, livia], months_back=6)
        s.expenses([("Aluguel da sala · Clínica Girassol", "aluguel", 210000), ("Atendente · a sua parte", "equipe", 145000),
                    ("Contador", "servicos", 52000)])
        tomorrow = today + timedelta(days=1)
        s.appointment(lucas, "follow_up", at(tomorrow, "08:30"), "agendado")
        s.appointment(davi, "well_child", at(tomorrow, "09:00"), "confirmado", source="familia")
    s.conn.close()

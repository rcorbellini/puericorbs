"""Capturas das telas para conferir o layout: celular (390 px) e computador (1280 px), claro e escuro.

Uso (com o servidor no ar na porta 8930 e a demonstração semeada):
    uv run -q --with playwright python scripts/qa_shots.py PASTA [filtro]

Entra pelas contas da demonstração (sem senha), passa pelas telas de cada perfil e avisa erro de JavaScript e
rolagem lateral (a página não pode ser mais larga que a tela).
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://{host}:8930"
PHONE = {"width": 390, "height": 844}
DESK = {"width": 1280, "height": 900}


def shots(out: Path, only: str = "") -> int:
    out.mkdir(parents=True, exist_ok=True)
    problems = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")

        def run(name: str, host: str, hash_: str, viewport: dict, who: str | None = None, theme: str = "claro",
                before=None, expect_404: bool = False, after=None) -> None:
            nonlocal problems
            if only and only not in name:
                return
            ctx = browser.new_context(viewport=viewport, device_scale_factor=2 if viewport is PHONE else 1,
                                      locale="pt-BR", timezone_id="America/Sao_Paulo")
            ctx.add_init_script(f"try {{ localStorage.setItem('pc-theme', '{theme}') }} catch (e) {{}}")
            page = ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            # a tela que mostra um 404 de propósito (o convite inventado) não conta o 404 como erro
            page.on("console", lambda m: errors.append(m.text) if m.type == "error"
                    and not (expect_404 and "status of 404" in m.text) else None)
            base = BASE.format(host=host)
            if who:
                r = ctx.request.post(f"{base}/api/auth/demo", data={"email": who}, headers={"X-PC": "1"})
                assert r.ok, (name, r.status, r.text())
            extra = before(ctx, base) if before else ""
            page.goto(f"{base}/{hash_}{extra}")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)
            if after:
                after(page)
                page.wait_for_timeout(500)
            wide = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            page.screenshot(path=str(out / f"{name}.png"), full_page=True)
            if errors or wide:
                problems += 1
                print(f"!! {name}: {'rolagem lateral; ' if wide else ''}{' | '.join(errors)[:600]}")
            else:
                print(f"ok {name}")
            ctx.close()

        def encounter(ctx, base):
            r = ctx.request.get(f"{base}/api/staff/today")
            focus = r.json()["focus"]["appointment"]["id"]
            e = ctx.request.post(f"{base}/api/staff/appointments/{focus}/encounter", headers={"X-PC": "1"})
            return str(e.json()["encounter_id"])

        def invite(role: str, kind: str = "staff", clinic: bool = False):
            """O token de um convite novo. `clinic`: o da equipe do consultório (a pediatra que entra nele, a atendente,
            a administração); sem ele, o de pediatra é o de um consultório criado vazio."""
            def make(ctx, base):
                from puericorbs import config, invites
                from puericorbs.db import connect_platform, connect_practice, one
                data = config.load().data_dir
                pconn = connect_platform(data)
                try:
                    if kind == "family":  # um responsável sem conta ainda
                        g = one(connect_practice(data, 1), "SELECT id FROM guardians WHERE user_id IS NULL ORDER BY id LIMIT 1")
                        return invites.create(pconn, kind="family", practice_id=1, guardian_id=g["id"])[0]
                    if kind != "staff":
                        return invites.create(pconn, kind=kind, created_by=2)[0]
                    if clinic:
                        cid = one(pconn, "SELECT clinic_id FROM practices WHERE id = 1")["clinic_id"]
                        return invites.create(pconn, kind="staff", clinic_id=cid, role=role, label="Ana Lúcia Prado")[0]
                    return invites.create(pconn, kind="staff", practice_id=1, role=role)[0]
                finally:
                    pconn.close()
            return make

        def family_prefill(token: bool = True):
            """Um convite de família nova, com o que a recepção já sabia (a mãe e o nome da criança)."""
            def make(ctx, base):
                import json
                from puericorbs import config, invites
                from puericorbs.db import connect_platform, connect_practice, insert, now_iso
                data = config.load().data_dir
                pconn = connect_platform(data)
                tok, iid = invites.create(pconn, kind="family", practice_id=1)
                pconn.close()
                conn = connect_practice(data, 1)
                insert(conn, "invite_prefill", {"invite_id": iid, "created_at": now_iso(), "data": json.dumps(
                    {"guardian": {"name": "Rita Prado", "relation": "mãe", "phone": "(11) 95555-2000"},
                     "child": {"name": "Davi Prado", "sex": "M"}}, ensure_ascii=False)})
                conn.close()
                return tok if token else ""
            return make

        def click(selector: str):
            return lambda page: page.click(selector)

        def click_then(selector: str, ready: str):
            """Clica e espera a próxima página (o link de entrada muda de endereço; voltar ao painel recarrega)."""
            def go(page):
                page.click(selector)
                page.wait_for_selector(ready)
                page.wait_for_load_state("networkidle")
            return go

        def view_as(email: str = "", family: str = ""):
            """O link de entrada da administração no consultório 1, vendo como a conta (email) ou como uma família
            ("com conta" ou "sem conta")."""
            def make(ctx, base):
                from puericorbs import config
                from puericorbs.db import connect_platform, connect_practice, one
                data = config.load().data_dir
                if email:
                    pconn = connect_platform(data)
                    target = {"user_id": one(pconn, "SELECT id FROM users WHERE email = ?", (email,))["id"]}
                    pconn.close()
                else:
                    conn = connect_practice(data, 1)
                    cond = "IS NULL" if family == "sem conta" else "IS NOT NULL"
                    target = {"guardian_id": one(conn, f"SELECT id FROM guardians WHERE user_id {cond} ORDER BY id LIMIT 1")["id"]}
                    conn.close()
                r = ctx.request.post(f"{base}/api/admin/view-as", data={"practice_id": 1, **target}, headers={"X-PC": "1"})
                assert r.ok, (r.status, r.text())
                return r.json()["url"].lstrip("/")
            return make

        def closed_day(ctx, base):
            """Fecha a agenda da Dra. Marina num dia com consulta marcada e abre a agenda nesse dia."""
            from datetime import date, timedelta
            day = (date.today() + timedelta(days=1)).isoformat()
            if not any(c["reason"] == "Doença" for c in ctx.request.get(f"{base}/api/staff/schedule").json()["closures"]):
                r = ctx.request.post(f"{base}/api/staff/closures", data={"start": day, "end": day, "reason": "Doença"},
                                     headers={"X-PC": "1"})
                assert r.ok, (r.status, r.text())
            return f"?d={day}"

        def reopen_all(ctx, base):
            """Desfaz o fechamento de closed_day (a demonstração volta como estava)."""
            for c in ctx.request.get(f"{base}/api/staff/schedule").json()["closures"]:
                if c["reason"] == "Doença":
                    ctx.request.delete(f"{base}/api/staff/closures/{c['id']}", headers={"X-PC": "1"})

        def tomorrow(ctx, base):
            from datetime import date, timedelta
            return f"?d={(date.today() + timedelta(days=1)).isoformat()}"

        m, c, a, adm = "marina@demo.test", "carla@demo.test", "ana@demo.test", "admin@demo.test"
        run("plataforma-1280", "localhost", "", DESK)
        run("plataforma-390", "localhost", "", PHONE)
        run("site-1280", "dramarina.localhost", "", DESK)
        run("site-390", "dramarina.localhost", "", PHONE)
        run("site-paulo-1280", "drpauloreis.localhost", "", DESK)
        run("hoje-1280", "dramarina.localhost", "#/hoje", DESK, m)
        run("hoje-390", "dramarina.localhost", "#/hoje", PHONE, m)
        run("hoje-escuro-1280", "dramarina.localhost", "#/hoje", DESK, m, theme="escuro")
        run("agenda-1280", "dramarina.localhost", "#/agenda", DESK, m)
        run("pacientes-1280", "dramarina.localhost", "#/pacientes", DESK, m)
        for tab in ("cuidado", "curvas", "vacinas", "marcos", "consultas", "arquivos", "agenda"):
            run(f"paciente-{tab}-1280", "dramarina.localhost", f"#/paciente/1?tab={tab}", DESK, m)
        run("paciente-curvas-390", "dramarina.localhost", "#/paciente/1?tab=curvas", PHONE, m)
        run("consulta-1280", "dramarina.localhost", "#/consulta/", DESK, m, before=encounter)
        run("consulta-390", "dramarina.localhost", "#/consulta/", PHONE, m, before=encounter)
        run("revisar-1280", "dramarina.localhost", "#/revisar", DESK, m)
        run("servicos-1280", "dramarina.localhost", "#/servicos?s=2", DESK, m)
        run("servicos-390", "dramarina.localhost", "#/servicos?s=2", PHONE, m)
        run("planos-1280", "dramarina.localhost", "#/planos", DESK, m)
        run("financeiro-1280", "dramarina.localhost", "#/financeiro", DESK, m)
        run("financeiro-390", "dramarina.localhost", "#/financeiro", PHONE, m)
        run("consultorio-1280", "dramarina.localhost", "#/consultorio", DESK, m)
        run("consultorio-390", "dramarina.localhost", "#/consultorio", PHONE, m)
        run("consultorio-escuro-1280", "dramarina.localhost", "#/consultorio", DESK, m, theme="escuro")
        run("convite-1280", "dramarina.localhost", "#/convite/", DESK, before=invite("clinician"))
        run("convite-390", "dramarina.localhost", "#/convite/", PHONE, before=invite("clinician"))
        run("convite-escuro-390", "dramarina.localhost", "#/convite/", PHONE, theme="escuro", before=invite("clinician"))
        run("convite-recepcao-390", "dramarina.localhost", "#/convite/", PHONE, before=invite("receptionist"))
        run("convite-invalido-390", "dramarina.localhost", "#/convite/inventado", PHONE, expect_404=True)
        run("convite-pediatra-do-consultorio-390", "dramarina.localhost", "#/convite/", PHONE, before=invite("clinician", clinic=True))
        run("convite-administracao-do-consultorio-390", "dramarina.localhost", "#/convite/", PHONE, before=invite("manager", clinic=True))
        run("convite-familia-nova-390", "dramarina.localhost", "#/convite/", PHONE, before=family_prefill())
        run("convite-familia-nova-escuro-390", "dramarina.localhost", "#/convite/", PHONE, theme="escuro", before=family_prefill())
        run("convidar-familia-390", "dramarina.localhost", "#/recepcao", PHONE, c, after=click('[data-act="invite-family"]'))
        run("familias-convites-1280", "dramarina.localhost", "#/pacientes", DESK, c, before=family_prefill(token=False))
        run("convite-qr-390", "dramarina.localhost", "#/consultorio", PHONE, m, after=lambda page: (
            page.click('[data-team="invite"]'), page.click('dialog.dlg .dlg-foot .btn:not(.ghost)'),
            page.wait_for_selector('[data-mode="qr"]'), page.click('[data-mode="qr"]')))
        # CPF ou CNPJ: a conta com outro faturamento, refeita na hora, e as duas listas abertas
        conta = lambda page: (page.fill('#cpf-ou-cnpj [name="revenue"]', "30.000,00"),
                              page.fill('#cpf-ou-cnpj [name="accountant"]', "500,00"), page.wait_for_timeout(800),
                              [d.evaluate("d => d.open = true") for d in page.query_selector_all('#cpf-ou-cnpj details')])
        run("consultorio-conta-390", "dramarina.localhost", "#/consultorio", PHONE, m, after=conta)
        run("consultorio-conta-escuro-1280", "dramarina.localhost", "#/consultorio", DESK, m, theme="escuro", after=conta)
        run("consultorio-bia-1280", "dramarina.localhost", "#/consultorio", DESK, "bia@demo.test")
        run("consultorio-bia-390", "dramarina.localhost", "#/consultorio", PHONE, "bia@demo.test")
        run("consultorio-convidar-390", "dramarina.localhost", "#/consultorio", PHONE, m, after=click('[data-team="invite"]'))
        run("consultorio-paulo-1280", "drpauloreis.localhost", "#/consultorio", DESK, "paulo@demo.test")
        run("recepcao-bia-390", "dramarina.localhost", "#/recepcao", PHONE, "bia@demo.test")
        # como a pediatra recebe e o recibo (ou a nota) de cada pagamento (fiscal.py)
        run("recebe-paulo-390", "drpauloreis.localhost", "#/consultorio", PHONE, "paulo@demo.test")
        run("recebe-ainda-nao-sei-390", "dramarina.localhost", "#/consultorio", PHONE, m, after=click('[data-mode=""]'))
        run("recebe-empresa-escuro-390", "dramarina.localhost", "#/consultorio", PHONE, m, theme="escuro",
            after=click('[data-mode="pj"]'))
        run("emitir-recibo-390", "dramarina.localhost", "#/recepcao", PHONE, c, after=click('[data-act="issue"]'))
        run("emitir-recibo-escuro-390", "dramarina.localhost", "#/recepcao", PHONE, c, theme="escuro",
            after=click('[data-act="issue"]'))
        run("emitir-nota-1280", "drpauloreis.localhost", "#/financeiro", DESK, "paulo@demo.test", after=click('[data-act="issue"]'))
        run("convite-familia-390", "dramarina.localhost", "#/convite/", PHONE, before=invite("", "family"))
        run("convite-colega-1280", "dramarina.localhost", "#/convite/", DESK, before=invite("", "practice"))
        run("convite-colega-390", "dramarina.localhost", "#/convite/", PHONE, before=invite("", "practice"))
        run("convite-admin-390", "dramarina.localhost", "#/convite/", PHONE, before=invite("", "admin"))
        run("acesso-familia-1280", "dramarina.localhost", "#/paciente/1", DESK, m, after=click('[data-act="access"]'))
        run("acesso-familia-390", "dramarina.localhost", "#/paciente/1", PHONE, m, after=click('[data-act="access"]'))
        run("acesso-familia-recepcao-390", "dramarina.localhost", "#/paciente/1", PHONE, c, after=click('[data-act="access"]'))
        run("admin-entrar-390", "dramarina.localhost", "#/admin", PHONE)
        run("admin-1280", "localhost", "#/admin", DESK, "admin@demo.test")
        run("admin-390", "localhost", "#/admin", PHONE, "admin@demo.test")
        run("admin-escuro-1280", "localhost", "#/admin", DESK, "admin@demo.test", theme="escuro")
        run("admin-no-site-390", "dramarina.localhost", "", PHONE, "admin@demo.test")
        run("admin-familias-390", "localhost", "#/admin", PHONE, adm, after=click('[data-act="as-family"]'))
        run("admin-familias-1280", "localhost", "#/admin", DESK, adm, after=click('[data-act="as-family"]'))
        run("admin-entrada-vencida-390", "localhost", "#/admin/entrada-vencida", PHONE, adm)
        run("admin-ver-como-clique-1280", "localhost", "#/admin", DESK, adm, after=click_then('[data-act="as-user"]', ".actingbar"))
        run("vendo-como-pediatra-1280", "dramarina.localhost", "", DESK, adm, before=view_as(m))
        run("vendo-como-pediatra-390", "dramarina.localhost", "", PHONE, adm, before=view_as(m))
        run("vendo-como-pediatra-escuro-1280", "dramarina.localhost", "", DESK, adm, theme="escuro", before=view_as(m))
        run("vendo-como-recepcao-390", "dramarina.localhost", "", PHONE, adm, before=view_as(c))
        run("vendo-como-familia-390", "dramarina.localhost", "", PHONE, adm, before=view_as(family="com conta"))
        run("vendo-como-familia-escuro-390", "dramarina.localhost", "", PHONE, adm, theme="escuro", before=view_as(family="com conta"))
        run("vendo-como-familia-sem-conta-390", "dramarina.localhost", "", PHONE, adm, before=view_as(family="sem conta"))
        run("vendo-como-voltar-1280", "dramarina.localhost", "", DESK, adm, before=view_as(m), after=click_then(".actingbar button", ".pcard"))
        run("horarios-1280", "dramarina.localhost", "#/horarios", DESK, m)
        run("horarios-390", "dramarina.localhost", "#/horarios", PHONE, m)
        run("horarios-escuro-390", "dramarina.localhost", "#/horarios", PHONE, m, theme="escuro")
        run("horarios-recepcao-390", "dramarina.localhost", "#/horarios", PHONE, c)
        run("horarios-fechar-390", "dramarina.localhost", "#/horarios", PHONE, m, after=click('[data-act="close"]'))
        run("horarios-sabado-390", "dramarina.localhost", "#/horarios", PHONE, m, after=click('[data-day="5"]'))
        run("agenda-amanha-dialogo-390", "dramarina.localhost", "#/agenda", PHONE, c, before=tomorrow,
            after=click('.appt:has(.pill.todo)'))
        run("agenda-fechada-1280", "dramarina.localhost", "#/agenda", DESK, m, before=closed_day)
        run("agenda-fechada-390", "dramarina.localhost", "#/agenda", PHONE, m, before=closed_day)
        run("horarios-com-fechamento-390", "dramarina.localhost", "#/horarios", PHONE, m, before=closed_day,
            after=click('[data-act="warn"]'))
        run("horarios-limpa", "dramarina.localhost", "#/horarios", PHONE, m, before=lambda ctx, base: reopen_all(ctx, base) or "")
        run("recepcao-1280", "dramarina.localhost", "#/recepcao", DESK, c)
        run("recepcao-390", "dramarina.localhost", "#/recepcao", PHONE, c)
        run("recepcao-agenda-1280", "dramarina.localhost", "#/agenda", DESK, c)
        run("recepcao-paciente-1280", "dramarina.localhost", "#/paciente/1", DESK, c)
        run("familia-inicio-390", "dramarina.localhost", "#/inicio", PHONE, a)
        run("familia-inicio-escuro-390", "dramarina.localhost", "#/inicio", PHONE, a, theme="escuro")
        run("familia-inicio-1280", "dramarina.localhost", "#/inicio", DESK, a)
        run("familia-agenda-390", "dramarina.localhost", "#/agenda", PHONE, a)
        run("familia-agendar-390", "dramarina.localhost", "#/agendar", PHONE, a)
        run("familia-saude-390", "dramarina.localhost", "#/saude", PHONE, a)
        run("familia-arquivos-390", "dramarina.localhost", "#/arquivos", PHONE, a)
        run("familia-theo-390", "dramarina.localhost", "#/inicio?c=2", PHONE, a)
        browser.close()
    return problems


if __name__ == "__main__":
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "shots")
    sys.exit(1 if shots(folder, sys.argv[2] if len(sys.argv) > 2 else "") else 0)

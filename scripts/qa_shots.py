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
                before=None, expect_404: bool = False) -> None:
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

        def invite(role: str):
            def make(ctx, base):
                from puericorbs import config, invites
                from puericorbs.db import connect_platform
                pconn = connect_platform(config.load().data_dir)
                try:
                    return invites.create(pconn, 1, role)
                finally:
                    pconn.close()
            return make

        m, c, a = "marina@demo.test", "carla@demo.test", "ana@demo.test"
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

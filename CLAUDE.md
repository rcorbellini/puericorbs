# Puericorbs: como trabalhar neste projeto

O Puericorbs é um SaaS self-hosted para o consultório pediátrico pequeno: agenda, financeiro, acompanhamento da
criança, planos recorrentes e arquivos. Cada pediatra tem o próprio domínio, todos apontam para este servidor, e o
endereço decide a prática. O uso e a instalação estão no `README.md`; aqui fica o que importa para mexer no código.

## Idioma e tom

- Responda em português do Brasil. Documentos, textos da tela, mensagens de erro, comentários e commits também em PT-BR.
- Identificadores no código (variáveis, funções, rotas, tabelas, colunas) em inglês. O nome de cada termo do domínio
  está em `docs/glossario.md`: use o de lá ("plano" é `plan`, nunca `care_plan`).
- Frases curtas e diretas, que dizem o porquê. Mensagem de erro diz o que fazer.

## Invariantes (não se negociam)

1. **Cada pediatra só vê os seus pacientes.** Cada prática tem o próprio banco (`data/practices/p<id>/practice.db`); o
   banco da plataforma não guarda dado de paciente. Na API, outra prática só se abre por `_practice()` (em
   `api_staff.py`), que confere a filiação (`staff_practices`). No consultório com várias pediatras, a atendente e a
   administração do consultório atendem todas, sem nada clínico; a pediatra, mesmo a que administra, só a dela. Quem
   entra por um domínio do consultório cai na prática que é sua (`context.py`), nunca na de outro consultório. Toda rota
   nova de paciente ganha um teste em `tests/test_isolation.py`.
2. **A atendente e a administração do consultório nunca veem conteúdo clínico.** O servidor monta a resposta sem ele (`views.patient_brief(clinical=False)`,
   `care.timeline(audience="reception")`); a tela nunca esconde o que chegou.
3. **A família vê o que foi liberado para ela.** Todo arquivo e item do cuidado tem visibilidade (`internal`, `family`,
   `admin`), decidida no servidor. Criança de outra família responde 404, nunca 403.
4. **Prontuário não se apaga.** Corrige-se com histórico. Guarda mínima de 20 anos.
5. **Todo acesso a dado de paciente pela equipe vai para o `audit_log`** da prática (`ctx.audit`).
6. **O serviço é a unidade de configuração** (`catalog.py`): o que o pediatra quiser mudar mora no `config` dele.
7. **O que deve acontecer com a criança sai de `care.timeline`.** A tela da família, a busca ativa e os painéis leem
   dali; lista paralela não existe.
8. **Pedido que muda dado precisa do cabeçalho `X-PC: 1`** (a proteção contra CSRF do `server.py`).
9. **Uma conta só se liga com a senha dela.** Toda conta nasce de um convite (`invites.py`): a plataforma convida a
   pediatra que cria o consultório; a administração do consultório, a equipe; a pediatra e a recepção, as famílias. O cadastro não liga
   responsável a conta nenhuma, e o link da família só troca a senha de quem é só daquela família, naquele consultório.
10. **A administração vê como quem usa, e fica registrado.** O painel (`api_admin.py`) só conta; a ficha, a agenda e o
   app da família ela vê entrando no consultório **vendo como** a pediatra, a atendente ou uma família, com a faixa no
   topo. Lá, `ctx.user` e `ctx.role` são os da pessoa e `ctx.actor` é a administração (`context.py`): cada pedido vai
   para o `audit_log` do consultório com o `actor_id`. Fora disso, nenhuma rota de paciente aceita a administração, e o
   nome de família nunca vai para o banco da plataforma.
11. **A produção nunca recebe a demonstração.** Ela mora em `~/.local/share/puericorbs` com `demo = false`; a semente
   se recusa a rodar ali, e nenhum comando de teste ou captura aponta para ela. Comando na produção leva `--data`.
12. **A página nova chega a quem já abriu o site.** O `index.html` sai com `/static/v/<versão>/` (`server.py`), porque
   o Cloudflare guarda .js e .css no navegador por 4 horas, até por cima do `no-cache`. Import entre módulos e `url()`
   do CSS são sempre relativos (`./lib.js`, `fonts/…`): um caminho que começa com `/static/` escapa da versão.
13. **Nada que já estava marcado é desmarcado sozinho.** Mudar os horários ou fechar a agenda nunca cancela consulta:
   a resposta devolve as consultas afetadas, com o telefone da família, para a recepção avisar (`scheduling.py`).

## Comandos

| Para | Comando |
|---|---|
| Instalar | `uv sync` |
| Testes | `uv run -q pytest -q` (~5 s) |
| Demonstração do zero | `uv run puericorbs seed --reset` |
| Servidor | `uv run puericorbs serve` (porta 8930) |
| Domínio para uma prática | `uv run puericorbs domain HOST SLUG` |
| Consultório novo, na produção | `uv run puericorbs --data ~/.local/share/puericorbs practice SLUG --name "…" --domain HOST` |
| Convite (o link de primeiro acesso) | `uv run puericorbs --data ~/.local/share/puericorbs invite SLUG [--role receptionist]` ou `invite --admin` |
| Capturas das telas | `uv run -q --with playwright python scripts/qa_shots.py PASTA [filtro]` (390 e 1280 px, claro e escuro; acusa erro de JavaScript e rolagem lateral) |
| Sintaxe do JavaScript | `cd puericorbs/web/js && for f in *.js; do node --experimental-default-type=module --check $f; done` |

- Três serviços de usuário do systemd (as unidades estão em `deploy/`): `puericorbs-producao` (8931, os consultórios
  de verdade), `puericorbs-demo` (8930) e `puericorbs-tunel` (o túnel do Cloudflare, separado do túnel do CardLine).
  Depois de mudar o código: `systemctl --user restart puericorbs-producao puericorbs-demo`. O túnel e o DNS estão em
  `docs/dominios.md`; as credenciais do túnel ficam em `~/.cloudflared/` e nunca aparecem na conversa nem no git.
- Nunca use `pkill -f` com um padrão que aparece na própria linha de comando: ele mata o seu shell. Ache o processo
  pela porta (`ss -ltnp | grep 8930`).

## Mapa do código

- `config.py`: o `puericorbs.toml` (no git) e, por cima, o `data/config.toml` (fora do git). `demo = true` liga as
  contas sem senha e a visita aos sites pelo endereço da plataforma: **desligar em produção**.
- `db.py`: os dois esquemas (plataforma e prática), com `PRAGMA user_version` e migrações (suba a versão, ponha a coluna
  no esquema e escreva a migração).
- `tenancy.py`: o endereço → a prática (domínio cadastrado, subdomínio `<slug>.<base>`, plataforma); o `www.` volta
  para o domínio sem ele.
- `clinics.py`: o consultório (a clínica): as pediatras dele e a equipe que atende todas (`clinic_members`: a
  atendente e a administração do consultório).
- `invites.py`: os quatro convites (consultório próprio, equipe do consultório, família, administração), onde cada um
  abre, o QR code de cada link (`qr_svg`, com o `segno`) e o registro da plataforma. `api_invites.py`: abrir, aceitar, a equipe do consultório e o que a pediatra e a
  recepção geram. `api_admin.py`: o painel e o "vendo como" (o link de entrada, `handoffs`).
- `context.py`: o contexto de cada pedido (site, usuário, papel, a prática de quem entra por outro domínio do
  consultório e, com a administração vendo como alguém, `actor`) e os guardas (`staff`, `clinician`, `manager`,
  `family`).
- `auth.py`: senha (scrypt) e sessão (token no cookie, hash no banco).
- `catalog.py`: o catálogo de serviços, a configuração padrão e os modelos de registro.
- `protocols.py`: puericultura, vacinas (PNI) e marcos. `care.py`: a linha do cuidado. `growth.py`: as curvas da OMS
  (`data/who_lms.json`, do pacote anthro da OMS).
- `scheduling.py`: horários livres, marcar, mudar o estado, a grade da pediatra (`set_hours`) e a agenda fechada
  (`closure`). `plans.py`: cota e cobertura. `finance.py`: cobranças e resumo do mês. `fiscal.py`: como a pediatra
  recebe (pessoa física ou empresa; por ora, na cidade de São Paulo) e o documento de cada pagamento (o recibo do
  Receita Saúde ou a nota), com o CPF e o CNPJ conferidos pelos dígitos; as rotas em `api_fiscal.py`. `files.py`:
  guardar, limpar EXIF, quem vê.
- `api_public.py`, `api_staff.py`, `api_family.py`: as rotas. `views.py`: o formato das respostas.
- `share.py`: como o consultório aparece fora da página: o nome do app no celular (o manifesto), as metatags e a
  imagem da prévia do link (`/og.png`), montados pelo endereço em `server.py`.
- `seed.py`: a demonstração (tudo relativo ao dia de hoje; recusa a pasta com `demo = false`). `practices.py`: criar
  uma prática (com ou sem pediatra; sem, ela entra pelo convite).
- `web/`: a página, sem build e sem framework. `glass.css` (os tokens e o vidro), `app.css` (layout), `js/main.js`
  (entrada), `js/staff*.js` (equipe; o Consultório e a equipe estão em `staff-admin.js`, os Horários em
  `staff-schedule.js`, e o WhatsApp com a mensagem pronta e o diálogo de emitir o recibo ou a nota em
  `staff-common.js`), `js/family.js` (família),
  `js/site.js` (plataforma, site público e convite), `js/admin.js` (o painel da administração), `js/lib.js`
  (html escapado, API, formatos, ícones, diálogos), `js/charts.js` (curva e barras).

## Visual

Vidro líquido claro, derivado do CardLine (`~/cardline/docs/design.md` tem as regras e as armadilhas). Os tokens e o que
muda estão em `docs/identidade-visual.md`; o protótipo das telas é o canvas
https://claude.ai/artifact/Mrnek95xeh8xLoHdqJarYZ. Regras de sempre: uma ação com a cor do destaque por tela, opção
marcada sem cor, nada de vidro sobre vidro, estado com palavra. Mudou o layout? Rode as capturas e confira 390 e 1280 px.

## Como entregar

1. Se faltar uma decisão que só o dono pode tomar, pergunte uma vez, com uma opção recomendada. O resto, decida e
   conte na resposta.
2. Testes passando; mudou a tela, capturas sem erro.
3. Mudou uma decisão de produto? `docs/decisoes.md` e o documento do módulo no mesmo commit.
4. Um commit por funcionalidade, título e corpo em PT-BR (o que muda e o porquê). Depois, reinicie o serviço.
5. Dado real de paciente nunca entra em teste, exemplo, captura, documento ou commit.

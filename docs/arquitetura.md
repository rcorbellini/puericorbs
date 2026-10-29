# Arquitetura

> 28/10/2026 · o modelo e o que a v0.1 já faz dele. Os nomes no código estão em `glossario.md`; o mapa do código, no
> `CLAUDE.md`.

## Quem é dono de quê

```
Clínica (opcional) ─┬─ Unidades ── Salas
                    ├─ Equipe: atendentes, gestor, enfermagem
                    └─ Práticas ─┬─ Pediatra(s)
                                 ├─ Serviços, planos, protocolos, modelos
                                 ├─ Grade e agenda (por unidade)
                                 ├─ Financeiro
                                 └─ Vínculos ── Criança ── Família (responsáveis)
```

- **A prática é a unidade de isolamento.** Pacientes, prontuários, serviços, planos e dinheiro são dela. Um pediatra
  sozinho é uma prática. Dois pediatras na mesma clínica são duas práticas, e cada um só vê os seus, a não ser que
  escolham uma prática em grupo.
- **A clínica é o lugar e a equipe que as práticas dividem:** unidades, salas, atendentes, gestor e o repasse. A
  clínica não é dona de paciente nenhum.
- **A família tem conta própria, fora das práticas.** O responsável entra uma vez e vê os filhos em todas as
  práticas que os atendem (ex.: mudou de pediatra).
- **O vínculo (criança × prática) é o que dá acesso.** Sem vínculo, a prática não acha a criança, nem pelo CPF, e não
  descobre que ela existe em outra prática.
- **A família é dona da identidade da criança; cada prática guarda o prontuário que produziu.** Levar o histórico de
  uma prática para outra é decisão da família (portabilidade), feita no app.
- **Na LGPD,** a prática é a controladora dos dados de saúde que produz e o Puericorbs é o operador. Os dados da conta da
  família (login, contato) têm o Puericorbs como controlador.

Por que não isolar pela clínica: o pedido é "cada um vendo só os seus pacientes", e o pediatra muitas vezes atende
em mais de um lugar, com a família seguindo o médico, não a clínica.

## O que cada papel vê

| | Pediatra | Atendente | Gestor da clínica | Responsável legal | Cuidador | Contador |
|---|---|---|---|---|---|---|
| Agenda | da prática | das práticas que atende | ocupação, sem nomes | dos filhos | dos filhos | — |
| Cadastro e contato | sim | sim | — | o próprio | — | — |
| Registro clínico (prontuário) | sim | **nunca** | **nunca** | não (cópia por pedido formal) | — | — |
| Resumo, próximos passos, curvas, vacinas | sim | só o que é de agenda (consulta a marcar) | — | sim | orientações | — |
| Exames e fotos clínicas | sim | **nunca** | — | sim | — | — |
| Comprovantes, recibos, notas | sim | sim | — | sim | — | sim |
| Financeiro da prática | sim | lança e recebe; o resultado, só se liberado | o repasse | o que pagou | — | leitura |
| Serviços, planos, configuração | sim | leitura | — | — | — | — |

## Visibilidade de cada registro

Todo registro e todo arquivo carrega uma visibilidade:

| Visibilidade | Quem vê | Padrão para |
|---|---|---|
| `internal` | os pediatras da prática | registro clínico, notas internas |
| `family` | + os responsáveis legais | resumo para a família, próximos passos, vacinas, curvas, documentos entregues, arquivos enviados pela família |
| `admin` | + a atendente | comprovantes, recibos, notas fiscais, documentos de cadastro |
| `confidential` | só o pediatra autor (e quem ele indicar) | sigilo do adolescente (Código de Ética Médica, art. 74); nunca chega aos responsáveis |

A visibilidade é decidida no servidor, na consulta ao banco, nunca na tela.

## Como o isolamento é garantido

- **Um banco por prática.** Cada prática tem o próprio arquivo SQLite (`data/practices/p<id>/practice.db`); o banco da
  plataforma guarda contas, sessões, práticas, domínios, filiações e convites, e nenhum dado de paciente. Um filtro
  esquecido não vaza nada: o banco da outra prática nem está aberto.
- **A rota abre outra prática só pela filiação.** `_practice()` (em `api_staff.py`) confere se quem pede trabalha na
  prática antes de abrir o banco dela; a atendente da clínica atende mais de uma assim.
- **Teste de isolamento obrigatório** (`tests/test_isolation.py`) para cada rota com dado de paciente: o teste tenta
  atravessar a fronteira e precisa ser barrado. O teste já foi provado quebrando a guarda de propósito.
- **Arquivos** na pasta da prática, com nome aleatório, servidos por uma rota que confere a permissão de cada pedido
  (`files.can_see`) e registra quem abriu.
- **Log de auditoria** por prática: quem da equipe viu ou mudou qual registro, quando e de onde.
- **Produção e demonstração em instâncias separadas** (`dominios.md`): a demonstração, que entra sem senha, nunca
  divide pasta com consultório de verdade.
- A fazer: acesso fora da prática (cobertura entre pediatras, suporte) como concessão com prazo, motivo e registro.

## Como cada pessoa entra: o convite

Ninguém escolhe a senha de ninguém. Toda conta nasce de um convite (`invites.py`, `api_invites.py`): um link de uso
único, que vale 7 dias, gerado por quem tem o direito e mandado por essa pessoa (WhatsApp, cópia); o Puericorbs não
manda nada sozinho.

| Convite | Quem gera | Onde abre | O que faz |
|---|---|---|---|
| Pediatra (equipe) | a administração, para um consultório que ainda não tem pediatra | o domínio do consultório | cria a conta; ela diz o nome do site e o CRM |
| Atendente (equipe) | a pediatra, em **Consultório** | o domínio do consultório | cria a conta da atendente; a pediatra pode tirar o acesso depois |
| Família | a pediatra ou a recepção, na ficha (**Acesso da família**) | o domínio do consultório | o responsável cria a senha do app (ou uma nova, se esqueceu) |
| Colega | a pediatra, em **Consultório**; a administração, no painel | qualquer site nosso | o colega cria a conta e o **próprio** consultório, que nasce sem domínio até a plataforma ligar um |
| Administração | a administração, no painel; a linha de comando | qualquer site nosso | uma conta da plataforma (senha de 12 ou mais) |

As regras que fecham o caminho para tomar a conta de alguém:

- **Uma conta que já existe só se liga com a senha dela.** O cadastro da recepção não liga o responsável a conta
  nenhuma (o e-mail digitado não prova nada); quem liga é a própria pessoa, ao aceitar o convite.
- **O link da família só troca a senha de quem é só daquela família, naquele consultório.** A conta da equipe, da
  administração ou de quem também é responsável em outro consultório pede a senha que já tem.
- **A plataforma não põe ninguém dentro de um consultório que já tem pediatra:** a equipe é a pediatra quem convida.
- **Senha errada demais espera:** 10 por endereço ou 20 por conta em 15 minutos (`auth.throttled`).

## O painel da administração

Em `#/admin`, de qualquer site nosso (ainda não há domínio da plataforma). A administração vê os consultórios em
números (crianças, famílias, contas da família, consultas), a equipe de cada um, os convites (menos os da família, que
levam o nome do responsável) e o registro da plataforma (`platform_log`); liga domínios e gera os convites dela.

**Vendo como.** Em cada consultório, **Ver como** (numa pessoa da equipe) ou **Ver como uma família** (a busca pelo
responsável ou pela criança) leva a administração para dentro dele, com a tela e as ações dessa pessoa e uma faixa no
topo ("Vendo como …", **Voltar ao painel**). Como cada domínio tem a própria sessão, o painel gera um link de entrada
(`handoffs`: 2 minutos, uso único, só no domínio daquele consultório), que liga o "vendo como" na sessão da
administração naquele endereço (`sessions.as_*`). Lá, `ctx.user` e `ctx.role` são os da pessoa e `ctx.actor` é a
administração; cada pedido vai para o `audit_log` do consultório com o `actor_id`. Fora do "vendo como", a
administração não abre ficha, lista de pacientes ou arquivo. Consultório sem domínio ainda não tem onde entrar.

## Como o consultório aparece fora da página

O app instalado e a prévia do link levam o nome que a pediatra deu ao consultório. Quem lê o link (o WhatsApp, o
iMessage) não roda o JavaScript, então tudo sai do servidor para cada endereço (`share.py`): o `<title>` e as metatags
(`og:*`, `apple-mobile-web-app-title`) entram no lugar do `<title>` do `index.html`, o `/manifest.webmanifest` é montado
na hora e `/og.png` desenha o cartão (a bolha com a cor do consultório, o nome, a especialidade, o CRM e o domínio). O
endereço da imagem leva a versão do cartão, porque o WhatsApp guarda a imagem pelo endereço. Só o endereço da plataforma
se chama Puericorbs.

## As duas peças centrais

**O serviço** (`service`) é a unidade de configuração. A agenda pega dele a duração e quem pode marcar; o financeiro,
o preço; o plano, a cota; o prontuário, o modelo; a nota fiscal, o código. Configuração nova entra no serviço, nunca
espalhada pelo código. O serviço tem versões: o atendimento guarda a versão com que foi marcado, e mudar o preço não
reescreve o passado.

**O item do cuidado** (`care_item`) é tudo o que deve acontecer ou aconteceu com a criança: consulta do protocolo,
vacina, exame pedido, retorno, tarefa, orientação, marco. Tem origem (protocolo, conduta, pedido), janela de datas,
dono (família ou consultório), estado e ligações (agendamento, arquivo, consulta). A linha do cuidado da família, os
lembretes, a busca ativa e os alertas do pediatra são consultas sobre ele, nunca listas paralelas.

## Entidades (rascunho)

| Grupo | Entidades |
|---|---|
| Plataforma | `user`, `clinic`, `location`, `room`, `practice`, `member` (usuário × clínica ou prática × papel), `coverage_grant`, `platform_subscription`, `audit_log`, `consent` |
| Família | `family`, `guardian` (usuário × família × papéis `legal`, `financial`, `caregiver`), `patient`, `care_link` (criança × prática) |
| Configuração | `service` (com versões), `form_template` (com versões), `protocol` (puericultura, calendário de vacinas, marcos), `availability`, `schedule_exception` |
| Agenda | `appointment`, `reserved_slot`, `waitlist_entry`, `reminder` |
| Clínico | `encounter`, `encounter_note`, `family_summary`, `measurement`, `immunization`, `milestone_check`, `exam_request`, `document`, `care_item` |
| Arquivos | `file` (tipo, origem, visibilidade, versões, ligações) |
| Dinheiro | `plan`, `membership` (família × plano), `entitlement` (cota e consumo), `charge`, `payment`, `receipt`, `service_invoice`, `ledger_entry`, `cash_session`, `payout` |
| Conversa | `thread`, `message`, `broadcast` |

## Pilha (decidida: `decisoes.md`, 13, 16, 17 e 20)

- **Servidor:** Python com FastAPI, como o CardLine (`puericorbs serve`).
- **Banco:** SQLite em WAL, um arquivo por prática e um da plataforma, com versão e migrações (`db.py`). Uma prática
  escreve só no próprio arquivo, então a concorrência é a de um consultório.
- **Trabalhos de fundo** (lembretes, cobranças, notas): ainda não existem; quando vierem, um laço no próprio processo
  ou um serviço do systemd com temporizador.
- **Página:** um PWA sem build (HTML, CSS e JavaScript puros, em módulos), como o CardLine, com o vidro claro.
  Os arquivos saem com a versão no endereço (`/static/v/<versão>/`): uma atualização nunca esbarra no JavaScript
  velho guardado no navegador.
- **Arquivos:** no disco, na pasta da prática; a imagem perde o EXIF e o HEIC vira JPEG.
- **Hospedagem:** self-hosted, num computador da casa, atrás de um túnel do Cloudflare só do Puericorbs. A produção
  (8931) e a demonstração (8930) são serviços de usuário do systemd (`deploy/`). O que isso cobra está na decisão 13 e
  em `dominios.md`, "Antes do primeiro paciente de verdade".

## Integrações candidatas

| Para | Candidatos | Observação |
|---|---|---|
| Cobrança e recorrência | Asaas; Pagar.me, Iugu, Mercado Pago, Stripe | o Asaas junta PIX, boleto, cartão recorrente, split e NFS-e; confirmar o PIX Automático e as taxas |
| Nota fiscal de serviço | o próprio gateway; Focus NFe, NFE.io, PlugNotas | cada município é um caso; o provedor resolve |
| Receita Saúde | — | sem API pública conhecida; o Puericorbs prepara os dados e lembra |
| WhatsApp | API oficial da Meta (direto ou por um parceiro) | lembretes são mensagens de modelo, pagas por mensagem |
| Assinatura digital | certificado ICP-Brasil em nuvem (BirdID, VIDaaS e outros) | receita e atestado válidos sem papel |
| Prescrição | Memed | base de remédios e receita digital |
| E-mail | SES, Postmark, Resend | só transacional |
| Vídeo (depois) | Daily, LiveKit, Jitsi | teleconsulta |

## Segurança e LGPD

- **Base legal:** tutela da saúde, por profissional de saúde (LGPD, art. 11, II, f), para o cuidado; cumprimento de
  obrigação legal, para guardar o prontuário; consentimento só para o que é opcional (comunicados, pesquisa).
- **Criança e adolescente:** tratamento no melhor interesse deles (LGPD, art. 14).
- **Dados em casa, no Brasil** (self-hosted): o banco e os arquivos ficam no computador da plataforma. O Cloudflare
  termina o HTTPS na borda e vê o tráfego: é suboperador, entra na política e no contrato.
- **Guarda:** prontuário por no mínimo 20 anos desde o último registro (Lei 13.787/2018). Pedido de exclusão não
  apaga prontuário: ele é guardado por obrigação legal, e o titular é informado.
- **Prontuário sem papel:** a regra do CFM exige que o sistema atenda ao nível NGS2 da certificação SBIS/CFM
  (assinatura digital ICP-Brasil nos registros). Decidir entre certificar o sistema ou assinar cada registro com o
  certificado em nuvem do pediatra (`decisoes.md`).
- **Contratos:** a prática contrata o Puericorbs como operador; o Puericorbs tem contrato de tratamento com cada suboperador
  (Cloudflare, gateway, WhatsApp, e-mail).
- **Incidente:** plano de resposta, com comunicação à ANPD e aos titulares.
- **Acesso:** 2FA para quem vê prontuário; sessão por aparelho, com encerramento remoto.

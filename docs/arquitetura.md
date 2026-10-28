# Arquitetura

> 28/10/2026 · rascunho de descoberta. Ainda não é código: é o modelo que o código vai seguir. Os nomes no código
> estão em `glossario.md`.

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
- **Na LGPD,** a prática é a controladora dos dados de saúde que produz e o Pueri é o operador. Os dados da conta da
  família (login, contato) têm o Pueri como controlador.

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

- PostgreSQL com **Row-Level Security**: toda tabela com dado de paciente tem `practice_id`; a sessão fixa a prática
  ativa e a política do banco filtra. As tabelas da clínica usam `clinic_id`.
- **Teste de isolamento obrigatório** para cada tabela nova: o teste tenta ler, alterar e apagar dados de outra
  prática, e tem de falhar.
- Arquivos guardados com chave por prática e servidos por link assinado que expira.
- **Log de auditoria** só de acréscimo: quem viu ou mudou qual registro, quando e de onde.
- Acesso fora da prática (cobertura entre pediatras, suporte do Pueri) é uma concessão com prazo, motivo e registro.

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

## Pilha (recomendação; a decisão está em aberto em `decisoes.md`)

- **Servidor:** Python com FastAPI, como o CardLine.
- **Banco:** PostgreSQL gerenciado: RLS, JSONB para formulários e configurações, backup com restauração a um ponto no
  tempo. O SQLite do CardLine não serve aqui (muitas práticas escrevendo ao mesmo tempo e isolamento por linha).
- **Trabalhos de fundo** (lembretes, cobranças, notas, conversão de mídia): fila no próprio PostgreSQL no começo.
- **Página:** um PWA sem build (HTML, CSS e JavaScript puros), como o CardLine, reaproveitando o vidro. A família usa
  no celular; o consultório, no computador e no celular.
- **Arquivos:** armazenamento de objetos compatível com S3, criptografado, na região de São Paulo.
- **Hospedagem:** nuvem com região no Brasil. Dado de saúde de criança não roda no PC de casa nem atrás de túnel.

## Integrações candidatas

| Para | Candidatos | Observação |
|---|---|---|
| Cobrança e recorrência | Asaas; Pagar.me, Iugu, Mercado Pago, Stripe | o Asaas junta PIX, boleto, cartão recorrente, split e NFS-e; confirmar o PIX Automático e as taxas |
| Nota fiscal de serviço | o próprio gateway; Focus NFe, NFE.io, PlugNotas | cada município é um caso; o provedor resolve |
| Receita Saúde | — | sem API pública conhecida; o Pueri prepara os dados e lembra |
| WhatsApp | API oficial da Meta (direto ou por um parceiro) | lembretes são mensagens de modelo, pagas por mensagem |
| Assinatura digital | certificado ICP-Brasil em nuvem (BirdID, VIDaaS e outros) | receita e atestado válidos sem papel |
| Prescrição | Memed | base de remédios e receita digital |
| E-mail | SES, Postmark, Resend | só transacional |
| Vídeo (depois) | Daily, LiveKit, Jitsi | teleconsulta |

## Segurança e LGPD

- **Base legal:** tutela da saúde, por profissional de saúde (LGPD, art. 11, II, f), para o cuidado; cumprimento de
  obrigação legal, para guardar o prontuário; consentimento só para o que é opcional (comunicados, pesquisa).
- **Criança e adolescente:** tratamento no melhor interesse deles (LGPD, art. 14).
- **Dados no Brasil:** evita a transferência internacional e as cláusulas dela.
- **Guarda:** prontuário por no mínimo 20 anos desde o último registro (Lei 13.787/2018). Pedido de exclusão não
  apaga prontuário: ele é guardado por obrigação legal, e o titular é informado.
- **Prontuário sem papel:** a regra do CFM exige que o sistema atenda ao nível NGS2 da certificação SBIS/CFM
  (assinatura digital ICP-Brasil nos registros). Decidir entre certificar o sistema ou assinar cada registro com o
  certificado em nuvem do pediatra (`decisoes.md`).
- **Contratos:** a prática contrata o Pueri como operador; o Pueri tem contrato de tratamento com cada suboperador
  (nuvem, gateway, WhatsApp, e-mail).
- **Incidente:** plano de resposta, com comunicação à ANPD e aos titulares.
- **Acesso:** 2FA para quem vê prontuário; sessão por aparelho, com encerramento remoto.

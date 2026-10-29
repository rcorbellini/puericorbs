# Glossário

> Os termos do domínio, o nome de cada um no código e o que significam. Na tela e nos documentos, o termo em
> português; no código, o da segunda coluna. Termo novo entra aqui antes de entrar no código.

## Quem

| Termo | No código | O que é |
|---|---|---|
| Prática | `practice` | a parte de uma pediatra dentro do consultório; dona dos pacientes, do prontuário, dos serviços e do dinheiro |
| Consultório, clínica | `clinic` | o lugar e a equipe que uma ou mais pediatras dividem; não é dono de paciente (`clinics.py`) |
| Unidade | `location` | endereço onde se atende |
| Sala | `room` | consultório físico dentro da unidade |
| Membro | `member` | um usuário numa clínica ou prática, com um papel |
| Pediatra | papel `clinician` | o médico da prática (o nome genérico deixa espaço para outros profissionais) |
| Atendente | papel `receptionist` (`clinic_members`) | a secretária ou a recepção do consultório, que atende todas as pediatras dele |
| Administração do consultório | `clinic_members.role = 'manager'`, `ctx.manages` | faz o que a atendente faz e cuida da equipe e dos convites; nada clínico. A pediatra que criou o consultório já nasce nela |
| Família | `family` | o grupo de responsáveis e crianças |
| Responsável | `guardian` | o adulto ligado à família, com papéis `legal`, `financial` e `caregiver` |
| Convite | `invite` | o link de uso único com que alguém cria a conta: a equipe do consultório (`staff`: pediatra, atendente, administração), a família (`family`), a pediatra que cria o consultório (`practice`) e a administração da plataforma (`admin`) |
| Convite pré-preenchido | `invite_prefill` (banco da prática) | o que a recepção já sabia da família nova (o responsável, a criança), à espera do aceite; vira ficha quando a família aceita |
| Administração da plataforma | `is_platform_admin`, painel `#/admin` | quem acompanha os consultórios, liga os domínios e entra em cada um vendo como quem usa |
| Vendo como | `ctx.actor`, `handoffs`, `sessions.as_*` | a administração dentro de um consultório com a tela e as ações de alguém dele; a faixa no topo avisa, e o registro guarda quem estava de fato |
| Paciente, criança | `patient` | a criança atendida |
| Vínculo | `care_link` | a ligação criança × prática que dá acesso |
| Cobertura | `coverage_grant` | o empréstimo temporário de pacientes a outro pediatra |

## Agenda

| Termo | No código | O que é |
|---|---|---|
| Serviço | `service` | o que se agenda e se cobra, com toda a configuração |
| Grade de atendimento, horários | `availability` | os períodos em que a pediatra atende, por dia da semana (ela muda em Horários) |
| Agenda fechada | `schedule_exceptions` | os dias sem atendimento (férias, congresso, folga), de `day` a `end_day` |
| Pedido de confirmação | `confirm_asked_at` | quando a recepção abriu o WhatsApp para pedir a confirmação |
| Agendamento | `appointment` | um horário marcado |
| Vaga protegida para agudo | `reserved_slot` | horário que só abre no dia, para a criança doente |
| Encaixe | `squeeze_in` | agendamento fora da grade |
| Retorno | `follow_up` | consulta de volta, sem custo dentro do prazo do serviço |
| Lista de espera | `waitlist_entry` | quem quer um horário que ainda não abriu |
| Confirmação | `confirmation` | a família diz que vem |
| Chegada | `check_in` | a criança chegou à recepção |
| Falta | `no_show` | não veio e não avisou |
| Busca ativa | `outreach` | a lista de quem está atrasado, para ligar |
| Lembrete | `reminder` | aviso automático (push, e-mail, WhatsApp) |

## Cuidado

| Termo | No código | O que é |
|---|---|---|
| Consulta (o atendimento) | `encounter` | o atendimento em si, ligado ao agendamento |
| Puericultura | `well_child` | a consulta de rotina do crescimento e do desenvolvimento |
| Intercorrência | `sick_visit` | a consulta por doença aguda |
| Prontuário | `medical_record` | o conjunto dos registros da criança na prática |
| Registro da consulta | `encounter_note` | o que o pediatra escreve, pelo modelo do serviço |
| Modelo de registro | `form_template` | o formulário configurável, com versões |
| Resumo para a família | `family_summary` | o texto que o pediatra libera para os responsáveis |
| Medida | `measurement` | peso, comprimento ou altura, perímetro cefálico, IMC |
| Curva de crescimento | `growth_chart` | as curvas da OMS com os percentis |
| Percentil, escore-z | `percentile`, `z_score` | a posição da medida na curva |
| Idade corrigida | `corrected_age` | a idade descontada a prematuridade |
| Marco do desenvolvimento | `milestone` | o que a criança costuma fazer em cada idade |
| Marco marcado | `milestone_check` | o registro de que a criança alcançou o marco |
| Caderneta de vacinação | `immunization_record` | o conjunto das vacinas da criança |
| Vacina aplicada | `immunization` | dose, data, lote e local |
| Calendário vacinal | `vaccine_schedule` | o protocolo de vacinas (PNI, SBIm ou o do pediatra) |
| Triagem neonatal | `newborn_screening` | pezinho, orelhinha, olhinho, coraçãozinho, linguinha |
| Protocolo | `protocol` | a regra que gera itens do cuidado pela idade |
| Linha do cuidado | `care_timeline` | a lista do feito e do a fazer da criança |
| Item do cuidado | `care_item` | uma coisa que deve acontecer ou aconteceu, com dono, prazo e estado |
| Pedido de exame | `exam_request` | o exame que o pediatra pediu; fecha quando o resultado chega |
| Receita | `prescription` | |
| Atestado | `medical_certificate` | |
| Declaração de comparecimento | `attendance_statement` | |
| Encaminhamento | `referral` | |
| Orientação | `guidance` | conteúdo educativo do pediatra para a família |
| Documento | `document` | o PDF gerado por modelo (receita, atestado…) |
| Arquivo | `file` | o que alguém enviou (exame, foto, comprovante…) |
| Caixa de revisão | `review_inbox` | o que chegou e o pediatra ainda não viu |
| Visibilidade | `visibility` | `internal`, `family`, `admin` ou `confidential` |

## Dinheiro

| Termo | No código | O que é |
|---|---|---|
| Plano de acompanhamento | `plan` | o pacote recorrente que o pediatra vende (nunca `care_plan`, que em inglês médico é o plano terapêutico) |
| Adesão ao plano | `membership` | a família (ou a criança) num plano |
| Cota | `entitlement` | o que o plano dá direito a usar, e o quanto já foi usado |
| Cobrança | `charge` | o que a família deve pagar |
| Pagamento | `payment` | o que entrou |
| Recibo | `receipt` | |
| Nota fiscal de serviço | `service_invoice` | a NFS-e |
| Receita Saúde | `receita_saude` | o recibo da Receita Federal para o profissional pessoa física (nome próprio, fica em português) |
| Kit reembolso | `reimbursement_kit` | a nota, o recibo e o relatório que o convênio pede |
| Lançamento | `ledger_entry` | entrada ou saída no financeiro da prática |
| Caixa do dia | `cash_session` | abrir, fechar e conferir o caixa da recepção |
| Repasse | `payout` | a divisão entre a prática e a clínica |
| Régua de cobrança | `dunning` | os avisos antes e depois do vencimento |
| Inadimplência | `delinquency` | |
| Receita recorrente mensal | `mrr` | |
| Assinatura do Puericorbs | `platform_subscription` | o que a prática paga ao Puericorbs (nunca "plano", para não confundir com o do pediatra) |

## Conversa e plataforma

| Termo | No código | O que é |
|---|---|---|
| Conversa | `thread` | as mensagens de uma família com a prática, por criança |
| Mensagem | `message` | |
| Comunicado | `broadcast` | mensagem para muitas famílias de uma vez |
| Log de auditoria | `audit_log` | quem viu ou mudou o quê |
| Prévia do link | `share.head`, `/og.png` | o nome, o texto e a imagem que o WhatsApp mostra quando alguém manda o endereço |
| Nome no celular | `short_name` | o nome embaixo do ícone do app instalado (até 12 letras) |
| Consentimento | `consent` | o aceite registrado (termo, comunicados, plano) |

# Funcionalidades: a exploração

> 28/10/2026. O que foi pedido, o que propomos a mais e em que fase entra cada coisa. Os marcos estão em
> `roadmap.md`; os nomes no código, em `glossario.md`.

**Fases:** `M0` fundação · `M1` o consultório funciona (piloto) · `M2` o dinheiro entra sozinho · `M3` a clínica e o
SaaS aberto · `Depois` explorar.

## Resumo

| Pedido | Onde está | Começa em |
|---|---|---|
| Agenda do pediatra | 1. Agenda | M1 |
| Acompanhamento financeiro | 7. Financeiro | M1 (recebimentos), M2 (completo) |
| A família acompanha o feito e o a fazer | 4. Linha do cuidado, 5. Família | M1 |
| Planos com recorrência | 8. Planos de acompanhamento | M1 (cota), M2 (cobrança automática) |
| Arquivos do pediatra e da família | 6. Arquivos e documentos | M1 |
| SaaS, cada pediatra só com os seus | 10. Clínica e equipe, 11. Plataforma, `arquitetura.md` | M0 (isolamento), M3 (clínica) |
| Cada serviço configurável | 2. Serviços | M1 |

## O que propomos a mais (os destaques)

1. **Linha do cuidado calculada pela idade.** Puericultura, vacinas e marcos vêm de protocolos que o pediatra escolhe
   e edita; a família vê o que vem, com a janela de datas, sem ninguém digitar. (4)
2. **Vagas protegidas para a criança doente.** Pediatria tem doença do dia: o pediatra reserva horários que só abrem
   no próprio dia, e o encaixe não estoura a agenda. (1)
3. **Busca ativa.** A lista de crianças com puericultura, retorno ou vacina atrasados, para a atendente ligar. É
   cuidado e é receita. (1, 4)
4. **Resumo para a família separado do registro clínico.** O pediatra escreve à vontade no prontuário e libera para
   a família só o resumo e os próximos passos. (3)
5. **Caixa de revisão.** Exame pedido → resultado enviado pela família → revisado com comentário → família avisada. O
   ciclo fecha no Puericorbs, não no WhatsApp. (3, 6)
6. **Vários responsáveis, com papéis.** Mãe, pai, avó, babá: cada um com o seu acesso. O responsável financeiro
   recebe a nota no CPF dele, o cuidador só vê a agenda e as orientações, e a guarda compartilhada é respeitada por
   padrão. (5)
7. **Retorno e falta configuráveis.** Retorno sem custo em N dias, taxa de falta, pré-pagamento: por serviço. (2)
8. **Nota e reembolso sem trabalho.** Nota fiscal (ou Receita Saúde, para quem atende como pessoa física) e o kit que
   o convênio pede para reembolsar a família, prontos no app. (7)
9. **Confirmação automática por WhatsApp.** Confirmar, remarcar ou cancelar num toque; a vaga liberada vai para a
   lista de espera. (1, 9)
10. **Cobertura entre pediatras.** Nas férias, o pediatra empresta pacientes escolhidos a um colega, com prazo e
    registro, sem abrir a carteira inteira. (10)
11. **Sigilo do adolescente e LGPD de criança no modelo.** Visibilidade por registro, log de todo acesso, guarda de
    20 anos. (3, 11)
12. **Orientação no momento certo.** O conteúdo do pediatra (introdução alimentar, febre, sono seguro) chega à
    família na idade em que serve. (9)

---

## 1. Agenda

**Pedido:** gerenciar a agenda do pediatra.

- `M1` Grade de atendimento por pediatra, unidade e dia da semana, em turnos. Exceções: férias, congresso, feriados
  nacionais e municipais.
- `M1` Horário por serviço: cada serviço tem duração e intervalo próprios, e a grade só oferece o horário em que o
  serviço cabe.
- `M1` **Vagas protegidas para agudos:** horários reservados que só abrem no dia, para a criança doente.
- `M1` Encaixe fora da grade, com aviso de sobreposição.
- `M1` Recepção do dia: chegou, em espera (com o tempo), em atendimento, atendido, faltou. O pediatra vê quem chegou.
- `M1` Retorno: o agendamento sabe se está dentro do prazo de retorno sem custo do serviço.
- `M1` A família agenda pelo app, dentro das regras de cada serviço (quem pode, antecedência mínima e máxima).
- `M1` Puericultura guiada: o sistema sabe a janela da próxima consulta pelo protocolo e lembra a família de agendar.
- `M1` **Busca ativa:** crianças com puericultura ou retorno atrasados.
- `M1` Falta: registro e contagem por família. `M2` Política por serviço: cobrar, pedir pré-pagamento, bloquear o
  agendamento pelo app.
- `M1` Confirmação por push e e-mail. `M2` Por WhatsApp, com confirmar, remarcar e cancelar num toque.
- `M2` Lista de espera por período ("terça de manhã, qualquer horário"), com aviso automático quando abre vaga.
- `M2` Sincronização com o Google Agenda ou o iCloud do pediatra: só ocupado e livre, nunca o nome do paciente.
- `M2` Visita domiciliar: endereço e tempo de deslocamento antes e depois.
- `M3` Vários pediatras lado a lado para a atendente; salas como recurso (não deixa marcar dois na mesma sala).
- `Depois` Teleconsulta, com o link da sala gerado no agendamento.

## 2. Serviços (o catálogo configurável)

**Pedido:** cada serviço precisa ser customizado.

O serviço é a unidade de configuração do Puericorbs: a agenda, o preço, o plano, o prontuário e a nota fiscal leem dele.
Exemplos de um consultório pediátrico: primeira consulta do recém-nascido, puericultura, intercorrência (doença
aguda), retorno, consulta pré-natal pediátrica (com a gestante), visita domiciliar, teleconsulta, avaliação de
amamentação, teste da linguinha, pequenos procedimentos, relatório para a escola.

A ficha de cada serviço (`M1`):

| Parte | O que o pediatra define |
|---|---|
| Identidade | nome, texto para a família, categoria, faixa etária (ex.: recém-nascido até 28 dias) |
| Tempo | duração, intervalo antes e depois, dias e turnos em que é oferecido, unidades |
| Quem agenda | só a recepção, a família pelo app, a página pública; antecedência mínima e máxima; se aceita encaixe |
| Preço | valor particular; no plano (incluído na cota, com desconto ou à parte); pré-pagamento; taxa de falta e de cancelamento tardio; retorno sem custo (prazo e quantidade) |
| Consulta | modelo de registro, questionário prévio para a família, medidas pedidas |
| Depois | o que dispara: próxima consulta do protocolo, retorno sugerido, orientações, pesquisa de satisfação |
| Documentos | o que sai sozinho (declaração de comparecimento) e os modelos sugeridos |
| Nota fiscal | código do serviço, descrição na nota, emitir sozinha ou não |

- `M1` Modelos prontos para começar (puericultura, intercorrência, recém-nascido…), que a prática copia e edita.
- `M1` Construtor de formulário do prontuário: texto, número com unidade, escolha, sim/não, data, medida com
  percentil, lista de marcos. Com versões: mudar o modelo não altera registro antigo.
- `M1` Protocolos editáveis: as idades da puericultura, o calendário de vacinas (PNI, SBIm ou o do pediatra) e os
  marcos do desenvolvimento.
- `M1` Módulos ligáveis por prática (planos, vacinas aplicadas, domiciliar, teleconsulta): quem não usa, não vê.

## 3. Prontuário e consulta

- `M1` Ficha da criança: dados, responsáveis, nascimento (idade gestacional, peso, Apgar, parto), triagens
  neonatais, **alergias e alertas sempre à vista**, condições crônicas, remédios em uso, história familiar.
- `M1` Registro pelo modelo do serviço, com a consulta anterior ao lado e o que se repete já preenchido.
- `M1` Medidas (peso, comprimento ou altura, perímetro cefálico, IMC) com percentil e escore-z na hora, nas curvas da
  OMS. **Idade corrigida** para o prematuro (em geral até os 2 anos; Intergrowth-21st antes do termo).
- `M1` Hipóteses com CID.
- `M1` A conduta gera os próximos passos (retorno, exame pedido, orientação, vacina), que entram na linha do cuidado.
- `M1` **Resumo para a família:** texto curto, separado do registro, que o pediatra revisa e libera. O registro fica
  interno.
- `M1` Documentos por modelo (receita, atestado, declaração, pedido de exame, encaminhamento, relatório, orientação),
  em PDF com a identidade da prática. `M2` Assinatura digital ICP-Brasil (receita válida sem papel) e prescrição
  integrada (Memed).
- `M1` **Caixa de revisão:** exames e fotos enviados pela família e mensagens marcadas como clínicas. Revisar com um
  comentário avisa a família.
- `M1` Contato fora da consulta (ligação, mensagem) registrado no histórico.
- `M0` Correção com histórico; nada se apaga.
- `Depois` Calculadora de dose por peso, com a fonte e a confirmação do pediatra.

## 4. Linha do cuidado: o que foi feito e o que vem

**Pedido:** o paciente acompanha o que foi feito e o que precisa ser feito.

Tudo o que deve acontecer com a criança é um **item do cuidado**: tem origem (protocolo, conduta, pedido), prazo ou
janela de datas, dono (família ou consultório) e estado (pendente, agendado, feito, atrasado, dispensado). A linha do
cuidado é a lista desses itens, dividida em **feito** e **a fazer**.

- `M1` **Feito:** consultas (com o resumo para a família), medidas, vacinas aplicadas, exames com resultado,
  documentos, marcos alcançados.
- `M1` **A fazer:** a próxima consulta do protocolo (com a janela de datas), vacinas devidas e atrasadas, exames
  pedidos sem resultado, retorno, tarefas do pediatra ("trazer a caderneta", "anotar a febre"), orientações em curso
  com prazo.
- `M1` Curvas de crescimento para a família, em linguagem simples ("dentro do esperado para a idade"), com o detalhe
  para quem quiser.
- `M1` Carteira de vacinação digital: aplicadas (data, lote, local), foto da caderneta, próximas pelo calendário
  escolhido. `M2` Link temporário para mandar à escola ou à creche.
- `M1` Marcos do desenvolvimento por idade: a família marca em casa ("sentou sem apoio"), com foto ou vídeo; o
  pediatra confere na consulta.
- `M1` Triagens neonatais (pezinho, orelhinha, olhinho, coraçãozinho, linguinha): feito ou pendente, com o resultado
  anexado.
- `M1` Lembrete de cada item a fazer (push e e-mail; `M2` WhatsApp).
- `Depois` Diário da família: febre e remédio com horário; mamadas, fraldas e sono nas primeiras semanas; à vista do
  pediatra.

## 5. Família (o app do responsável)

- `M1` Entrar sem senha: código por e-mail ou SMS. `M2` Google e Apple.
- `M1` Vários filhos e **vários responsáveis**, cada um com acesso próprio e papel: responsável legal (vê o que é da
  família), responsável financeiro (paga e recebe a nota no CPF dele), cuidador (agenda e orientações).
- `M1` **Guarda compartilhada:** os dois genitores têm direito à informação de saúde do filho (Código Civil, art.
  1.583, §5º; quem nega fica sujeito a multa, art. 1.584, §6º). Restringir um deles só com decisão judicial
  registrada pela prática.
- `M1` Agendar, remarcar, cancelar e confirmar, vendo as regras e o valor antes.
- `M1` Linha do cuidado, curvas, vacinas e marcos.
- `M1` Enviar arquivo com contexto: para a próxima consulta, resultado de um exame pedido, dúvida.
- `M1` Documentos sempre à mão: receitas, atestados para a escola, pedidos de exame, declarações.
- `M1` Questionário antes da consulta (o do serviço).
- `M1` Instala como app (PWA), com notificações.
- `M1` Recibos. `M2` Pagar no app (PIX, cartão), ver o plano e a cota, baixar a nota, pedir o kit reembolso.
- `M2` Mensagens com o consultório, no horário e no prazo de resposta que o plano promete, com o aviso de que
  urgência é pronto-socorro.
- `Depois` O adolescente com acesso próprio e notas que os pais não veem (Código de Ética Médica, art. 74).

## 6. Arquivos e documentos

**Pedido:** mídias do pediatra e do paciente (exames, comprovantes, nota fiscal…).

- `M1` Tipos: exame (laboratório, imagem), laudo, receita, atestado, declaração, pedido, comprovante, nota fiscal,
  recibo, foto clínica, vídeo, caderneta, documento pessoal (certidão, carteirinha do convênio, cartão do SUS).
- `M1` Quem envia: família, pediatra ou atendente. Cada arquivo fica ligado à criança e, quando for o caso, à
  consulta, ao pedido de exame (que fecha o pendente) ou ao pagamento.
- `M1` Visibilidade por arquivo: interno, família, administrativo (a atendente vê comprovantes e notas, nunca exames).
- `M1` Caixa de revisão do pediatra para o que chega da família.
- `M1` Foto e vídeo do celular: HEIC vira JPEG, o vídeo é comprimido, sem localização nem EXIF.
- `M1` Reenviar não apaga o anterior: guarda as versões.
- `M0` Armazenamento criptografado, links que expiram, antivírus e limite de espaço por assinatura.
- `Depois` Ler o PDF do exame e sugerir os valores (hemoglobina, ferritina…) para um gráfico de evolução, com a
  confirmação do pediatra.
- `Depois` Encaminhar do WhatsApp para o número do Puericorbs e o arquivo cair na criança certa.

## 7. Financeiro

**Pedido:** acompanhamento financeiro.

- `M1` Recebimento por atendimento: forma (PIX, cartão, dinheiro, plano, cortesia), parcelas, desconto, quem recebeu.
- `M1` Caixa da recepção: abrir, fechar e conferir o dia.
- `M1` Recibo. `M2` Nota fiscal de serviço (NFS-e) automática, por um provedor, para quem atende como PJ.
- `M2` **Receita Saúde** para quem atende como pessoa física (obrigatório desde 2025): o Puericorbs prepara os dados e
  lembra de emitir; integração direta se a Receita abrir uma API.
- `M2` **Kit reembolso:** a nota ou o recibo no CPF de quem pagou, com o nome da criança, CRM e RQE, data e serviço e,
  se a família pedir, o relatório com CID. É o que o convênio exige para reembolsar.
- `M2` Contas a pagar da prática: aluguel ou repasse, atendente, materiais, vacinas, contador.
- `M2` Fluxo de caixa com previsão: a agenda futura e os planos ativos viram receita prevista.
- `M1` Relatórios básicos (faturamento por serviço e por forma). `M2` Completos: por plano, ticket médio, faltas em
  dinheiro, inadimplência.
- `M2` Livro-caixa do pediatra pessoa física e exportação para o contador. `M3` Acesso de leitura para o contador.
- `M2` Conciliação com o extrato do gateway de pagamento.
- `M3` **Repasse na clínica:** regra por pediatra (percentual, valor por consulta ou aluguel de sala por turno),
  extrato e divisão automática no gateway (split).
- `M1` O resultado da prática é do pediatra: a atendente lança e recebe, mas só vê o lucro se ele liberar.

## 8. Planos de acompanhamento (recorrência)

**Pedido:** ofertar pacotes de planos com recorrência.

- `M1` Construtor de plano: nome, descrição, preço mensal (ou anual com desconto), vigência (ex.: 12 meses),
  renovação automática, idade de entrada (ex.: até 3 meses), fidelidade.
- `M1` O que inclui: serviços com cota (por mês ou na vigência, acumulando ou não), desconto nos serviços fora da
  cota, canal de mensagens com prazo de resposta, extras (visita domiciliar).
- `M1` Irmãos: preço por criança e desconto a partir da segunda.
- `M1` **Consumo automático:** agendar um serviço incluído desconta da cota; a família vê "5 de 12 consultas usadas".
- `M1` A cobrança do plano é registrada à mão, para o piloto já vender planos. `M2` **Cobrança automática:** cartão
  recorrente, PIX Automático (Banco Central, desde junho de 2025) ou boleto, com dia de vencimento.
- `M2` Régua de cobrança: aviso antes do vencimento, no dia e depois; benefícios suspensos após N dias de atraso
  (configurável).
- `M2` Termo de adesão versionado, com aceite eletrônico (data, hora, IP e versão) e cancelamento com regras claras
  (Código de Defesa do Consumidor).
- `M2` Pausa, troca de plano com pró-rata e cancelamento.
- `M2` Indicadores: assinantes, receita recorrente mensal, cancelamentos, inadimplência e consumo médio da cota (o
  plano dá lucro?).
- `M3` Página de venda do plano, para mandar à gestante ou à família nova.

> **Atenção regulatória (validar com advogado antes de vender):** o plano é um pacote de serviços do próprio
> pediatra, não plano de saúde. Não pode cobrir risco (urgência, internação, exames de terceiros, consulta "ilimitada"),
> para não cair na regulação da ANS. O Código de Ética Médica (art. 72, com a redação da Resolução CFM 2.226/2019) veda
> o vínculo com empresas de planos de financiamento e de consórcios; os cartões de desconto saíram da vedação em 2019.
> Na tela, o nome é "plano de acompanhamento". O que se recomenda para os planos, e as interações que valem a pena,
> estão em `planos-e-interacoes.md`.

## 9. Comunicação

- `M1` Lembretes automáticos: consulta, confirmação, vacina, retorno, exame pendente, pagamento, renovação (push e
  e-mail; `M2` WhatsApp).
- `M2` Mensagens família ↔ consultório, por criança: horário de atendimento, resposta automática fora dele, triagem
  (administrativo vai à atendente, clínico ao pediatra), respostas prontas.
- `M2` Comunicados segmentados por idade, plano ou pendência (campanha da gripe, férias do pediatra, endereço novo).
- `M2` **Orientação no momento certo:** o conteúdo do pediatra (introdução alimentar, febre, sono seguro) chega na
  idade em que serve.
- `M2` Aniversário da criança.
- `M2` Pesquisa de satisfação depois da consulta.

## 10. Clínica e equipe

- `M0` Papéis: pediatra e atendente. `M3` Gestor da clínica, enfermagem (medidas e vacinas), financeiro e contador
  (só leitura).
- `M1` A atendente do pediatra (consultório de um pediatra só). `M3` A atendente da clínica, que atende os pediatras
  escolhidos um a um.
- `M3` Unidades e salas.
- `M3` O pediatra em mais de uma clínica com um login só, trocando de contexto.
- `M3` **Cobertura entre pediatras** (férias, plantão): empréstimo de pacientes escolhidos, com prazo e registro.
- `M3` Painel do gestor: ocupação das salas, repasses e faturamento por pediatra; nada clínico.
- `M3` Prática em grupo (opcional): pediatras que dividem a carteira de propósito.

## 11. Plataforma (o SaaS)

- `M0` Segurança: 2FA para quem vê prontuário, sessões por aparelho, log de acesso, backups com restauração testada,
  criptografia.
- `M0` LGPD: termo e política, encarregado, pedidos do titular (acesso, correção, portabilidade), base legal
  registrada por tratamento.
- `M0` O suporte do Puericorbs não vê dado clínico; só com autorização registrada da prática.
- `M1` Modelos mantidos pela plataforma: protocolos, calendários, formulários e orientações.
- `M2` Marca da prática: logo e cor de destaque dentro da identidade.
- `M2` Exportação completa: o pediatra sai com os seus dados.
- `M3` Cadastro sozinho, com teste grátis e roteiro de primeiros passos (serviços a partir dos modelos, grade,
  convidar a atendente, importar pacientes de planilha). Até lá, o piloto é configurado à mão.
- `M3` Assinatura do Puericorbs por pediatra; a clínica pode pagar pelos seus.
- `M3` Página pública do pediatra, com CRM e RQE, serviços e agendamento, dentro das regras de publicidade médica do
  CFM (Res. 2.336/2023).

## 12. Indicadores

- `M1` Pediatra: ocupação e faltas, faturamento, puericulturas e vacinas atrasadas, exames sem resultado.
- `M2` Planos (receita recorrente, cancelamentos, consumo), previsão de caixa, tempo de resposta às mensagens,
  espera na recepção, satisfação.
- `M3` Gestor: ocupação, repasses e faturamento por pediatra.

## 13. Para explorar depois

- **Teleconsulta** (Lei 14.510/2022 e Res. CFM 2.314/2022), com o vídeo no próprio Puericorbs.
- **IA como rascunho, nunca como decisão**, com o dado protegido (modelo local ou provedor com contrato de
  tratamento): transcrever a consulta e rascunhar o registro, escrever o resumo para a família a partir do registro,
  ler exames, triar mensagens.
- **Sala de vacina:** estoque, lote, validade e aplicação, para a clínica que vacina.
- **RNDS:** trazer as vacinas do SUS e enviar as aplicadas.
- **Convênios** (TISS, guias, glosas): só se os pilotos pedirem.
- **Outros profissionais da criança** (fono, nutricionista, psicólogo) na mesma linha do cuidado, com consentimento.
- **App nativo**, se o PWA não bastar (no iPhone, o push funciona com o app instalado desde o iOS 16.4).

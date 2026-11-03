# Pagamentos: a AbacatePay e como o Puericorbs receberia

> 29/10/2026. Pesquisa pedida pelo dono: a AbacatePay (pela documentação da API v2), o recibo e a nota da família, e
> os gateways que aceitam pessoa física e empresa (pelas páginas de cada um). Tudo lido nesta data. Do recibo e da nota,
> o fluxo assistido está construído (`fiscal.py`); o pagamento pelo gateway, ainda não.

## O que a AbacatePay é

Um gateway de pagamento brasileiro com uma API simples:

- **O que cobra:**
  - **PIX direto:** a cobrança "transparente", com o QR Code e o copia e cola devolvidos na hora.
  - **Checkout hospedado:** PIX, cartão em até 12 vezes e boleto.
  - **Assinatura no cartão:** com cobrança automática a cada ciclo.
  - **O resto:** clientes, produtos, cupons e saques.
- **Como fala com a gente:**
  - **Endereço e chave:** a API fica em `https://api.abacatepay.com/v2`, com a chave no cabeçalho
    `Authorization: Bearer`.
  - **Teste e produção:** é a chave que decide o ambiente. A de teste ("dev mode") simula tudo; a de produção mexe com
    dinheiro de verdade. Toda resposta traz `devMode`.
  - **Avisos (webhooks):** `transparent.completed` (o PIX foi pago), `checkout.completed`, `subscription.renewed`,
    `subscription.cancelled`, mais os de devolução e de disputa.
  - **Como saber que o aviso é dela:** o segredo vem no endereço (`?webhookSecret=`), e a assinatura HMAC-SHA256 do
    corpo vem no cabeçalho `X-Webhook-Signature`. O `id` do aviso se repete quando ela tenta de novo, e é por ele que
    um pagamento não recebe baixa duas vezes.
- **O dinheiro:** fica no saldo da AbacatePay, e o saque é pelo painel, a qualquer hora. O PIX cai em segundos; o
  cartão tem prazo de liquidação.

## As condições que mais pesam

1. **Só pessoa jurídica.** A conta de produção exige CNPJ. A AbacatePay aceita ME e MEI, mas medicina não pode ser
   MEI. A pediatra que atende como pessoa física (carnê-leão, Receita Saúde) não recebe pela AbacatePay.
2. **O site precisa estar pronto.** No ar, com contatos (e-mail e WhatsApp), termos de uso, política de privacidade e
   o CNPJ no rodapé. A análise leva até 3 dias úteis. O site do consultório no Puericorbs ainda não tem o CNPJ nem as
   duas páginas, que já faltavam para o primeiro paciente de verdade.
3. **Recursos que a documentação não traz:**
   - PIX Automático;
   - divisão do pagamento (split) entre pediatras ou com a plataforma;
   - nota fiscal.

   A assinatura é no cartão. No PIX, a família paga um PIX novo todo mês.
4. **As taxas não estão na documentação.** Fontes de terceiros falam em R$ 0,80 por PIX e em R$ 0,60 + 3,5% no
   cartão. Numa consulta de R$ 450, o PIX sairia por menos de 0,2%. Confirmar com a AbacatePay antes de decidir.

## Como o Puericorbs receberia

**Cada pediatra recebe na conta dela.** Ela abre a conta na AbacatePay, com o CNPJ dela, e cola a chave no
Puericorbs. O dinheiro vai direto para ela, e a plataforma nunca segura o dinheiro de ninguém: não há custódia nem
repasse, e o Puericorbs não vira instituição de pagamento. Num consultório com várias pediatras, cada uma usa a sua
conta, e a recepção cobra na conta da pediatra da consulta.

### 1. A consulta na recepção: PIX na hora

1. A recepção toca **Receber** e escolhe **PIX**.
2. O Puericorbs cria a cobrança (`POST /v2/transparents/create`), com o valor, a descrição e o número da cobrança no
   `externalId`.
3. A tela mostra o QR Code e o copia e cola, ou manda no WhatsApp da família.
4. O aviso `transparent.completed` dá baixa sozinho, e a tela vira "Recebido".
5. Se o aviso não chegar (a internet caiu), **Conferir** pergunta à AbacatePay (`GET /v2/transparents/check`).

### 2. Pagar antes de marcar

O serviço já tem a chave **Pagamento antecipado**, que hoje só existe na configuração. Ligada, ela muda o agendamento
pelo app:

1. A família marca e paga o PIX ali mesmo.
2. O horário fica guardado por 30 minutos (`expiresIn`).
3. Pago, a consulta fica confirmada; sem pagamento, o horário volta para a agenda.

Isso diminui as faltas.

### 3. A mensalidade do plano

- **No cartão, automático:**
  1. Cada plano vira um produto na AbacatePay, com ciclo mensal (`POST /v2/products/create`).
  2. A família cadastra o cartão uma vez, na página da AbacatePay (`POST /v2/subscriptions/create`).
  3. Todo mês, o aviso `subscription.renewed` dá baixa na mensalidade.
  4. Se o cartão falhar nas tentativas, `subscription.cancelled` avisa a recepção.
- **No PIX:** o Puericorbs gera o PIX no vencimento e a família paga pelo app, que avisa antes. Sem PIX Automático,
  cada mês é um pagamento novo.
- **A régua de cobrança** (M2) fica no Puericorbs: o aviso antes do vencimento, no dia e depois, e os benefícios
  suspensos depois de alguns dias de atraso.

### 4. O que o Puericorbs ganha por dentro

- **O módulo:** `payments.py`, com um provedor e quatro operações: cobrar no PIX, conferir, assinar e validar o
  aviso. Começa pela AbacatePay, e outro provedor entra sem mexer nas telas.
- **No banco da prática:**
  - a chave, guardada cifrada e nunca mostrada depois de salva;
  - o segredo dos avisos;
  - os pagamentos (o id na AbacatePay, o valor, o estado e o QR Code);
  - os avisos já processados.
- **A rota dos avisos:** fica no domínio da pediatra (`https://<domínio>/api/pay/abacatepay?webhookSecret=…`). Ela
  confere o segredo e a assinatura antes de dar baixa.
- **A chave só cobra e consulta.** Ela recebe as permissões de PIX, checkout, assinatura, cliente e produto, e nunca a
  de saque. Se vazar, ninguém tira dinheiro da conta da pediatra.

### 5. O que fica fora da AbacatePay

- **A nota fiscal (NFS-e):** outro provedor, como já está no M2.
- **A pediatra pessoa física:** precisa de um gateway que aceite CPF, como o Asaas ou a InfinitePay (abaixo, "Pessoa
  física e empresa").
- **A mensalidade do Puericorbs (a pediatra pagando a plataforma):** pode ser pela conta da AbacatePay da própria
  plataforma, com o CNPJ dela.

## A nota fiscal e o recibo da família

Pergunta do dono (29/10/2026): o médico ou o consultório precisa de CNPJ, e o sistema consegue fazer a nota para mandar
à família?

- **CNPJ não é obrigatório.** A pediatra pode atender como pessoa física: profissional liberal, com o CRM, a inscrição
  na prefeitura e o imposto pelo carnê-leão. MEI não pode, porque medicina não está na lista. Com CNPJ, a empresa é uma
  SLU ou uma sociedade simples, e também se registra no CRM. Costuma pagar menos imposto a partir de certa renda; essa
  conta é do contador.
- **No consultório compartilhado:** cada pediatra fatura no próprio nome, como pessoa física ou com o CNPJ dela. O
  consultório só precisa de CNPJ se as pediatras montarem uma empresa juntas.
- **O documento que a família recebe depende disso:**
  - **Pessoa física:** não existe nota fiscal. O documento é o recibo do **Receita Saúde**, obrigatório desde
    1º/01/2025 (IN RFB 2.240/2024). A pediatra emite no app Receita Saúde ou no e-CAC, com a conta gov.br dela, e o
    recibo vai sozinho para a declaração de IR da família. **Não há API oficial**, então o Puericorbs não emite sozinho.
    O que dá para fazer:
    1. o sistema monta a lista "Recibos a emitir", com cada dado pronto para copiar (CPF de quem pagou, CPF da criança,
       valor, data e serviço);
    2. a pediatra emite no app;
    3. o PDF anexado chega à família pelo app e pelo WhatsApp.

    Há fornecedor que diz ter uma API para o Receita Saúde, mas não é da Receita: não vale pôr a conta gov.br da
    pediatra nas mãos de terceiros.
  - **Com CNPJ:** a nota fiscal de serviço eletrônica (NFS-e), e **o sistema consegue emitir sozinho**: ao receber, o
    Puericorbs emite a nota e manda o PDF para a família (no app e no WhatsApp). Há dois caminhos:
    1. **Direto pela NFS-e Nacional.** Desde 1º/01/2026 todo município aderiu ao padrão nacional (LC 214/2025). As
       empresas do Simples Nacional emitem pelo Emissor Nacional a partir de 1º/11/2026 (Resolução CGSN 191/2026). A
       API é do governo e não cobra por nota. Ela pede o certificado digital da empresa (A1), o XML assinado e a conexão
       com o certificado.
    2. **Por um provedor** (Focus NFe, NFE.io e outros): uma API só para todas as prefeituras, inclusive as que ainda
       exigem o sistema próprio. Isso é comum para quem está no Lucro Presumido em cidades grandes. O provedor cobra por
       nota ou por mês.
- **O que o Puericorbs já tem (29/10/2026, por ora na cidade de São Paulo).** O dono pediu as duas situações: "por
  ser um SaaS deveria conseguir lidar com as duas".
  - **Em Consultório, "Como você recebe":** pessoa física; empresa, com o CNPJ, a razão social, a inscrição municipal
    (o CCM), o regime e o ISS; ou "ainda não sei". Só a pediatra muda.
  - **A fila:** "Recibos a emitir" (ou "Notas a emitir") na Recepção, e o mesmo **Emitir** no Financeiro da pediatra.
  - **O diálogo de cada pagamento:**
    - os dados prontos para copiar;
    - os CPFs que faltam, ali mesmo, com a conferência dos dígitos;
    - o portal certo: o e-CAC, o Emissor Nacional ou a Nota Fiscal Paulistana;
    - o anexo do PDF.
  - **O PDF vai para os Arquivos da família,** e a recepção avisa pelo WhatsApp, com a mensagem pronta.
  - **Em cada serviço,** o código da nota (04.01, medicina).
- **Falta:**
  - a nota emitida sozinha: o certificado digital A1 da empresa e a integração (a API da NFS-e Nacional, no Simples; um
    provedor, no Lucro Presumido);
  - outras cidades: cada prefeitura é um caso, até todas estarem na NFS-e Nacional.
- **E a AbacatePay:** só recebe com CNPJ. A pediatra pessoa física precisa de um gateway que aceite CPF.

## Pessoa física e empresa: os gateways que aceitam os dois

Pergunta do dono (29/10/2026): algum gateway atende CPF e CNPJ, com taxa baixa? As condições abaixo foram lidas nas
páginas de cada gateway nesta data. As marcadas com † não foram confirmadas na página oficial.

| Gateway | Quem recebe | PIX | Cartão de crédito à vista | Pela API |
|---|---|---|---|---|
| **InfinitePay** | CPF, MEI e CNPJ | grátis | 3,15% (débito 1,37%), em 1 dia útil, até R$ 20 mil por mês | o link de pagamento (`POST /links`) e o aviso; sem assinatura e sem nota |
| **Asaas** | CPF e CNPJ, com a conta aprovada e a prova de vida | R$ 1,99 por cobrança (R$ 0,99 nos 3 primeiros meses) | 2,99% + R$ 0,49 (1,99% + R$ 0,49 nos 3 primeiros meses); débito 1,89% + R$ 0,35 | PIX, boleto (R$ 1,99; com CPF, até R$ 5.000 cada), cartão, assinatura e a nota da empresa (R$ 0,49 cada) |
| **Mercado Pago** | CPF e CNPJ | cerca de 0,99%† | a confirmar† | completa, com assinatura |
| **AbacatePay** | só CNPJ | R$ 0,80† | R$ 0,60 + 3,5%† | PIX, checkout e assinatura no cartão |
| **Stripe** | CPF e CNPJ (lido em 02/11/2026) | 1,19%, só por convite, e proibido para "serviços médicos" (abaixo) | 3,99% + R$ 0,39 | completa, com assinatura no cartão; sem PIX Automático e sem nota |

Numa consulta de R$ 450:

| | InfinitePay | Asaas |
|---|---|---|
| no PIX | R$ 0 | R$ 1,99 (0,44%) |
| no cartão à vista | R$ 14,18 | R$ 13,95 |
| 80 consultas no PIX, num mês | R$ 0 | R$ 159,20 |

No Stripe, a mesma consulta custaria R$ 18,35 no cartão e R$ 5,36 no PIX (R$ 428,40 em 80 PIX), se o PIX fosse liberado.

- **O PIX Automático exige CNPJ de quem recebe** (regra do Banco Central). A pediatra pessoa física cobra a mensalidade
  do plano no cartão recorrente (o Asaas faz) ou com um PIX novo a cada mês.
- **A InfinitePay é a mais barata e a mais curta.** O PIX é de graça para CPF e CNPJ, e o cartão custa quase o mesmo
  que no Asaas. Mas a API só cria o link e avisa do pagamento: não assina e não emite nota. A página do checkout não diz
  se a conta com CPF usa a API, nem fala em assinatura do aviso; quem já integrou confere cada aviso na API
  (`payment_check`) antes de dar baixa.
- **O Asaas é o mais completo.** Uma integração atende pessoa física e empresa, com PIX, boleto, cartão, assinatura e,
  para a empresa, a nota. O preço é o R$ 1,99 por PIX.
- **Cada pediatra recebe na conta dela** (acima). O Puericorbs pode ter mais de um provedor atrás do mesmo
  `payments.py`, e cada pediatra cola a chave do dela.

## O Stripe

Pergunta do dono (02/11/2026): o Stripe aceita CPF e CNPJ? Lido nas páginas do Stripe nesta data.

- **Aceita os dois.** A conta brasileira abre como pessoa física (CPF) ou jurídica (CNPJ), e a conta do banco tem de
  ser do mesmo CPF ou CNPJ. O tipo e o nome não mudam depois da verificação: quem passa de CPF para CNPJ abre outra
  conta, e a chave no Puericorbs troca junto.
- **O PIX é o problema.** Pela documentação, o PIX no Stripe proíbe a categoria "serviços médicos" (MCC 8099), além
  de hospitais e laboratórios. O consultório costuma entrar como "médicos" (MCC 8011), que não está na lista, mas a
  conta pode cair na categoria proibida. Além disso, o PIX é por convite, custa 1,19% e passa pela EBANX, que aparece
  como recebedor no extrato da família. O PIX Automático não existe para empresa brasileira.
- **É o mais caro.** O cartão sai a 3,99% + R$ 0,39, contra 2,99% + R$ 0,49 no Asaas, e o Stripe não emite nota.
- **O que ele tem de melhor:** a API e a documentação, as melhores do mercado, e o checkout pronto.
- **Resumo:** serve para o cartão. Para o PIX na recepção, que é o caso do dia a dia, ele fica atrás do Asaas e da
  InfinitePay até alguém confirmar com o Stripe que o PIX funciona para um consultório pediátrico.

## A taxa é do consultório, e aparece

Decisão do dono (02/11/2026): a taxa do gateway fica com o consultório, nunca com a família, e precisa ficar clara.

- **A família paga o preço do serviço,** sem acréscimo, em qualquer forma de pagamento.
- **A pediatra vê a taxa antes de escolher:** em "Como você recebe", cada gateway com o custo de uma consulta dela, no
  PIX e no cartão.
- **Cada pagamento mostra o bruto, a taxa e o líquido,** no Financeiro e na exportação para o contador. A taxa entra
  como despesa do mês, e o "Resultado" já sai sem ela.
- **Construído quando o primeiro gateway entrar;** hoje não há gateway, e o pagamento é registrado à mão.

## Recomendação

1. **O gateway: o Asaas primeiro.** Atende a pediatra pessoa física e a com empresa numa integração só, com a
   assinatura no cartão e a nota. A InfinitePay entra depois, para quem quer o PIX de graça, testada antes numa conta
   com CPF. A AbacatePay serve a quem tem CNPJ e prefere ela.
2. **Começar pelo PIX na recepção, no ambiente de teste do gateway.** Dá para construir e testar tudo sem dinheiro de
   verdade, inclusive os avisos.
3. **O recibo e a nota já funcionam, à mão** (acima). A nota automática entra quando a primeira pediatra tiver CNPJ e
   o certificado A1.
4. **Depois:** o pagamento antes de marcar e a mensalidade do plano no cartão.

## Para decidir

- **Como a Dra. Karita recebe:** como pessoa física ou com CNPJ? Com CNPJ, no Simples Nacional? Ela mesma marca em
  Consultório, e isso decide o recibo ou a nota, e se a AbacatePay serve.
- **O gateway:** o Asaas (recomendado: completo, R$ 1,99 por PIX) ou a InfinitePay (PIX grátis, API curta)?
- **Por onde começar:** o PIX na recepção (recomendado) ou a mensalidade do plano?
- **A taxa:** quem paga, o consultório (o padrão) ou a família? O checkout de cartão permite repassar a taxa.

## Fontes

Documentação da AbacatePay, lida em 29/10/2026:
- [chaves e autenticação](https://docs.abacatepay.com/pages/authentication.md);
- [PIX](https://docs.abacatepay.com/pages/transparents/create.md) e
  [conferir o PIX](https://docs.abacatepay.com/pages/transparents/check.md);
- [checkout](https://docs.abacatepay.com/pages/payment/create.md);
- [assinaturas](https://docs.abacatepay.com/pages/subscriptions/create.md);
- [produtos](https://docs.abacatepay.com/pages/products/create.md);
- [clientes](https://docs.abacatepay.com/pages/client/create.md);
- [avisos (webhooks)](https://docs.abacatepay.com/pages/webhooks.md);
- [ambiente de teste](https://docs.abacatepay.com/pages/devmode.md);
- [produção](https://docs.abacatepay.com/pages/production.md);
- [perguntas frequentes](https://docs.abacatepay.com/pages/faq/index.md).

Nota fiscal e recibo:
- [CFM: médicos devem emitir recibos pelo Receita Saúde desde 1º de janeiro (de 2025)](https://portal.cfm.org.br/noticias/desde-1o-de-janeiro-medicos-devem-emitir-recibos-fiscais-pelo-receita-saude/);
- [NFS-e Nacional, manual da API do contribuinte (gov.br/nfse)](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual/manual-contribuintes-emissor-publico-api-sistema-nacional-nfs-e-v1-2-out2025.pdf/@@download/file);
- [Conta Azul: prazos da NFS-e padrão nacional e a CGSN 191/2026](https://contaazul.com/blog/nfse-padrao-nacional/);
- [Contabilizei: médico pode ser MEI?](https://www.contabilizei.com.br/contabilidade-online/medico-pode-ser-mei/).

Gateways que aceitam pessoa física e empresa, lidos em 29/10/2026:
- [Asaas: PIX](https://www.asaas.com/pix-asaas) e [preços e taxas](https://www.asaas.com/precos-e-taxas);
- [Asaas: pessoa física pode emitir boleto](https://blog.asaas.com/pessoa-fisica-pode-emitir-boleto/amp/);
- [InfinitePay: PIX](https://www.infinitepay.io/pix), [taxas](https://www.infinitepay.io/blog/infinitepay-taxas)
  (de 20/10/2026) e [checkout integrado](https://www.infinitepay.io/checkout);
- [uma integração do checkout da InfinitePay](https://github.com/ghostmoneyx1/escola-castelo-do-saber/pull/1), que
  confere cada aviso com o `payment_check`.

Taxas, de fontes de terceiros sem data:
- [discussão no GitHub do Pix](https://github.com/bacen/pix-api/discussions/266);
- [TabNews](https://www.tabnews.com.br/RickRibeiro/5ef2665c-40cc-4d02-a98a-76cf794bf670).

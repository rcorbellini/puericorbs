# Pagamentos: a AbacatePay e como o Puericorbs receberia

> 29/10/2026. Pesquisa pedida pelo dono. A fonte é a documentação da AbacatePay (API v2), lida nesta data; as taxas
> não estão nela. Nada disto está construído ainda.

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
- **A pediatra pessoa física:** precisa de um gateway que aceite CPF. A recomendação anterior (Asaas, em
  `decisoes.md`) era por isso e pela nota fiscal; conferir as condições de hoje.
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
- **O que o Puericorbs já tem e o que falta.**
  - **Já tem:**
    - a fila "Notas a emitir" na recepção;
    - o anexo de nota e de recibo, que a família vê no app;
    - em cada serviço, o código da nota (04.01, medicina) e a chave "emitir sozinha".
  - **Falta:**
    - o CPF da criança (hoje só o responsável tem CPF);
    - os dados fiscais da pediatra: CNPJ, inscrição municipal, regime e alíquota do ISS;
    - o certificado digital, no caso do CNPJ.
- **E a AbacatePay:** só recebe com CNPJ. A pediatra pessoa física precisa de um gateway que aceite CPF.

## Recomendação

1. **Começar pelo PIX na recepção, com a chave de teste.** Dá para construir e testar tudo sem dinheiro de verdade,
   inclusive os avisos. Para isso, basta uma conta da AbacatePay, que pode ser a do dono.
2. **Antes de ligar a produção, confirmar se a Dra. Karita atende com CNPJ.** Se atender, ela abre a conta dela, e o
   site ganha o CNPJ no rodapé, os termos e a política.
3. **Depois:** o pagamento antes de marcar e a mensalidade do plano no cartão.

## Para decidir

- **CNPJ da Dra. Karita:** ela atende como pessoa física ou com CNPJ? Com CNPJ, ela está no Simples Nacional, e em
  qual cidade? Isso decide o recibo (Receita Saúde) ou a nota (NFS-e Nacional ou provedor), e se a AbacatePay serve.
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

Taxas, de fontes de terceiros sem data:
- [discussão no GitHub do Pix](https://github.com/bacen/pix-api/discussions/266);
- [TabNews](https://www.tabnews.com.br/RickRibeiro/5ef2665c-40cc-4d02-a98a-76cf794bf670).

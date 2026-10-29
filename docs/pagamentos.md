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

## Recomendação

1. **Começar pelo PIX na recepção, com a chave de teste.** Dá para construir e testar tudo sem dinheiro de verdade,
   inclusive os avisos. Para isso, basta uma conta da AbacatePay, que pode ser a do dono.
2. **Antes de ligar a produção, confirmar se a Dra. Karita atende com CNPJ.** Se atender, ela abre a conta dela, e o
   site ganha o CNPJ no rodapé, os termos e a política.
3. **Depois:** o pagamento antes de marcar e a mensalidade do plano no cartão.

## Para decidir

- **CNPJ da Dra. Karita:** ela atende com CNPJ? Sem CNPJ, a AbacatePay não serve para ela.
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

Taxas, de fontes de terceiros sem data:
- [discussão no GitHub do Pix](https://github.com/bacen/pix-api/discussions/266);
- [TabNews](https://www.tabnews.com.br/RickRibeiro/5ef2665c-40cc-4d02-a98a-76cf794bf670).

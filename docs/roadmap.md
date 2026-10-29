# Roadmap

> 28/10/2026. Os marcos, do primeiro uso real ao SaaS aberto. O detalhe de cada funcionalidade está em
> `funcionalidades.md`, com a mesma marcação (`M0`…`M3`).

## Onde estamos (28/10/2026)

A **v0.1** está construída e no ar em duas instâncias (`dominios.md`): a demonstração, para validar, e a produção, com
o consultório da primeira pediatra no ar em https://karitanaves.com.br, ainda vazio, esperando o convite ser aceito.

- **Do M0, feito:** contas, práticas, papéis, isolamento por prática (um banco por prática, com os testes), auditoria,
  famílias e crianças, catálogo de serviços configurável, o vidro claro, o domínio por pediatra e a entrada por
  convite (equipe, família, colega e administração), o painel da administração (com o "vendo como") e o limite de senha errada.
  **Falta:** termo e política, segundo fator, backup fora de casa.
- **Do M1, feito:** agenda (grade, vagas da criança doente, encaixe, recepção do dia, busca ativa), consulta com
  modelos, medidas e curvas da OMS, linha do cuidado (puericultura, vacinas, marcos), app da família, arquivos com caixa
  de revisão, plano com cota, recebimentos e o financeiro do mês, e o acesso da família pelo link (que também serve
  para a família criar outra senha). Também: os horários da pediatra e a agenda fechada, o pedido de confirmação pelo
  WhatsApp (o primeiro passo do M2) e o nome do consultório no app instalado e na prévia do link.
- **Do M3, adiantado (29/10):** o consultório com várias pediatras, cada uma com os pacientes dela, a atendente de
  todas e a administração do consultório, com a equipe entrando por convite.
- **Também em 29/10:** o convite da família nova pré-preenchido (a família confere e completa), o QR code em todo
  convite e o recibo ou a nota de cada pagamento, para a pediatra pessoa física ou com empresa (por ora em São Paulo):
  a recepção emite com os dados prontos e o PDF chega à família. **Falta:** recuperar a senha da equipe, documentos em
  PDF, caixa, lembretes (push e e-mail).

## Conversar com pediatras

Três a cinco conversas com pediatras que atendem particular: de preferência um sozinho, um numa clínica pequena e um
que já vende plano de acompanhamento. Roteiro:

1. Como você agenda hoje? Quem agenda? Quantas faltas por semana?
2. Você reserva horário para a criança doente do dia? Como faz o encaixe?
3. Onde fica o prontuário? O que mais te irrita nele?
4. Você vende plano de acompanhamento? Como cobra? Quanto atrasa?
5. Atende como pessoa física ou jurídica? Como emite a nota ou o recibo? E o reembolso do convênio da família?
6. Como os pais mandam exame e foto? Onde isso fica guardado?
7. O que a sua atendente faz o dia inteiro? O que você queria que sumisse da rotina dela?
8. Quanto você paga hoje em sistema? O que faria você trocar?
9. A família pergunta "qual é a próxima vacina, a próxima consulta"? Com que frequência?
10. Você atende em mais de um lugar? Divide paciente com colega?

Sai daí: o piloto, o que entra no M1 e o que pode esperar.

## Marcos

### M0 — Fundação

Contas, práticas, membros e papéis; isolamento por prática (RLS) com os testes; log de auditoria; cadastro de
famílias, responsáveis e crianças; catálogo de serviços; o vidro claro no código; termo e política.

**Pronto quando:** duas práticas de teste não se enxergam em nenhuma tela nem rota, e os testes de isolamento provam
isso.

### M1 — O consultório funciona (piloto)

Agenda completa (grade, vagas protegidas, encaixe, recepção do dia, retorno, busca ativa), prontuário com modelos,
medidas e curvas, linha do cuidado com protocolos, vacinas e marcos, app da família, arquivos com caixa de revisão,
recebimentos, caixa e recibos, plano com cota (cobrança registrada à mão), lembretes por push e e-mail.

**Pronto quando:** um pediatra-piloto e a atendente passam 30 dias sem voltar ao caderno, à planilha nem ao WhatsApp
para agendar.

### M2 — O dinheiro entra sozinho

Cobrança automática do plano (cartão, PIX Automático, boleto) com a régua de cobrança, pagamento no app, NFS-e,
Receita Saúde, kit reembolso, contas a pagar e fluxo de caixa, WhatsApp (confirmação e lembretes), lista de espera,
mensagens, assinatura digital e prescrição.

**Pronto quando:** o plano do piloto cobra, emite a nota e avisa a família sem a atendente tocar, e o mês fecha com um
arquivo para o contador.

### M3 — A clínica e o SaaS aberto

~~Várias práticas numa clínica, atendente compartilhada, gestor~~ (feitos em 29/10), salas, repasse, cobertura entre
pediatras, pediatra em várias clínicas, página pública, cadastro sozinho com teste grátis, assinatura do Puericorbs.

**Pronto quando:** uma clínica com dois pediatras roda um mês com o repasse automático, e um pediatra novo se
cadastra e atende sem a nossa ajuda.

### Depois

Teleconsulta, IA como rascunho, sala de vacina, RNDS, convênios, adolescente com acesso próprio, outros profissionais,
app nativo (`funcionalidades.md`, seção 13).

## Próximos passos

1. A primeira pediatra já criou a conta (28/10, no karitanaves.com.br). O dono aceita o convite da administração e
   valida a plataforma pelo "vendo como".
2. O domínio da plataforma (com o nome): o painel e os convites de colega saem do domínio da primeira pediatra.
3. Antes do primeiro paciente de verdade: backup criptografado fora de casa, termo, política, o contrato com a
   pediatra (prevendo o acesso da administração) e a tela em que ela vê as entradas da administração (`dominios.md`,
   última seção; `decisoes.md`, em aberto).
4. Acompanhar a primeira pediatra e conversar com mais dois ou três (o roteiro acima).
5. Decidir o nome e o gateway (`decisoes.md`, "Em aberto").
6. Validar com um advogado o plano de acompanhamento, o termo e a política antes de vender.
7. As interações que eu faria primeiro (`planos-e-interacoes.md`): busca ativa e vacina atrasada pelo WhatsApp,
   confirmar presença no app, fazer funcionar as quatro chaves de Serviços que hoje não fazem nada (perguntas antes da
   consulta, orientações pela idade, declaração, pesquisa), dúvidas para a próxima consulta e o resumo do ano na
   renovação do plano.

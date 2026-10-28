# Roadmap

> 28/10/2026. Os marcos, do primeiro uso real ao SaaS aberto. O detalhe de cada funcionalidade está em
> `funcionalidades.md`, com a mesma marcação (`M0`…`M3`).

## Antes de construir: conversar com pediatras

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

Várias práticas numa clínica, atendente compartilhada, salas, repasse, gestor, cobertura entre pediatras, pediatra em
várias clínicas, página pública, cadastro sozinho com teste grátis, assinatura do Puericorbs.

**Pronto quando:** uma clínica com dois pediatras roda um mês com o repasse automático, e um pediatra novo se
cadastra e atende sem a nossa ajuda.

### Depois

Teleconsulta, IA como rascunho, sala de vacina, RNDS, convênios, adolescente com acesso próprio, outros profissionais,
app nativo (`funcionalidades.md`, seção 13).

## Próximos passos

1. Decidir o nome, a pilha e o gateway (`decisoes.md`, "Em aberto").
2. Conversar com os pediatras e escolher o piloto.
3. Especificar o M0.
4. Validar com um advogado o plano de acompanhamento, o termo e a política antes de vender.

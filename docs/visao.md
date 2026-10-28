# Visão do produto

> 28/10/2026 · descoberta. "Pueri" é nome de trabalho.

## O problema

O pediatra que atende no próprio consultório, sozinho ou numa clínica pequena, costuma rodar o dia com:

- a agenda num caderno, no Google Agenda ou na cabeça da secretária, e a confirmação feita à mão pelo WhatsApp;
- o prontuário em papel ou num sistema feito para clínica grande, caro e sem nada de pediatria (curvas, vacinas,
  marcos do desenvolvimento);
- o financeiro numa planilha, a nota fiscal emitida uma a uma e o recibo para o reembolso do convênio feito na hora,
  quando a família pede;
- o plano de acompanhamento (o "pediatra por assinatura") vendido de boca, controlado na planilha e cobrado por PIX
  todo mês, com a inadimplência descoberta tarde;
- exames, fotos e comprovantes chegando soltos no WhatsApp, misturados com a conversa, perdidos uma semana depois.

E a família não sabe o que vem pela frente: quando é a próxima consulta da puericultura, que vacina está para vencer,
se o exame que o pediatra pediu já foi visto.

## Para quem

- **Pediatra** que atende particular (com ou sem alguns convênios), sozinho ou numa clínica de 1 a 5 pediatras, com
  0 a 2 atendentes.
- **Família** com criança de 0 a 18 anos. O centro é a puericultura dos primeiros 2 anos: é quando há mais
  consultas, vacinas, marcos e dúvidas, e quando o plano de acompanhamento faz mais sentido.

## Os perfis

| Perfil | Quem é | O que faz |
|---|---|---|
| Pediatra | o médico; a carteira de pacientes é dele | atende, registra, acompanha, configura serviços e planos, vê o próprio dinheiro |
| Atendente | a secretária do consultório ou a recepção da clínica | agenda, confirma, recebe, cobra, emite nota, cuida da papelada; nunca vê conteúdo clínico |
| Família | os responsáveis (o cliente) e a criança (o paciente) | agenda, paga, acompanha o cuidado, envia arquivos, recebe documentos |

Papéis que entram depois, sem mudar o modelo: gestor da clínica, enfermagem e contador (`arquitetura.md`).

## O que foi pedido

1. **Agenda do pediatra.**
2. **Acompanhamento financeiro.**
3. **A família acompanha o que foi feito e o que precisa ser feito.**
4. **Planos com recorrência.**
5. **Arquivos dos dois lados:** exames, comprovantes, notas fiscais.
6. **SaaS:** vários pediatras, em clínicas diferentes, cada um vendo só os seus pacientes.
7. **Cada serviço configurável.**
8. **Visual:** vidro líquido como o CardLine, com cores mais claras.

Onde cada pedido vira funcionalidade, e o que propomos a mais, está em `funcionalidades.md`.

## Princípios

1. **A família vê o caminho, não o prontuário.** O registro clínico é do pediatra. A família vê o resumo que ele
   libera e a linha do cuidado: o que já foi feito e o que vem, com data.
2. **A carteira é do pediatra.** O isolamento é por prática, não por clínica. Dois pediatras na mesma sala de espera
   não se enxergam, a não ser que escolham dividir.
3. **Nada fixo no código que o pediatra queira mudar.** O serviço é a unidade de configuração: duração, preço, quem
   agenda, retorno, formulário, nota.
4. **O que deve acontecer vira item com data.** Consulta do protocolo, vacina, exame pedido, retorno, tarefa: tudo é
   um item do cuidado, com dono e prazo. É ele que alimenta a tela da família, os lembretes e a busca ativa.
5. **Menos WhatsApp, não zero WhatsApp.** O lembrete vai pelo canal que a família já lê; a conversa clínica, os
   arquivos e os documentos ficam no Pueri, organizados por criança.
6. **Primeiro o consultório de um pediatra só.** O que funciona para um pediatra e uma atendente escala para a
   clínica. O contrário não vale.
7. **Celular primeiro para a família; computador e celular para o consultório.**
8. **Conformidade desenhada no modelo.** Dado de saúde de criança (LGPD), guarda do prontuário, sigilo do
   adolescente, guarda compartilhada: entram no desenho dos dados, não num remendo depois.

## O que o Pueri não é

- **Não é plano de saúde.** O plano de acompanhamento é um pacote de serviços do próprio pediatra. Não cobre urgência,
  internação nem exames de terceiros.
- **Não é sistema de hospital nem de pronto-socorro.**
- **Não substitui o atendimento de urgência.** O canal de mensagens diz isso em toda conversa.
- **Não faz convênio (TISS, guias, glosas) no começo.** O alvo é o particular; convênio só se os pilotos pedirem.

## Como saber que deu certo

Hipóteses para medir com os pilotos (os números se calibram com eles):

- O pediatra e a atendente passam 30 dias sem voltar ao caderno, à planilha nem ao WhatsApp para agendar.
- As faltas caem depois da confirmação automática.
- A família abre o Pueri entre uma consulta e outra, para ver o que vem, mandar um exame ou baixar um documento.
- A cobrança do plano roda sozinha: a atendente só trata exceção.
- O pediatra fecha o mês sem montar planilha para o contador.

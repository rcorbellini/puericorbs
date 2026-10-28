# Pueri

Sistema para o consultório pediátrico pequeno: a agenda do pediatra, o financeiro, o acompanhamento da criança
(o que já foi feito e o que vem pela frente), os planos de acompanhamento com recorrência e os arquivos que
pediatra e família trocam (exames, comprovantes, notas fiscais, fotos).

É um SaaS: cada pediatra, sozinho ou numa clínica com outros, tem a sua carteira de pacientes e só vê a dele.

> **Estado: descoberta (28/10/2026).** Ainda não há código: há a visão, a exploração das funcionalidades, o modelo
> de dados e a identidade visual. "Pueri" é nome de trabalho (de *puericultura*, o acompanhamento da criança que
> cresce).

## Os três perfis

| Perfil | Quem é | O que faz no Pueri |
|---|---|---|
| **Pediatra** | o médico; a carteira de pacientes é dele | atende, registra, acompanha, configura serviços e planos, vê o próprio dinheiro |
| **Atendente** | a secretária do consultório ou a recepção da clínica | agenda, confirma, recebe, cobra, emite nota, cuida da papelada; nunca vê conteúdo clínico |
| **Família** | os responsáveis (o cliente) e a criança (o paciente) | agenda, paga, acompanha o cuidado, envia exames e fotos, recebe receitas e notas |

## Documentos

- [`docs/visao.md`](docs/visao.md): o problema, para quem, os princípios e o que o Pueri não é.
- [`docs/funcionalidades.md`](docs/funcionalidades.md): a exploração, módulo por módulo: o que foi pedido, o que
  propomos a mais e em que fase entra.
- [`docs/arquitetura.md`](docs/arquitetura.md): quem é dono de quê no SaaS, o que cada perfil vê, os dados, a pilha
  e as integrações.
- [`docs/identidade-visual.md`](docs/identidade-visual.md): o vidro líquido claro, derivado do CardLine, com os tokens.
- [`docs/glossario.md`](docs/glossario.md): os termos do domínio e o nome de cada um no código.
- [`docs/roadmap.md`](docs/roadmap.md): os marcos, do piloto ao SaaS aberto, e o roteiro de conversa com pediatras.
- [`docs/decisoes.md`](docs/decisoes.md): o que já foi decidido, com o porquê, e o que está em aberto.

O protótipo das telas e da identidade é um canvas: https://claude.ai/artifact/Mrnek95xeh8xLoHdqJarYZ

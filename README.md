# Puericorbs

O consultório pediátrico pequeno inteiro num lugar: a agenda do pediatra, o financeiro, o acompanhamento da criança
(o que já foi feito e o que vem pela frente), os planos de acompanhamento com recorrência e os arquivos que pediatra e
família trocam (exames, fotos, receitas, notas fiscais).

É um SaaS self-hosted. Cada pediatra tem o próprio domínio (`dramarina.com.br`), todos apontam para este servidor, e o
endereço decide de qual consultório é o site. Cada pediatra só vê os seus pacientes: cada prática tem o próprio banco.

> **Estado: v0.1 em validação (28/10/2026).** "Puericorbs" é nome provisório.

## Os três perfis

| Perfil | Quem é | O que faz no Puericorbs |
|---|---|---|
| **Pediatra** | o médico; a carteira de pacientes é dele | atende, registra, acompanha, configura serviços e planos, vê o próprio dinheiro |
| **Atendente** | a secretária do consultório ou a recepção da clínica | agenda, confirma, recebe, cobra, cuida das notas; nunca vê conteúdo clínico |
| **Família** | os responsáveis (o cliente) e a criança (o paciente) | agenda, acompanha o cuidado, envia exames e fotos, recebe receitas e notas |

## Rodar

```bash
uv sync
uv run puericorbs seed --reset   # a demonstração: Clínica Girassol, Dra. Marina, Dr. Paulo, a recepção e as famílias
uv run puericorbs serve          # http://localhost:8930
uv run -q pytest -q              # os testes (o isolamento entre consultórios primeiro)
```

- `http://localhost:8930` é a plataforma: a lista de consultórios.
- `http://dramarina.localhost:8930` e `http://drpauloreis.localhost:8930` são os sites de cada pediatra (o navegador
  manda `*.localhost` para a própria máquina).
- Na demonstração, a tela de entrada mostra as contas (pediatra, recepção, famílias), e a senha de todas é `demo1234`.
  Pelo endereço da plataforma (o do ngrok, por exemplo), "Abrir o site" visita o consultório como se fosse o domínio
  dele.
- Apontar um domínio para uma prática: `uv run puericorbs domain dramarina.com.br dramarina`. O passo a passo para pôr
  domínios no ar está em [`docs/dominios.md`](docs/dominios.md).

## O que a v0.1 já faz

- **Pediatra:** o dia (quem chegou, a agenda, o que revisar, a busca ativa, o dinheiro do dia); a consulta com o modelo
  do serviço, as medidas com percentil da OMS na hora, os marcos, o resumo para a família separado do registro e os
  próximos passos; a ficha da criança (linha do cuidado, curvas, caderneta, marcos, consultas, arquivos); a caixa de
  revisão; os serviços (cada um configurável); os planos com cota; o financeiro com a exportação para o contador.
- **Recepção:** as tarefas do dia de todos os pediatras que atende (chegadas, receber, confirmar amanhã, busca ativa,
  notas a emitir, mensalidades em atraso); a agenda da clínica em grade, com encaixe e as vagas da criança doente; o
  cadastro das famílias.
- **Família:** o próximo passo e o "a fazer" calculados pela idade; o feito, com o resumo de cada consulta; agendar
  dentro da janela do protocolo e das regras do serviço, com o plano; a curva de crescimento, as vacinas e os marcos;
  os arquivos, com o envio de exames e fotos para a pediatra revisar.

O que ainda não existe (cobrança automática, NFS-e, WhatsApp, mensagens, documentos em PDF, o construtor de
formulários) está no [`docs/roadmap.md`](docs/roadmap.md).

## Documentos

- [`docs/visao.md`](docs/visao.md): o problema, para quem, os princípios e o que o Puericorbs não é.
- [`docs/funcionalidades.md`](docs/funcionalidades.md): a exploração, módulo por módulo, com as fases.
- [`docs/arquitetura.md`](docs/arquitetura.md): quem é dono de quê, o que cada perfil vê, os bancos e a pilha.
- [`docs/dominios.md`](docs/dominios.md): o domínio de cada pediatra, do local à produção.
- [`docs/identidade-visual.md`](docs/identidade-visual.md): o vidro líquido claro, derivado do CardLine.
- [`docs/glossario.md`](docs/glossario.md): os termos do domínio e o nome de cada um no código.
- [`docs/roadmap.md`](docs/roadmap.md): os marcos e o estado de cada um.
- [`docs/decisoes.md`](docs/decisoes.md): o que já foi decidido, com o porquê, e o que está em aberto.

O protótipo das telas (a referência visual) é um canvas: https://claude.ai/artifact/Mrnek95xeh8xLoHdqJarYZ

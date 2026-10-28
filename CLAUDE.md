# Pueri: como trabalhar neste projeto

O Pueri é um SaaS para o consultório pediátrico pequeno: agenda, financeiro, acompanhamento da criança, planos
recorrentes e arquivos. O projeto está em **descoberta**: a fonte da verdade são os documentos em `docs/` (lista no
`README.md`).

## Idioma e tom

- Responda em português do Brasil. Documentos, textos da tela, mensagens de erro e commits também em PT-BR.
- Identificadores no código (variáveis, funções, rotas, tabelas, colunas) em inglês. O nome de cada termo do domínio
  está em `docs/glossario.md`: use o de lá, não invente outro ("plano" é `plan`, nunca `care_plan`).
- Frases curtas e diretas, que dizem o porquê. Mensagem de erro diz o que fazer.

## Invariantes (não se negociam)

1. **Cada pediatra só vê os seus pacientes.** O isolamento é pela prática (`practice`), não pela clínica: toda
   consulta a dado de paciente é filtrada por ela no banco. Acesso fora da prática só por concessão com prazo, motivo
   e registro.
2. **A atendente nunca vê conteúdo clínico.** Ela vê agenda, cadastro, dinheiro e documentos administrativos.
3. **A família vê o que foi liberado para ela.** Todo registro e todo arquivo tem visibilidade (`internal`, `family`,
   `admin`, `confidential`), decidida no servidor. O registro clínico nasce `internal`; o resumo para a família,
   `family`.
4. **Prontuário não se apaga.** Corrige-se com histórico (quem, quando, o quê). Guarda mínima de 20 anos.
5. **Todo acesso a dado de paciente vai para o log de auditoria** (quem, o quê, quando, de onde).
6. **O serviço é a unidade de configuração.** Duração, preço, quem agenda, retorno, formulário, nota fiscal: o que o
   pediatra quiser mudar mora no serviço, nunca fixo no código.
7. **O que deve acontecer com a criança é um item do cuidado** (`care_item`). A linha do cuidado da família, os
   lembretes e a busca ativa leem dele; lista paralela não existe.

O porquê de cada um está em `docs/arquitetura.md` e `docs/decisoes.md`.

## Visual

Vidro líquido claro, derivado do CardLine (`~/cardline/cardline/web/glass.css` e `~/cardline/docs/design.md`). As
regras, os tokens e o que muda em relação ao CardLine estão em `docs/identidade-visual.md`. O protótipo das telas é
um canvas editável: https://claude.ai/artifact/Mrnek95xeh8xLoHdqJarYZ

## Como entregar

1. Se faltar uma decisão que só o dono pode tomar, pergunte uma vez, com uma opção recomendada. O resto, decida e
   conte na resposta.
2. Mudou uma decisão de produto? Atualize `docs/decisoes.md` e o documento do módulo no mesmo commit.
3. Um commit por funcionalidade, com título e corpo em PT-BR (o que muda e o porquê).
4. Dado real de paciente nunca entra em teste, exemplo, captura, documento ou commit. Exemplos usam famílias
   fictícias.

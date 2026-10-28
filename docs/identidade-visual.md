# Identidade visual: vidro líquido claro

> 28/10/2026. Pedido do dono: "liquid glass estilo CardLine, porém com cores mais claras". O material e as regras vêm
> do CardLine (`~/cardline/cardline/web/glass.css` e `~/cardline/docs/design.md`); este guia diz o que se herda, o
> que muda e os tokens. O protótipo das telas é um canvas: https://claude.ai/artifact/Mrnek95xeh8xLoHdqJarYZ (cada
> tela tem os ajustes "escuro" e "destaque", para comparar; a marca ali ainda é o nome antigo, "pueri").
>
> **No código:** os tokens e os materiais estão em `puericorbs/web/glass.css`, o layout em `app.css`. A Figtree fica no
> projeto (`web/fonts/`): nenhuma página carrega fonte de fora. O destaque de cada consultório vem do `data-accent`,
> e a pediatra escolhe o dela em **Consultório**. As capturas (`scripts/qa_shots.py`) conferem 390 e 1280 px, claro e
> escuro.

## O que se herda do CardLine

O material é o mesmo: painéis de vidro translúcido (o degradê branco de cima para baixo, a borda acesa por dentro e
uma sombra macia), botões que são lentes (quase transparentes no meio, a borda grossa e acesa, o reflexo na curva de
cima) e um fundo vivo para o vidro ter o que refratar.

As regras também (o detalhe e o porquê de cada uma está no `design.md` do CardLine):

1. **A cor do destaque é da ação principal.** Uma por tela, no máximo duas.
2. **Estado não é ação.** Opção marcada (seletor, chip, filtro) é uma lente mais cheia e sem cor. A exceção é a
   navegação: o item atual tem o ícone na cor do destaque.
3. **Três níveis de botão, pelo estilo e não pelo tamanho:** principal (`.btn`, lente com véu e texto no destaque),
   secundário (`.btn.ghost`, lente clara), terciário (`.linkbtn`, texto sublinhado leve). Destrutivo é vermelho e
   nunca é o principal.
4. **Nada de vidro sobre vidro.** Dentro de um painel, campos e grupos são um poço raso, sem desfoque nem lente.
5. **Nada colorido atrás do vidro.** O desfoque espalha a cor pela superfície inteira.
6. **Cada ação fica no grupo a que pertence.**
7. **Formulário em linhas, como os Ajustes do iPhone:** rótulo à esquerda, controle à direita; sim/não é a chave
   (verde quando ligada, nunca a cor do destaque).
8. **Criar e adicionar é um diálogo**, e a ação principal aparece desde o começo, desabilitada até estar pronta.
9. **A mudança aparece na hora; guardar é em segundo plano.**
10. **Movimento para com o "reduzir movimento".**

## O que muda

| | CardLine | Puericorbs | Por quê |
|---|---|---|---|
| Tema padrão | segue o aparelho | **claro**; o escuro existe | o pedido é "cores mais claras"; o escuro serve a quem usa o celular no escuro e ao plantão |
| Chão | `#e7eaf3` | `#f5f7fb`, quase branco com um toque de azul | mais claro, mais ar |
| Vidro | branco de 62% a 28% | branco de 74% a 40% | painéis mais leitosos, com o fundo pastel por trás |
| Fundo vivo | cartas em 3D, nas cores do jogo | **bolhas de sabão** com a borda furta-cor, sobre um véu pastel (céu, menta, pêssego, lavanda, manteiga) | a bolha é vidro, é leve e é infância; as cartas eram o jogo |
| Destaque | dourado | **verde-água** (`#08746b`) | saúde e calma; separa-se do âmbar de "a fazer" e do vermelho de "atrasado" |
| Fonte | a do sistema | **Figtree** (Google Fonts, licença OFL) | humanista e arredondada sem ser infantil; números tabulares onde alinham |
| Avatar | foto | a inicial numa bolha, quando não há foto | criança sem foto continua reconhecível, e a bolha repete o fundo |
| Navegação | abas no topo | barra lateral no computador; menu de baixo no celular | o consultório tem mais seções que o CardLine |

## A semântica do cuidado

Uma cor, um sentido, em toda tela (pílulas de estado, linha do cuidado, agenda):

| Token | Sentido | Claro | Escuro |
|---|---|---|---|
| `--done` | feito (vai com o ✓; neutro de propósito: o passado não pede atenção) | `#5a6b7d` | `#a2b0c0` |
| `--todo` | a fazer, pendente | `#9a5200` | `#ffb454` |
| `--late` | atrasado | `#c0392b` | `#ff8a80` |
| `--booked` | agendado, confirmado | `#2563c9` | `#8ab4ff` |
| `--up` / `--down` | dinheiro que entra / que sai ou falta | `#12773f` / `#c0392b` | `#5be49b` / `#ff8a80` |
| `--on` | a chave ligada | `rgb(52 199 89)` | `rgb(48 209 88)` |

Estado sempre leva o texto junto ("Atrasado", "Agendado"), nunca só a cor.

## Gráficos

Seguem a skill de visualização de dados (paleta validada para daltonismo em 28/10/2026):

- **Séries:** azul `#2a78d6` (claro) / `#3987e5` (escuro) e laranja `#eb6834` / `#d95926`, nessa ordem. O laranja
  fica abaixo de 3:1 no claro: o gráfico leva legenda e a tabela ("Ver tabela").
- **Curva de crescimento:** a criança é a série (azul, linha de 2 px, pontos de 8 px com anel da cor do fundo); os
  percentis da OMS são referência, em cinza: faixa P3–P97 bem leve, P15–P85 um pouco mais forte, P50 em linha. Os
  rótulos P3…P97 ficam na ponta direita, no texto suave.
- Grade e eixos em linha fina e contínua (nunca tracejada), um tom fora do fundo. Texto nunca na cor da série.
- A cor do destaque não entra em gráfico: ela é da ação principal.

## Tokens

O tema claro é o `:root`; o escuro entra pelos dois caminhos do CardLine (`@media (prefers-color-scheme: dark)` com
`:root:not([data-theme="light"])`, e `:root[data-theme="dark"]`). Abaixo, os valores.

```css
:root {
  color-scheme: light;
  --font: "Figtree", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  /* o chão e o véu do fundo (o véu e as bolhas só; nunca em texto) */
  --bg: #f5f7fb;
  --veil-1: #a9d8ff;  /* céu */
  --veil-2: #aeeedb;  /* menta */
  --veil-3: #ffd2bf;  /* pêssego */
  --veil-4: #dccfff;  /* lavanda */
  --veil-5: #ffeaa8;  /* manteiga */
  /* o texto */
  --text: #1c2b3a;
  --muted: #5a6b7d;
  /* a ação principal: o texto no destaque, o véu no tint */
  --accent: #08746b;
  --tint: #18a596;
  /* o cuidado e o dinheiro */
  --done: #5a6b7d; --todo: #9a5200; --late: #c0392b; --booked: #2563c9;
  --up: #12773f; --down: #c0392b; --on: rgb(52 199 89);
  /* o vidro dos painéis */
  --panel: rgb(255 255 255 / .56);
  --panel-2: rgb(255 255 255 / .42);
  --glass: linear-gradient(180deg, rgb(255 255 255 / .74), rgb(255 255 255 / .40));
  --glass-rim: inset 0 0 0 1px rgb(255 255 255 / .65), inset 0 1.5px 1px rgb(255 255 255 / 1),
    inset 0 -1.5px 2px rgb(40 70 110 / .06), inset 0 -8px 16px -10px rgb(255 255 255 / .85);
  --glass-drop: 0 1px 1px rgb(30 60 100 / .04), 0 10px 30px rgb(40 80 130 / .09);
  --edge: rgb(30 60 100 / .08);
  /* a lente dos botões */
  --lens: linear-gradient(180deg, rgb(255 255 255 / .66), rgb(255 255 255 / .20) 52%, rgb(255 255 255 / .36));
  --lens-rim: inset 0 0 0 1px rgb(255 255 255 / .95), inset 0 0 6px 1px rgb(255 255 255 / .6),
    inset 0 8px 9px -8px rgb(255 255 255 / 1), inset 0 -7px 9px -7px rgb(255 255 255 / .8);
  --lens-glow: 0 0 0 .5px rgb(40 70 110 / .16), 0 0 14px rgb(255 255 255 / .7), 0 12px 22px -10px rgb(40 80 140 / .28);
  --spec: rgb(255 255 255 / .85);
  /* o poço raso dos campos e grupos dentro do vidro */
  --well: color-mix(in srgb, var(--text) 5%, transparent);
  /* as barras que ficam por cima da página (menu de baixo do celular) */
  --bar: color-mix(in srgb, var(--bg) 40%, transparent);
}

/* o escuro ("anoitecer"): azul-ardósia, nunca preto; repetir em :root[data-theme="dark"] */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #0e1622;
    --veil-1: #2a5d8f; --veil-2: #1f6b5d; --veil-3: #7a4a3c; --veil-4: #4d3f86; --veil-5: #6b5a2a;
    --text: #edf2f7; --muted: #a2b0c0;
    --accent: #5fd6c6; --tint: #2bb3a3;
    --done: #a2b0c0; --todo: #ffb454; --late: #ff8a80; --booked: #8ab4ff;
    --up: #5be49b; --down: #ff8a80; --on: rgb(48 209 88);
    --panel: rgb(28 42 62 / .5); --panel-2: rgb(255 255 255 / .06);
    --glass: linear-gradient(180deg, rgb(255 255 255 / .14), rgb(255 255 255 / .04));
    --glass-rim: inset 0 0 0 1px rgb(255 255 255 / .12), inset 0 1.5px 1px rgb(255 255 255 / .28),
      inset 0 -1.5px 2px rgb(0 0 0 / .25), inset 0 -8px 16px -10px rgb(255 255 255 / .12);
    --glass-drop: 0 1px 1px rgb(0 0 0 / .3), 0 10px 28px rgb(0 0 0 / .4);
    --edge: rgb(0 0 0 / .35);
    --lens: linear-gradient(180deg, rgb(255 255 255 / .2), rgb(255 255 255 / .05) 52%, rgb(255 255 255 / .12));
    --lens-rim: inset 0 0 0 1px rgb(255 255 255 / .62), inset 0 0 6px 1px rgb(255 255 255 / .24),
      inset 0 8px 9px -8px rgb(255 255 255 / .6), inset 0 -7px 9px -7px rgb(255 255 255 / .32);
    --lens-glow: 0 0 0 .5px rgb(255 255 255 / .12), 0 0 16px rgb(170 220 255 / .2), 0 12px 24px -10px rgb(0 0 0 / .75);
    --spec: rgb(255 255 255 / .38);
  }
}
```

Destaques alternativos (o ajuste "destaque" do protótipo): azul `#1f5fbf` / `#8ab4ff`, coral `#b8452a` / `#ff9a7a`,
lavanda `#5b47c4` / `#b7a6ff` (claro / escuro). Todos passam de 4,5:1 sobre o vidro claro.

## Contraste

Medido (WCAG) sobre o branco e sobre o vidro no pior ponto, com o véu azul por trás (`#eef6fd`):

| Cor | sobre o branco | sobre o vidro | no escuro, sobre o vidro (`#1f2a3a`) |
|---|---|---|---|
| texto | 14,4:1 | 13,2:1 | 12,9:1 |
| texto suave | 5,5:1 | 5,0:1 | 6,6:1 |
| destaque | 5,6:1 | 5,2:1 | 8,2:1 |
| a fazer | 5,9:1 | 5,4:1 | 8,2:1 |
| atrasado | 5,4:1 | 5,0:1 | 6,3:1 |
| agendado | 5,7:1 | 5,2:1 | 6,9:1 |

Cor nova só entra com o contraste medido aqui.

## O fundo: bolhas de sabão

- O véu: quatro manchas radiais dos pastéis nos cantos, paradas, sobre o `--bg`.
- As bolhas: 5 a 8 por tela, de tamanhos diferentes, cada uma um círculo com a película furta-cor (um degradê cônico
  dos pastéis, transparente no meio e cheio na borda) e um reflexo branco em cima, à esquerda. Sobem e descem devagar
  (12 a 18 s), sem seguir a rolagem nem o mouse.
- No escuro, as mesmas bolhas, mais apagadas.
- Com "reduzir movimento", param.
- Nada de bolha atrás de texto longo: elas ficam nas bordas da tela, onde o vidro as refrata.

## Checklist de cada tela

- [ ] Uma ação principal com a cor do destaque (no máximo duas).
- [ ] Opção marcada sem cor; campo sem lente; nada de vidro sobre vidro.
- [ ] Estado com texto, não só cor; contraste medido para cor nova.
- [ ] Celular (390 e 320 px) e computador (1200 px), claro e escuro, sem rolagem lateral.
- [ ] Toque de no mínimo 44 px no celular.
- [ ] Nada clínico na tela da atendente.

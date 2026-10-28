# Decisões

> Cada decisão com o porquê. Mudou uma? Escreva a nova com a data e diga qual ela substitui.

## Tomadas

### 28/10/2026 — construir (a v0.1)

13. **Tudo self-hosted.** Pedido do dono; substitui a 11 ("dados no Brasil, em nuvem"). O servidor roda numa máquina
    própria, atrás de um túnel do Cloudflare, como o CardLine. O que isso cobra, porque são dados de saúde de criança
    (LGPD, art. 46, a segurança é de quem trata): disco criptografado; backup criptografado fora de casa, com
    restauração testada; nobreak; o túnel como única porta de entrada; atualizações em dia; `demo = false` em produção.
14. **Nome provisório: Puericorbs.** Pedido do dono, até a escolha do nome final. A pasta é `~/puericorbs`.
15. **Cada pediatra com o próprio domínio, todos apontando para este servidor.** Pedido do dono. O endereço do pedido
    decide a prática (`tenancy.py`); quem não tem domínio usa um subdomínio da plataforma. O passo a passo para pôr no ar
    está em `dominios.md`.
16. **Um banco por prática.** Cada pediatra tem o próprio arquivo SQLite (`data/practices/p<id>/practice.db`); a
    plataforma tem outro, sem dado de paciente. O isolamento fica físico, não um filtro que alguém esquece, e o backup,
    a exportação e a saída de um pediatra são um arquivo. Substitui a recomendação de PostgreSQL com RLS, que fazia
    sentido na nuvem e pedia um servidor de banco a mais em casa.
17. **A pilha: FastAPI, SQLite e uma página sem build** (HTML, CSS e JavaScript puros, em módulos), como o CardLine. Era
    a recomendação em aberto; o dono mandou construir.
18. **A demonstração vem ligada** (`demo = true`): as contas entram sem senha pelos botões da tela de entrada, e o
    endereço da plataforma (o do ngrok) "visita" o site de um pediatra por um cookie. Desligar antes de produção.
19. **Fontes e curvas locais.** A Figtree e as tabelas da OMS ficam no projeto: nenhuma página carrega nada de fora (o
    navegador da família não avisa ao Google que abriu o consultório).

### 28/10/2026 — o começo

1. **O Puericorbs é um SaaS para o consultório pediátrico pequeno.** Pedido do dono: vários pediatras, em clínicas
   diferentes.
2. **A prática é a unidade de isolamento, não a clínica.** Pedido: "cada um vendo só os seus pacientes". O pediatra
   muitas vezes atende em mais de um lugar, e a família segue o médico. A clínica é lugar e equipe, não dona de
   paciente (`arquitetura.md`).
3. **Três perfis: pediatra, atendente e família.** Gestor, enfermagem e contador entram como papéis, sem mudar o
   modelo.
4. **A atendente nunca vê conteúdo clínico.** Ela trabalha com agenda, cadastro, dinheiro e papelada; o resto é
   sigilo médico.
5. **A família tem conta própria e é dona da identidade da criança; cada prática guarda o prontuário que produziu.**
   Assim a família muda de pediatra sem perder o histórico, e uma prática não descobre a outra.
6. **O serviço é a unidade de configuração.** Pedido: "cada serviço precisa ser customizado". Tudo o que o pediatra
   quiser mudar mora no serviço.
7. **Tudo o que deve acontecer com a criança é um item do cuidado.** Uma peça só alimenta a tela da família, os
   lembretes e a busca ativa; listas paralelas divergem.
8. **O registro clínico e o resumo para a família são coisas separadas.** O pediatra escreve à vontade no prontuário e
   libera só o que a família deve ler.
9. **O plano é "plano de acompanhamento": pacote de serviços do próprio pediatra, sem cobrir risco.** É o que mantém o
   produto fora da regulação da ANS (a validar com advogado).
10. **Visual: vidro líquido claro, derivado do CardLine.** Pedido do dono. Destaque verde-água; o fundo vivo são bolhas
    de sabão no lugar das cartas (`identidade-visual.md`).
11. ~~**Dados no Brasil, em nuvem.**~~ Substituída pela 13 (self-hosted).
12. **Código em inglês, produto em português.** Como no Loreforge e no CardLine; o mapa dos termos está em
    `glossario.md`.

## Em aberto

| Decisão | Opções | Recomendação |
|---|---|---|
| Nome do produto | "Puericorbs" (provisório) ou outro | decidir antes de registrar o domínio da plataforma e a marca |
| Como ligar os domínios | Cloudflare for SaaS (CNAME para a plataforma); uma zona por domínio | Cloudflare for SaaS (`dominios.md`) |
| Onde fica o backup fora de casa | outro disco em outro lugar; um armazenamento na nuvem, criptografado antes de sair | criptografado na origem, num armazenamento na nuvem |
| Gateway de pagamento | Asaas, Pagar.me, Iugu, Mercado Pago, Stripe | Asaas (recorrência, PIX, boleto, split e NFS-e num lugar só); confirmar o PIX Automático e as taxas |
| Preço do Puericorbs | por pediatra/mês; taxa sobre o que passa no gateway; os dois | conversar com os pilotos antes |
| Prontuário sem papel | certificar o sistema (SBIS/CFM, NGS2); assinar cada registro com o certificado em nuvem do pediatra | assinar por registro no começo; certificar quando houver tração |
| Convênios | fora; dentro no M3 | fora até os pilotos pedirem |
| Destaque da identidade | verde-água (atual), azul, coral, lavanda | verde-água; cada consultório já escolhe o seu (a Dra. Marina é verde-água, o Dr. Paulo é azul) |
| Processo de especificação | spec-kit, como no Loreforge; só documentos | spec-kit a partir da v0.2 |
| Pilotos | — | um pediatra sozinho e uma clínica pequena |

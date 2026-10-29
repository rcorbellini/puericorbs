# Decisões

> Cada decisão com o porquê. Mudou uma? Escreva a nova com a data e diga qual ela substitui.

## Tomadas

### 28/10/2026 — o nome do consultório no celular e na prévia do link

31. **O consultório aparece com o nome que a pediatra deu a ele, no app instalado e na prévia do link.** Pedido do
    dono. O manifesto, o título, as metatags e a imagem da prévia saem do servidor para cada endereço (`share.py`),
    porque o WhatsApp não roda o JavaScript. "Puericorbs" fica só no endereço da plataforma e no "Feito com Puericorbs"
    do site.

### 28/10/2026 — a administração vendo como quem usa

30. **A administração entra em qualquer consultório vendo como alguém dele** (substitui o "nunca paciente" da 27).
    Pedido do dono: "eu vejo tudo da mesma forma que ela veria e tenho as mesmas ações; a diferença é só o painel que
    fica avisando". A administração é o perfil de maior controle, e o dono vai validar a plataforma por ela. Vale para a
    pediatra, a atendente e qualquer família, com conta ou ainda sem (aí a tela é a que a família vai ver). A tela e as
    regras são as da pessoa; o registro guarda quem estava de fato: cada pedido vai para o `audit_log` do consultório
    com o `actor_id`, e a entrada vai também para o registro da plataforma, sem o nome da família (que não sai do banco
    do consultório). O que a administração faz como a pediatra fica no nome dela na tela, como se ela tivesse feito; só
    o registro diz que foi a administração. Numa família ainda sem conta, fica no nome da administração. A entrada
    passa por um link de 2 minutos e uso único, porque cada domínio tem a própria sessão.

### 28/10/2026 — a página nova chega a quem já abriu o site

29. **Os arquivos da página saem com a versão no endereço** (`/static/v/<versão>/`, em `server.py`). O link da
    administração travou em "Carregando…" no celular do dono: o aparelho tinha aberto o site às 13:44, e o Cloudflare
    manda o navegador guardar .js e .css por 4 horas, mesmo quando o servidor diz `no-cache`. Depois da atualização das
    14:29, a página nova rodava o JavaScript velho, que não conhecia o convite da administração. A versão muda sempre
    que um arquivo muda, então nenhum cache (o do navegador ou o do Cloudflare) devolve arquivo velho, e ninguém precisa
    limpar nada depois de atualizar.

### 28/10/2026 — convites e administração

24. **Quatro convites, e quem gera cada um** (`arquitetura.md`, "Como cada pessoa entra"). Pedido do dono: a pediatra
    gera o da família, o da atendente e o de um colega; a administração acompanha e também gera. A recepção também
    gera o da família, porque é ela quem cadastra.
25. **Uma conta só se liga com a senha dela; o cadastro não liga conta nenhuma.** Antes, a recepção cadastrava o
    responsável e o sistema ligava a ficha a qualquer conta com o mesmo e-mail; com um link de "criar senha", isso
    entregaria a conta (e os filhos) de outra pessoa. O link da família troca a senha só de quem é só daquela família,
    naquele consultório.
26. **O colega ganha o próprio consultório**, não entra no de quem convidou: "cada um vendo só os seus pacientes". Ele
    nasce sem domínio; a plataforma liga o domínio pelo painel e pelo DNS (`dominios.md`).
27. **O painel da administração fica em `#/admin` de qualquer site nosso**, até existir o domínio da plataforma. Vê
    números, equipes, convites e o registro; nunca paciente. Não põe ninguém num consultório que já tem pediatra.
28. **Limite de senha errada** (10 por endereço, 20 por conta, em 15 minutos), porque a entrada da administração
    está na internet desde o painel.

### 28/10/2026 — a primeira pediatra

20. **Produção e demonstração são duas instâncias.** A demonstração entra sem senha e o "reiniciar" apaga a pasta
    inteira; na mesma pasta, isso alcançaria o consultório de verdade. A produção mora em `~/.local/share/puericorbs`
    (fora do projeto, longe de um `git clean`), com `demo = false`, na porta 8931; a demonstração fica em `data/`, na
    8930. A semente se recusa a rodar com `demo = false` (`dominios.md`).
21. **A equipe entra por convite.** Um link de uso único, que vale 7 dias e só abre no domínio do consultório; a
    pessoa cria a própria senha, e a pediatra diz ali como o consultório aparece no site. Nenhuma senha passa por
    terceiros, e a plataforma não precisa saber o e-mail dela antes. O consultório nasce vazio (`puericorbs practice`)
    e a pediatra ajusta o resto em **Consultório**.
22. **Um túnel do Cloudflare só do Puericorbs**, separado do túnel do CardLine, com uma regra só: tudo vai para a
    produção, e o Puericorbs decide pelo domínio. Pediatra novo não mexe no túnel.
23. **O primeiro domínio, karitanaves.com.br, é uma zona na conta do Cloudflare da plataforma** (o dono já fez assim).
    Funciona sem domínio da plataforma; o Cloudflare for SaaS fica para quando houver o nome e muitos pediatras.

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
| Domínio da plataforma | nenhum (hoje o painel e os convites de colega abrem no domínio de uma pediatra); um domínio com o nome | registrar junto com o nome: o painel e os convites de colega vão para ele (uma linha no `config.toml`) |
| A pediatra ver as entradas da administração | numa tela dela (o `audit_log` com o `actor_id`, em Consultório); só quando ela pedir | na tela dela, antes do primeiro paciente de verdade: os dados são dela, e a transparência é a contrapartida do "vendo como" |
| O contrato prever o acesso da plataforma | sim, para suporte e validação, com registro; não | sim: pela LGPD, a plataforma opera os dados que a pediatra controla; validar com advogado |
| Recuperar a senha da equipe | link por e-mail; a administração gera um link de troca | link por e-mail quando houver envio de e-mail; até lá, falar com a plataforma |
| Como ligar os domínios, em escala | uma zona por domínio (em uso, decisão 23); Cloudflare for SaaS (CNAME para a plataforma) | Cloudflare for SaaS quando houver o domínio da plataforma (`dominios.md`) |
| Onde fica o backup fora de casa (antes do primeiro paciente de verdade) | outro disco em outro lugar; um armazenamento na nuvem, criptografado antes de sair | criptografado na origem, num armazenamento na nuvem |
| Gateway de pagamento | Asaas, Pagar.me, Iugu, Mercado Pago, Stripe | Asaas (recorrência, PIX, boleto, split e NFS-e num lugar só); confirmar o PIX Automático e as taxas |
| Preço do Puericorbs | por pediatra/mês; taxa sobre o que passa no gateway; os dois | conversar com os pilotos antes |
| Prontuário sem papel | certificar o sistema (SBIS/CFM, NGS2); assinar cada registro com o certificado em nuvem do pediatra | assinar por registro no começo; certificar quando houver tração |
| Convênios | fora; dentro no M3 | fora até os pilotos pedirem |
| Destaque da identidade | verde-água (atual), azul, coral, lavanda | verde-água; cada consultório já escolhe o seu (a Dra. Marina é verde-água, o Dr. Paulo é azul) |
| Processo de especificação | spec-kit, como no Loreforge; só documentos | spec-kit a partir da v0.2 |
| Pilotos | — | um pediatra sozinho e uma clínica pequena |

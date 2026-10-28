# O domínio de cada pediatra

> 28/10/2026. Pedido do dono: cada pediatra com o próprio domínio, todos apontando para este projeto. O endereço
> decide de qual consultório é o site.

## Como o servidor decide

O pedido chega com o endereço (o cabeçalho `Host`). A ordem está em `puericorbs/tenancy.py`:

1. **O domínio cadastrado** na tabela `domains` abre a prática dele (`dramarina.com.br` → Dra. Marina).
2. **O subdomínio** `<slug>.<base>` de uma das `base_domains` do `puericorbs.toml` abre a prática do slug. Serve para
   quem ainda não tem domínio (`dramarina.puericorbs.com.br`) e para testar no computador (`dramarina.localhost`).
3. **Os `platform_hosts`** abrem a plataforma: a lista de consultórios e a administração.
4. **O resto:** na demonstração, a plataforma; em produção (`demo = false`), "domínio não configurado".

A sessão vale por domínio (o cookie é do endereço): entrar em `dramarina.com.br` não entra em `drpauloreis.com.br`. A
mesma conta pode existir nos dois, com papéis diferentes em cada prática.

## No computador

`http://dramarina.localhost:8930` e `http://drpauloreis.localhost:8930`: o navegador manda `*.localhost` para a própria
máquina, sem configurar nada.

## Na demonstração pelo ngrok

O ngrok gratuito dá um endereço só, e ele cai na plataforma. O botão "Abrir o site" guarda num cookie (`pc_site`) qual
consultório visitar, e a página se comporta como se fosse o domínio dele. Fora da demonstração esse cookie é ignorado.

## Em produção (self-hosted, como o CardLine)

O servidor fica atrás de um túnel do Cloudflare (`cloudflared`), sem porta aberta em casa. Recomendação: **um túnel só
do Puericorbs**, separado do túnel do CardLine, para que uma regra de um nunca derrube o outro.

### O caminho recomendado: hostnames personalizados (Cloudflare for SaaS)

1. Ter o domínio da plataforma no Cloudflare (por exemplo, `puericorbs.com.br`) e, no túnel do Puericorbs, um hostname
   de origem: `clientes.puericorbs.com.br` → `http://localhost:8930`. A última regra do `ingress` (a que pega qualquer
   endereço) também vai para `http://localhost:8930`, porque os pedidos chegam com o domínio do pediatra no `Host`.
2. Ligar o Cloudflare for SaaS na zona e cadastrar `clientes.puericorbs.com.br` como *fallback origin*.
3. Para cada pediatra:
   - no registrador do domínio dele, um CNAME de `dramarina.com.br` (e de `www`) para `clientes.puericorbs.com.br`;
   - no Cloudflare, o *custom hostname* `dramarina.com.br`; o certificado sai sozinho depois da validação (HTTP ou TXT);
   - no servidor: `uv run puericorbs domain dramarina.com.br dramarina` (e o `www` também).
4. O pediatra não precisa levar o DNS inteiro para o Cloudflare. Os primeiros hostnames personalizados são gratuitos:
   conferir o limite atual antes de vender.

### A alternativa: uma zona por domínio

Se o pediatra puser o domínio inteiro no Cloudflare, na conta da plataforma, basta rotear o hostname no túnel
(`cloudflared tunnel route dns <túnel> dramarina.com.br`) e cadastrar o domínio aqui. Dá mais trabalho por pediatra e
mexe no DNS dele inteiro (e-mail incluído).

### Quem ainda não tem domínio

Com `base_domains = ["puericorbs.com.br"]` no `data/config.toml` e um curinga `*.puericorbs.com.br` no túnel,
`dramarina.puericorbs.com.br` funciona sem cadastro nenhum.

## Antes de ligar em produção

- `demo = false` no `data/config.toml` (sem isso, qualquer um entra como qualquer conta pelos botões da demonstração).
- `platform_hosts` com o endereço da plataforma (por exemplo, `["puericorbs.com.br", "localhost"]`).
- As senhas reais de cada pediatra e da recepção; as contas `@demo.test` apagadas.

## Conferir

- `curl -sI https://dramarina.com.br/healthz` responde 200.
- `curl -s https://dramarina.com.br/api/site` traz o nome do consultório certo em `practice.name`.

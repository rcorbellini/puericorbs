# O domínio de cada pediatra

> 28/10/2026. Pedido do dono: cada pediatra com o próprio domínio, todos apontando para este projeto. O endereço
> decide de qual consultório é o site. O primeiro é o karitanaves.com.br, da primeira pediatra.

## Como o servidor decide

O pedido chega com o endereço (o cabeçalho `Host`). A ordem está em `puericorbs/tenancy.py`:

1. **O domínio cadastrado** na tabela `domains` abre a prática dele (`dramarina.com.br` → Dra. Marina).
2. **O subdomínio** `<slug>.<base>` de uma das `base_domains` abre a prática do slug. Serve para quem ainda não tem
   domínio (`dramarina.puericorbs.com.br`, quando houver um domínio da plataforma) e para testar no computador
   (`dramarina.localhost`).
3. **Os `platform_hosts`** abrem a plataforma: a lista de consultórios e a administração.
4. **O resto:** na demonstração, a plataforma; em produção (`demo = false`), "domínio não configurado".

O `www.` de um domínio cadastrado volta para o domínio sem ele (301, no `server.py`): o `www` só precisa do DNS.

A sessão vale por domínio (o cookie é do endereço): entrar em `dramarina.com.br` não entra em `drpauloreis.com.br`. A
mesma conta pode existir nos dois, com papéis diferentes em cada prática.

## Duas instâncias: a produção e a demonstração

| | Produção | Demonstração |
|---|---|---|
| Para quê | os consultórios de verdade | validar e mostrar (tudo fictício) |
| Serviço (usuário) | `puericorbs-producao` | `puericorbs-demo` |
| Porta | 8931 | 8930 |
| Dados | `~/.local/share/puericorbs` (fora do projeto) | `~/puericorbs/data` |
| `demo` | `false` (no `config.toml` da pasta) | `true` |
| Chega da internet | pelo túnel `puericorbs` (os domínios) | não (só no computador, ou por um túnel de teste) |

Por que separadas: a demonstração entra sem senha e o "reiniciar a demonstração" apaga a pasta inteira. Na mesma
pasta, isso alcançaria o consultório de verdade. A semente (`puericorbs seed`) se recusa a rodar com `demo = false`.

Os comandos da produção levam `--data ~/.local/share/puericorbs` (ou `PUERICORBS_DATA`):

```bash
cd ~/puericorbs
uv run puericorbs --data ~/.local/share/puericorbs practice karitanaves --name "Consultório pediátrico" --domain karitanaves.com.br
uv run puericorbs --data ~/.local/share/puericorbs invite karitanaves     # o link de primeiro acesso da pediatra
uv run puericorbs --data ~/.local/share/puericorbs domain outro.com.br karitanaves
```

## O túnel do Cloudflare

O servidor fica atrás de um túnel do Cloudflare, sem porta aberta em casa, como o CardLine. É **um túnel só do
Puericorbs** (`puericorbs`, serviço `puericorbs-tunel`), separado do túnel do CardLine: reiniciar um nunca derruba o
outro. A configuração é `~/.cloudflared/puericorbs.yml` (modelo em `deploy/cloudflared-puericorbs.yml`), com uma regra
só: tudo o que chega por ele vai para a produção (8931), e o Puericorbs decide o consultório pelo domínio. Domínio novo
de pediatra não mexe no túnel.

Só um domínio da mesma conta do Cloudflare consegue apontar para o túnel: um domínio de fora não chega à produção.

## Pôr no ar o domínio de uma pediatra

O caminho em uso é **uma zona por domínio**: o domínio da pediatra entra na conta do Cloudflare da plataforma (foi o
que o dono fez com o karitanaves.com.br, servidores `konnor` e `susan`).

1. **A zona.** Adicionar o domínio no Cloudflare e trocar os servidores DNS no registro.br pelos que o Cloudflare
   indicar. Conferir: `dig +short NS dominio.com.br` mostra os dois servidores do Cloudflare.
2. **O certificado da zona.** O `cloudflared` cria registros só na zona do certificado com que fez o login (com o
   certificado do CardLine, `dominio.com.br` viraria `dominio.com.br.cardline.com.br`, dentro da zona do CardLine). Um
   login por zona, sem tocar no `cert.pem` que já existe:

   ```bash
   T=$(mktemp -d); HOME=$T cloudflared tunnel login && mv "$T/.cloudflared/cert.pem" ~/.cloudflared/cert-dominio.pem
   ```

   O comando mostra um link; quem tem a conta do Cloudflare abre, escolhe a zona e autoriza. O link espera uns 9
   minutos.
3. **O DNS.** Os dois nomes apontam para o túnel:

   ```bash
   cloudflared tunnel --origincert ~/.cloudflared/cert-dominio.pem route dns puericorbs dominio.com.br
   cloudflared tunnel --origincert ~/.cloudflared/cert-dominio.pem route dns puericorbs www.dominio.com.br
   ```

   Sem o certificado, à mão no painel do Cloudflare (DNS → Adicionar registro), duas vezes: tipo **CNAME**, nome `@`
   (e depois `www`), destino **`28af9767-af05-4b68-8962-b72660d23653.cfargotunnel.com`**, proxy **ligado** (nuvem
   laranja).
4. **O consultório.** `practice` (se ainda não existe) ou `domain` (se já existe), com `--data` da produção.
5. **O convite.** `invite SLUG` imprime o link de primeiro acesso. Ele vale 7 dias e uma vez só: mande direto para a
   pediatra. Abrir o link não gasta o convite; criar a conta, sim. Lá ela cria a senha, diz o nome que aparece no site e
   o CRM; o resto ela ajusta em **Consultório** e **Serviços**.
6. **Conferir.** `curl -sI https://dominio.com.br/healthz` responde 200, e `curl -s https://dominio.com.br/api/site`
   traz o consultório certo em `practice.name`.

### Para muitos pediatras: Cloudflare for SaaS

Quando houver um domínio da plataforma (depende do nome) e pediatras que não queiram levar o DNS para a conta da
plataforma: o pediatra cria só um CNAME de `dominio.com.br` para `clientes.<plataforma>`, e a plataforma cadastra o
*custom hostname* no Cloudflare (o certificado sai sozinho). O túnel e o Puericorbs não mudam. Os primeiros hostnames
personalizados são gratuitos: conferir o limite antes de vender.

### Quem ainda não tem domínio

Com um domínio da plataforma no Cloudflare, `base_domains = ["<plataforma>"]` no `config.toml` da produção e um curinga
`*.<plataforma>` no túnel, `slug.<plataforma>` funciona sem cadastro.

## Antes do primeiro paciente de verdade

O consultório da primeira pediatra está no ar desde 28/10/2026 (karitanaves.com.br e www, pelo túnel, com o
certificado da zona em `~/.cloudflared/cert-karitanaves.pem`), vazio. Antes de entrar dado de paciente:

- **Backup** da pasta `~/.local/share/puericorbs` criptografado e fora de casa, com uma restauração testada.
- **Disco** do computador criptografado; nobreak.
- **Entrada:** o link para a família criar a senha, limite de tentativas no login e segundo fator para quem vê
  prontuário (ainda não existem no código).
- **Termo de uso, política de privacidade e o contrato com a pediatra** (a plataforma é operadora dos dados dela),
  validados com um advogado.
- O Cloudflare termina o HTTPS na borda: ele é suboperador e entra na política.

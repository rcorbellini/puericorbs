# Decisões

> Cada decisão com o porquê. Mudou uma? Escreva a nova com a data e diga qual ela substitui.

## Tomadas

### 28/10/2026 — o começo

1. **O Pueri é um SaaS para o consultório pediátrico pequeno.** Pedido do dono: vários pediatras, em clínicas
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
11. **Dados no Brasil, em nuvem.** Dado de saúde de criança não roda no PC de casa.
12. **Código em inglês, produto em português.** Como no Loreforge e no CardLine; o mapa dos termos está em
    `glossario.md`.

## Em aberto

| Decisão | Opções | Recomendação |
|---|---|---|
| Nome do produto | "Pueri" (de trabalho) ou outro | decidir antes de registrar domínio e marca |
| Pilha | FastAPI + PostgreSQL + PWA sem build (como o CardLine); TypeScript (Next.js ou parecido) + PostgreSQL | a do CardLine: é o que já se domina, e o vidro está pronto para reaproveitar |
| Gateway de pagamento | Asaas, Pagar.me, Iugu, Mercado Pago, Stripe | Asaas (recorrência, PIX, boleto, split e NFS-e num lugar só); confirmar o PIX Automático e as taxas |
| Preço do Pueri | por pediatra/mês; taxa sobre o que passa no gateway; os dois | conversar com os pilotos antes |
| Prontuário sem papel | certificar o sistema (SBIS/CFM, NGS2); assinar cada registro com o certificado em nuvem do pediatra | assinar por registro no começo; certificar quando houver tração |
| Convênios | fora; dentro no M3 | fora até os pilotos pedirem |
| Destaque da identidade | verde-água (atual), azul, coral, lavanda | verde-água; o protótipo troca as quatro para comparar |
| Processo de especificação | spec-kit, como no Loreforge; só documentos | spec-kit a partir do M0 |
| Pilotos | — | um pediatra sozinho e uma clínica pequena |

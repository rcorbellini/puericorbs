# Planos de acompanhamento e as conversas entre a família e a pediatra

> 28/10/2026. Pesquisa pedida pelo dono: o que se recomenda para os planos de acompanhamento pediátrico e que
> interações entre a família e a pediatra valem a pena. As fontes estão no fim. Os pontos de lei não são parecer: vão
> para o advogado antes de vender o primeiro plano.

## O que achei, e o que não achei

Não achei consultoria brasileira que publique um modelo de plano pediátrico com o que ele inclui e quanto custa: o
material publicado é de marketing e não traz o modelo. Serve de referência o seguinte:

1. **O calendário da Sociedade Brasileira de Pediatria (SBP):** a base clínica de qualquer plano.
2. **O "direct primary care" pediátrico dos Estados Unidos.** A família paga uma mensalidade e tem a puericultura, a
   consulta por doença e o acesso por mensagem à própria pediatra.
3. **As assinaturas de telemedicina pediátrica no Brasil:** a referência de preço do "acesso online".
4. **O argumento dos pediatras particulares:** consulta com tempo, a mesma médica e um canal direto entre as consultas.
5. **As regras do CFM e a Lei dos Planos de Saúde:** o que o plano pode e não pode ser.

## 1. O calendário (a base do plano)

| Idade | Consultas (SBP) |
|---|---|
| Gestação | uma consulta pediátrica no terceiro trimestre |
| Nascimento | a primeira entre 7 e 10 dias de vida |
| 0 a 6 meses | mensal |
| 6 a 12 meses | a cada dois meses |
| 12 a 18 meses | a cada três meses |
| 18 meses a 5 anos | a cada seis meses |
| 5 a 18 anos | uma por ano |

- **Primeiro ano:** são cerca de dez consultas pela SBP (7 a 10 dias, de 1 a 6 meses, 8, 10 e 12 meses). O Ministério
  da Saúde pede pelo menos sete: 1ª semana, 1, 2, 4, 6, 9 e 12 meses.
- **O conteúdo de cada consulta:** peso e altura nas curvas da OMS, alimentação e suplementos (vitamina D e ferro),
  desenvolvimento, vacinas do PNI, sono, telas, contato com a natureza e prevenção de acidentes.
- **Triagem de autismo:** a SBP e a Academia Americana de Pediatria indicam o M-CHAT-R/F nas consultas de 18 e 24
  meses, com as 20 perguntas respondidas pelos pais.
- **No Puericorbs, hoje:** a linha do cuidado segue o mínimo do Ministério da Saúde (`protocols.py`). Um plano
  "Primeiro ano" com 12 puericulturas mostra só 7 consultas na tela da família, e ela pode achar que sobra cota.
  Proposta: a pediatra escolher o calendário (MS ou SBP), como `funcionalidades.md` já prevê em "protocolos editáveis".
- **O convênio já cobre a puericultura.** Ela está no rol da ANS desde 2014, então o plano particular compete com uma
  consulta que a família com convênio já tem. O valor do plano não pode ser "consulta mais barata". Tem de ser tempo, a
  mesma médica e acesso.

## 2. Como os planos são montados, lá fora e aqui

- **Direct primary care pediátrico (Estados Unidos):**
  - A mensalidade é por criança, de US$ 85 a 105, e o primeiro ano é a faixa mais cara.
  - Cobre a puericultura do calendário e as consultas por doença; umas sem limite, outras com um número por ano.
  - Inclui mensagem direto com a pediatra, às vezes a qualquer hora. Uma clínica vende só o acesso por mensagem, por
    US$ 20.
  - Fica de fora o que custa caro e não depende da pediatra: exames complexos, imagem, especialistas, pronto-socorro e
    internação.
- **Telemedicina pediátrica por assinatura (Brasil):**
  - **PedCare:** R$ 49,99 por mês no plano anual, com consulta online sem limite, uma criança e 12 meses de fidelidade.
  - **Consultei Online:** R$ 29,90 por mês, com clínico e pediatra, sem fidelidade.
  - O plano da pediatra não disputa preço com eles: oferece a mesma médica, o exame físico e a história da criança num
    lugar só.
- **O particular avulso:** consulta longa e "um canal direto para dúvidas entre as consultas". Um modelo comum é
  combinar o convênio, para o pronto-socorro e a internação, com a pediatra particular para a rotina.

## 3. O que recomendo para os planos

1. **Um plano por fase da vida, seguindo a SBP.** Os da demonstração já vão nessa linha:
   - **Gestante e bebê:** o pré-natal pediátrico e o primeiro ano.
   - **Primeiro ano:** 10 a 12 puericulturas, com entrada até os 3 meses.
   - **1 a 2 anos:** as consultas de 15, 18 e 24 meses, com o M-CHAT aos 18 e aos 24.
   - **2 a 6 anos:** duas consultas por ano.
2. **Cota, não "ilimitado".** Cada plano inclui um número de cada serviço, e o Puericorbs já funciona assim (plano com
   cota e desconto fora dela). Há duas razões:
   - **A conta fecha:** dá para calcular quanto custa cada criança.
   - **A lei:** a Lei 9.656/98 (art. 1º, I) define plano de saúde como a "prestação continuada de serviços ou cobertura
     de custos assistenciais a preço pré ou pós estabelecido", "com a finalidade de garantir, sem limite financeiro, a
     assistência à saúde". Um pacote com um número de consultas da própria pediatra fica longe disso. "Consulta por
     doença ilimitada" chega perto, porque passa a cobrir risco.

   Deixe o "ilimitado" fora até o advogado dizer o contrário.
3. **O canal de mensagens é um benefício do plano, com a regra escrita.** A regra diz o horário, o prazo de resposta
   (por exemplo, até 4 horas úteis), o que se resolve por mensagem, o que vira consulta e o aviso de urgência. Três
   referências sustentam isso:
   - **CFM, Parecer 14/2017:** o WhatsApp pode ser usado entre o médico e os pacientes, em caráter privado, para
     enviar dados e tirar dúvidas, com sigilo absoluto.
   - **CREMERS, Parecer 20/2024:** o médico não é obrigado a responder o WhatsApp, mesmo com a mensagem visualizada.
   - **CREMERS, Parecer 19/2024** (citado no 20/2024): a consulta por WhatsApp gera conduta e deve ser remunerada.

   No plano, quem paga essa orientação é a mensalidade. Cada resposta vai para o prontuário.
4. **A teleconsulta como benefício** (CFM, Resolução 2.314/2022), para o retorno e para a dúvida que precisa de
   conversa. O serviço "Teleconsulta" já existe no catálogo, desligado.
5. **A visita em casa na primeira semana:** já está no plano de exemplo e é o que a família de primeira viagem mais
   valoriza.
6. **O que fica fora, escrito no plano:** exames, vacinas, pronto-socorro, internação e especialistas. É a lição do
   modelo americano, e evita a briga na renovação.
7. **O termo de adesão** (já no M2 de `funcionalidades.md`) traz fidelidade, cancelamento, reajuste e pausa, pelo
   Código de Defesa do Consumidor.
8. **Divulgar o preço é permitido.** Pela Resolução CFM 2.336/2023, em vigor desde 11/03/2024, a peça precisa trazer o
   nome, o CRM e, se citar a especialidade, o RQE. A "página de venda do plano" (M3) pode vir antes.
9. **Correção no nosso documento.** `funcionalidades.md` dizia que o Código de Ética Médica veda o vínculo com cartões
   de desconto. Desde a Resolução CFM 2.226/2019, o art. 72 veda só o vínculo com empresas de planos de financiamento e
   de consórcios para procedimentos médicos. O CRM do Pará (Parecer 16/2025) entende que a adesão a cartão de desconto
   é lícita, dentro do Código. Já corrigi o texto.

## 4. Interações entre a família e a pediatra

O que já existe:
- **Marcar consulta:** pelo app.
- **Acompanhamento:** a linha do cuidado ("Próximo passo", "A fazer", "Feito"), as curvas, as vacinas e os marcos.
- **Arquivos:** a troca de arquivos, com a caixa de revisão.
- **Depois da consulta:** o resumo liberado pela pediatra.
- **Confirmação:** desde hoje, o pedido de confirmação pelo WhatsApp.

O que proponho, pela ordem da consulta:

| Quando | Ideia | O que resolve | Hoje | Tamanho |
|---|---|---|---|---|
| Antes | **Confirmar presença no app:** a família toca "Confirmo", e a recepção vê | fecha o ciclo do pedido pelo WhatsApp; menos trabalho para a recepção | não existe | pequeno |
| Antes | **Perguntas antes da consulta,** respondidas ao marcar ou na véspera; a pediatra abre a consulta com as respostas | consulta mais rápida e completa | a chave está em Serviços, mas **não faz nada** | médio |
| Antes | **Dúvidas para a próxima consulta:** a família anota quando lembra, e a lista vira a pauta da consulta | "esqueci de perguntar" | não existe | pequeno |
| Antes | **M-CHAT-R/F aos 18 e 24 meses,** respondido em casa, com o resultado na consulta | a triagem que a SBP indica, sem tomar tempo da consulta | não existe | médio (precisa da versão em português e conferir a licença de uso) |
| Depois | **Orientações da idade** junto do resumo: textos curtos da pediatra sobre sono seguro, introdução alimentar, febre, telas e acidentes (os temas da SBP) | a família leva para casa o que ouviu | a chave está em Serviços, mas **não faz nada** | médio |
| Depois | **Receita, atestado e declaração no app,** em PDF | a família não perde o papel; a escola recebe o arquivo | a chave da declaração existe, mas **não faz nada**; os documentos em PDF estão no "falta" do M1 | médio |
| Depois | **Pesquisa de satisfação:** uma nota de 0 a 10 e um campo | a pediatra sabe o que melhorar | a chave existe, mas **não faz nada** | pequeno |
| Entre | **Busca ativa pelo WhatsApp:** a recepção chama a família com a puericultura atrasada, com a mensagem pronta (o mesmo botão de hoje) | cuidado em dia e agenda cheia | o cartão existe, só com o telefone | pequeno |
| Entre | **Mensagens com a regra do plano:** por criança, com foto, horário e prazo, triagem (o administrativo vai para a recepção, o clínico para a pediatra) e registro no prontuário | é o que a família mais pede e o que justifica a mensalidade | M2 | grande |
| Entre | **Diário de febre:** a temperatura, o remédio e o horário, num gráfico que a pediatra vê | a dúvida que mais chega no fim de semana | "Depois" | médio |
| Entre | **Orientação no momento certo:** o conteúdo chega na idade em que serve | menos dúvida repetida | M2 | médio |
| Entre | **Lista de espera:** a vaga que abre vai para quem pediu | encaixe sem telefonema | M2 | médio |
| Renovação | **Resumo do ano do plano:** quantas consultas, vacinas e quanto cresceu, antes de renovar | a família vê o que pagou | não existe | pequeno |

## 5. Por onde eu começaria

1. **Busca ativa e vacina atrasada pelo WhatsApp,** com a mensagem pronta. É o mesmo padrão do pedido de confirmação:
   a recepção confere e envia.
2. **Confirmar presença no app:** fecha o ciclo do pedido de hoje.
3. **Fazer funcionar as quatro chaves de Serviços:** perguntas antes da consulta, orientações pela idade, declaração e
   pesquisa. Hoje a tela promete e nada acontece.
4. **Dúvidas para a próxima consulta.**
5. **Resumo do ano na renovação do plano.**

Depois vem o canal de mensagens com a regra do plano. É o maior trabalho, e pede o termo de adesão e o advogado.

## Fontes

- SBP, [Consulta de puericultura](https://www.sbp.com.br/pediatria-para-familias/cuidados-com-a-saude/consulta-de-puericultura/) (calendário e conteúdo da consulta).
- SBP, [Triagem precoce para autismo (M-CHAT-R/F)](https://www.sbp.com.br/fileadmin/user_upload/24331c-MO_Triagem_Perecoce_para_Autismo.pdf).
- SBP, [Consulta de puericultura no rol da ANS](https://smp.org.br/wp-content/uploads/arquivos/defesa-profissional/consulta-de-puericultura-agora-esta-no-rol-da-ans.pdf).
- Lei 9.656/1998, [art. 1º](https://www.planalto.gov.br/ccivil_03/leis/l9656.htm).
- CFM, [Resolução 2.226/2019](https://sistemas.cfm.org.br/normas/arquivos/resolucoes/BR/2019/2226_2019.pdf) (novo art. 72 do Código de Ética Médica); CRM-PA, [Parecer 16/2025](https://sistemas.cfm.org.br/normas/arquivos/pareceres/PA/2025/16_2025.pdf) (cartão de desconto).
- CFM, [Resolução 2.336/2023](https://sistemas.cfm.org.br/normas/arquivos/resolucoes/BR/2023/2336_2023.pdf) (publicidade médica) e [Resolução 2.314/2022](https://ses.sp.bvs.br/wp-content/uploads/2022/05/U_RS-CFM-2314_200422.pdf) (telemedicina).
- CFM, [Parecer 14/2017](https://sistemas.cfm.org.br/normas/arquivos/pareceres/BR/2017/14_2017.pdf) (WhatsApp); CREMERS, [Parecer 20/2024](https://cremers.org.br/wp-content/uploads/2024/11/PARECER-No-SEI-202024-Obrigatoriedade-de-respostas-medicas-atraves-da-ferramenta-WhatsApp.pdf) (cita o 19/2024).
- Direct primary care pediátrico: [Free Market Healthcare, como funciona](https://freemarkethealthcareblog.com/pediatric-direct-primary-care/), [Peach Blossom Pediatrics, perguntas](https://www.peachblossompediatrics.com/faqs), [KevinMD](https://kevinmd.com/2026/06/why-pediatric-direct-primary-care-belongs-at-the-door.html).
- Telemedicina por assinatura: [PedCare](https://pedcare.com.br/plans-and-products), [Consultei Online](https://consultei.online/).
- Particular: [Dra. Jéssica Dantas, pediatra particular ou convênio](https://drajessicadantas.com/pediatra-particular-ou-convenio-o-que-faz-sentido-para-o-seu-filho/).

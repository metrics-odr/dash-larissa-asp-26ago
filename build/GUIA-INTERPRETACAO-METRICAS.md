# GUIA — Interpretação de Métricas de Funil High Ticket

> Referência **durável** para quem redige os Insights de Tráfego (a Routine do
> Claude, ou qualquer pessoa preenchendo `build/relatorios.json` manualmente).
> Como cada execução automática é uma sessão nova, sem memória da conversa que
> originou este guia, **este arquivo precisa ser lido por inteiro antes de
> redigir** — é aqui que moram as regras de diagnóstico, não só no
> `GUIA-RELATORIOS.md` (que define o formato/estrutura do texto).

A forma mais útil de interpretar um funil de High Ticket é tratar cada
métrica como um **diagnóstico probabilístico**, não uma regra absoluta. Uma
métrica ruim raramente significa, sozinha, que aquele é o problema. Ela
precisa ser analisada junto com as métricas anteriores e posteriores do
funil.

## CTR (Click Through Rate)

**O que mede:** percentual de pessoas que visualizaram o anúncio e clicaram
nele. **Funil:** Impressões → Cliques. **Objetivo:** avaliar a capacidade do
anúncio de gerar interesse suficiente para levar o usuário até a página ou
formulário.

**Quando é considerado baixo:** depende da plataforma, do público e da
oferta, mas normalmente um CTR abaixo do histórico da conta ou do benchmark
do nicho indica dificuldade do anúncio em gerar interesse.

**Possíveis gargalos:** criativo pouco chamativo; gancho fraco; copy
genérica; promessa pouco clara; público inadequado; fadiga criativa;
frequência elevada; comunicação desalinhada com a dor do público.

**Ações recomendadas:** criar novos ganchos; testar novas headlines;
melhorar os primeiros segundos do vídeo; testar novas promessas; explorar
diferentes dores e desejos; renovar criativos saturados; revisar a
segmentação; testar anúncios com maior especificidade.

**Quando NÃO é necessariamente um problema:** um CTR baixo pode ser positivo
quando o anúncio é altamente qualificador, a copy afasta pessoas sem perfil,
a Tx-MQL permanece alta, o CPMQL continua saudável, o CAC permanece dentro
da meta, ou a taxa de vendas dos leads é superior à média. Exemplo: CTR
baixo + Tx-MQL alta + CAC baixo + ROAS saudável → o anúncio traz menos
cliques, mas atrai pessoas mais qualificadas.

**Deve ser analisado junto com:** ConvLP, Tx-MQL, CPMQL, CAC, ROAS. Nunca
analisar isoladamente.

## Connect Rate

**O que mede:** percentual de pessoas que clicaram no anúncio e realmente
chegaram à página. **Fórmula:** Visitas na página ÷ Cliques. **Objetivo:**
avaliar a eficiência da conexão entre o anúncio e a página de captação
(perdas entre o clique e o carregamento).

**Possíveis gargalos:** página lenta; hospedagem ruim; imagens pesadas;
excesso de scripts; redirecionamentos; problemas de DNS; erros de
carregamento; experiência mobile ruim; pixel/ferramenta de análise mal
configurados.

**Ações recomendadas:** melhorar velocidade da página; otimizar imagens;
reduzir scripts; usar CDN; remover redirecionamentos desnecessários;
verificar erros 404/500; testar em diferentes dispositivos; revisar a
instalação dos eventos de visita.

**Quando NÃO é necessariamente um problema:** Connect Rate baixo nem sempre
é problema técnico — pode ser falha de mensuração (pixel bloqueado, AdBlock,
restrições do iOS, consentimento de cookies, navegadores bloqueando
rastreamento, eventos mal configurados, diferenças entre Meta/GA4/servidor).
Nesses casos cliques permanecem altos, leads e MQLs permanecem normais, CAC
e ROAS continuam saudáveis — só o número de visitas parece menor.

**Deve ser analisado junto com:** ConvLP, CPL, CPMQL, CAC, ROAS. Se as
métricas posteriores permanecem saudáveis, provavelmente não há gargalo
operacional relevante.

## ConvLP (Conversão da Landing Page)

**O que mede:** percentual das visitas que viram lead. **Fórmula:** Leads ÷
Visitas na página. **Objetivo:** avaliar se a página/oferta convence o
visitante a preencher o formulário.

**Possíveis gargalos:** promessa pouco clara; página desalinhada com o
anúncio; formulário extenso; excesso de campos obrigatórios; falta de prova
social; design pouco confiável; CTA fraco; página lenta; oferta pouco
atrativa; problemas no formulário; experiência mobile ruim.

**Ações recomendadas:** melhorar headline; reforçar a promessa; alinhar
anúncio e página; reduzir campos desnecessários; melhorar o CTA; inserir
provas sociais; explicar melhor o benefício do cadastro; testar formulário
em etapas; melhorar a versão mobile; verificar erros de envio/integração.

**Quando NÃO é necessariamente um problema:** ConvLP baixa pode ser aceitável
quando o formulário é intencionalmente qualificador (perguntas que eliminam
leads sem perfil), a Tx-MQL é alta, o CPMQL permanece saudável, a taxa de
vendas é superior, ou o CAC continua dentro da meta. Formulário curto = mais
leads, porém possivelmente menos MQLs; formulário mais completo = menos
leads, porém com maior qualidade.

**Deve ser analisado junto com:** CPL, Tx-MQL, CPMQL, Agendamentos, CAC.

## CPL (Custo por Lead)

**O que mede:** quanto custa, em média, gerar um lead. **Fórmula:**
Investimento ÷ Leads. **Objetivo:** eficiência financeira da captação.

**Possíveis gargalos:** CPM elevado; CTR baixo; Connect Rate ruim; ConvLP
baixa; público saturado; criativos pouco eficientes; página pouco
persuasiva; formulário excessivamente complexo.

**Ações recomendadas:** nunca analisar isoladamente — identificar qual etapa
anterior está aumentando o custo (CPM alto → público/posicionamentos; CTR
baixo → criativos/comunicação; Connect Rate baixo → carregamento/mensuração;
ConvLP baixa → página/formulário).

**Quando NÃO é necessariamente um problema:** CPL alto pode ser saudável
quando a Tx-MQL é alta, os leads têm maior poder de compra, a taxa de
agendamento é alta, a taxa de vendas é superior, o CAC permanece dentro da
meta, ou o ticket médio/LTV é elevado. Um lead mais caro pode gerar mais
vendas do que vários leads baratos e desqualificados.

**Deve ser analisado junto com:** Tx-MQL, CPMQL, Taxa de Agendamento, CAC,
ROAS.

## Tx MQL (Taxa de MQL)

**O que mede:** percentual dos leads que atendem aos critérios mínimos de
qualificação comercial (faixa de faturamento, poder de investimento, momento
de compra, perfil, problema compatível, autoridade de decisão). **Fórmula:**
MQLs ÷ Leads. **Objetivo:** qualidade dos leads gerados.

**Possíveis gargalos:** anúncios atraindo curiosos; promessa muito ampla;
comunicação pouco qualificada; segmentação inadequada; formulário com poucas
perguntas; critérios de qualificação mal definidos; oferta desalinhada;
conteúdo apelativo/pouco específico; leads sem capacidade financeira.

**Ações recomendadas:** copy mais específica; informar para quem a oferta é
(e não é) indicada; inserir perguntas qualificadoras; revisar critérios de
MQL; testar novos públicos; analisar quais campanhas geram mais MQLs;
otimizar com base em MQL (não só lead); enviar eventos de MQL para a
plataforma de anúncios; revisar a promessa dos criativos.

**Quando NÃO é necessariamente um problema:** Tx-MQL baixa pode ocorrer
quando a campanha está em expansão, o público ficou mais amplo, o volume de
leads aumentou muito, o CPL caiu, ou os critérios de qualificação ficaram
mais rígidos. Também pode ser problema de classificação (leads não
atualizados no CRM, comercial não avaliou todos, dados incompletos, critérios
mudaram no período, atraso de atualização). Tx-MQL menor é aceitável se o
volume total de MQLs aumentar e o CPMQL continuar saudável.

**Deve ser analisado junto com:** CPL, CPMQL, Taxa de Agendamento, CAC, ROAS.

## CPMQL (Custo por MQL)

**O que mede:** quanto custa, em média, gerar um MQL. **Fórmula:**
Investimento ÷ MQLs. **Objetivo:** custo real de atrair uma oportunidade com
perfil comercial — em High Ticket, normalmente mais relevante que o CPL.

**Possíveis gargalos:** CPL alto; Tx-MQL baixa; criativos atraindo gente sem
perfil; formulário pouco qualificador; segmentação inadequada; critérios de
MQL excessivamente rígidos; falta de alinhamento marketing/vendas; problemas
de atualização no CRM.

**Ações recomendadas:** identificar se o problema é custo do lead ou
qualificação; comparar CPMQL entre anúncios/públicos; ajustar comunicação
para o perfil ideal; melhorar perguntas de qualificação; padronizar
critérios de MQL; integrar CRM e plataforma de anúncios; otimizar campanhas
para eventos mais próximos do MQL.

**Quando NÃO é necessariamente um problema:** CPMQL alto pode ser saudável
quando a taxa de agendamento é elevada, os MQLs têm alta taxa de
comparecimento, a taxa de vendas é superior, o ticket médio é elevado, o CAC
permanece dentro da meta, ou o LTV compensa o custo. Um MQL caro que compra
pode valer mais que vários MQLs baratos que não avançam.

**Deve ser analisado junto com:** Taxa de Agendamento, Custo por
Agendamento, Taxa de Comparecimento, CAC, ROAS.

## Taxa de Agendamento

**O que mede:** percentual dos MQLs que agendam reunião/call comercial.
**Fórmula:** Agendamentos ÷ MQLs. **Objetivo:** capacidade de qualificação +
contato de transformar MQLs em oportunidades comerciais.

**Possíveis gargalos:** demora no primeiro contato; leads não atendidos;
poucas tentativas; abordagem comercial ruim; falta de cadência de
follow-up; dificuldade para encontrar horários; processo de agendamento
complicado; calendário com pouca disponibilidade; falta de percepção de
valor da reunião; MQLs sem intenção real de compra; dados de contato
incorretos.

**Ações recomendadas:** reduzir tempo de primeiro contato; criar cadência de
follow-up (WhatsApp/ligação/e-mail); simplificar agendamento; mais horários
disponíveis; melhorar script de abordagem; explicar o benefício da reunião;
enviar automaticamente o link do calendário; lembretes para quem não
agendou; analisar taxa por vendedor/origem.

**Quando NÃO é necessariamente um problema:** critérios de MQL muito amplos;
lead ainda precisa ser nutrido; ciclo de decisão mais longo; produto exige
maior confiança; atrasos no CRM; parte dos MQLs ainda não recebeu todas as
tentativas de contato. Também pode haver poucos agendamentos, porém muito
qualificados, com alta conversão em venda.

**Deve ser analisado junto com:** tempo de primeiro contato, taxa de
contato, Taxa de Comparecimento, Taxa de Vendas, CAC.

## Custo por Agendamento

**O que mede:** quanto custa, em média, gerar um agendamento. **Fórmula:**
Investimento ÷ Agendamentos. **Objetivo:** eficiência conjunta de
marketing + qualificação + processo de contato.

**Possíveis gargalos:** CPL alto; Tx-MQL baixa; CPMQL alto; baixa taxa de
contato; baixa taxa de agendamento; demora do comercial; pouca
disponibilidade no calendário; falta de follow-up.

**Ações recomendadas:** não atacar o custo por agendamento diretamente —
identificar em qual etapa está a perda (captação, qualificação, contato,
agendamento) e corrigir a de maior impacto.

**Quando NÃO é necessariamente um problema:** custo por agendamento alto
pode ser saudável quando a Taxa de Comparecimento é alta, a Taxa de Vendas é
alta, o ticket médio é elevado, o CAC permanece dentro da meta, ou os
clientes têm alto LTV. Avaliar pela qualidade/resultado dos agendamentos, não
só pela quantidade.

**Deve ser analisado junto com:** CPMQL, Taxa de Agendamento, Taxa de
Comparecimento, Custo por Comparecimento, CAC.

## Taxa de Comparecimento (Show Rate)

**O que mede:** percentual dos agendados que comparecem à reunião. **Fórmula:**
Comparecimentos ÷ Agendamentos. **Objetivo:** capacidade da operação de
transformar agendamentos em reuniões realmente realizadas.

**Possíveis gargalos:** falta de lembretes; intervalo muito longo entre
agendamento e reunião; lead sem percepção de valor; agendamento sem
compromisso real; horários inadequados; ausência de confirmação; processo
comercial pouco humanizado; lead esqueceu; falta de contato antes da call;
agendamentos pouco qualificados.

**Ações recomendadas:** confirmação imediata; lembretes automáticos
(24h e 1h antes); reduzir intervalo entre cadastro e reunião; solicitar
confirmação ativa; explicar o que será entregue na reunião; prova social ou
conteúdo preparatório; facilitar reagendamento; contato humano antes da
call; analisar comparecimento por vendedor/origem.

**Quando NÃO é necessariamente um problema:** volume de agendamentos
aumentou rapidamente; calendário com horários muito distantes; campanha
atingiu público mais frio; agendamentos recentes que ainda não aconteceram;
sistema contando reagendamentos como novos; CRM não atualizado
corretamente. Também pode haver menor taxa acompanhada de maior volume
absoluto de reuniões e vendas.

**Deve ser analisado junto com:** Taxa de Agendamento, Custo por
Agendamento, Taxa de Vendas, Custo por Comparecimento, CAC.

## Custo por Comparecimento

**O que mede:** quanto custa, em média, gerar uma reunião efetivamente
realizada. **Fórmula:** Investimento ÷ Comparecimentos. **Objetivo:** quanto
a operação precisa investir para colocar uma oportunidade real diante do
comercial.

**Possíveis gargalos:** CPMQL alto; baixa taxa de agendamento; custo por
agendamento elevado; Show Rate baixo; falta de confirmação; agendamentos
pouco qualificados; intervalo excessivo até a reunião.

**Ações recomendadas:** identificar se a perda ocorre antes ou depois do
agendamento; melhorar velocidade de contato; ajustar processo de
agendamento; lembretes; confirmar reuniões; diminuir tempo entre agendamento
e call; comparar entre campanhas; analisar qualidade das reuniões.

**Quando NÃO é necessariamente um problema:** custo alto pode ser saudável
quando as reuniões têm alta qualidade, a taxa de vendas é elevada, o ticket
médio é alto, o CAC permanece sustentável, há elevado LTV, ou o processo
comercial tem boa margem.

**Deve ser analisado junto com:** Taxa de Comparecimento, Taxa de Vendas,
CAC, Ticket Médio, ROAS.

## Taxa de Vendas (Close Rate)

**O que mede:** percentual das reuniões realizadas que viram venda.
**Fórmula:** Vendas ÷ Comparecimentos. **Objetivo:** capacidade do comercial
de converter oportunidades qualificadas em clientes.

**Possíveis gargalos:** script comercial fraco; diagnóstico superficial;
oferta mal apresentada; falta de confiança; objeções não trabalhadas;
vendedores despreparados; falta de follow-up; MQLs pouco qualificados;
promessa do anúncio desalinhada com a oferta; preço incompatível; condições
de pagamento ruins; reuniões com quem não decide.

**Ações recomendadas:** revisar gravações das calls; melhorar script
comercial; treinar diagnóstico/objeções; melhorar apresentação da oferta;
cadência de follow-up; analisar conversão por vendedor; separar perdas por
motivo; revisar critérios de MQL; identificar campanhas que geram mais
vendas; melhorar condições de pagamento; alinhar anúncio e oferta comercial.

**Quando NÃO é necessariamente um problema:** ciclo comercial longo;
propostas ainda em negociação; período com reuniões recentes; venda
acontece dias após a call; ticket aumentou; oferta ficou mais premium;
expansão de público; volume de reuniões cresceu muito. Também pode haver
subatribuição por vendas não atualizadas no CRM — não comparar reuniões
recentes com vendas do mesmo período sem considerar a janela de conversão.

**Deve ser analisado junto com:** Tx-MQL, Taxa de Agendamento, Taxa de
Comparecimento, CAC, Ticket Médio, Ciclo de vendas.

## CAC (Custo de Aquisição)

**O que mede:** quanto custa adquirir um novo cliente. **Fórmula:**
Investimento ÷ Vendas. **Objetivo:** eficiência financeira de toda a
operação de aquisição.

**Possíveis gargalos:** CAC alto normalmente é *consequência* de problemas
anteriores — CPL alto, Tx-MQL baixa, CPMQL alto, baixa taxa de agendamento,
Show Rate baixo, taxa de vendas baixa, público saturado, escala excessiva,
falhas no processo comercial.

**Ações recomendadas:** nunca atacar o CAC diretamente — identificar em qual
etapa do funil está a maior perda (Impressão→Clique, Clique→Visita,
Visita→Lead, Lead→MQL, MQL→Agendamento, Agendamento→Comparecimento,
Comparecimento→Venda) e corrigir a etapa responsável.

**Quando NÃO é necessariamente um problema:** CAC alto pode ser saudável
quando o ticket médio aumentou, a margem permanece positiva, o LTV é
elevado, há receita recorrente, o ROAS permanece saudável, os clientes têm
maior retenção, ou a operação está em expansão (natural que o CAC suba ao
buscar públicos mais amplos).

**Deve ser analisado junto com:** ROAS, Ticket Médio, LTV, Taxa de Vendas,
Margem.

## ROAS

**O que mede:** retorno sobre o investimento em mídia. **Fórmula:** Receita
÷ Investimento. **Objetivo:** retorno financeiro gerado pelas campanhas.

**Possíveis gargalos:** ROAS baixo normalmente é consequência de CAC alto,
ticket médio baixo, baixa Tx-MQL, poucos agendamentos, Show Rate baixo,
taxa de vendas baixa, ciclo comercial longo, vendas não atualizadas, ou
escala excessiva.

**Ações recomendadas:** encontrar qual etapa anterior reduziu a eficiência —
nunca otimizar diretamente para ROAS sem entender o resto do funil. Também
verificar: todas as vendas foram registradas? a receita está corretamente
atribuída? há propostas ainda em negociação? o período considera o ciclo
comercial completo? os pagamentos foram aprovados?

**Quando NÃO é necessariamente um problema:** ROAS baixo pode ser temporário
quando o ciclo de vendas é longo, há propostas abertas, a campanha começou
recentemente, o investimento ocorre antes do fechamento, o objetivo é ganhar
escala, há receita recorrente, o LTV é elevado, ou existem renovações/
upsells/indicações. Em High Ticket, comparar investimento e receita do
*mesmo* período pode gerar leitura incorreta — leads de um mês podem virar
venda só no mês seguinte.

**Deve ser analisado junto com:** CAC, Ticket Médio, LTV, Ciclo de vendas,
Receita futura/pipeline.

## Ticket Médio

**O que mede:** receita média por venda. **Fórmula:** Receita ÷ Vendas.
**Objetivo:** quanto cada novo cliente gera de receita na aquisição.

**Possíveis gargalos:** descontos excessivos; vendas concentradas nos planos
mais baratos; pouca oferta premium; condições comerciais mal estruturadas;
downsell excessivo; falta de upsell; vendedores oferecendo desconto cedo
demais; mix de produtos com valores diferentes.

**Ações recomendadas:** criar planos premium; melhorar empilhamento de
valor; reduzir descontos desnecessários; revisar condições de pagamento;
criar upsells; melhorar ancoragem de preço; treinar o comercial; analisar
ticket por vendedor/campanha/público.

**Quando NÃO é necessariamente um problema:** ticket baixo pode ser
proposital quando a oferta de entrada facilita a aquisição, há receita
recorrente, o LTV é elevado, há upsells posteriores, a taxa de vendas
aumenta, o CAC diminui, ou a empresa busca ganhar participação de mercado.

**Deve ser analisado junto com:** CAC, ROAS, Taxa de Vendas, LTV, Margem.

## Visão geral do funil High Ticket

Ordem de leitura: Impressões → Cliques → Visitas → Leads → MQLs →
Agendamentos → Comparecimentos → Vendas.

Cada métrica é um diagnóstico probabilístico — uma métrica ruim não
significa automaticamente que aquela etapa é o verdadeiro problema.
Exemplos: CPL baixo + Tx-MQL baixa → leads baratos e desqualificados; CPMQL
alto + alta taxa de vendas → pode continuar saudável; Taxa de Agendamento
baixa → pode ser o comercial, não o tráfego; Show Rate baixo → falta de
lembrete; Taxa de Vendas baixa → pode ser reuniões recentes ainda em
negociação; CAC alto → pode ser sustentável se ticket/margem/LTV forem
altos; ROAS baixo no período atual → pode ser só efeito do ciclo de vendas
mais longo.

A análise deve localizar a **primeira quebra relevante do funil** e
verificar como ela afeta todas as etapas posteriores.

## Heurísticas obrigatórias de interpretação

- Nunca concluir que uma métrica isolada representa o gargalo do funil —
  sempre interpretar junto com a etapa anterior e a posterior.
- Connect Rate baixo + ConvLP alta → investigar **primeiro** problema de
  mensuração (pixel, CAPI, consentimento, bloqueadores, atribuição) antes de
  assumir problema de carregamento.
- CPL alto → normalmente é efeito, não causa. Identificar a etapa anterior
  que perdeu eficiência antes de propor ações.
- ROAS baixo → costuma ser combinação de fatores (CAC, Ticket Médio,
  conversões) — não tratar como ponto de otimização isolado.
- Mudança de público/escala → quedas moderadas em CTR/VisCHK/ConvCHK podem
  ser esperadas ao expandir audiências; comparar a perda com o aumento de
  volume/receita antes de classificar como gargalo.
- Sempre considerar o **histórico da própria conta**: uma métrica abaixo de
  benchmark geral pode ainda ser um bom resultado se estiver acima da média
  histórica da operação. Priorizar **tendência ao longo do tempo** sobre
  valor absoluto isolado.

## Unidade de análise do anúncio: campanha + conjunto + anúncio

O mesmo anúncio (mesmo nome) pode rodar em campanhas/conjuntos diferentes com
resultados diferentes. A unidade operacional obrigatória é sempre a tripla
**campanha + conjunto + anúncio** (`por_anuncio` em `relatorios_dados.json` já
vem quebrado nessa granularidade). Nunca dê uma única decisão global a um
anúncio sem checar `criativos_consolidado` — se `n_estruturas > 1`, faça as
duas análises: consolidada (resultado total do criativo) e por ocorrência
(cada estrutura recebe decisão própria). "Cortar esta ocorrência nesta
estrutura" é uma decisão diferente de "cortar o criativo em todas as
estruturas" — nunca generalize corte de 1 estrutura fraca para o criativo
inteiro que é vencedor nas demais.

## Nível correto de orçamento (ABO x CBO)

Em **ABO** (orçamento por conjunto), o ajuste de verba é feito no **conjunto
de anúncios**. Em **CBO** (orçamento por campanha), o ajuste é na
**campanha**. No **anúncio**, as ações possíveis são ativar, pausar,
duplicar, substituir ou replicar — nunca "aumentar a verba do anúncio" como
se o orçamento estivesse configurado nele. A fonte de dados atual (planilha
de mídia paga) **não informa o tipo de orçamento** por estrutura — nunca
assuma ABO ou CBO; quando não for possível confirmar, escreva a recomendação
de forma neutra ("ajustar o orçamento no nível do conjunto/campanha,
conforme a configuração real — confirmar no Gerenciador de Anúncios antes de
executar").

## Como citar "padrão de mercado" no texto

Os limiares/benchmarks deste guia (ex.: Connect Rate crítico abaixo de 60%)
são **referências gerais do nicho High Ticket**, não dados medidos deste
cliente — nenhuma busca em tempo real acontece na geração automática. Sempre
que o texto usar um desses benchmarks, deixe explícito que é "referência
geral de mercado" (e não um número exclusivo desta conta), e prefira comparar
primeiro com o **histórico da própria conta** quando ele já existir.

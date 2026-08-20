# CLAUDE.md — Contexto do projeto (TEMPLATE High Ticket)

> Este arquivo é lido automaticamente pelo Claude Code ao abrir o repositório.
> Ele carrega TODO o contexto necessário para continuar o trabalho sem depender
> de mensagens anteriores. Mantenha-o atualizado.
>
> **Este é um TEMPLATE limpo.** Todos os valores específicos do cliente estão
> marcados como `<<PREENCHER: descrição>>`. Siga o CHECKLIST abaixo para
> configurar um cliente novo.

---

## ✅ CHECKLIST DE NOVO CLIENTE (fazer em ordem)

Preencha cada `<<PREENCHER: …>>` do repositório. Ordem sugerida:

1. **`build/build.py` — constantes do topo:**
   - `SPREADSHEET_ID` — ID da planilha central do Google Sheets do cliente.
   - `GID_CONVERSAS` — gid da aba de Conversas (fonte principal de leads).
   - `GID_LEADS` — gid da aba de Leads legado (popup/form; só contada).
   - `GID_META` — gid da aba Meta Ads.
   - `GID_SALES` — gid da aba de Compradores (New Subscriptions).
   - `CLIENT_NAME`, `MAIN_PRODUCT` — nome do cliente e da oferta principal.
   - `MAIN_PRODUCT_PREFIX` — prefixo comum às campanhas do cliente.
   - `TAX_FACTOR` — fator de imposto/taxa da mídia (1.0 = sem imposto).
2. **`build/build.py` — critério de MQL:** ajuste `is_medico()` e os aliases da
   coluna de qualificação em `process()` (`"medico": [...]` + índice de fallback)
   ao critério e ao cabeçalho da aba Conversas do cliente.
3. **`build/app.js`:** revisar os rótulos fixos de UI que citam o critério de MQL
   ("MQLs (...)") e o agrupamento de "faixa"/especialidade — o critério de
   `build.py` não propaga sozinho para esses textos.
4. **`build/template.html`:** preencher `<title>` e o logo (`logo-main`/`logo-sub`)
   com o nome/slogan do cliente. (Opcional: trocar o favicon base64.)
5. **`build/identidade-visual.css`:** ajustar cores se o cliente tiver identidade
   própria (opcional — o default funciona).
6. **`README.md` / `SETUP-CRON.md` / este `CLAUDE.md` / `AGENTS.md`:** owner/repo
   do GitHub, URL do GitHub Pages, nome do cliente, planilha/gids.
7. **`build/GUIA-RELATORIOS.md`:** preencher o "Contexto do funil" (cliente,
   oferta, critério de MQL).
8. **GitHub Pages + Actions:** confirmar que `build/` + `.github/workflows/deploy.yml`
   estão na `main` (ativa `workflow_dispatch`); rodar o workflow uma vez.
9. **cron-job.org:** seguir `SETUP-CRON.md` — token fine-grained novo (Actions:
   read/write, só neste repo), nunca reaproveitar um token exposto em chat.
10. **Insights de Tráfego (opcional):** `build/relatorios.json` e
    `build/relatorios_dados.json` começam vazios (`{}`). Para ativar os Insights:
    - deixar a Routine do Actions `briefing.yml` rodar (gera `relatorios_dados.json`
      com os números), e
    - criar a **Routine do Claude** (`create_trigger` apontando para este repo)
      que lê os números + os 2 guias e escreve `relatorios.json` na `main`
      (ver "Briefing automático" abaixo). **Não vem pronta** — precisa ser
      recriada por cliente.
11. **Testar local** com CSVs de amostra antes de publicar (3 páginas, tema
    claro/escuro, multi-seleção).

> **Fora do escopo deste template:** não há Cloudflare Worker nem chamada paga à
> API da Anthropic no pipeline. A automação de Insights é feita por Routine
> agendada do Claude Code (item 10). Se o cliente precisar de outra camada, é
> desenvolvimento novo.

---

## O que é

Dashboard de **Captura de Leads** — um app de BI estático (HTML/CSS/JS
puro + Chart.js via CDN) publicado no **GitHub Pages**, que cruza a lista de
**Leads** com o gerenciador de mídia paga e se atualiza sozinho a cada ~30 min
(build 100% na nuvem via GitHub Actions, disparado externamente pelo cron-job.org).

- **URL pública:** `https://<<PREENCHER: owner do GitHub>>.github.io/<<PREENCHER: nome do repositório>>/`
- **Somente leitura** das planilhas. Nunca escrever de volta.

## Fontes de dados (Google Sheets)

Spreadsheet ID: `<<PREENCHER: SPREADSHEET_ID>>` ("<<PREENCHER: nome da planilha central>>").

| Aba | gid | Colunas usadas |
|-----|-----|----------------|
| **Conversas** (fonte principal — webhook de mensageria/WhatsApp) | `<<PREENCHER: GID_CONVERSAS>>` | `Data` · `Mensagem` · `Nome` · `Telefone` · coluna de MQL · `Campanha` · `Conjunto` · `Anúncio` · `Especialidades` |
| **Leads** (legado — popup/form antigo, só contada) | `<<PREENCHER: GID_LEADS>>` | `Data` · `Nome` · `Email` · `Telefone` · coluna de MQL · `Especialidade` · `utm_*` · `MQL` · `Compra Detectada`/`Faturamento Detectado`/`Data Compra` |
| **Meta Ads** | `<<PREENCHER: GID_META>>` | `Day` · `Ad ID` · `Campaign Name` · `Ad Set Name` · `Ad Name` · `Amount Spent` · `Impressions` · `Link Clicks` · `Landing Page Views` · `Content Views` · `Adds to Cart` · `Subscriptions` · `Subscribe Conversion Value` |
| **New Subscriptions** (Compradores) | `<<PREENCHER: GID_SALES>>` | `Data` · `Nome` · `Email` · `Telefone` · `Produto` · `Oferta` · `Faturamento` · `Receita` · `Método de Pagamento` · `Campanha` · `Conjunto` · `Anúncio` · `UF` · `Cidade` · `Zip Code` · `Endereço` |

URL de export CSV: `https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<GID>`

### Regra de Lead Qualificado (MQL)
Coluna de qualificação (<<PREENCHER: nome da coluna de MQL, ex. "É médico?">>) == "Sim".
Lógica em `build.py` → `is_medico`. O gráfico "Leads por especialidade" (`app.js`,
`renderGeralCore`) colore verde/cinza pelo mesmo critério, usando a coluna
`Especialidades`/`Especialidade` como dimensão.

### Vendas & Faturamento (cruzamento com Compradores)
`build.py` → `build_sales_index()` lê a aba **New Subscriptions** e indexa por
**telefone** (normalizado, só dígitos) → lista de compras **não agregada**,
uma entrada por linha: `[{d, fat, receita}, ...]` (`d` = data real daquela
compra). Em `process()`, as linhas da **Conversas** são ordenadas pela **data
já parseada** (`parse_date`, não a string bruta) para achar a **1ª conversa**
(mais antiga de fato) de cada telefone; essa conversa define **apenas**
camp/adset/ad da venda (o anúncio que trouxe aquele contato) — nunca a data.
Cada compra vira um registro próprio em `DATA.sales[]`
(`{d, camp, adset, ad, vendas:1, fat, receita}`) com a **data real da compra**.
No navegador, `salesActive()` (`app.js`) filtra `sales[]` pela mesma data ativa
que `leadsActive()`/`metaActive()`, e os três arrays (`fL`/`fM`/`fS`) se
propagam juntos em `buildAgg`/`daily`/`totals`.

**TODA venda entra na dash** (regra geral: "todas as vendas entram na Visão
Geral; só as atribuídas ao Meta entram na aba de mídia paga"). O cruzamento
Compradores × Conversas usa `canon_phone()` — **chave canônica** = DDD +
últimos 8 dígitos, robusta a **DDI "55"** presente/ausente e ao **9º dígito**
do celular. Quando o telefone bate com uma conversa, a venda recebe
camp/adset/ad daquela conversa. Quando **não** bate, a venda **ainda conta nos
totais/Visão Geral**, porém como `(sem campanha)` / `src="org"` — some apenas da
quebra por campanha do Meta. `log_unmatched_sales()` loga no build quantas
vendas ficaram sem anúncio de origem. **Não** usa as colunas `Compra Detectada`
/ `Faturamento Detectado` já calculadas na planilha (decisão de projeto: cruzar
do zero, mais robusto a erro de fórmula).

### Imposto da mídia paga
`TAX_FACTOR` em `build.py` (`<<PREENCHER: fator, ex. 1.13806>>`). O toggle
"Imposto Meta" fica **ativo por padrão** (`STATE.tax=true` em `app.js`) e aplica
o fator em todo o gasto/derivados (CPL, CPMQL, CAC etc.); desativar o toggle
volta ao gasto sem imposto. Se o cliente não tiver imposto, use `TAX_FACTOR = 1.0`.

### Convenções de campanha (do cliente)
Todas as campanhas usam o prefixo `<<PREENCHER: MAIN_PRODUCT_PREFIX>>`
(`MAIN_PRODUCT_PREFIX`), sem filtrar por sub-funil — mantém TODAS as campanhas
no dashboard. Ajuste o prefixo e, se o cliente usar siglas de etapa
(ex. `<<PREENCHER: siglas de etapa, se houver>>`), documente-as aqui. A Conversas
já traz `Campanha`/`Conjunto`/`Anúncio` prontos (nomes idênticos ao
`Campaign Name`/`Ad Set Name`/`Ad Name` do Meta Ads) — `build.py` só copia esses
valores, sem precisar de UTM nessa aba.

## Arquitetura / arquivos

```
build/build.py            # lê os CSVs (read-only), emite REGISTROS BRUTOS (leads[]/meta[]/sales[]/ad_links); render() COSTURA os 4 arquivos abaixo
build/template.html       # esqueleto HTML. Placeholders __STYLES__, __APP_JS__, __DATA_JSON__, __BUILD_ID__, __GENERATED_BRT__
build/identidade-visual.css  # TODAS as cores (tema claro=padrão / escuro). Mexa AQUI p/ trocar só cor
build/estilos.css         # layout/componentes (sidebar, topbar, period-picker, funil, tabelas, gráficos, aba Relatório)
build/app.js              # lógica + renderização (KPIs, funil, tabelas, filtro cruzado, period-picker, heatmap, Relatório)
build/relatorios.json     # Insights de Tráfego por período (aba Relatório) — VERSIONADO; lido no build, sem API. Vazio no template ({}).
build/relatorios_dados.json      # números brutos por período (insumo p/ a Routine escrever relatorios.json) — não lido pelo site. Vazio no template ({}).
build/relatorio_lib.py           # datas/agregação compartilhadas (gerar_relatorios.py + coletar_dados_relatorio.py)
build/coletar_dados_relatorio.py # gera relatorios_dados.json (só números, sem texto) — roda no briefing.yml, 1x/dia
build/gerar_relatorios.py        # gera relatorios.json determinístico (sem IA) — fallback MANUAL, não roda mais sozinho
build/GUIA-RELATORIOS.md            # formato/estrutura dos Insights da aba Relatório (os 7 blocos) — preencher o contexto do funil
build/GUIA-INTERPRETACAO-METRICAS.md # regras de diagnóstico por métrica (High Ticket) — leitura obrigatória p/ redigir
.github/workflows/deploy.yml    # roda build.py e publica no Pages (workflow_dispatch + schedule + push)
.github/workflows/briefing.yml  # roda coletar_dados_relatorio.py e commita relatorios_dados.json na main (cron 1x/dia)
dist/index.html           # saída gerada (gitignored; o Actions reconstrói)
GUIA-REPLICACAO.md        # como replicar este modelo para outros relatórios/clientes
SETUP-CRON.md             # valores exatos do cron-job.org (com marcadores a preencher)
```

### Aba Relatório
Terceira página (sidebar, entre a de mídia paga e o rodapé). **Espelha a Visão
Geral** (mesmo funil/KPIs/gráficos/tabela diária, via `renderGeralCore(REL_IDS)`)
e, abaixo, acrescenta 3 blocos novos + um painel de metas editável:
- **Metas & parâmetros (painel editável)** — no topo da aba: Meta CPMQL, Meta CAC, Volume
  mínimo amostral (MQLs), N dias p/ corte. Persiste em `localStorage['dm_metas']`, default de
  `build.py` (`META_CPMQL`/`META_CAC`=None → "não definida"; `VOLUME_MIN_AMOSTRAL`/`N_DIAS_CORTE`).
  Editar recolore **CPMQL/CAC** nas tabelas de anúncio (verde ≤ meta · amarelo até +30% ·
  vermelho acima) e ajusta o badge Em observação/Avaliável, **tudo ao vivo**
  (`METAS` + `renderRelAds()` em `app.js`).
- **Top Anúncios** e **Piores Anúncios** — 17 colunas + coluna **Status** (Anúncio · Status ·
  Campanha · Conjunto · Gasto · Impr · CPM · CTR · Leads · CPL · MQLs · Tx‑MQL · CPMQL · ConvMQL ·
  Vendas · CAC · Faturamento · ROAS · **Link**). Anúncio, Status e Link ficam **sticky**.
  Ranking pelo **resultado mais profundo disponível** (Venda→MQL), amostra relevante primeiro;
  sem amostra → badge **"Em observação"**. Limiares em `build.py`: `SAMPLE_MIN_SPEND`,
  `SAMPLE_MIN_MQLS`, `TOP_ADS_N`.
- **Insights de Tráfego** — texto por período redigido pelo **Claude** (linguagem de
  gestor de tráfego), lido de `build/relatorios.json` (sem API no build/navegador —
  o site só exibe o texto já pronto). Formato em **4 quadrantes** por período. Cada
  período compara com o período anterior **correto para aquela janela** (regra em
  `relatorio_lib.previous_period`). Chaves de período fixas
  (`hoje/ontem/3d/7d/14d/30d/mes/mespass/todo`), tags `Escalar/Otimizar/Cortar/Observar`.
  Toda a aritmética é pré-calculada em `build/relatorios_dados.json` — a Routine só
  interpreta, nunca recalcula. Regras completas em `build/GUIA-RELATORIOS.md` +
  `build/GUIA-INTERPRETACAO-METRICAS.md`. `app.js` ainda reconhece o formato antigo
  (`{"html": "…"}`) como fallback.

### Briefing automático do gestor (Routine do Claude, sem chamada à API Anthropic)
`build/relatorios.json` pode ser escrito 1×/dia por uma **Routine do Claude**
(Claude Code Remote — mesma infraestrutura de sessão/agente deste repo, agendada;
não é chamada paga à API). Fluxo em 2 etapas, porque o ambiente da Routine não
alcança `docs.google.com` (só o runner do GitHub Actions alcança):
1. `build/coletar_dados_relatorio.py` (GitHub Actions, `.github/workflows/briefing.yml`,
   1×/dia) agrega **só números** em `build/relatorios_dados.json` e commita na `main`.
2. A Routine do Claude lê esse JSON + `build/GUIA-RELATORIOS.md` +
   `build/GUIA-INTERPRETACAO-METRICAS.md`, redige `build/relatorios.json` e faz
   commit/push direto na `main`, disparando o `deploy.yml`. **Precisa ser criada
   por cliente** (`create_trigger` apontando para o repo novo) — não vem pronta.

`build/gerar_relatorios.py` (gerador determinístico, sem IA) continua no repo só
como **fallback manual**. Limitação conhecida: usa os defaults de `build.py`
(`META_CPMQL`/`META_CAC`/`VOLUME_MIN_AMOSTRAL`/`N_DIAS_CORTE`), não o que o gestor
editou no painel (fica em `localStorage`).

Funil completo: `Impressões → Cliques → Leads → MQLs → Agendamentos → Reuniões
Realizadas → Vendas → Faturamento`. Enquanto só houver mídia paga × Leads, o funil
vai até MQL; Agendamentos/Reuniões/Vendas/Fat aparecem "-" até chegar a lista do
comercial.

### Link do criativo (aba de mídia paga)
`build.py` lê uma coluna opcional de permalink do criativo na aba de mídia →
mapa `ad_links` (anúncio → 1 permalink). Usado no "Link" das tabelas Top/Piores.
Sem a coluna, o link vira "—".

> **Layout modular:** o front-end é separado em `identidade-visual.css` + `estilos.css`
> + `app.js`, costurados por `render()` nos placeholders `__STYLES__`/`__APP_JS__`.
> Página 1 usa **funil vertical de leads** + KPIs secundários. Topbar tem
> **seletor de período em calendário** (default "Este mês"). **Heatmap** = cor FIXA
> por métrica (só opacidade varia): **Gasto=vermelho · Leads=azul · MQLs=ciano ·
> Vendas=verde · ROAS=amarelo** (`--heat-gasto/leads/mqls/vendas/roas`).

O `build.py` **não agrega**: exporta as linhas cruas e TODA a lógica (filtros de
data, filtro cruzado, KPIs, tabelas, gráficos, heatmap, imposto) roda no navegador.

## Rodar/testar local

```bash
python build/build.py --leads-file leads.csv --meta-file meta.csv --out dist/index.html
# (o sandbox do agente NÃO alcança docs.google.com; use CSVs locais para testar.
#  O runner do GitHub Actions tem internet e busca os CSVs ao vivo.)
```

## Especificação funcional (resumo)

Três **páginas separadas** (sidebar):
1. **Visão Geral de Leads** — funil vertical (Gasto → Impressões → Cliques → Leads →
   MQLs → Vendas/Faturamento) + KPIs secundários; gráfico combinado diário +
   tabela diária com heatmap (todos os leads); barras por origem/faixa/plataforma/profissão.
2. **Captura mídia paga** — funil em etapas; combinado diário; barras por utm_content;
   tabela diária com heatmap (só mídia paga); 3 tabelas hierárquicas Campanha →
   Conjunto → Anúncio, cada uma com gráfico de linha embaixo.
3. **Relatório** — espelha a Visão Geral + painel de Metas editável + Top/Piores
   Anúncios (17 colunas + Status) + Insights de Tráfego. Ver `build/GUIA-RELATORIOS.md`.

**Ordem das colunas nas tabelas:** `Data · Dia · Gasto · CPM · CTR · ConvForm · Leads ·
CPL · Tx‑MQL · MQLs · CPMQL · ConvMQL · Vendas · CAC · Fat. · Receita · ROAS`. Nas
tabelas diárias entram também **Checkouts** e **VisCHK** (da coluna "Adds to Cart"
do Meta Ads, proxy de Checkout). Sem essas colunas, ficam "-".

**Regras obrigatórias das tabelas** (ver `GUIA-REPLICACAO.md`): cabeçalho sticky;
ordenação tri‑state; colunas redimensionáveis (persist localStorage); linha
"Total Geral" fixa; dimensão nunca truncada; seleção com toggle + Ctrl multi;
filtro cruzado bidirecional; tabela diária com último dia no topo; heatmap de cor
fixa por métrica.

## Lacunas de dados (comuns até o cliente enviar mais fontes)
- **Agendamentos / Reuniões Realizadas** → precisam da lista do comercial; aparecem "-".
- **Page Views, CR, CPV, ConvLP** → precisam de uma fonte de page views.
- Enquanto não vierem, essas métricas aparecem como "-".

## Publicação — problemas conhecidos
1. **Push:** se a integração GitHub da sessão for somente‑leitura (403), o caminho
   é `git push` direto para `github.com` com o **PAT do usuário**. Nunca gravar o
   token no `.git/config` (usar URL efêmera `https://x-access-token:<TOKEN>@github.com/...`).
2. **cron-job.org só funciona na `main`:** `workflow_dispatch` só existe na branch
   padrão. Levar `build/` + `.github/workflows/deploy.yml` para a `main`.
3. **Pages liga sozinho:** `actions/configure-pages@v5` com `enablement: true`
   (precisa `permissions: pages: write, id-token: write`).
4. **Proxy do sandbox:** o ambiente do agente costuma NÃO alcançar `docs.google.com`,
   `*.github.io` nem a API REST de Actions/Pages — mas o runner do Actions alcança tudo.
5. **Token exposto:** se um token foi colado no chat, **revogar e gerar um novo**.

## Branch / git
- Desenvolvimento na branch designada da sessão; manter sincronizada com `main`.

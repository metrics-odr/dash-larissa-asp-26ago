# Guia de Replicação — Dashboard de BI estática (HTML/CSS/JS + Chart.js)

Este guia contém **tudo** para replicar este modelo de dashboard para outros
relatórios/clientes: arquitetura, CSS, JavaScript, lógicas de gráficos e tabelas,
e o passo a passo de publicação (incluindo como resolver os problemas que já
aconteceram). O código-fonte canônico e completo está em **`build/template.html`**
(app inteiro) e **`build/build.py`** (dados). Este guia explica *como funciona* e
*como adaptar*.

---

## 1. Arquitetura em 1 minuto

```
Google Sheets (2+ abas)  --export CSV público-->  build/build.py  (Python, só stdlib)
        │                                                 │ lê, limpa, qualifica, mascara PII
        │                                                 ▼
        │                                    injeta REGISTROS BRUTOS (leads[]/meta[]) em JSON
        │                                                 ▼
        └──────────────────────────────────────>  build/template.html  → dist/index.html
                                                          │  (todo cálculo/filtro/gráfico é no navegador)
                                                          ▼
                          GitHub Actions (deploy.yml) --> GitHub Pages (URL pública)
                                                          ▲
                                              cron-job.org dispara workflow_dispatch a cada 30 min
```

**Princípio central:** o Python **não agrega nada**. Ele só emite as linhas cruas.
Todo o resto (filtro de data, filtro cruzado, KPIs, tabelas, gráficos, heatmap,
imposto, tema) é recalculado no navegador a partir da mesma fonte. Isso dá
interatividade total (BI) sem servidor e garante que KPIs, gráficos e tabelas
**nunca divergem** (todos partem da mesma base filtrada).

Para adaptar a um novo relatório: troque os `gid`/colunas e o critério de
qualificação em `build.py`, ajuste os KPIs/colunas no template. A "engine" de
tabelas/gráficos/filtros abaixo é reutilizável sem mudanças.

---

## 2. `build.py` — do CSV aos registros brutos

Responsabilidades (stdlib apenas — `urllib`, `csv`, `json`, `re`):

- `fetch_csv(url)` / `read_csv_file(path)` — busca o CSV (ao vivo no Actions) ou lê local (teste).
- `header_index(header, aliases, fallback)` — acha colunas por nome (com fallback posicional), robusto a mudanças de ordem.
- `to_float` (aceita `R$ 1.234,56`), `parse_date` (vários formatos → `YYYY-MM-DD`).
- `is_qualified(bucket)` — **o critério do relatório** (ex.: faturamento ≥ um valor mínimo).
- `mask_email` / `mask_phone` / `first_last_initial` — **mascara PII** (a página é pública).
- Emite `{"build":{...}, "leads":[...], "meta":[...]}` e substitui os placeholders
  `__DATA_JSON__`, `__BUILD_ID__`, `__GENERATED_BRT__` no template.

Registro de lead: `{d,src,plat,camp,adset,ad,prof,bucket,q,utm,nm,em,ph}`.
Registro de meta: `{d,camp,adset,ad,sp,im,cl,ml}`.

> **PII:** como o GitHub Pages é público, e‑mail e telefone são mascarados no
> build. Para exibir contatos completos, use repositório/Pages **privado** (plano pago).

---

## 3. Design system (CSS) — tokens e shell

Tema via **CSS custom properties** com override `:root[data-theme="dark"]`. Nunca
use cores fixas em componentes; sempre `var(--…)` (foi o que quebrou o tema escuro
quando botões tinham `background:#fff`).

```css
:root{
  --text-primary:#1A1D2E; --accent-blue:#3B5BDB; --accent-blue-light:#EEF2FF; --selected:#DBEAFE;
  --bg:#F4F5F8; --surface:#FFFFFF; --border:#E6E8EE; --muted:#6B7280; --ink:#1A1D2E;
  --grid:#EEF0F5; --thead:#F5F7FB; --tfoot:#EEF1F7;
  --good:#0CA30C; --bad:#E34948; --yellow:#E8A400; --aqua:#1BAF7A; --red:#E34948;
}
:root[data-theme="dark"]{
  --text-primary:#0A0C11; --accent-blue:#5B7BF0; --accent-blue-light:#1B2440; --selected:#26365F;
  --bg:#0F1117; --surface:#171A22; --border:#2A2F3A; --muted:#9AA1AD; --ink:#F2F3F5;
  --grid:#252A34; --thead:#1E222C; --tfoot:#1B1F27;
}
```

**Shell**: `#app{display:flex}` → `.sidebar{width:220px;position:fixed}` (dark, nav) +
`.main-area{margin-left:220px}` → `.topbar{position:sticky;top:0}` + `.page-content`.
Páginas são `.page`/`.page.active` (mostra/esconde; **não** rolar entre elas).
Responsivo: abaixo de 900px a sidebar vira drawer via um `<input type=checkbox #navToggle>` + `label.ham`.

Cores de gráfico saem do CSS em runtime, para o tema valer também nos charts:
```js
const cvar=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const cmuted=()=>cvar('--muted'), cink=()=>cvar('--ink'), cgrid=()=>cvar('--grid');
```

---

## 4. Estado global e filtros

```js
const STATE = {
  page:'geral', from, to, preset:'todo', tax:false,
  selDays:new Set(),                       // filtro por data (multi, Ctrl)
  mSelC:new Set(), mSelA:new Set(), mSelAd:new Set(),  // filtro cruzado (Campanha/Conjunto/Anúncio)
  sort:{}, colw: JSON.parse(localStorage.getItem('dm_colw')||'{}'),
};
const taxf = ()=> STATE.tax ? TAX : 1;     // imposto Meta
```

**Data ativa** (o seletor De/Até é sobreposto pela seleção de dias na tabela):
```js
function dateActive(d){ if(!d) return false;
  if(STATE.selDays.size) return STATE.selDays.has(d);
  return (!STATE.from||d>=STATE.from) && (!STATE.to||d<=STATE.to); }
const leadsActive=()=>LEADS.filter(l=>dateActive(l.d));
const metaActive =()=>META.filter(m=>dateActive(m.d));
```

**Presets de data** (topbar): `hoje, ontem, 3/7/14/30 dias, este mês, mês passado,
todo período` — cada um devolve `[from,to]` calculado a partir de `B.today`.

**Agregação** (reconstrói SEMPRE da fonte filtrada — nunca tabela-de-tabela):
```js
function buildAgg(fL,fM,dim){ const m={}, g=k=>m[k]||(m[k]={sp:0,im:0,cl:0,leads:0,mqls:0});
  fM.forEach(r=>{const a=g(r[dim]); a.sp+=r.sp; a.im+=r.im; a.cl+=r.cl;});
  fL.forEach(r=>{const a=g(r[dim]); a.leads+=1; a.mqls+=r.q;}); return m; }
function derive(a){ const g=a.sp*taxf(); return { gasto:g, cpm:a.im?g/a.im*1000:null,
  ctr:a.im?a.cl/a.im:null, cpc:a.cl?g/a.cl:null, convf:a.cl?a.leads/a.cl:null,
  cpl:a.leads?g/a.leads:null, cpmql:a.mqls?g/a.mqls:null, tx:a.leads?a.mqls/a.leads:null, ...a }; }
```
Regra de ouro: **métricas acumulativas somam** (impr, cliques, leads, gasto…);
**derivadas recalculam dos totais** (CTR=cliques/impr etc.) — nunca somar percentuais.

---

## 5. Filtro cruzado bidirecional + multi-seleção (o pulo do gato)

Cada tabela hierárquica é montada de um **escopo que exclui a própria dimensão**, para
que as linhas irmãs continuem visíveis e o usuário possa **Ctrl+clicar várias** (OR):

```js
function metaScope(ex){ let fL=leadsActive().filter(l=>l.src==='meta'), fM=metaActive();
  if(ex!=='C'&&STATE.mSelC.size){ fL=fL.filter(r=>STATE.mSelC.has(r.camp)); fM=fM.filter(r=>STATE.mSelC.has(r.camp)); }
  if(ex!=='A'&&STATE.mSelA.size){ fL=fL.filter(r=>STATE.mSelA.has(r.adset)); fM=fM.filter(r=>STATE.mSelA.has(r.adset)); }
  if(ex!=='D'&&STATE.mSelAd.size){ fL=fL.filter(r=>STATE.mSelAd.has(r.ad)); fM=fM.filter(r=>STATE.mSelAd.has(r.ad)); }
  return {fL,fM}; }
// KPIs/funil/gráficos/tabela diária = metaScope(null) (todas as seleções aplicadas)
// tabela Campanhas = metaScope('C'); Conjuntos = metaScope('A'); Anúncios = metaScope('D')

function selDim(dim,key,ctrl){ const sets={C:STATE.mSelC,A:STATE.mSelA,D:STATE.mSelAd}, s=sets[dim];
  if(ctrl){ s.has(key)?s.delete(key):s.add(key); }                 // Ctrl: alterna (OR), não mexe nas outras dims
  else { const sole=s.has(key)&&s.size===1&&!Object.entries(sets).some(([k2,x])=>k2!==dim&&x.size);
    Object.values(sets).forEach(x=>x.clear()); if(!sole) s.add(key); }  // clique simples: troca a âncora
  renderMeta(); }
```
Prioridade da âncora quando `metaScope(null)` combina tudo: as três dims aplicam em
AND entre si e OR dentro de cada uma. Clicar de novo desfaz (toggle).

---

## 6. Engine de tabela interativa (`renderTable`)

Uma função monta qualquer tabela com **todas** as regras obrigatórias. Colunas:
`{key,label,type:'brl|pct|int|num|date|dim', heat:'hi'|'lo', big, w, cls}`.

Recursos implementados (ver `renderTable` em `template.html`):
- **`<colgroup>` com larguras** → **redimensionamento real**: arrastar `.rsz` (borda
  direita do `th`) muda a `<col>` e a largura da tabela (cresce com scroll lateral),
  persistido em `localStorage['dm_colw']`. Larguras padrão: dimensão 360px (`big`) /
  150px, data 96px, métrica 92px.
- **Ordenação tri-state** por clique no cabeçalho: asc → desc → ordem original.
- **Cabeçalho sticky** e **linha "Total Geral" sticky** no rodapé.
- **Heatmap por coluna** (escala dinâmica dos valores visíveis):
  ```js
  function heat(v,lo,hi,lower){ if(v==null||hi===lo) return 'transparent';
    let t=(v-lo)/(hi-lo), good=lower?1-t:t; const bad=[227,73,72], gd=[12,163,12];
    const r=Math.round(bad[0]+(gd[0]-bad[0])*good), g=..., b=...;
    return `rgba(${r},${g},${b},${(0.10+0.34*Math.abs(good-0.5)*2).toFixed(2)})`; }
  ```
  `heat:'hi'` = maior é melhor (verde); `heat:'lo'` = menor é melhor.
- **Seleção de linha** com toggle + **Ctrl multi** (via `selSet`+`onSelect`).
- Dimensão nunca truncada (`td.dim{white-space:normal;word-break:break-word}`),
  métricas `nowrap` à direita, nulo = `-`.

Ordem de colunas das tabelas de resultado (padrão do cliente):
`Data · Dia · Gasto · CPM · CTR · ConvForm(Leads/Cliques) · Leads · CPL · Tx‑MQL · MQLs · CPMQL`
(nas hierárquicas troca Data/Dia pela dimensão). **Tabela diária: último dia no topo**
(`daily(...).reverse()`).

---

## 7. Gráficos (Chart.js 4, via CDN)

- **Combinado diário** (`comboChart`): barras Leads/MQLs no eixo `y` + linhas
  Gasto(vermelha)/CPL(preta=`cink()`)/CPMQL(amarela) no eixo `y1` (R$). É o único
  lugar com 2 eixos, por exigência do cliente.
- **Barras horizontais** (`hbar`): Top N, rótulo de valor no fim da barra (plugin
  `barLabels`), nomes completos (regra: nunca truncar; Top 10 em vez de cortar).
- **Par Tabela+Gráfico** (`lineChart`): linha de CPMQL/CPL por dia **colada** logo
  abaixo de cada tabela hierárquica (`.table-chart-pair`, zero gap), refletindo o filtro.
- Cores de texto/grade lidas do tema (`cmuted/cink/cgrid`) e re-render ao trocar tema.

---

## 8. Publicação — checklist e solução dos problemas conhecidos

1. **Branch:** desenvolva na branch de feature e sincronize com a `main`.
   `workflow_dispatch` (o que o cron-job.org chama) **só existe na branch padrão** →
   **leve o workflow para a `main`** para ativar.
2. **Push quando a integração é somente‑leitura:** se `git push`/MCP derem
   `403 Resource not accessible by integration`, faça push com o **PAT do usuário**
   direto para o github.com (o proxy libera o túnel git; a API REST de Actions é bloqueada):
   ```bash
   git push "https://x-access-token:<TOKEN>@github.com/<owner>/<repo>.git" main:main
   ```
   Não persista o token no `.git/config` (use a URL efêmera acima).
3. **GitHub Pages liga sozinho:** `actions/configure-pages@v5` com `enablement: true`
   + `permissions: {pages: write, id-token: write}` habilita o Pages na 1ª execução.
   Fonte deve ficar **Source = GitHub Actions** (Settings → Pages).
4. **cron-job.org** (a cada 30 min):
   - URL: `https://api.github.com/repos/<owner>/<repo>/actions/workflows/deploy.yml/dispatches`
   - Método: `POST` · Body: `{"ref":"main"}`
   - Headers: `Accept: application/vnd.github+json` · `Authorization: Bearer <TOKEN>` ·
     `X-GitHub-Api-Version: 2022-11-28` · `Content-Type: application/json`
   - Sucesso = HTTP **204**. (Ver `SETUP-CRON.md`.)
5. **Cache-bust:** metatags `no-cache` + `?t=timestamp` no reload + auto-refresh 30 min.
6. **Sandbox do agente:** não alcança `docs.google.com`, `*.github.io` nem a API REST de
   Actions/Pages — **mas o runner do Actions alcança tudo**. Teste dados com CSV local
   e confie no Actions para o resto; peça ao usuário para confirmar Actions verde e a URL.
7. **Token exposto no chat:** oriente **revogar e gerar um novo** (fine‑grained,
   só Actions: read/write no repo).

---

## 9. Como adaptar para um novo relatório (passo a passo)

1. `build.py`: troque `SPREADSHEET_ID`, `GID_*`, o `header_index` (colunas), o
   `is_qualified` (critério do relatório) e o `TAX_FACTOR` se preciso.
2. `template.html`: ajuste os KPIs (nível 1/2), os rótulos das colunas e quais
   dimensões existem (Campanha/Conjunto/Anúncio, ou outras). A engine de tabela,
   filtros, heatmap e gráficos não muda.
3. Rode local com CSVs de teste, confira 2 páginas, tema claro/escuro e a
   multi-seleção. Commit → `main` → Actions publica → configure o cron-job.org.
4. Siga o **checklist de novo cliente** no topo de `CLAUDE.md`/`AGENTS.md` — cobre
   também a aba **Relatório** (Top/Piores anúncios, painel de metas e Insights de
   Tráfego, ver `build/GUIA-RELATORIOS.md`). Este template **não inclui** automação
   de geração dos Insights por IA (nenhum Worker/Action chama uma API de LLM); o
   `build/relatorios.json` vem vazio e pode ser preenchido manualmente ou por uma
   automação própria que você configurar depois.

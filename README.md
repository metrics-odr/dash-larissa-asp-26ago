# Dashboard de Captura de Leads · Larissa Topper

Dashboard **100% na nuvem** do Funil **Acenda Seu Propósito** de **Larissa
Topper** (Sala Secreta) que cruza a aba **Lista de Leads** (formulário + leads
Meta via utm_*) com o investimento de mídia paga (**Meta Ads**), trazendo
**Vendas/Faturamento** das colunas Purchases do próprio Meta Ads, atribuídos
por anúncio, e é publicada no **GitHub Pages**. Reconstrói sozinha a cada
~30 min, disparada pelo **cron-job.org** — sem depender de nenhum PC ligado.

**URL pública:** `https://metrics-odr.github.io/dash-larissa-asp-26ago/`

---

## O que ela mostra

- **KPIs**: Gasto Total, Leads Totais, CPL, **MQLs** (critério do cliente), CPMQL, Tx-MQL, Impressões, Cliques, CTR, CPC, CPM.
- **Evolução diária**: gasto/dia, leads × MQLs/dia, CPL × CPMQL/dia.
- **Qualificação & origem**: leads por faixa/critério (qualificado destacado), por origem (mídia paga vs. orgânico), por profissão e por plataforma.
- **Cruzamento por campanha**: gasto (mídia paga) × leads/MQLs (lista) → CPL, CPMQL e Tx-MQL calculados.
- **Tabela de leads qualificados** (e-mail e telefone **mascarados**, pois a página é pública).
- **Toggle de imposto da mídia paga** (opcional) e **modo claro/escuro**.
- **Aba Relatório**: painel de metas editável + Top/Piores Anúncios + Insights de Tráfego (texto, preenchido manualmente ou por automação própria — ver `build/GUIA-RELATORIOS.md`).

## Critério de Lead Qualificado (MQL)

Coluna de qualificação do cliente (— (cliente não usa MQL))
== "Sim". Lógica em `build.py` → `is_medico` (renomeie/ajuste ao critério do cliente).

## Fontes de dados (somente leitura)

Planilha central `ASP | Planilha Central de Lançamento Clássico`
(`1aySlj8ryPjXICkRFT6SiFnEZC7z0NkN755jtoAbqQDI`):

| Aba | gid | Uso |
|-----|-----|-----|
| Conversas (fonte principal) | `1836439885` | fonte **principal** de leads (webhook/mensageria) — usada em todos os gráficos/cards/tabelas |
| Leads (legado) | `— (não usado)` | popup/form antigo — só contada (total), não entra em cálculo algum |
| Meta Ads | `1059708846` | gasto, impressões, cliques |
| New Subscriptions (Compradores) | `— (não usado)` | cruzada por telefone com a Conversas → Vendas/Faturamento por anúncio |

O build lê essas abas via **export CSV público** (`.../export?format=csv&gid=...`).
**Nada é escrito de volta** nas planilhas.

---

## Arquitetura

```
cron-job.org  ──(POST workflow_dispatch a cada 30 min)──▶  GitHub Actions
                                                              │
                          build/build.py  lê os CSVs ◀────────┘
                                 │  cruza dados + calcula MQLs
                                 ▼
                          dist/index.html  ──▶  deploy  ──▶  GitHub Pages (URL pública)
```

- `build/build.py` — baixa os CSVs, cruza os dados, gera `dist/index.html`.
- `build/template.html` — layout/gráficos/tema (Chart.js via CDN).
- `.github/workflows/deploy.yml` — roda o build e publica no Pages.

**Cache-bust:** a página usa `Cache-Control: no-cache`, mostra o horário do último
build, tem botão **Atualizar** e se recarrega sozinha (`?t=timestamp`) ~30 min após
aberta — sempre pegando a versão mais nova.

## Rodar localmente (opcional)

```bash
python build/build.py --out dist/index.html            # busca os CSVs ao vivo
# ou, com arquivos locais para teste:
python build/build.py --conversas-file conversas.csv --meta-file meta.csv \
  --sales-file compradores.csv --leads-file leads.csv --out dist/index.html
```

---

## Ativação (uma vez) e cron-job.org

O disparo por `workflow_dispatch` só funciona quando o workflow está na branch
**`main`**. Veja **`SETUP-CRON.md`** para o passo a passo e os valores exatos
(URL, headers e body, com marcadores a preencher) a colar no cron-job.org.

> ⚠️ **Segurança:** nunca comite tokens no repositório. Gere um token
> *fine-grained*, só com **Actions: read/write** neste repositório, e use-o
> apenas no cron-job.org (ou em GitHub Secrets, se aplicável).

## Como usar este template para um novo cliente

Veja o **CHECKLIST DE NOVO CLIENTE** no topo de `CLAUDE.md` (ou `AGENTS.md`) e
o passo a passo completo em `GUIA-REPLICACAO.md`.

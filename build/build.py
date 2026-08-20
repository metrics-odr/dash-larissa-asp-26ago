#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a dashboard estatica (index.html) a partir de 4 abas da planilha central
<<PREENCHER: nome da planilha central do cliente>>:

  - "Conversas" (gid <<PREENCHER: GID_CONVERSAS>>): fonte PRINCIPAL de leads — webhook
    de mensageria disparado na 1a mensagem recebida no WhatsApp Business. Usada em
    TODOS os graficos/cards/tabelas/calculos de conversao.
  - "Leads" (gid <<PREENCHER: GID_LEADS>>): fonte ANTIGA (popup/form legado). So e
    contada (total), nunca entra em grafico/card/tabela/conversao.
  - "Meta Ads" (gid <<PREENCHER: GID_META>>): investimento/impressoes/cliques do gerenciador.
  - "New Subscriptions" / Compradores (gid <<PREENCHER: GID_SALES>>): usada para cruzar por
    TELEFONE com a Conversas e atribuir Venda/Faturamento ao anuncio de origem.

Criterio de Lead Qualificado (MQL): coluna de qualificacao do cliente
(<<PREENCHER: nome da coluna de MQL, ex. "E medico?">>) == "Sim". Ajuste is_medico()
e os aliases de coluna em process() para o criterio deste cliente.

Este script apenas LE as planilhas (export CSV publico) e emite os REGISTROS
BRUTOS (leads[], meta[] e sales[]) dentro do HTML. sales[] tem um registro POR
COMPRA (nunca agregado por telefone), com a DATA REAL da compra — camp/adset/ad
vem da 1a conversa daquele telefone (atribuicao do anuncio de origem), mas a
data nunca e' a da conversa, senao vendas de dias diferentes seriam somadas no
mesmo dia. Todos os filtros, agregacoes, KPIs, tabelas e graficos sao
calculados no navegador (client-side). Nunca escreve nada de volta.

Teste local: --conversas-file / --meta-file / --sales-file / --leads-file
apontando para CSVs baixados.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone, timedelta

SPREADSHEET_ID = "<<PREENCHER: ID da planilha central (Google Sheets) do cliente>>"
GID_CONVERSAS = "<<PREENCHER: gid da aba de Conversas / fonte principal de leads>>"
GID_LEADS = "<<PREENCHER: gid da aba de Leads legado (popup/form) — só contada>>"
GID_META = "<<PREENCHER: gid da aba Meta Ads>>"
GID_SALES = "<<PREENCHER: gid da aba de Compradores (New Subscriptions) — cruzada por telefone>>"
EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"

# Identificação do cliente/conta (usada só em textos/relatórios — não afeta o cruzamento de dados).
CLIENT_NAME = "<<PREENCHER: nome do cliente>>"
MAIN_PRODUCT = "<<PREENCHER: nome do produto/oferta principal>>"
# Prefixo comum a TODAS as campanhas da conta (usado para agrupar campanhas no
# dashboard). Ajuste ao padrão de nomenclatura de campanha deste cliente.
MAIN_PRODUCT_PREFIX = "<<PREENCHER: prefixo das campanhas do cliente, ex. NOMECLIENTE>>"

BRT = timezone(timedelta(hours=-3))   # horario de Brasilia (exibicao)
TAX_FACTOR = 1.0   # <<PREENCHER: fator de imposto/taxa da conta de mídia, ex. 1.13806 (13,806%); 1.0 = sem imposto>>

# --------------------------------------------------------------------------- #
# Regras da aba Relatório (Top/Piores anúncios)
# --------------------------------------------------------------------------- #
# Amostra mínima para julgar um anúncio como "vencedor" ou "ruim". Abaixo disso
# ele entra como "Em observação" (dado insuficiente) — nunca é classificado só
# porque teve 1 resultado com pouco investimento. Ajuste conforme o ticket/CAC.
SAMPLE_MIN_SPEND = 100.0   # gasto mínimo (R$) para amostra relevante
SAMPLE_MIN_MQLS = 3        # MQLs mínimos para julgar qualidade profunda
TOP_ADS_N = 10             # nº de linhas em Top / Piores anúncios

# Metas & parâmetros da conta (DEFAULTS do painel editável da aba Relatório).
# São só o valor inicial: o usuário edita no navegador (persistido em
# localStorage) e as tabelas de anúncios recoram CPMQL/CAC e reavaliam a
# amostra ao vivo. None = "meta não definida" (métrica aparece sem cor até o
# gestor preencher).
META_CPMQL = None          # meta de CPMQL (R$/MQL); None = não definida
META_CAC = None            # meta de CAC (R$/venda); None = não definida
VOLUME_MIN_AMOSTRAL = SAMPLE_MIN_MQLS  # conversões (MQLs) mínimas p/ amostra confiável
N_DIAS_CORTE = 5           # dias consecutivos acima do teto p/ considerar corte


# --------------------------------------------------------------------------- #
# Leitura
# --------------------------------------------------------------------------- #
def fetch_csv(url: str) -> list[list[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "dash-template-bot/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return list(csv.reader(io.StringIO(raw)))


def read_csv_file(path: str) -> list[list[str]]:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.reader(f))


def load_rows(url: str, local: str | None) -> list[list[str]]:
    return read_csv_file(local) if local else fetch_csv(url)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s: str | None) -> str:
    return strip_accents((s or "").strip().lower())


def to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v).strip())
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(v: str) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def is_test_lead(rowtext: str) -> bool:
    return "<test lead" in rowtext.lower()


# <<PREENCHER: critério de MQL deste cliente>> — implementação de referência abaixo
# usa uma coluna booleana "Sim/Não". Renomeie a função e ajuste conforme o critério
# de qualificação do cliente (o exemplo abaixo qualifica pela coluna de MQL == "Sim").
def is_medico(v: str | None) -> bool:
    """Critério de MQL: coluna de qualificação (<<PREENCHER: nome da coluna>>) == "Sim"."""
    return norm(v) in ("sim", "s", "yes", "true", "1")


def pretty_specialty(v: str) -> str:
    s = (v or "").strip()
    return s if s else "Sem resposta"


def mask_email(e: str) -> str:
    e = (e or "").strip()
    if "@" not in e:
        return "—"
    user, dom = e.split("@", 1)
    keep = user[:2] if len(user) > 2 else user[:1]
    return f"{keep}****@{dom}"


def mask_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    return f"…{digits[-4:]}" if len(digits) >= 4 else "—"


def norm_phone(p: str) -> str:
    return re.sub(r"\D", "", p or "")


def canon_phone(p: str) -> str:
    """Chave CANÔNICA de telefone p/ cruzar Compradores × Conversas, robusta às
    3 variações que faziam o mesmo número não bater quando comparado só por
    dígitos (norm_phone):
      - DDI "55" presente de um lado e ausente do outro
        (5511988887777 vs 11988887777);
      - 9º dígito do celular presente/ausente
        (11988887777 vs 1188887777);
      - máscara/espacos/parênteses (já removidos por norm_phone).
    Estratégia: remove o DDI 55 (quando sobra DDD+número) e usa DDD (2 díg.) +
    ÚLTIMOS 8 DÍGITOS — que é o mesmo com ou sem o 9. Devolve chave de 10 díg.
    (DDD+8). Números curtos/estrangeiros (< 10 díg. após limpar) voltam como
    estão, pra não colidir à toa."""
    d = norm_phone(p)
    if len(d) > 11 and d.startswith("55"):
        d = d[2:]            # tira DDI do Brasil, sobrando DDD + local
    if len(d) >= 10:
        return d[:2] + d[-8:]   # DDD + últimos 8 (drop do 9º dígito, se houver)
    return d


def first_last_initial(name: str) -> str:
    parts = (name or "").strip().split()
    if not parts:
        return "—"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][:1]}."


def valid_utm(campaign: str) -> bool:
    c = norm(campaign)
    return bool(c) and c not in ("-", "—", "nao encontrado")


# --------------------------------------------------------------------------- #
# Indexacao das colunas
# --------------------------------------------------------------------------- #
def header_index(header, wanted, fallback):
    idx = {}
    hn = [norm(h) for h in header]
    for key, aliases in wanted.items():
        found = None
        for a in aliases:
            a = norm(a)
            for i, h in enumerate(hn):
                if h == a or (a and a in h):
                    found = i
                    break
            if found is not None:
                break
        idx[key] = found if found is not None else fallback.get(key)
    return idx


def cell(row, i):
    if i is None or i < 0 or i >= len(row):
        return ""
    return (row[i] or "").strip()


# --------------------------------------------------------------------------- #
# Compradores ("New Subscriptions") -> indice por telefone
# --------------------------------------------------------------------------- #
def build_sales_index(sales_rows):
    """Le a aba de Compradores e devolve {telefone_normalizado: [{"d":..,"fat":..,"receita":..,"nm":..}, ...]},
    UMA ENTRADA POR LINHA de compra (nao agregada por telefone). Cruzamento é por
    TELEFONE (a Conversas não tem e-mail; o Lead LP antigo tem e-mail mas está fora
    do escopo principal deste dashboard). Mantemos cada compra separada — com sua
    própria data — para atribuir a venda ao dia em que ela REALMENTE aconteceu,
    em vez de empilhar todo o histórico de compras do telefone num único dia.
    "nm" (nome, sem mascara) fica só p/ diagnóstico de telefone não casado
    (log_unmatched_sales) — nunca é exportado em sales[]/DATA."""
    header = sales_rows[0] if sales_rows else []
    idx = header_index(
        header,
        {"phone": ["telefone"], "date": ["data"], "faturamento": ["faturamento"], "receita": ["receita"],
         "name": ["nome"]},
        {"phone": 3, "date": 0, "faturamento": 6, "receita": 7, "name": 1},
    )
    out: dict[str, list] = {}
    for row in sales_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        phone = norm_phone(cell(row, idx["phone"]))
        if not phone:
            continue
        out.setdefault(phone, []).append({
            "d": parse_date(cell(row, idx["date"])),
            "fat": to_float(cell(row, idx["faturamento"])),
            "receita": to_float(cell(row, idx["receita"])),
            "nm": cell(row, idx["name"]),
        })
    return out


def log_unmatched_sales(sales_index, phone_attrib):
    """Diagnóstico (stderr, não afeta a saída): compras da aba Compradores cujo
    telefone não bate com NENHUMA conversa da aba Conversas MESMO após a
    canonicalização (canon_phone, que já cobre DDI "55" e o 9º dígito do
    celular). Essas vendas AGORA entram na dash mesmo assim (contam nos totais /
    Visão Geral), só ficam SEM atribuição de anúncio ("(sem campanha)") — este
    log serve pra dimensionar quanta receita fica sem origem e conferir se é
    compra por outro canal (esperado) ou algum telefone ainda divergente."""
    matched = sum(1 for phone in sales_index if canon_phone(phone) in phone_attrib)
    unmatched = [(phone, p) for phone, purchases in sales_index.items()
                 if canon_phone(phone) not in phone_attrib for p in purchases]
    print(f"  vendas atribuídas a anúncio: {matched}/{len(sales_index)} telefones "
          f"(cruzamento canônico Compradores × Conversas)", file=sys.stderr)
    if not unmatched:
        return
    print(f"  {len(unmatched)} compra(s) SEM anúncio de origem (entram nos totais como \"(sem campanha)\"):",
          file=sys.stderr)
    for phone, p in unmatched:
        print(f"    - {p['d'] or '?'}  {first_last_initial(p['nm'])}  tel …{phone[-4:] if len(phone) >= 4 else phone}",
              file=sys.stderr)


# --------------------------------------------------------------------------- #
# Processamento -> registros brutos
# --------------------------------------------------------------------------- #
def process(conversas_rows, meta_rows, sales_rows, leads_lp_rows):
    sales_index = build_sales_index(sales_rows)

    cheader = conversas_rows[0] if conversas_rows else []
    # <<PREENCHER: aliases da coluna de MQL do cliente>> — "medico" abaixo é o exemplo
    # (ajuste os aliases e o índice de fallback ao cabeçalho da aba Conversas do cliente).
    cidx = header_index(
        cheader,
        {"created": ["data"], "phone": ["telefone"], "name": ["nome"],
         "medico": ["e medico", "medico"], "campaign": ["campanha"],
         "adset": ["conjunto"], "ad": ["anuncio"], "specialty": ["especialidades", "especialidade"]},
        {"created": 0, "phone": 3, "name": 2, "medico": 4, "campaign": 8, "adset": 9, "ad": 10, "specialty": 11},
    )

    leads = []
    # atribuicao do ANUNCIO/campanha de uma venda por telefone: a 1a conversa
    # daquele telefone (a mais antiga de fato) e' quem levou aquele contato a
    # comprar, entao e' ela que define camp/adset/ad da venda — evita atribuir
    # a mesma compra a mais de uma conversa quando o numero aparece varias vezes.
    # A DATA da venda, porem, e' a data real da compra (aba Compradores), nunca
    # a data da conversa — datas diferentes nao devem ser somadas no mesmo dia.
    rows_sorted = sorted(
        [r for r in conversas_rows[1:] if any((c or "").strip() for c in r)],
        key=lambda r: parse_date(cell(r, cidx["created"])) or "",
    )
    attributed_phones: set[str] = set()
    phone_attrib: dict[str, dict] = {}
    for row in rows_sorted:
        if is_test_lead(" ".join(str(c) for c in row)):
            continue
        campaign_raw = cell(row, cidx["campaign"])
        campaign_valid = valid_utm(campaign_raw)
        src = "meta" if campaign_valid else "org"
        phone = canon_phone(cell(row, cidx["phone"]))
        camp = campaign_raw if campaign_valid else "(sem campanha)"
        adset = cell(row, cidx["adset"]) if campaign_valid else "(sem conjunto)"
        ad = cell(row, cidx["ad"]) if campaign_valid else "(sem anúncio)"
        conversa_date = parse_date(cell(row, cidx["created"]))
        if phone and phone not in attributed_phones:
            attributed_phones.add(phone)
            phone_attrib[phone] = {"src": src, "camp": camp, "adset": adset, "ad": ad, "d": conversa_date}
        specialty = pretty_specialty(cell(row, cidx["specialty"]))
        leads.append({
            "d": parse_date(cell(row, cidx["created"])),
            "src": src,
            "plat": "ig" if src == "meta" else "—",
            "camp": camp,
            "adset": adset,
            "ad": ad,
            "prof": specialty,
            "bucket": specialty,
            "q": 1 if is_medico(cell(row, cidx["medico"])) else 0,
            "utm": 1 if campaign_valid else 0,
            "nm": first_last_initial(cell(row, cidx["name"])),
            "em": "—",
            "ph": mask_phone(cell(row, cidx["phone"])),
        })

    # Vendas: um registro POR COMPRA (nunca agregada por telefone), na data real
    # da compra. TODA venda entra (aparece na Visão Geral e nos totais) — decisão
    # do cliente: "todas as vendas entram na Geral, só as atribuídas ao Meta
    # entram no Meta". camp/adset/ad vem da 1a conversa daquele telefone
    # (phone_attrib, cruzado pela chave canônica canon_phone). Quando NÃO há
    # conversa correspondente (comprou por outro canal, ou o telefone do checkout
    # difere do WhatsApp de um jeito que a canonicalização não cobre), a venda
    # ainda conta, porém SEM atribuição de anúncio: cai em "(sem campanha)" /
    # src="org" — some da quebra por campanha do Meta, mas nunca dos totais.
    sales = []
    NO_ATTRIB = {"src": "org", "camp": "(sem campanha)", "adset": "(sem conjunto)",
                 "ad": "(sem anúncio)", "d": None}
    for phone, purchases in sales_index.items():
        attrib = phone_attrib.get(canon_phone(phone)) or NO_ATTRIB
        for p in purchases:
            sales.append({
                "d": p["d"] or attrib["d"],
                "src": attrib["src"],
                "camp": attrib["camp"],
                "adset": attrib["adset"],
                "ad": attrib["ad"],
                "vendas": 1,
                "fat": round(p["fat"], 2),
                "receita": round(p["receita"], 2),
            })

    log_unmatched_sales(sales_index, phone_attrib)

    mheader = meta_rows[0] if meta_rows else []
    midx = header_index(
        mheader,
        {"day": ["day", "data"], "campaign": ["campaign name", "campaign"], "adset": ["ad set name", "adset"],
         "ad": ["ad name"], "spent": ["amount spent", "valor gasto", "gasto"], "impr": ["impressions", "impress"],
         "clicks": ["link clicks", "clicks", "cliques"], "leads": ["leads"],
         "pv": ["landing page views", "page views", "pageviews"],
         # Cliente não tem evento "Initiate Checkout" configurado no pixel — usa
         # "Adds to Cart" como proxy de Checkout (decisão do cliente).
         "chk": ["adds to cart", "add to cart", "initiate checkout", "checkouts iniciados", "checkouts"],
         # Link do criativo (ex. Instagram) — coluna opcional adicionada pelo cliente
         # na aba de mídia. Usada na aba Relatório (Top/Piores anúncios) para linkar
         # o anúncio. Aliases cobrem variações do cabeçalho.
         "link": ["creative instagram permalink", "instagram permalink", "permalink",
                  "creative link", "link do anuncio", "link do criativo"]},
        {"day": 0, "campaign": 2, "adset": 3, "ad": 4, "spent": 5, "impr": 6, "clicks": 7, "leads": None, "pv": 8},
    )

    meta = []
    # Anúncio (nome) -> 1 permalink do criativo. "Qualquer um correlato" ao
    # anúncio serve (o mesmo criativo pode rodar em vários dias/conjuntos);
    # guardamos o primeiro link não-vazio encontrado para cada anúncio.
    ad_links = {}
    for row in meta_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        ad = cell(row, midx["ad"]) or "(sem anúncio)"
        link = cell(row, midx["link"])
        if link and ad not in ad_links:
            ad_links[ad] = link
        meta.append({
            "d": parse_date(cell(row, midx["day"])),
            "camp": cell(row, midx["campaign"]) or "(sem campanha)",
            "adset": cell(row, midx["adset"]) or "(sem conjunto)",
            "ad": ad,
            "sp": round(to_float(cell(row, midx["spent"])), 4),
            "im": to_float(cell(row, midx["impr"])),
            "cl": to_float(cell(row, midx["clicks"])),
            "pv": to_float(cell(row, midx["pv"])),
            "ck": to_float(cell(row, midx["chk"])),
            "ml": to_float(cell(row, midx["leads"])),
        })

    # Leads (LP) — fonte antiga, fora de uso. Só contamos o total para
    # referência (não entra em leads[]/gráficos/tabelas/conversão).
    leads_lp_total = sum(
        1 for row in leads_lp_rows[1:]
        if any((c or "").strip() for c in row) and not is_test_lead(" ".join(str(c) for c in row))
    ) if leads_lp_rows else 0

    dates = sorted({d for d in (
        [l["d"] for l in leads if l["d"]] + [m["d"] for m in meta if m["d"]] + [s["d"] for s in sales if s["d"]]
    )})
    now_brt = datetime.now(BRT)
    return {
        "build": {
            "generated_at_brt": now_brt.strftime("%d/%m/%Y %H:%M"),
            "build_id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "today": now_brt.strftime("%Y-%m-%d"),
            "date_min": dates[0] if dates else None,
            "date_max": dates[-1] if dates else None,
            "tax_factor": TAX_FACTOR,
            # config da aba Relatório (lida pelo front)
            "sample_min_spend": SAMPLE_MIN_SPEND,
            "sample_min_mqls": SAMPLE_MIN_MQLS,
            "top_ads_n": TOP_ADS_N,
            # metas & parâmetros (defaults do painel editável; None = não definida)
            "meta_cpmql": META_CPMQL,
            "meta_cac": META_CAC,
            "volume_min_amostral": VOLUME_MIN_AMOSTRAL,
            "n_dias_corte": N_DIAS_CORTE,
            # referência apenas (não usado na UI): total da fonte antiga "Leads LP".
            "leads_lp_total": leads_lp_total,
        },
        "leads": leads,
        "meta": meta,
        "sales": sales,
        # Anúncio -> permalink do criativo (aba Relatório).
        "ad_links": ad_links,
        # Insights de Tráfego (texto pré-escrito, lido de relatorios.json). Preenchido
        # em main() via load_briefings(); fica {} se relatorios.json não existir.
        "briefings": {},
    }


# --------------------------------------------------------------------------- #
# Insights de Tráfego (aba Relatório)
# --------------------------------------------------------------------------- #
def load_briefings(path: str) -> dict:
    """Lê build/relatorios.json. Estrutura:
        {"generated_at": "...", "periodos": {"<preset>": {"html": "..."}, ...}}
    Retorna o dict inteiro (ou {} se o arquivo não existir/for inválido).
    A geração NÃO acontece aqui — este build só lê o texto já pronto, sem
    chamar nenhuma API (custo zero no build/no navegador)."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except (ValueError, OSError):
        return {}


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render(data, template_path):
    # A dashboard e montada a partir de arquivos separados (visual x logica):
    #   template.html          -> esqueleto HTML (placeholders __STYLES__/__APP_JS__)
    #   identidade-visual.css  -> TODAS as cores (edite aqui p/ mexer so em cor)
    #   estilos.css            -> layout/componentes
    #   app.js                 -> logica + renderizacao
    # Esta funcao so COSTURA os arquivos e injeta os dados; nao altera nada deles.
    base = os.path.dirname(os.path.abspath(template_path))

    def readf(name):
        with open(os.path.join(base, name), "r", encoding="utf-8") as f:
            return f.read()

    with open(template_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    styles = readf("identidade-visual.css") + "\n" + readf("estilos.css")
    tpl = tpl.replace("__STYLES__", styles)
    tpl = tpl.replace("__APP_JS__", readf("app.js"))
    tpl = tpl.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    tpl = tpl.replace("__BUILD_ID__", data["build"]["build_id"])
    tpl = tpl.replace("__GENERATED_BRT__", data["build"]["generated_at_brt"])
    return tpl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conversas-file", help="CSV local da aba Conversas (fonte principal de leads)")
    ap.add_argument("--leads-file", help="CSV local da aba Leads (LP, legado — só contada)")
    ap.add_argument("--meta-file")
    ap.add_argument("--sales-file", help="CSV local da aba New Subscriptions (Compradores)")
    ap.add_argument("--template", default="build/template.html")
    ap.add_argument("--out", default="dist/index.html")
    args = ap.parse_args()

    conversas_rows = load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID, gid=GID_CONVERSAS), args.conversas_file)
    meta_rows = load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID, gid=GID_META), args.meta_file)
    sales_rows = load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID, gid=GID_SALES), args.sales_file)
    leads_lp_rows = load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID, gid=GID_LEADS), args.leads_file)

    data = process(conversas_rows, meta_rows, sales_rows, leads_lp_rows)

    # Insights de Tráfego (texto pré-escrito) — lidos do arquivo versionado ao
    # lado do template. Sem chamada de API no build.
    briefings_path = os.path.join(os.path.dirname(os.path.abspath(args.template)), "relatorios.json")
    data["briefings"] = load_briefings(briefings_path)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(data, args.template))

    b = data["build"]
    q = sum(l["q"] for l in data["leads"])
    vd = sum(s["vendas"] for s in data["sales"])
    fat = sum(s["fat"] for s in data["sales"])
    print("== build ok ==", file=sys.stderr)
    print(f"  periodo   : {b['date_min']} -> {b['date_max']}", file=sys.stderr)
    print(f"  leads MSG : {len(data['leads'])}  MQLs (qualificados): {q}", file=sys.stderr)
    print(f"  vendas    : {vd}  faturamento: R$ {fat:,.2f}", file=sys.stderr)
    print(f"  leads LP  : {b['leads_lp_total']} (fonte antiga, não usada na UI)", file=sys.stderr)
    print(f"  meta      : {len(data['meta'])} linhas", file=sys.stderr)
    print(f"  out       : {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

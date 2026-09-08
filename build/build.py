#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a dashboard estatica (index.html) do funil "Acenda Seu Propósito" (Larissa
Topper · Sala Secreta), a partir de 2 abas da planilha central
"ASP | Planilha Central de Lançamento Clássico":

  - "Lista de Leads" (gid 1836439885): fonte PRINCIPAL de leads — formulário Sala
    Secreta + leads atribuídos ao Meta via utm_*. Usada em TODOS os
    graficos/cards/tabelas. Este cliente NÃO usa critério de MQL (q=0).
  - "Meta Ads" (gid 1059708846): investimento/impressoes/cliques + Vendas
    (Purchases) e Faturamento (Purchases Conversion Value) do gerenciador.

Vendas/Faturamento vêm do próprio Meta Ads SOMADAS à aba de Vendas totais
unificadas de uma planilha separada ("Larissa | Planilha Central",
SPREADSHEET_ID_VENDAS/GID_VENDAS), cruzada com a Lista de Leads por TELEFONE
OU E-MAIL (nunca por UTM). Funil e Temperatura (seletores das tabelas de
otimização) saem do nome da campanha (classify_funil / classify_temp).

Este script apenas LE as planilhas (export CSV publico) e emite os REGISTROS
BRUTOS (leads[] e meta[]) dentro do HTML. Todos os filtros, agregacoes, KPIs,
tabelas e graficos sao calculados no navegador (client-side). Nunca escreve
nada de volta.

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

SPREADSHEET_ID = "1aySlj8ryPjXICkRFT6SiFnEZC7z0NkN755jtoAbqQDI"
# Fonte PRINCIPAL de leads: aba "Lista de Leads" (formulário Sala Secreta + leads
# atribuídos ao Meta via utm_*). Este cliente NÃO usa aba "Conversas" (webhook) nem
# critério de MQL — por isso GID_CONVERSAS aponta para a própria Lista de Leads e
# a qualificação (is_medico) fica sempre desligada (q=0). Vendas/Faturamento vêm
# das colunas Purchases / Purchases Conversion Value do próprio Meta Ads SOMADAS
# à planilha de Vendas totais unificadas abaixo (SPREADSHEET_ID_VENDAS).
GID_CONVERSAS = "1836439885"   # Lista de Leads (fonte principal)
GID_LEADS = ""                 # sem aba de Leads legado
GID_META = "1059708846"        # Meta Ads
EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"

# Planilha separada "Larissa | Planilha Central" — aba de VENDAS TOTAIS
# UNIFICADAS (contratos assinados / New Subscriptions do cliente), cruzada com
# a Lista de Leads por E-MAIL e TELEFONE (nunca por UTM: essa aba não tem
# campanha/anúncio próprios — quem atribui camp/adset/ad é a 1ª conversa cujo
# telefone OU e-mail bate com o comprador). Colunas usadas: telefone · email ·
# data_envio · caixaVenda (entrada/receita imediata) · faturamentoVenda (valor
# total contratado da venda). Linhas sem telefone válido E sem e-mail válido
# são ignoradas (não têm como cruzar com nenhum lead).
SPREADSHEET_ID_VENDAS = "1P7c_7rutl0fdnqIc2DX5DuGl6H9E7WRU_gzDpOdphkw"
GID_VENDAS = "179764332"

# Planilha separada "Versalhes - Input Grupo" — 1 linha por lead que ENTROU no
# grupo de WhatsApp do lançamento (bot de automação, não a Central de Lançamento).
# Colunas: Nome do Grupo | id_grupo | telefone_lead | hora de input (ISO c/ offset
# -03:00). "Nome do Grupo" traz o sufixo "- ORGANICO" pros grupos de tráfego
# orgânico (fallback de origem quando o telefone não cruza com nenhuma conversa).
SPREADSHEET_ID_GRUPO = "1GDUYqHUF51bZ7f7KKKzAl_V7tMWKzwrdS__45X9LzMw"
GID_GRUPO = "0"

# Identificação do cliente/conta (usada só em textos/relatórios — não afeta o cruzamento de dados).
CLIENT_NAME = "Larissa Topper"
MAIN_PRODUCT = "Acenda Seu Propósito"
# Prefixo comum às campanhas de captura do funil Sala Secreta.
MAIN_PRODUCT_PREFIX = "ASP"

BRT = timezone(timedelta(hours=-3))   # horario de Brasilia (exibicao)
TAX_FACTOR = 1.13806   # imposto de mídia do cliente: 13,806%

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
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        # pt-BR: ponto isolado sem vírgula é separador de milhar (ex. "3.073" = 3073),
        # nunca separador decimal (decimal em pt-BR sempre usa vírgula).
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


PT_MONTHS = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
             "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
             "novembro": 11, "dezembro": 12}


def parse_date(v: str) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # formato do formulário (data_e_hora): "17 de agosto de 2026 20:07"
    m = re.match(r"(\d{1,2})\s+de\s+([A-Za-zçÇ]+)\s+de\s+(\d{4})", s, re.IGNORECASE)
    if m:
        mon = PT_MONTHS.get(strip_accents(m.group(2)).lower())
        if mon:
            return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(1)):02d}"
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------- #
# Classificação por nome de campanha (funil + temperatura)
# --------------------------------------------------------------------------- #
# Critérios extraídos do Campaign Name / utm_campaign, usados pelos 2 seletores
# (Funil · Temperatura) das tabelas de otimização no navegador.
#   Funil:  DIAG (contém "DIAG") · APD-MUNDO (contém "MUNDO") ·
#           APD-BR (contém "APD", ou tag antiga "[VERSALHES-APLICACAO" sem "MUNDO").
#   Temp.:  Quente ("QUENTE"/"HOT") · Frio ("FRIO"/"COLD").
def classify_funil(campaign: str) -> str:
    c = (campaign or "").upper()
    if "DIAG" in c:
        return "DIAG"
    if "MUNDO" in c:
        return "APD-MUNDO"
    if "APD" in c:
        return "APD-BR"
    if "VERSALHES" in c and "APLICA" in c:   # tag antiga sem "MUNDO" (já pego acima) => BR
        return "APD-BR"
    return "(outros)"


def classify_temp(campaign: str) -> str:
    c = (campaign or "").upper()
    if "QUENTE" in c or re.search(r"\bHOT\b", c):
        return "Quente"
    if "FRIO" in c or re.search(r"\bCOLD\b", c):
        return "Frio"
    return "—"


def is_test_lead(rowtext: str) -> bool:
    return "<test lead" in rowtext.lower()


# Este cliente NÃO usa critério de MQL — a qualificação fica desligada (q=0 em
# process()). Função mantida só por compatibilidade; nunca marca ninguém.
def is_medico(v: str | None) -> bool:
    """Sem MQL neste cliente — sempre False."""
    return False


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


def norm_email(e: str) -> str:
    e = (e or "").strip().lower()
    return e if "@" in e else ""


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
# Origem do lead: "certeza que é do Meta" vs. link na bio / orgânico
# --------------------------------------------------------------------------- #
# O painel de mídia paga (aba "Captura Meta Ads") só pode contar leads que temos
# CERTEZA que vieram do tráfego pago do Meta. Leads do LINK NA BIO (perfil do
# Instagram) e de fontes orgânicas costumam chegar com utm_source/utm_medium/
# utm_campaign marcados como "bio", "linktree", "organic" etc. — NÃO são clique
# em anúncio pago, então NÃO entram no funil de mídia paga (mas continuam
# contando na Visão Geral, como orgânicos).
#
# Tokens abaixo são casados por PALAVRA (split em não-alfanumérico), então
# "link na bio", "link-in-bio", "utm_medium=bio" batem em "bio", sem
# falso-positivo dentro de nomes de campanha paga (ex.: "ASP | E2-CAP | ...").
# Ajuste/expanda a lista conforme as convenções reais de UTM do cliente — o
# build loga quantos leads caíram em cada origem (ver process()).
ORGANIC_TOKENS = {
    "bio", "linkbio", "linkinbio", "linktree", "instabio", "beacons",
    "perfil", "profile", "organic", "organico", "organica",
    "api",
}


def is_organic_source(*vals) -> bool:
    """True quando o lead veio do link na bio / fonte orgânica / API (não é
    clique em anúncio pago do Meta). Inspeciona utm_source/utm_medium/
    utm_campaign/utm_term normalizados, casando qualquer TOKEN contra
    ORGANIC_TOKENS."""
    text = norm(" ".join(str(v or "") for v in vals))
    return any(t in ORGANIC_TOKENS for t in re.split(r"[^a-z0-9]+", text) if t)


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
# Vendas totais unificadas -> lista de compras (cruzamento por telefone/e-mail)
# --------------------------------------------------------------------------- #
def build_sales_index(sales_rows):
    """Le a aba de Vendas totais unificadas (planilha separada "Larissa | Planilha
    Central", SPREADSHEET_ID_VENDAS/GID_VENDAS) e devolve uma lista de compras
    [{"phone":.., "email":.., "d":.., "fat":.., "receita":.., "nm":..}, ...], UMA
    ENTRADA POR LINHA (nao agregada). "fat" = faturamentoVenda (valor total
    contratado da venda) · "receita" = caixaVenda (entrada/receita já recebida).
    Cruzamento em process() é por TELEFONE OU E-MAIL (nunca por UTM — esta aba
    não tem campanha/anúncio próprios). Linhas sem telefone válido E sem e-mail
    válido são descartadas aqui (não há como cruzar com nenhum lead).
    "nm" (nome, sem mascara) fica só p/ diagnóstico de venda não casada
    (log_unmatched_sales) — nunca é exportado em sales[]/DATA."""
    header = sales_rows[0] if sales_rows else []
    idx = header_index(
        header,
        {"phone": ["telefone"], "email": ["email"], "date": ["data_envio", "data"],
         "faturamento": ["faturamentovenda", "faturamento"], "receita": ["caixavenda", "receita", "caixa"],
         "name": ["nomecompleto", "nome"]},
        {"phone": 9, "email": 4, "date": 0, "faturamento": 11, "receita": 10, "name": 3},
    )
    out = []
    for row in sales_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        phone = norm_phone(cell(row, idx["phone"]))
        email = norm_email(cell(row, idx["email"]))
        if not phone and not email:
            continue   # sem telefone nem e-mail válido: impossível cruzar com um lead
        out.append({
            "phone": phone,
            "email": email,
            "d": parse_date(cell(row, idx["date"])),
            "fat": to_float(cell(row, idx["faturamento"])),
            "receita": to_float(cell(row, idx["receita"])),
            "nm": cell(row, idx["name"]),
        })
    return out


def log_unmatched_sales(sales_list, phone_attrib, email_attrib):
    """Diagnóstico (stderr, não afeta a saída): compras cujo telefone (canon_phone,
    já cobre DDI "55" e o 9º dígito do celular) NEM e-mail batem com nenhuma
    conversa da Lista de Leads. Essas vendas AGORA entram na dash mesmo assim
    (contam nos totais / Visão Geral), só ficam SEM atribuição de anúncio
    ("(sem campanha)") — este log serve pra dimensionar quanta receita fica sem
    origem e conferir se é compra por outro canal (esperado) ou algum
    telefone/e-mail ainda divergente."""
    unmatched = [p for p in sales_list
                 if not (p["phone"] and canon_phone(p["phone"]) in phone_attrib)
                 and not (p["email"] and p["email"] in email_attrib)]
    print(f"  vendas atribuídas a anúncio: {len(sales_list) - len(unmatched)}/{len(sales_list)} "
          f"(cruzamento por telefone OU e-mail × Lista de Leads)", file=sys.stderr)
    if not unmatched:
        return
    print(f"  {len(unmatched)} compra(s) SEM anúncio de origem (entram nos totais como \"(sem campanha)\"):",
          file=sys.stderr)
    for p in unmatched:
        tel = p["phone"][-4:] if len(p["phone"]) >= 4 else p["phone"]
        print(f"    - {p['d'] or '?'}  {first_last_initial(p['nm'])}  tel …{tel or '—'}  {mask_email(p['email'])}",
              file=sys.stderr)


# --------------------------------------------------------------------------- #
# Processamento -> registros brutos
# --------------------------------------------------------------------------- #
def build_group_records(group_rows):
    """Le a planilha separada 'Versalhes - Input Grupo' (1 linha por lead que
    ENTROU no grupo de WhatsApp do lancamento) e devolve [{"d":..., "src":...}, ...].
    Origem (src) vem SEMPRE do texto da própria coluna "Nome do Grupo" (não do
    telefone): o bot grava o nome "limpo" (== MAIN_PRODUCT, sem nenhum sufixo)
    só pros grupos de tráfego pago; QUALQUER indicativo/sufixo no nome
    (" - ORGANICO", " - API" etc. — variações de texto não são todas
    previsíveis) marca lead que NÃO é de mídia paga. Por isso a checagem é por
    ALLOWLIST (nome == MAIN_PRODUCT exato), não por blacklist de palavras:
    nome "limpo" => src="meta" (tráfego pago); qualquer outra coisa => src="org"."""
    if not group_rows:
        return []
    header = group_rows[0]
    idx = header_index(
        header,
        {"date": ["hora de input", "data"], "nome_grupo": ["nome do grupo"]},
        {"date": 3, "nome_grupo": 0},
    )
    out = []
    for row in group_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        src = "meta" if norm(cell(row, idx["nome_grupo"])) == norm(MAIN_PRODUCT) else "org"
        out.append({"d": parse_date(cell(row, idx["date"])), "src": src})
    return out


def process(conversas_rows, meta_rows, sales_rows, leads_lp_rows, group_rows=None):
    sales_index = build_sales_index(sales_rows)

    cheader = conversas_rows[0] if conversas_rows else []
    # Fonte principal = "Lista de Leads" (formulário Sala Secreta + leads Meta via utm_*).
    # Sem coluna de MQL (cliente não qualifica) => is_medico fica sempre 0.
    # utm_campaign traz o nome COMPLETO da campanha (ex. "ASP | E2-CAP | P1-QUENTE | ...")
    # — dele saem funil/temperatura; utm_content é o anúncio; conjunto vem de
    # utm_medium (utm_term traz o PLACEMENT, ex. "Instagram_Reels", "Facebook_Mobile_Feed" —
    # usado só no hint de plataforma abaixo, nunca como conjunto).
    cidx = header_index(
        cheader,
        {"created": ["data_e_hora", "data"], "phone": ["telefone", "whatsapp"], "email": ["email"],
         "name": ["nome"],
         "medico": ["__sem_mql__"], "campaign": ["utm_campaign", "campanha"],
         "adset": ["utm_medium"], "ad": ["utm_content", "anuncio"],
         "source": ["utm_source"], "term": ["utm_term"],
         "specialty": ["qual sua profissao", "profissao", "especialidade"]},
        {"created": 9, "phone": 2, "email": 1, "name": 0, "medico": None, "campaign": 6, "adset": 7,
         "ad": 5, "source": 4, "term": 7, "specialty": 3},
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
    attributed_emails: set[str] = set()
    email_attrib: dict[str, dict] = {}
    for row in rows_sorted:
        if is_test_lead(" ".join(str(c) for c in row)):
            continue
        campaign_raw = cell(row, cidx["campaign"])
        source_raw = cell(row, cidx["source"])
        adset_raw = cell(row, cidx["adset"])
        term_raw = cell(row, cidx["term"])
        campaign_valid = valid_utm(campaign_raw)
        # "Certeza que é do Meta" (regra do cliente): só entra no painel de mídia
        # paga o lead que tem utm_source presente E NÃO é link na bio / orgânico /
        # API. Leads sem UTM (utm_source vazio), da bio ou via API caem em "org"
        # — contam só na Visão Geral (que exibe TODOS os leads da planilha), nunca
        # no Meta.
        has_source = bool(norm(source_raw))
        organic = is_organic_source(source_raw, adset_raw, campaign_raw, term_raw)
        is_meta = campaign_valid and has_source and not organic
        src = "meta" if is_meta else "org"
        phone = canon_phone(cell(row, cidx["phone"]))
        email = norm_email(cell(row, cidx["email"]))
        camp = campaign_raw if is_meta else "(sem campanha)"
        adset = adset_raw if is_meta else "(sem conjunto)"
        ad = cell(row, cidx["ad"]) if is_meta else "(sem anúncio)"
        conversa_date = parse_date(cell(row, cidx["created"]))
        attrib = {"src": src, "camp": camp, "adset": adset, "ad": ad, "d": conversa_date}
        if phone and phone not in attributed_phones:
            attributed_phones.add(phone)
            phone_attrib[phone] = attrib
        if email and email not in attributed_emails:
            attributed_emails.add(email)
            email_attrib[email] = attrib
        specialty = pretty_specialty(cell(row, cidx["specialty"]))
        # plataforma a partir do utm_term/utm_source (ex. "Instagram_Feed", "Facebook_Mobile_Feed")
        plat_hint = norm(cell(row, cidx["term"]) + " " + cell(row, cidx["source"]))
        plat = "ig" if "insta" in plat_hint else ("fb" if "face" in plat_hint else ("ig" if src == "meta" else "—"))
        leads.append({
            "d": parse_date(cell(row, cidx["created"])),
            "src": src,
            "plat": plat,
            "camp": camp,
            "adset": adset,
            "ad": ad,
            # funil/temperatura do lead (só quando há campanha atribuída) — usados
            # pelos seletores das tabelas de otimização; lead sem campanha some do
            # recorte quando um funil específico é escolhido (não pode ser reivindicado).
            "funil": classify_funil(campaign_raw) if is_meta else "(sem)",
            "temp": classify_temp(campaign_raw) if is_meta else "—",
            "prof": specialty,
            "bucket": specialty,
            "q": 0,          # cliente não usa MQL
            "utm": 1 if campaign_valid else 0,
            "nm": first_last_initial(cell(row, cidx["name"])),
            "em": mask_email(cell(row, cidx["email"])),
            "ph": mask_phone(cell(row, cidx["phone"])),
        })

    group = build_group_records(group_rows)

    # Vendas: um registro POR COMPRA (nunca agregada), na data real da compra
    # (data_envio da própria planilha de Vendas — NUNCA a data da conversa: usar
    # a data da conversa como proxy faria uma venda antiga/sem data aparecer
    # como "venda de hoje" só porque o comprador também é um lead recente,
    # distorcendo o dia errado do funil). Decisão do cliente: a dashboard deve
    # refletir SÓ o que foi efetivamente CRUZADO com a Lista de Leads — venda
    # sem correspondência por TELEFONE OU E-MAIL (comprou por outro canal, ou
    # os dados de contato divergem) é DESCARTADA aqui, não entra em lugar
    # nenhum (nem Visão Geral, nem totais). camp/adset/ad da venda vem da 1a
    # conversa cujo telefone (prioridade) ou e-mail (fallback) bate com o
    # comprador — nunca UTM, essa aba de vendas não tem UTM próprio. Vendas SEM
    # data_envio na planilha de origem também são descartadas (não há como
    # posicioná-las corretamente em nenhum período). Ambos os descartes só
    # contam no log (stderr), nunca no site.
    sales = []
    sem_data = sem_match = 0
    for p in sales_index:
        if not p["d"]:
            sem_data += 1
            continue
        attrib = None
        if p["phone"]:
            attrib = phone_attrib.get(canon_phone(p["phone"]))
        if attrib is None and p["email"]:
            attrib = email_attrib.get(p["email"])
        if attrib is None:
            sem_match += 1
            continue
        sales.append({
            "d": p["d"],
            "src": attrib["src"],
            "camp": attrib["camp"],
            "adset": attrib["adset"],
            "ad": attrib["ad"],
            "vendas": 1,
            "fat": round(p["fat"], 2),
            "receita": round(p["receita"], 2),
        })

    log_unmatched_sales(sales_index, phone_attrib, email_attrib)
    if sem_data:
        print(f"  {sem_data} compra(s) SEM data_envio na planilha de Vendas — descartadas "
              f"(não entram em nenhum período; não usamos a data da conversa como proxy)",
              file=sys.stderr)
    if sem_match:
        print(f"  {sem_match} compra(s) SEM correspondência por telefone/e-mail na Lista de "
              f"Leads — descartadas (a dashboard só mostra vendas efetivamente cruzadas)",
              file=sys.stderr)

    # Diagnóstico da origem dos leads: quantos são "certeza Meta" (entram no
    # painel de mídia paga) vs. link na bio / sem UTM (só na Visão Geral).
    n_meta = sum(1 for l in leads if l["src"] == "meta")
    n_org = len(leads) - n_meta
    print(f"  leads Meta (utm_source, entram no painel Meta): {n_meta}", file=sys.stderr)
    print(f"  leads bio/sem-UTM (só Visão Geral, fora do Meta): {n_org}", file=sys.stderr)

    mheader = meta_rows[0] if meta_rows else []
    midx = header_index(
        mheader,
        {"day": ["day", "data"], "campaign": ["campaign name", "campaign"], "adset": ["ad set name", "adset"],
         "ad": ["ad name"], "spent": ["amount spent", "valor gasto", "gasto"], "impr": ["impressions", "impress"],
         "clicks": ["link clicks", "clicks", "cliques"], "leads": ["leads"],
         "pv": ["landing page views", "page views", "pageviews"],
         # Cliente não tem evento "Initiate Checkout" configurado no pixel — usa
         # "Adds to Cart" como proxy de Checkout (decisão do cliente).
         "chk": ["checkouts initiated", "adds to cart", "add to cart", "initiate checkout", "checkouts iniciados", "checkouts"],
         # Vendas/Faturamento vêm do próprio Meta Ads (sem aba de Compradores):
         "purch": ["purchases", "compras", "results"],
         "rev": ["purchases conversion value", "conversion value", "subscribe conversion value", "faturamento"],
         # Link do criativo (ex. Instagram) — coluna opcional adicionada pelo cliente
         # na aba de mídia. Usada na aba Relatório (Top/Piores anúncios) para linkar
         # o anúncio. Aliases cobrem variações do cabeçalho.
         "link": ["creative instagram permalink", "instagram permalink", "permalink",
                  "creative link", "link do anuncio", "link do criativo"]},
        {"day": 0, "campaign": 1, "adset": 2, "ad": 3, "spent": 4, "impr": 5, "clicks": 6,
         "pv": 7, "leads": 8, "chk": 9, "purch": 10, "rev": 11},
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
        camp_name = cell(row, midx["campaign"]) or "(sem campanha)"
        meta.append({
            "d": parse_date(cell(row, midx["day"])),
            "camp": camp_name,
            "adset": cell(row, midx["adset"]) or "(sem conjunto)",
            "ad": ad,
            "funil": classify_funil(camp_name),
            "temp": classify_temp(camp_name),
            "sp": round(to_float(cell(row, midx["spent"])), 4),
            "im": to_float(cell(row, midx["impr"])),
            "cl": to_float(cell(row, midx["clicks"])),
            "pv": to_float(cell(row, midx["pv"])),
            "ck": to_float(cell(row, midx["chk"])),
            "ml": to_float(cell(row, midx["leads"])),
            # Vendas/Faturamento do próprio Meta Ads (Purchases / Purchases Conversion Value)
            "vd": to_float(cell(row, midx["purch"])),
            "fat": round(to_float(cell(row, midx["rev"])), 2),
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
        "group": group,
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
    ap.add_argument("--sales-file", help="CSV local da aba de Vendas totais unificadas (cruzamento por telefone/e-mail)")
    ap.add_argument("--grupo-file", help="CSV local da planilha 'Versalhes - Input Grupo' (leads que entraram no grupo)")
    ap.add_argument("--template", default="build/template.html")
    ap.add_argument("--out", default="dist/index.html")
    args = ap.parse_args()

    def load_gid(gid, local):
        # gid vazio (aba inexistente p/ este cliente) => sem fetch, lista vazia.
        if not local and not gid:
            return []
        return load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID, gid=gid), local)

    conversas_rows = load_gid(GID_CONVERSAS, args.conversas_file)
    meta_rows = load_gid(GID_META, args.meta_file)
    sales_rows = (read_csv_file(args.sales_file) if args.sales_file
                  else load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID_VENDAS, gid=GID_VENDAS), None))
    leads_lp_rows = load_gid(GID_LEADS, args.leads_file)
    group_rows = (read_csv_file(args.grupo_file) if args.grupo_file
                  else load_rows(EXPORT_URL.format(sid=SPREADSHEET_ID_GRUPO, gid=GID_GRUPO), None))

    data = process(conversas_rows, meta_rows, sales_rows, leads_lp_rows, group_rows)

    # Insights de Tráfego (texto pré-escrito) — lidos do arquivo versionado ao
    # lado do template. Sem chamada de API no build.
    briefings_path = os.path.join(os.path.dirname(os.path.abspath(args.template)), "relatorios.json")
    data["briefings"] = load_briefings(briefings_path)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(data, args.template))

    b = data["build"]
    q = sum(l["q"] for l in data["leads"])
    # Vendas/Faturamento vêm do Meta Ads (Purchases / Purchases Conversion Value).
    vd = sum(s["vendas"] for s in data["sales"]) + sum(m.get("vd", 0) for m in data["meta"])
    fat = sum(s["fat"] for s in data["sales"]) + sum(m.get("fat", 0) for m in data["meta"])
    print("== build ok ==", file=sys.stderr)
    print(f"  periodo   : {b['date_min']} -> {b['date_max']}", file=sys.stderr)
    print(f"  leads MSG : {len(data['leads'])}  MQLs (qualificados): {q}", file=sys.stderr)
    print(f"  vendas    : {vd}  faturamento: R$ {fat:,.2f}", file=sys.stderr)
    print(f"  leads LP  : {b['leads_lp_total']} (fonte antiga, não usada na UI)", file=sys.stderr)
    print(f"  meta      : {len(data['meta'])} linhas", file=sys.stderr)
    print(f"  grupo     : {len(data['group'])} leads entraram no grupo", file=sys.stderr)
    print(f"  out       : {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

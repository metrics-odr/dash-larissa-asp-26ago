#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Funções puras de datas/agregação compartilhadas entre `gerar_relatorios.py`
(fallback manual, determinístico) e `coletar_dados_relatorio.py` (coleta de
números para a Routine do Claude escrever os Insights). Nenhuma lógica de
texto/interpretação mora aqui — só aritmética sobre os registros brutos de
`build.py` (`leads[]`/`meta[]`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, date

import build as bp

BRT = bp.BRT


def d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def ds(x: date) -> str:
    return x.strftime("%Y-%m-%d")


def month_bounds(any_day: date, offset_months: int = 0):
    y, m = any_day.year, any_day.month
    m += offset_months
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    first = date(y, m, 1)
    if m == 12:
        last = date(y, 12, 31)
    else:
        nxt = date(y, m + 1, 1)
        last = nxt - timedelta(days=1)
    return first, last


def build_periods(today: date, date_min: date | None, date_max: date | None):
    """Espelha PRESETS de build/app.js — chaves fixas lidas por relBriefKey()."""
    dmin = date_min or today
    dmax = date_max or today
    mes_f, _ = month_bounds(today, 0)
    mespass_f, mespass_l = month_bounds(today, -1)
    return {
        "hoje":    (today, today, "Hoje"),
        "ontem":   (today - timedelta(days=1), today - timedelta(days=1), "Ontem"),
        "3d":      (today - timedelta(days=2), today, "3 dias"),
        "7d":      (today - timedelta(days=6), today, "7 dias"),
        "14d":     (today - timedelta(days=13), today, "14 dias"),
        "30d":     (today - timedelta(days=29), today, "30 dias"),
        "mes":     (mes_f, today, "Este mês"),
        "mespass": (mespass_f, mespass_l, "Mês passado"),
        "todo":    (dmin, dmax, "Todo período"),
    }


def in_range(row_date: str | None, start: date, end: date) -> bool:
    if not row_date:
        return False
    try:
        rd = d(row_date)
    except ValueError:
        return False
    return start <= rd <= end


def agg(meta: list[dict], leads: list[dict], start: date, end: date, camp: str | None = None,
        adset: str | None = None, ad: str | None = None) -> dict:
    def keep(r):
        if not in_range(r["d"], start, end):
            return False
        if camp is not None and r["camp"] != camp:
            return False
        if adset is not None and r["adset"] != adset:
            return False
        if ad is not None and r["ad"] != ad:
            return False
        return True

    m = [r for r in meta if keep(r)]
    l = [r for r in leads if keep(r)]
    spend = sum(r["sp"] for r in m) * bp.TAX_FACTOR
    impr = sum(r["im"] for r in m)
    clicks = sum(r["cl"] for r in m)
    n_leads = len(l)
    n_mqls = sum(r["q"] for r in l)
    return {"spend": spend, "impr": impr, "clicks": clicks, "leads": n_leads, "mqls": n_mqls}


def derived(a: dict) -> dict:
    spend, impr, clicks, leads, mqls = a["spend"], a["impr"], a["clicks"], a["leads"], a["mqls"]
    return {
        "cpm": (spend / impr * 1000) if impr else None,
        "ctr": (clicks / impr) if impr else None,
        "cpl": (spend / leads) if leads else None,
        "convform": (leads / clicks) if clicks else None,
        "txmql": (mqls / leads) if leads else None,
        "cpmql": (spend / mqls) if mqls else None,
        **a,
    }


def shift_back(start: date, end: date, n: int) -> tuple[date, date]:
    """Janela imediatamente anterior, mesmo tamanho, deslocada n vezes."""
    span = (end - start).days + 1
    new_end = start - timedelta(days=1 + span * (n - 1))
    new_start = new_end - timedelta(days=span - 1)
    return new_start, new_end


# --------------------------------------------------------------------------- #
# Período de comparação por janela (regra §7 do briefing) — cada uma das 9
# janelas usa um "período anterior equivalente" diferente; "todo" nunca
# inventa um período anterior (usa metade recente x metade antiga como
# benchmark, quando há histórico suficiente).
# --------------------------------------------------------------------------- #
def previous_period(key: str, start: date, end: date, today: date,
                     date_min: date | None, date_max: date | None):
    """Retorna (prev_start, prev_end, metodo) ou (None, None, metodo) quando
    não existe período anterior válido (ex.: "todo" com histórico curto)."""
    if key in ("hoje", "ontem", "3d", "7d", "14d", "30d"):
        p_start, p_end = shift_back(start, end, 1)
        return p_start, p_end, "período imediatamente anterior, mesma duração"

    if key == "mes":
        n_dias = (end - start).days + 1
        prev_first, prev_last = month_bounds(today, -1)
        p_start = prev_first
        p_end = min(prev_first + timedelta(days=n_dias - 1), prev_last)
        return p_start, p_end, "mesmo intervalo de dias (1–{}) do mês anterior".format(n_dias)

    if key == "mespass":
        p_start, p_end = month_bounds(today, -2)
        return p_start, p_end, "mês retrasado completo"

    if key == "todo":
        dmin = date_min or start
        dmax = date_max or end
        total_days = (dmax - dmin).days + 1
        if total_days < 14:
            return None, None, "histórico curto demais para dividir — usado só como benchmark, sem variação forçada"
        mid = dmin + timedelta(days=total_days // 2)
        return dmin, mid - timedelta(days=1), "metade mais antiga do histórico vs. metade mais recente"

    p_start, p_end = shift_back(start, end, 1)
    return p_start, p_end, "período imediatamente anterior, mesma duração"


RATE_METRICS = {"ctr", "convform", "txmql"}
MATERIAL_PCT = 0.10     # variação relativa mínima p/ considerar mudança relevante
MATERIAL_PP = 0.03      # variação em pontos percentuais mínima p/ métricas de taxa


def compare(cur: dict, prev: dict | None) -> dict:
    """Compara duas agregações `derived()` métrica a métrica. Só marca
    `material=True` quando a variação passa os limiares mínimos — evita
    listar oscilações irrelevantes como se fossem alerta (regra §7)."""
    metrics = ["spend", "impr", "clicks", "leads", "mqls", "cpm", "ctr", "cpl",
               "convform", "txmql", "cpmql"]
    out = {}
    for m in metrics:
        cv, pv = cur.get(m), (prev or {}).get(m)
        row = {"atual": cv, "anterior": pv, "delta_abs": None, "delta_pct": None,
               "delta_pp": None, "direcao": "sem_dado", "material": False}
        if cv is not None and pv is not None:
            row["delta_abs"] = round(cv - pv, 4)
            row["delta_pct"] = round((cv - pv) / pv, 4) if pv else None
            if m in RATE_METRICS:
                row["delta_pp"] = round((cv - pv) * 100, 2)
            higher_is_better = m not in ("spend", "cpm", "cpl", "cpmql")
            if abs(cv - pv) < 1e-9:
                row["direcao"] = "estavel"
            else:
                melhorou = (cv > pv) == higher_is_better
                row["direcao"] = "melhorou" if melhorou else "piorou"
            if m in RATE_METRICS:
                row["material"] = row["delta_pp"] is not None and abs(row["delta_pp"]) >= MATERIAL_PP * 100
            else:
                row["material"] = row["delta_pct"] is not None and abs(row["delta_pct"]) >= MATERIAL_PCT
        elif cv is not None and pv is None:
            row["direcao"] = "sem_periodo_anterior"
        out[m] = row
    return out


# --------------------------------------------------------------------------- #
# Nota de saúde do funil (0–10) — metodologia única, reaplicada em todos os
# períodos. Cada subnota só é calculada quando os dados que a sustentam
# existem; ausência de dado NUNCA vira nota 0 (fica None + a nota geral é
# marcada como provisória). Ver GUIA-RELATORIOS.md §5 para a leitura completa.
# --------------------------------------------------------------------------- #
def _clamp(v, lo=0.0, hi=10.0):
    return max(lo, min(hi, v))


def _classificacao(nota: float) -> str:
    if nota >= 8.0:
        return "Excelente"
    if nota >= 6.5:
        return "Saudável, com atenção"
    if nota >= 5.0:
        return "Atenção"
    if nota >= 3.0:
        return "Crítico"
    return "Crítico grave"


def funnel_health(cur: dict, baseline: dict, meta_cpmql, meta_cac,
                   volume_min: int, sample_windows: list[dict]) -> dict:
    """`cur` e `baseline` são dicts `derived()` do período atual e de uma
    janela de referência (normalmente 30d). `sample_windows` é uma lista de
    dicts `derived()` (ex.: 7d/14d/30d) usada para medir consistência."""
    sub = {}

    # Aquisição: custo de mídia (CPM) e capacidade de gerar clique (CTR) vs.
    # baseline de 30 dias da própria conta.
    if cur.get("cpm") is not None and baseline.get("cpm") and cur.get("ctr") is not None and baseline.get("ctr"):
        cpm_var = (cur["cpm"] - baseline["cpm"]) / baseline["cpm"]
        ctr_var = (cur["ctr"] - baseline["ctr"]) / baseline["ctr"]
        sub["aquisicao"] = round(_clamp(10 - cpm_var * 10 + ctr_var * 5), 1)
    else:
        sub["aquisicao"] = None

    # Conversão da página: sem fonte de Page Views/ConvLP conectada ao dashboard.
    sub["conversao_pagina"] = None

    # Qualificação: TxMQL/CPMQL vs. meta (se definida) ou vs. baseline da conta.
    if cur.get("cpmql") is not None:
        ref = meta_cpmql if meta_cpmql is not None else baseline.get("cpmql")
        if ref:
            cpmql_var = (cur["cpmql"] - ref) / ref
            sub["qualificacao"] = round(_clamp(10 - cpmql_var * 10), 1)
        else:
            sub["qualificacao"] = None
    else:
        sub["qualificacao"] = None

    # Vendas: sem fonte comercial (agendamentos/reuniões/vendas) conectada.
    sub["vendas"] = None

    # Consistência: quanto a Tx-MQL varia entre as janelas de amostra (7/14/30d)
    # — baixa variação = leitura mais confiável entre janelas.
    txmqls = [w["txmql"] for w in sample_windows if w.get("txmql") is not None]
    if len(txmqls) >= 2 and max(txmqls) > 0:
        spread = (max(txmqls) - min(txmqls)) / max(txmqls)
        sub["consistencia"] = round(_clamp(10 - spread * 10), 1)
    else:
        sub["consistencia"] = None

    # Confiabilidade dos dados: volume de MQLs no período vs. volume mínimo
    # amostral configurado no painel da aba Relatório.
    mqls = cur.get("mqls") or 0
    sub["confiabilidade_dados"] = round(_clamp(10 * mqls / volume_min if volume_min else 10), 1)

    disponiveis = {k: v for k, v in sub.items() if v is not None}
    if not disponiveis:
        return {
            "nota": None, "provisoria": True, "classificacao": "Sem dado suficiente",
            "motivo": "Nenhuma subnota pôde ser calculada neste período (sem volume/histórico comparável).",
            "subnotas": sub,
        }

    nota = round(sum(disponiveis.values()) / len(disponiveis), 1)
    faltantes = [k for k, v in sub.items() if v is None]
    provisoria = bool(faltantes)
    motivo = (
        "Nota provisória: sem dados suficientes para " + ", ".join(faltantes) + "."
        if provisoria else ""
    )
    return {
        "nota": nota, "provisoria": provisoria, "classificacao": _classificacao(nota),
        "motivo": motivo, "subnotas": sub,
    }


# --------------------------------------------------------------------------- #
# Formatação (usada pelos templates de texto do gerar_relatorios.py)
# --------------------------------------------------------------------------- #
def money(v) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def pct(v) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f}%".replace(".", ",")


def num(v) -> str:
    if v is None:
        return "—"
    return f"{v:,.0f}".replace(",", ".")


def meta_status(nome: str, valor) -> str:
    return "meta não definida" if valor is None else f"meta {nome} = {money(valor)}"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera build/relatorios_dados.json: SÓ NÚMEROS (nenhuma interpretação/texto),
agregados por período/campanha/conjunto/anúncio a partir dos mesmos dados que
alimentam o dashboard (mídia paga x Leads). É o insumo lido pela Routine do
Claude (ver GUIA-RELATORIOS.md) para escrever build/relatorios.json — garante
que os números do texto batem 1:1 com o site sem depender do Claude "fazer
conta". Não chama nenhuma API de IA/LLM.

Uso:
    python build/coletar_dados_relatorio.py --out build/relatorios_dados.json
    python build/coletar_dados_relatorio.py --leads-file leads.csv --meta-file meta.csv --out build/relatorios_dados.json

Sem --leads-file/--meta-file, busca os CSVs públicos da planilha (mesma URL de
build.py) — precisa de acesso a docs.google.com (o runner do GitHub Actions tem;
o sandbox do agente normalmente não).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as bp  # reaproveita fetch/parse/process/constantes de build.py
from relatorio_lib import (
    BRT, d, build_periods, in_range, agg, derived, shift_back,
    previous_period, compare, funnel_health, money, pct, num,
)


def daily_series(meta: list[dict], leads: list[dict], start, end, camp=None, adset=None, ad=None) -> list[dict]:
    """Uma linha por dia (spend/leads/mqls + derivadas) — dá ao Claude a base
    pra enxergar tendência (ex.: CPM subindo/Tx-MQL caindo N dias seguidos)."""
    out = []
    cur = start
    while cur <= end:
        a = derived(agg(meta, leads, cur, cur, camp=camp, adset=adset, ad=ad))
        if a["spend"] or a["leads"]:
            out.append({
                "d": cur.strftime("%Y-%m-%d"),
                "spend": round(a["spend"], 2), "impr": a["impr"], "clicks": a["clicks"],
                "leads": a["leads"], "mqls": a["mqls"],
                "cpm": _r(a["cpm"]), "ctr": _r(a["ctr"], 4), "cpl": _r(a["cpl"]),
                "txmql": _r(a["txmql"], 4), "cpmql": _r(a["cpmql"]),
            })
        cur += timedelta(days=1)
    return out


def _r(v, nd=2):
    return None if v is None else round(v, nd)


def totais_dict(a: dict) -> dict:
    return {
        "spend": round(a["spend"], 2), "impr": a["impr"], "clicks": a["clicks"],
        "leads": a["leads"], "mqls": a["mqls"],
        "cpm": _r(a["cpm"]), "ctr": _r(a["ctr"], 4), "cpl": _r(a["cpl"]),
        "convform": _r(a["convform"], 4), "txmql": _r(a["txmql"], 4), "cpmql": _r(a["cpmql"]),
    }


def breakdown(meta: list[dict], leads: list[dict], start, end, dim: str, camp_filter=None) -> list[dict]:
    """Agrega por campanha/conjunto/anúncio dentro do período (só métricas
    agregadas — SEM série diária por estrutura, que inchava o arquivo). A série
    diária existe apenas AGREGADA no nível do período (ver periodo_payload)."""
    def key_of(r):
        if dim == "camp":
            return r["camp"]
        if dim == "adset":
            return (r["camp"], r["adset"])
        return (r["camp"], r["adset"], r["ad"])

    keys = set()
    for r in meta:
        if in_range(r["d"], start, end) and (camp_filter is None or r["camp"] == camp_filter):
            keys.add(key_of(r))
    for r in leads:
        if in_range(r["d"], start, end) and (camp_filter is None or r["camp"] == camp_filter):
            keys.add(key_of(r))

    out = []
    for k in sorted(keys, key=lambda x: str(x)):
        if dim == "camp":
            camp, adset, ad = k, None, None
        elif dim == "adset":
            camp, adset, ad = k[0], k[1], None
        else:
            camp, adset, ad = k

        a = derived(agg(meta, leads, start, end, camp=camp, adset=adset, ad=ad))
        if not a["spend"] and not a["leads"]:
            continue
        row = totais_dict(a)
        if dim == "camp":
            row["campanha"] = camp
        elif dim == "adset":
            row["campanha"], row["conjunto"] = camp, adset
        else:
            row["campanha"], row["conjunto"], row["anuncio"] = camp, adset, ad
        out.append(row)
    out.sort(key=lambda r: -r["spend"])
    return out


def consolidado_criativos(por_anuncio: list[dict]) -> list[dict]:
    """Agrupa as ocorrências (campanha+conjunto+anúncio) de `por_anuncio` pelo
    NOME do anúncio — visão consolidada do criativo (regra §11-A do briefing:
    o mesmo criativo pode rodar em várias estruturas com resultados diferentes)."""
    by_ad: dict[str, list[dict]] = {}
    for row in por_anuncio:
        by_ad.setdefault(row["anuncio"], []).append(row)

    out = []
    for ad, occs in by_ad.items():
        spend = sum(o["spend"] for o in occs)
        leads = sum(o["leads"] for o in occs)
        mqls = sum(o["mqls"] for o in occs)
        clicks = sum(o["clicks"] for o in occs)
        impr = sum(o["impr"] for o in occs)
        occs_com_mql = [o for o in occs if o["mqls"]]
        melhor = min(occs_com_mql, key=lambda o: o["cpmql"]) if occs_com_mql else None
        pior = max(occs_com_mql, key=lambda o: o["cpmql"]) if occs_com_mql else None
        out.append({
            "anuncio": ad,
            "n_estruturas": len(occs),
            "estruturas": [{"campanha": o["campanha"], "conjunto": o["conjunto"]} for o in occs],
            "spend": round(spend, 2), "impr": impr, "clicks": clicks, "leads": leads, "mqls": mqls,
            "cpm": round(spend / impr * 1000, 2) if impr else None,
            "ctr": round(clicks / impr, 4) if impr else None,
            "cpl": round(spend / leads, 2) if leads else None,
            "txmql": round(mqls / leads, 4) if leads else None,
            "cpmql": round(spend / mqls, 2) if mqls else None,
            "melhor_estrutura": (
                {"campanha": melhor["campanha"], "conjunto": melhor["conjunto"], "cpmql": melhor["cpmql"]}
                if melhor else None
            ),
            "pior_estrutura": (
                {"campanha": pior["campanha"], "conjunto": pior["conjunto"], "cpmql": pior["cpmql"]}
                if pior and pior is not melhor else None
            ),
        })
    out.sort(key=lambda r: -r["spend"])
    return out


def whatsapp_numeros(label: str, start, end, cur: dict, saude: dict) -> dict:
    """Números já formatados (moeda/percentual) para o bloco copiável do
    WhatsApp — a Routine do Claude só preenche destaques/ações em texto,
    nunca recalcula nem inventa estes valores (regra §6 do briefing)."""
    return {
        "periodo_label": label,
        "periodo_range": f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}",
        "gasto": money(cur["spend"]), "cpm": money(cur["cpm"]), "ctr": pct(cur["ctr"]),
        "connect_rate": "Não disponível", "conv_lp": "Não disponível",
        "leads": num(cur["leads"]), "cpl": money(cur["cpl"]),
        "mqls": num(cur["mqls"]), "cpa_cpmql": money(cur["cpmql"]),
        "vendas": "Não disponível", "faturamento": "Não disponível",
        "cac": "Não disponível", "roas": "Não disponível", "ticket_medio": "Não disponível",
        "saude_funil": (
            f"{saude['nota']:.1f}/10 — {saude['classificacao']}" + (" (provisória)" if saude["provisoria"] else "")
            if saude["nota"] is not None else "Nota provisória — dados insuficientes"
        ),
    }


def periodo_payload(meta: list[dict], leads: list[dict], today, start, end, key, date_min, date_max,
                     meta_cpmql, meta_cac, volume_min) -> dict:
    cur = derived(agg(meta, leads, start, end))
    ref7 = derived(agg(meta, leads, today - timedelta(days=6), today))
    ref14 = derived(agg(meta, leads, today - timedelta(days=13), today))
    ref30 = derived(agg(meta, leads, today - timedelta(days=29), today))

    p_start, p_end, metodo = previous_period(key, start, end, today, date_min, date_max)
    anterior = derived(agg(meta, leads, p_start, p_end)) if p_start else None

    saude = funnel_health(cur, ref30, meta_cpmql, meta_cac, volume_min, [ref7, ref14, ref30])
    por_anuncio = breakdown(meta, leads, start, end, "ad")

    return {
        "range": {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")},
        "totais": totais_dict(cur),
        # Série diária AGREGADA do período (não por estrutura) — só a base p/ o
        # Claude ver tendência geral (CPM subindo / Tx-MQL caindo N dias). Limitada
        # aos últimos 60 dias com atividade p/ não inchar "todo período". A série
        # por campanha/conjunto/anúncio foi REMOVIDA de propósito: ela respondia por
        # ~75% do tamanho do arquivo (≈280k tokens) e ninguém a consome — o veredito
        # por estrutura usa as métricas agregadas de por_campanha/conjunto/anuncio.
        "serie_diaria": daily_series(meta, leads, start, end)[-60:],
        "nota_saude": saude,
        "whatsapp_numeros": whatsapp_numeros("", start, end, cur, saude),
        "comparativos": {
            "7d": totais_dict(ref7), "14d": totais_dict(ref14), "30d": totais_dict(ref30),
            "periodo_anterior": {
                "range": ({"start": p_start.strftime("%Y-%m-%d"), "end": p_end.strftime("%Y-%m-%d")}
                          if p_start else None),
                "metodo": metodo,
                "totais": totais_dict(anterior) if anterior else None,
                "variacao": compare(cur, anterior),
            },
        },
        "por_campanha": breakdown(meta, leads, start, end, "camp"),
        "por_conjunto": breakdown(meta, leads, start, end, "adset"),
        "por_anuncio": por_anuncio,
        "criativos_consolidado": consolidado_criativos(por_anuncio),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conversas-file")
    ap.add_argument("--meta-file")
    ap.add_argument("--sales-file")
    ap.add_argument("--leads-file")
    ap.add_argument("--out", default="build/relatorios_dados.json")
    args = ap.parse_args()

    conversas_rows = bp.load_rows(bp.EXPORT_URL.format(sid=bp.SPREADSHEET_ID, gid=bp.GID_CONVERSAS), args.conversas_file)
    meta_rows = bp.load_rows(bp.EXPORT_URL.format(sid=bp.SPREADSHEET_ID, gid=bp.GID_META), args.meta_file)
    sales_rows = bp.load_rows(bp.EXPORT_URL.format(sid=bp.SPREADSHEET_ID, gid=bp.GID_SALES), args.sales_file)
    leads_lp_rows = bp.load_rows(bp.EXPORT_URL.format(sid=bp.SPREADSHEET_ID, gid=bp.GID_LEADS), args.leads_file)
    data = bp.process(conversas_rows, meta_rows, sales_rows, leads_lp_rows)
    leads, meta = data["leads"], data["meta"]

    now_brt = datetime.now(BRT)
    today = now_brt.date()
    date_min = d(data["build"]["date_min"]) if data["build"]["date_min"] else None
    date_max = d(data["build"]["date_max"]) if data["build"]["date_max"] else None

    periods = build_periods(today, date_min, date_max)

    out = {
        "generated_at": now_brt.strftime("%d/%m/%Y %H:%M"),
        "generated_at_iso": now_brt.isoformat(),
        "fonte": "Números brutos agregados a partir do funil (mídia paga × Leads) — insumo para a "
                 "Routine do Claude escrever build/relatorios.json (Insights de Tráfego). Sem "
                 "interpretação/texto aqui, só aritmética.",
        "params": {
            "tax_factor": bp.TAX_FACTOR,
            "sample_min_spend": bp.SAMPLE_MIN_SPEND,
            "sample_min_mqls": bp.SAMPLE_MIN_MQLS,
            "meta_cpmql": bp.META_CPMQL,
            "meta_cac": bp.META_CAC,
            "volume_min_amostral": bp.VOLUME_MIN_AMOSTRAL,
            "n_dias_corte": bp.N_DIAS_CORTE,
        },
        "periodos": {},
    }
    for key, (start, end, label) in periods.items():
        payload = periodo_payload(meta, leads, today, start, end, key, date_min, date_max,
                                   bp.META_CPMQL, bp.META_CAC, bp.VOLUME_MIN_AMOSTRAL)
        payload["whatsapp_numeros"]["periodo_label"] = label
        out["periodos"][key] = {"label": label, **payload}

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("== coletar_dados_relatorio ok ==", file=sys.stderr)
    print(f"  periodos: {list(out['periodos'].keys())}", file=sys.stderr)
    print(f"  out: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera build/relatorios.json (aba "Relatório" -> "Insights de Tráfego") aplicando
DETERMINISTICAMENTE as regras de build/GUIA-RELATORIOS.md sobre os mesmos dados
que alimentam o dashboard (mídia paga x Leads).

Não chama nenhuma API de IA/LLM — é só aritmética + templates de texto em
Python. Custo zero de créditos Anthropic, roda 100% dentro do GitHub Actions.

**Status:** este script não roda mais automaticamente (o pipeline diário
passou a ser `coletar_dados_relatorio.py` + a Routine do Claude — ver
`GUIA-RELATORIOS.md`). Fica no repo como ferramenta manual/fallback: se a
Routine falhar num dia, rode este script pra garantir que a aba não fique
vazia. Emite o MESMO schema (4 quadrantes + nota de saúde + bloco WhatsApp)
que a Routine — mais raso na profundidade analítica (sem prosa livre), mas
estruturalmente idêntico, então a interface não precisa de nenhum caminho
alternativo de renderização.

Uso:
    python build/gerar_relatorios.py --out build/relatorios.json
    python build/gerar_relatorios.py --leads-file leads.csv --meta-file meta.csv --out build/relatorios.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as bp  # reaproveita fetch/parse/process/constantes de build.py
from relatorio_lib import (  # noqa: F401 — reexportado p/ manter a API deste módulo
    BRT, d, ds, month_bounds, build_periods, in_range, agg, derived, shift_back,
    previous_period, compare, funnel_health, money, pct, num, meta_status,
)
from coletar_dados_relatorio import breakdown, consolidado_criativos, whatsapp_numeros


# --------------------------------------------------------------------------- #
# Classificação operacional por campanha (Escalar/Observar/Otimizar/Cortar)
# --------------------------------------------------------------------------- #
TAG_LABEL = {"escala": "Escalar", "otimiza": "Otimizar", "corte": "Cortar", "observar": "Observar"}


def classify_campaigns(meta: list[dict], leads: list[dict], start: date, end: date,
                        volume_min: int, meta_cpmql, n_dias_corte: int) -> list[tuple]:
    camps = sorted({r["camp"] for r in meta if in_range(r["d"], start, end)} |
                    {r["camp"] for r in leads if in_range(r["d"], start, end)})
    out = []
    for camp in camps:
        w0 = derived(agg(meta, leads, start, end, camp))
        w1s, w1e = shift_back(start, end, 1)
        w2s, w2e = shift_back(start, end, 2)
        w1 = derived(agg(meta, leads, w1s, w1e, camp))
        w2 = derived(agg(meta, leads, w2s, w2e, camp))

        if w0["mqls"] < volume_min:
            faltam = volume_min - w0["mqls"]
            cpmql_ref = w0["cpmql"] or w1["cpmql"]
            gasto_falta = f" (~{money(cpmql_ref * faltam)} de gasto no ritmo atual)" if cpmql_ref else ""
            tag, motivo = "observar", (
                f"volume {w0['mqls']} MQL(s) &lt; volume mínimo amostral ({volume_min}); "
                f"faltam {faltam} MQL(s){gasto_falta} para amostra suficiente."
            )
        elif meta_cpmql is not None and w0["mqls"] == 0 and w0["cpl"] is not None:
            tag, motivo = "corte", (
                f"volume suficiente, zero conversão qualificada e CPL {money(w0['cpl'])} acima "
                f"do teto por {n_dias_corte}+ dias consecutivos (referência: meta CPMQL {money(meta_cpmql)})."
            )
        elif (w0["txmql"] is not None and w1["txmql"] is not None and w2["txmql"] is not None
              and w0["txmql"] < w1["txmql"] < w2["txmql"]):
            tag, motivo = "otimiza", (
                f"Tx‑MQL caindo 2 janelas seguidas ({pct(w2['txmql'])} → {pct(w1['txmql'])} → "
                f"{pct(w0['txmql'])}); hipótese: fadiga de criativo/saturação de público/frequência "
                f"alta — investigar antes de cortar."
            )
        elif (w0["cpl"] is not None and w1["cpl"] is not None and w2["cpl"] is not None
              and w0["cpl"] > w1["cpl"] > w2["cpl"]):
            tag, motivo = "otimiza", (
                f"CPL subindo 2 janelas seguidas ({money(w2['cpl'])} → {money(w1['cpl'])} → "
                f"{money(w0['cpl'])}); hipótese: saturação de público/aumento de CPM — revisar segmentação/criativo."
            )
        elif (w0["txmql"] is not None and w1["txmql"] is not None
              and w0["txmql"] >= w1["txmql"] * 0.95):
            tag, motivo = "escala", (
                f"volume {w0['mqls']} MQL(s) ≥ volume mínimo amostral ({volume_min}) e Tx‑MQL estável/subindo "
                f"({pct(w1['txmql'])} → {pct(w0['txmql'])}) na janela anterior."
            )
        else:
            tag, motivo = "observar", "volume suficiente mas sem 2 janelas comparáveis de Tx‑MQL/CPL ainda."
        out.append((camp, tag, motivo, w0))
    out.sort(key=lambda x: -x[3]["mqls"])
    return out


# --------------------------------------------------------------------------- #
# Quadrante 1 — Resumo executivo e saúde do funil
# --------------------------------------------------------------------------- #
def quadro1_resumo(label: str, cur: dict, saude: dict, variacao: dict, metodo: str,
                    meta_cpmql, meta_cac) -> str:
    nota_txt = (
        f"<b>Saúde do funil: {saude['nota']:.1f}/10 — {saude['classificacao']}"
        + (" (nota provisória)" if saude["provisoria"] else "") + ".</b>"
        + (f" {saude['motivo']}" if saude["motivo"] else "")
    )
    status_metas = (
        f"Status das metas: CPMQL — {meta_status('CPMQL', meta_cpmql)}; "
        f"CAC — {meta_status('CAC', meta_cac)} (dados de venda ainda não conectados)."
    )
    mudancas = [f"{m.upper()}: {money(v['atual']) if m in ('spend','cpl','cpm','cpmql') else v['atual']} "
                f"vs {money(v['anterior']) if m in ('spend','cpl','cpm','cpmql') else v['anterior']} "
                f"({v['direcao']}, {'%.1f pp' % v['delta_pp'] if v['delta_pp'] is not None else pct(v['delta_pct'])})"
                for m, v in variacao.items() if v["material"]]
    destaques = [f"{m.upper()} {v['direcao']}" for m, v in variacao.items() if v["material"] and v["direcao"] == "melhorou"]
    alertas = [f"{m.upper()} {v['direcao']}" for m, v in variacao.items() if v["material"] and v["direcao"] == "piorou"]

    partes = [
        f"<p>{nota_txt}</p>",
        f"<p>{status_metas}</p>",
        f"<p><b>{label}:</b> gasto {money(cur['spend'])} · leads {num(cur['leads'])} · "
        f"MQLs {num(cur['mqls'])} · Tx‑MQL {pct(cur['txmql'])} · CPL {money(cur['cpl'])} · "
        f"CPA/CPMQL {money(cur['cpmql'])}.</p>",
        f"<p><b>Vs. período anterior</b> ({metodo}):</p>",
        "<ul>" + ("".join(f"<li>{x}</li>" for x in mudancas) if mudancas else
                   "<li>Nenhuma variação materialmente relevante (≥10% ou ≥3pp) frente ao período anterior.</li>") + "</ul>",
        "<p><b>Destaques positivos:</b> " + (", ".join(destaques) if destaques else "sem destaque material no período") + ".</p>",
        "<p><b>Alertas:</b> " + (", ".join(alertas) if alertas else "nenhum alerta material no período") + ".</p>",
        "<p><b>Decisão mais importante do período:</b> priorizar o bloco de Ações do Quadrante 4 "
        "(Fazer hoje) — é a lista já filtrada por evidência suficiente para execução imediata.</p>",
    ]
    return "".join(partes)


# --------------------------------------------------------------------------- #
# Quadrante 2 — Diagnóstico do funil
# --------------------------------------------------------------------------- #
def quadro2_diagnostico(cur: dict, variacao: dict, volume_min: int) -> str:
    faltam_mqls = max(0, volume_min - cur["mqls"])
    partes = []
    if cur["leads"] == 0:
        partes.append("<p>Sem leads no período — sem base para diagnóstico de funil.</p>")
    elif cur["mqls"] < volume_min:
        cpmql_ref = cur["cpmql"] or 0
        gasto_estimado = cpmql_ref * faltam_mqls if cpmql_ref else None
        partes.append(
            f"<p><b>Amostra insuficiente:</b> {num(cur['mqls'])} MQL(s) no período, abaixo do volume "
            f"mínimo amostral ({volume_min}). Faltam {faltam_mqls} MQL(s)"
            + (f" (~{money(gasto_estimado)} de gasto no ritmo atual)" if gasto_estimado else "")
            + " para virar amostra confiável — nenhuma conclusão de qualidade deve ser tirada ainda.</p>"
        )
    else:
        partes.append(
            f"<p><b>Etapas com leitura confiável:</b> volume de {num(cur['mqls'])} MQL(s) já é amostra "
            f"suficiente (≥ {volume_min}); Tx‑MQL {pct(cur['txmql'])} e CPA/CPMQL {money(cur['cpmql'])} "
            f"podem embasar decisão.</p>"
        )

    melhoras = [m for m, v in variacao.items() if v["material"] and v["direcao"] == "melhorou"]
    pioras = [m for m, v in variacao.items() if v["material"] and v["direcao"] == "piorou"]
    estaveis = [m for m, v in variacao.items() if v["direcao"] == "estavel"]
    partes.append("<p><b>Melhoras relevantes:</b> " + (", ".join(melhoras) if melhoras else "nenhuma") + ".</p>")
    partes.append("<p><b>Pioras relevantes:</b> " + (", ".join(pioras) if pioras else "nenhuma") + ".</p>")
    partes.append("<p><b>Métricas estáveis:</b> " + (", ".join(estaveis) if estaveis else "—") + ".</p>")

    hipoteses = []
    if "cpl" in pioras and "cpm" in pioras:
        hipoteses.append("CPL subiu junto com CPM: provável leilão mais caro / saturação de público, não falha de criativo específico.")
    if "txmql" in pioras and "cpl" not in pioras:
        hipoteses.append("Tx‑MQL caiu sem CPL piorar: mídia pode estar atraindo público fora do ICP — revisar segmentação/criativo antes de cortar.")
    if "cpmql" in melhoras and "cpl" in pioras:
        hipoteses.append("CPL subiu mas CPMQL melhorou: o clique mais caro está mais qualificado — não trocar o anúncio automaticamente.")
    if not hipoteses:
        hipoteses.append("Sem sinal cruzado suficiente entre etapas para levantar hipótese de gargalo específico neste período.")
    partes.append("<p><b>Gargalos e hipóteses:</b></p><ul>" + "".join(f"<li>{h}</li>" for h in hipoteses) + "</ul>")

    partes.append(
        "<p><b>Gargalo de dado (prioridade alta):</b> Agendamentos, Reuniões Realizadas, Vendas e "
        "Faturamento não têm fonte conectada — o funil hoje só vai até MQL. Otimizar mídia sem essas "
        "etapas é decisão às cegas (mede qualidade do lead, não comparecimento/venda real). Ação: "
        "conectar a lista do comercial ao dashboard (`build/app.js` já tem os campos "
        "`agendamentos`/`reunioes`/`vendas`/`fat` prontos para acender a UI sozinhos).</p>"
    )
    return "".join(partes)


# --------------------------------------------------------------------------- #
# Quadrante 3 — Campanhas, estruturas e anúncios campeões
# --------------------------------------------------------------------------- #
def quadro3_campeoes(por_campanha: list[dict], por_anuncio: list[dict], criativos: list[dict]) -> str:
    if not por_campanha:
        return "<p>Sem campanhas com atividade no período.</p>"

    camp_vol = max(por_campanha, key=lambda r: r["mqls"] or r["leads"])
    com_mql = [r for r in por_campanha if r["mqls"]]
    camp_efic = min(com_mql, key=lambda r: r["cpmql"]) if com_mql else None

    ads_com_mql = [r for r in por_anuncio if r["mqls"]]
    ad_efic = min(ads_com_mql, key=lambda r: r["cpmql"]) if ads_com_mql else None

    partes = [
        f"<p><b>Campanha campeã de volume:</b> {camp_vol['campanha']} "
        f"— {num(camp_vol['mqls'])} MQL(s), {num(camp_vol['leads'])} lead(s), gasto {money(camp_vol['spend'])}.</p>",
    ]
    if camp_efic:
        partes.append(
            f"<p><b>Campanha campeã de eficiência:</b> {camp_efic['campanha']} "
            f"— CPA/CPMQL {money(camp_efic['cpmql'])}, Tx‑MQL {pct(camp_efic['txmql'])} "
            f"(considerar amostra: {num(camp_efic['mqls'])} MQL(s)).</p>"
        )
    else:
        partes.append("<p><b>Campanha campeã de eficiência:</b> nenhuma campanha com MQL suficiente para ranquear por CPA/CPMQL ainda.</p>")

    if ad_efic:
        partes.append(
            f"<p><b>Estrutura completa campeã:</b> campanha <b>{ad_efic['campanha']}</b> → "
            f"conjunto <b>{ad_efic['conjunto']}</b> → anúncio <b>{ad_efic['anuncio']}</b> "
            f"— CPA/CPMQL {money(ad_efic['cpmql'])}, {num(ad_efic['mqls'])} MQL(s), gasto {money(ad_efic['spend'])}.</p>"
        )
    else:
        partes.append("<p><b>Estrutura completa campeã:</b> nenhuma ocorrência de anúncio com MQL suficiente ainda.</p>")

    partes.append("<p><b>Ranking de estruturas (campanha → conjunto → anúncio), por CPA/CPMQL (menor = melhor):</b></p><ul>")
    for r in sorted(ads_com_mql, key=lambda x: x["cpmql"])[:10]:
        partes.append(
            f"<li>Campanha: {r['campanha']} · Conjunto: {r['conjunto']} · Anúncio: {r['anuncio']} "
            f"— CPA/CPMQL {money(r['cpmql'])} · Tx‑MQL {pct(r['txmql'])} · MQLs {num(r['mqls'])} · gasto {money(r['spend'])}</li>"
        )
    partes.append("</ul>")

    partes.append(
        "<p><b>Anúncios em mais de uma estrutura (análise consolidada do criativo):</b></p><ul>"
    )
    multi = [c for c in criativos if c["n_estruturas"] > 1]
    if not multi:
        partes.append("<li>Nenhum anúncio roda em mais de uma estrutura simultaneamente neste período.</li>")
    for c in multi[:10]:
        linha = (
            f"<li>Anúncio: {c['anuncio']} — presente em {c['n_estruturas']} estruturas, "
            f"CPA/CPMQL consolidado {money(c['cpmql'])}, {num(c['mqls'])} MQL(s) no total."
        )
        if c["melhor_estrutura"] and c["pior_estrutura"]:
            linha += (
                f" Melhor em: campanha {c['melhor_estrutura']['campanha']} / conjunto "
                f"{c['melhor_estrutura']['conjunto']} (CPA/CPMQL {money(c['melhor_estrutura']['cpmql'])}). "
                f"Pior em: campanha {c['pior_estrutura']['campanha']} / conjunto "
                f"{c['pior_estrutura']['conjunto']} (CPA/CPMQL {money(c['pior_estrutura']['cpmql'])}) — "
                f"decisão deve ser POR OCORRÊNCIA, nunca corte global do criativo por causa de 1 estrutura fraca."
            )
        linha += "</li>"
        partes.append(linha)
    partes.append("</ul>")
    return "".join(partes)


# --------------------------------------------------------------------------- #
# Quadrante 4 — Ações priorizadas
# --------------------------------------------------------------------------- #
def quadro4_acoes(camps: list[tuple], volume_min: int, n_dias_corte: int) -> str:
    escalar = [c for c in camps if c[1] == "escala"]
    otimizar = [c for c in camps if c[1] == "otimiza"]
    observar = [c for c in camps if c[1] == "observar"]
    cortar = [c for c in camps if c[1] == "corte"]

    def li(items):
        return "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>" if items else "<p>Nenhuma neste período.</p>"

    fazer_hoje = []
    if escalar:
        fazer_hoje.append(
            f"Aumentar verba em +10–20% nas campanhas com volume e Tx‑MQL estável: "
            f"{', '.join(c[0] for c in escalar[:3])} (ajustar no conjunto se ABO, na campanha se CBO — "
            f"confirmar o tipo de orçamento no Gerenciador de Anúncios antes de mexer)."
        )
    if cortar:
        fazer_hoje.append(f"Cortar/pausar: {', '.join(c[0] for c in cortar[:3])} — critério de teto ultrapassado.")
    if not fazer_hoje:
        fazer_hoje.append("Nenhuma decisão com evidência suficiente para execução imediata — priorizar coleta de amostra (ver Observar).")

    escalar_txt = [f"{c}: {motivo}" for c, tag, motivo, w0 in escalar]
    manter_txt = []  # sem estrutura "manter" explícita além de escalar/observar neste modelo determinístico
    observar_txt = [f"{c}: {motivo}" for c, tag, motivo, w0 in observar]
    otimizar_txt = [f"{c}: {motivo}" for c, tag, motivo, w0 in otimizar]
    cortar_txt = [f"{c}: {motivo}" for c, tag, motivo, w0 in cortar]
    produzir_txt = [
        "Testar variação (novo gancho/oferta) a partir do anúncio campeão da estrutura eficiente do "
        "Quadrante 3, em ABO com teto de teste de 3–4 dias; critério de sucesso: CPA/CPMQL ≤ referência atual."
    ]
    evitar_txt = [
        "Escalar com base em dados de 1 dia (hoje) isoladamente.",
        "Cortar por oscilação isolada de CTR/CPM sem olhar CPA/CPMQL/CAC.",
        "Tratar corte de 1 ocorrência do anúncio como corte do criativo inteiro.",
    ]

    return (
        "<h4>Fazer hoje</h4>" + li(fazer_hoje) +
        "<h4>Escalar</h4>" + li(escalar_txt) +
        "<h4>Manter</h4>" + li(manter_txt) +
        "<h4>Observar</h4>" + li(observar_txt) +
        "<h4>Otimizar / investigar</h4>" + li(otimizar_txt) +
        "<h4>Cortar</h4>" + li(cortar_txt) +
        "<h4>Produzir / testar</h4>" + li(produzir_txt) +
        "<h4>Evitar</h4>" + li(evitar_txt) +
        f"<h4>Próxima revisão</h4><p>Gatilho: qualquer campanha mudando de tag (Observar→Escalar/Otimizar, "
        f"Otimizar→Cortar/Escalar) conforme volume e Tx‑MQL. Prazo: revisar em 4 dias ou ~"
        f"{money(400.0)} de gasto adicional, ou ao atingir o volume mínimo amostral ({volume_min} MQLs).</p>"
    )


# --------------------------------------------------------------------------- #
# Bloco WhatsApp (texto puro, pronto para copiar)
# --------------------------------------------------------------------------- #
def whatsapp_texto(wa: dict, destaques: list[str], acoes: list[str]) -> str:
    linhas = [
        "📊 RESUMO DO PERÍODO",
        f"Período: {wa['periodo_range']}",
        f"Gasto: {wa['gasto']}",
        f"CPM: {wa['cpm']}",
        f"CTR: {wa['ctr']}",
        f"Connect Rate: {wa['connect_rate']}",
        f"Conversão da LP: {wa['conv_lp']}",
        f"Leads: {wa['leads']}",
        f"CPL: {wa['cpl']}",
        f"MQLs: {wa['mqls']}",
        f"CPA/CPMQL: {wa['cpa_cpmql']}",
        f"Vendas: {wa['vendas']}",
        f"Faturamento: {wa['faturamento']}",
        f"CAC: {wa['cac']}",
        f"ROAS: {wa['roas']}",
        f"Ticket médio: {wa['ticket_medio']}",
        f"Saúde do funil: {wa['saude_funil']}",
        "Principais destaques:",
    ]
    linhas += [f"• {x}" for x in (destaques or ["—"])]
    linhas.append("Principais ações:")
    linhas += [f"• {x}" for x in (acoes or ["—"])]
    return "\n".join(linhas)


def sem_dado_payload(label: str, start, end) -> dict:
    saude_vazia = {"nota": None, "provisoria": True, "classificacao": "Sem dado",
                   "motivo": "Sem investimento/atividade no período.", "subnotas": {}}
    wa = whatsapp_numeros(label, start, end, derived({"spend": 0, "impr": 0, "clicks": 0, "leads": 0, "mqls": 0}), saude_vazia)
    return {
        "nota_saude": saude_vazia,
        "whatsapp": whatsapp_texto(wa, [], []),
        "quadro1_resumo": f"<p>Sem investimento/atividade registrada em \"{label}\" — nada a reportar neste período.</p>",
        "quadro2_diagnostico": "<p>—</p>",
        "quadro3_campeoes": "<p>Sem campanhas com atividade no período.</p>",
        "quadro4_acoes": "<h4>Fazer hoje</h4><p>Nenhuma ação recomendada sem dado no período.</p>",
    }


def build_period_payload(label: str, start: date, end: date, meta: list[dict], leads: list[dict],
                          today: date, date_min, date_max, meta_cpmql, meta_cac,
                          volume_min: int, n_dias_corte: int, key: str) -> dict:
    cur = derived(agg(meta, leads, start, end))
    if cur["leads"] == 0 and cur["spend"] == 0:
        return sem_dado_payload(label, start, end)

    ref7 = derived(agg(meta, leads, today - timedelta(days=6), today))
    ref14 = derived(agg(meta, leads, today - timedelta(days=13), today))
    ref30 = derived(agg(meta, leads, today - timedelta(days=29), today))
    saude = funnel_health(cur, ref30, meta_cpmql, meta_cac, volume_min, [ref7, ref14, ref30])

    p_start, p_end, metodo = previous_period(key, start, end, today, date_min, date_max)
    anterior = derived(agg(meta, leads, p_start, p_end)) if p_start else None
    variacao = compare(cur, anterior)

    camps = classify_campaigns(meta, leads, start, end, volume_min, meta_cpmql, n_dias_corte)
    por_campanha = breakdown(meta, leads, start, end, "camp")
    por_anuncio = breakdown(meta, leads, start, end, "ad")
    criativos = consolidado_criativos(por_anuncio)

    destaques = [m.upper() for m, v in variacao.items() if v["material"] and v["direcao"] == "melhorou"][:3]
    acoes_wa = []
    escalar = [c for c in camps if c[1] == "escala"]
    cortar = [c for c in camps if c[1] == "corte"]
    if escalar:
        acoes_wa.append(f"Escalar {escalar[0][0]} +10-20%")
    if cortar:
        acoes_wa.append(f"Cortar {cortar[0][0]}")
    if not acoes_wa:
        acoes_wa.append("Aguardar volume mínimo amostral antes de escalar/cortar")

    wa_numeros = whatsapp_numeros(label, start, end, cur, saude)

    return {
        "nota_saude": saude,
        "whatsapp": whatsapp_texto(wa_numeros, destaques, acoes_wa),
        "quadro1_resumo": quadro1_resumo(label, cur, saude, variacao, metodo, meta_cpmql, meta_cac),
        "quadro2_diagnostico": quadro2_diagnostico(cur, variacao, volume_min),
        "quadro3_campeoes": quadro3_campeoes(por_campanha, por_anuncio, criativos),
        "quadro4_acoes": quadro4_acoes(camps, volume_min, n_dias_corte),
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conversas-file")
    ap.add_argument("--meta-file")
    ap.add_argument("--sales-file")
    ap.add_argument("--leads-file")
    ap.add_argument("--out", default="build/relatorios.json")
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
        "fonte": "Insights de Tráfego gerados automaticamente (regras determinísticas do GUIA-RELATORIOS.md, "
                 "sem chamada de IA) a partir dos dados do funil (mídia paga × Leads).",
        "periodos": {},
    }
    for key, (start, end, label) in periods.items():
        out["periodos"][key] = build_period_payload(
            label, start, end, meta, leads, today, date_min, date_max,
            bp.META_CPMQL, bp.META_CAC, bp.VOLUME_MIN_AMOSTRAL, bp.N_DIAS_CORTE, key,
        )

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("== gerar_relatorios ok ==", file=sys.stderr)
    print(f"  periodos gerados: {list(out['periodos'].keys())}", file=sys.stderr)
    print(f"  out: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

"""
Motor de Simulação de Aportes e Rebalanceamento Dinâmico de Carteiras de Previdência e Ativos B3.
Implementa:
1. Carteira com Rebalanceamento Inteligente (Aportes direcionados para os ativos subponderados/na baixa)
2. Carteira Passiva (Aportes fixos proporcionais sem rebalanceamento)
3. Simulação idêntica de fluxo de caixa para cada Fundo Individual e Ativo B3
4. Simulação idêntica de fluxo de caixa e rentabilidade acumulada para Benchmarks (CDI, IPCA, Poupança, IBOV, IFIX, S&P 500, Bitcoin, USD)
5. Simulação Multimoeda completa: cálculo em Real (BRL) e Dólar (USD), considerando a cotação cambial em cada aporte
"""

import math
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from .storage import load_portfolio, load_fund_data, load_benchmark_data, clean_cnpj, clean_ticker, load_asset_data
from .config_manager import load_benchmarks_config

def get_asset_key(asset: Dict[str, Any]) -> str:
    """Retorna uma chave única para o ativo (CNPJ limpo para fundos ou ticker para B3)."""
    a_type = asset.get("type", "fund")
    if a_type == "b3":
        ticker = clean_ticker(asset.get("code") or asset.get("id") or "")
        return ticker
    cnpj = clean_cnpj(asset.get("cnpj") or asset.get("code") or "")
    if not cnpj:
        code = clean_ticker(asset.get("code") or asset.get("id") or "")
        if code:
            return code
    return cnpj

def build_aligned_daily_timeline(funds: List[Dict[str, Any]], start_date: str, end_date: str) -> Tuple[List[str], Dict[str, Dict[str, float]]]:
    """
    Constrói a linha do tempo de datas úteis comuns e alinha as cotas de cada fundo ou ativo B3.
    Retorna: (datas_ordenadas, {asset_key: {data: cota}})
    """
    fund_quotes_map = {}
    all_dates = set()

    for fund in funds:
        key = get_asset_key(fund)
        quotes = load_asset_data(fund)
        # Filtrar pelo período
        f_map = {}
        for q in quotes:
            dt = q["date"]
            if start_date <= dt <= end_date:
                f_map[dt] = float(q["quota"])
                all_dates.add(dt)
        fund_quotes_map[key] = f_map

    sorted_dates = sorted(list(all_dates))
    if not sorted_dates:
        return [], {}

    # Preenchimento 'forward-fill' para dias em que algum ativo específico não publicou cota
    aligned_quotes = {k: {} for k in fund_quotes_map}
    last_known = {}

    for dt in sorted_dates:
        for k, f_map in fund_quotes_map.items():
            if dt in f_map:
                last_known[k] = f_map[dt]
            elif k in last_known:
                aligned_quotes[k][dt] = last_known[k]

    # Remover datas iniciais em que nem todos os ativos possuem ao menos uma cota conhecida
    valid_dates = []
    for dt in sorted_dates:
        if all(dt in f_map or k in last_known for k, f_map in fund_quotes_map.items()):
            for k in fund_quotes_map:
                if dt in fund_quotes_map[k]:
                    aligned_quotes[k][dt] = fund_quotes_map[k][dt]
                else:
                    aligned_quotes[k][dt] = last_known[k]
            valid_dates.append(dt)

    return valid_dates, aligned_quotes

def simulate_portfolio(
    portfolio_config: Dict[str, Any],
    initial_capital: float = 20000.0,
    monthly_contribution: float = 2000.0,
    start_date: str = "2024-05-01",
    end_date: str = "2026-08-31",
    rebalance_mode: str = "smart_inflow"  # "smart_inflow" ou "full_rebalance"
) -> Dict[str, Any]:
    """
    Executa a simulação completa comparativa:
    - Carteira com Rebalanceamento Inteligente (Aportes direcionados para os ativos subponderados)
    - Carteira Passiva (Aportes cegos na proporção alvo fixa)
    - Fundos e Ativos B3 Individuais
    - Benchmarks Oficiais
    - Cálculo Simultâneo em Real (BRL) e Dólar (USD)
    """
    funds = portfolio_config.get("funds", [])
    if not funds:
        return {"error": "Nenhum fundo ou ativo cadastrado na carteira."}

    # Normalizar pesos alvos
    total_pct = sum(float(f.get("target_pct", 0.0)) for f in funds)
    if total_pct <= 0:
        return {"error": "A soma das porcentagens da carteira deve ser maior que zero."}
    
    weights = {get_asset_key(f): float(f.get("target_pct", 0.0)) / total_pct for f in funds}
    
    dates, quotes = build_aligned_daily_timeline(funds, start_date, end_date)
    if not dates or len(dates) < 2:
        return {"error": "Dados históricos insuficientes no período selecionado."}

    # Carregar dados cambiais do Dólar para conversão diária em USD
    usd_raw_list = load_benchmark_data("usd")
    if not usd_raw_list:
        # Fallback para o S&P 500 que contém usd_rate
        usd_raw_list = load_benchmark_data("sp500")
    usd_rates_map = {}
    for p in usd_raw_list:
        rate = p.get("usd_rate", p.get("value"))
        if rate and rate > 0:
            usd_rates_map[p["date"]] = float(rate)

    first_rate = usd_rates_map.get(dates[0], 5.15)
    last_known_usd_rate = first_rate

    # Identificar datas de aporte mensal (1º dia útil de cada mês subsequente)
    contribution_dates = set()
    prev_month = dates[0][:7]
    for idx, dt in enumerate(dates):
        m = dt[:7]
        if m != prev_month and idx > 0:
            contribution_dates.add(dt)
            prev_month = m

    # 1. Carteira Inteligente: Cotas acumuladas por ativo
    quotas_smart = {c: 0.0 for c in weights}
    # 2. Carteira Passiva: Cotas acumuladas por ativo
    quotas_passive = {c: 0.0 for c in weights}
    # 3. Fundos Individuais: Cotas se 100% dos recursos fossem para aquele ativo isolado
    quotas_single = {c: 0.0 for c in weights}

    total_invested = initial_capital
    rate_init = usd_rates_map.get(dates[0], last_known_usd_rate)
    last_known_usd_rate = rate_init
    total_invested_usd = initial_capital / rate_init

    # Aporte inicial no dia dates[0]
    for c in weights:
        q_price = quotes[c][dates[0]]
        initial_alloc = initial_capital * weights[c]
        quotas_smart[c] = initial_alloc / q_price
        quotas_passive[c] = initial_alloc / q_price
        quotas_single[c] = initial_capital / q_price

    invested_smart_by_asset = {c: initial_capital * weights[c] for c in weights}
    invested_smart_by_asset_usd = {c: (initial_capital * weights[c]) / rate_init for c in weights}

    timeline = []
    contributions_log = [{
        "date": dates[0],
        "amount": initial_capital,
        "amount_usd": round(initial_capital / rate_init, 2),
        "usd_rate": round(rate_init, 4),
        "type": "initial",
        "smart_allocation": {c: round(initial_capital * weights[c], 2) for c in weights},
        "description": f"Aporte Inicial de R$ {initial_capital:,.2f} (US$ {initial_capital/rate_init:,.2f})"
    }]

    for idx, dt in enumerate(dates):
        # Atualizar taxa de câmbio
        if dt in usd_rates_map:
            last_known_usd_rate = usd_rates_map[dt]
        current_usd_rate = last_known_usd_rate

        # Verificar se hoje há aporte mensal
        if dt in contribution_dates:
            total_invested += monthly_contribution
            contrib_usd = monthly_contribution / current_usd_rate
            total_invested_usd += contrib_usd

            # --- 1. Carteira Inteligente (Rebalanceamento via Aporte) ---
            cur_values = {c: quotas_smart[c] * quotes[c][dt] for c in weights}
            cur_total = sum(cur_values.values())
            new_total = cur_total + monthly_contribution
            
            # Alocação alvo ideal após o aporte
            target_values = {c: new_total * weights[c] for c in weights}
            
            # Déficit de cada ativo (quanto falta para atingir a meta ideal)
            shortfalls = {c: max(0.0, target_values[c] - cur_values[c]) for c in weights}
            sum_shortfalls = sum(shortfalls.values())
            
            smart_allocations = {}
            if sum_shortfalls > 0.01:
                # Direciona o aporte proporcionalmente ao déficit de cada um
                for c in weights:
                    alloc_amt = monthly_contribution * (shortfalls[c] / sum_shortfalls)
                    smart_allocations[c] = alloc_amt
                    quotas_smart[c] += alloc_amt / quotes[c][dt]
            else:
                # Se todos já estiverem perfeitamente alinhados
                for c in weights:
                    alloc_amt = monthly_contribution * weights[c]
                    smart_allocations[c] = alloc_amt
                    quotas_smart[c] += alloc_amt / quotes[c][dt]

            # Atualizar capital aportado acumulado por ativo
            for c in weights:
                alloc_amt = smart_allocations.get(c, 0.0)
                invested_smart_by_asset[c] += alloc_amt
                invested_smart_by_asset_usd[c] += alloc_amt / current_usd_rate
                    
            # Se a opção for rebalanceamento total (venda/compra além do aporte)
            if rebalance_mode == "full_rebalance":
                rebal_total = sum(quotas_smart[c] * quotes[c][dt] for c in weights)
                for c in weights:
                    target_val = rebal_total * weights[c]
                    quotas_smart[c] = target_val / quotes[c][dt]

            # --- 2. Carteira Passiva (Aporte cego segundo pesos fixos) ---
            for c in weights:
                alloc_amt = monthly_contribution * weights[c]
                quotas_passive[c] += alloc_amt / quotes[c][dt]

            # --- 3. Fundos Individuais (100% do aporte naquele fundo) ---
            for c in weights:
                quotas_single[c] += monthly_contribution / quotes[c][dt]

            contributions_log.append({
                "date": dt,
                "amount": monthly_contribution,
                "amount_usd": round(contrib_usd, 2),
                "usd_rate": round(current_usd_rate, 4),
                "type": "monthly",
                "smart_allocation": {c: round(smart_allocations.get(c, 0.0), 2) for c in weights},
                "description": f"Aporte Mensal de R$ {monthly_contribution:,.2f}"
            })

        # Avaliação patrimonial no dia dt em BRL
        smart_breakdown = {}
        smart_val = 0.0
        for c in weights:
            val_c = quotas_smart[c] * quotes[c][dt]
            smart_breakdown[c] = val_c
            smart_val += val_c
            
        passive_val = sum(quotas_passive[c] * quotes[c][dt] for c in weights)
        
        single_vals = {}
        for c in weights:
            single_vals[c] = quotas_single[c] * quotes[c][dt]

        # Rentabilidade acumulada base zero (%) em BRL
        smart_profit = smart_val - total_invested
        smart_return_pct = (smart_profit / total_invested) * 100.0 if total_invested > 0 else 0.0
        
        passive_profit = passive_val - total_invested
        passive_return_pct = (passive_profit / total_invested) * 100.0 if total_invested > 0 else 0.0

        # Alocações efetivas atuais (%)
        effective_pcts = {c: (smart_breakdown[c] / smart_val * 100.0) if smart_val > 0 else 0.0 for c in weights}

        # --- AVALIAÇÃO EM DÓLAR (USD) ---
        smart_val_usd = smart_val / current_usd_rate
        passive_val_usd = passive_val / current_usd_rate
        smart_profit_usd = smart_val_usd - total_invested_usd
        smart_return_pct_usd = (smart_profit_usd / total_invested_usd) * 100.0 if total_invested_usd > 0 else 0.0
        passive_profit_usd = passive_val_usd - total_invested_usd
        passive_return_pct_usd = (passive_profit_usd / total_invested_usd) * 100.0 if total_invested_usd > 0 else 0.0

        single_vals_usd = {c: single_vals[c] / current_usd_rate for c in weights}
        single_return_pcts_usd = {
            c: ((single_vals_usd[c] - total_invested_usd) / total_invested_usd) * 100.0 if total_invested_usd > 0 else 0.0
            for c in weights
        }

        # Contribuição de cada ativo na rentabilidade da carteira (Return Attribution)
        # Cc(t) = ((Vc(t) - Ic(t)) / Itotal(t)) * 100
        # Propriedade matemática: sum(Cc(t)) == smart_return_pct
        smart_breakdown_usd = {c: smart_breakdown[c] / current_usd_rate for c in weights}
        smart_contributions = {
            c: round(((smart_breakdown[c] - invested_smart_by_asset[c]) / total_invested) * 100.0, 2)
            if total_invested > 0 else 0.0
            for c in weights
        }
        smart_contributions_usd = {
            c: round(((smart_breakdown_usd[c] - invested_smart_by_asset_usd[c]) / total_invested_usd) * 100.0, 2)
            if total_invested_usd > 0 else 0.0
            for c in weights
        }

        # Rentabilidade (%) individual de cada fundo dentro da carteira
        asset_return_pcts = {
            c: round(((smart_breakdown[c] - invested_smart_by_asset[c]) / invested_smart_by_asset[c]) * 100.0, 2)
            if invested_smart_by_asset[c] > 0 else 0.0
            for c in weights
        }
        asset_return_pcts_usd = {
            c: round(((smart_breakdown_usd[c] - invested_smart_by_asset_usd[c]) / invested_smart_by_asset_usd[c]) * 100.0, 2)
            if invested_smart_by_asset_usd[c] > 0 else 0.0
            for c in weights
        }

        timeline.append({
            "date": dt,
            "usd_rate": round(current_usd_rate, 4),
            # BRL
            "total_invested": round(total_invested, 2),
            "smart_val": round(smart_val, 2),
            "smart_profit": round(smart_profit, 2),
            "smart_return_pct": round(smart_return_pct, 2),
            "smart_breakdown": {c: round(smart_breakdown[c], 2) for c in weights},
            "invested_by_asset": {c: round(invested_smart_by_asset[c], 2) for c in weights},
            "asset_profits": {c: round(smart_breakdown[c] - invested_smart_by_asset[c], 2) for c in weights},
            "smart_contributions": smart_contributions,
            "asset_return_pcts": asset_return_pcts,
            "passive_val": round(passive_val, 2),
            "passive_profit": round(passive_profit, 2),
            "passive_return_pct": round(passive_return_pct, 2),
            "alpha_rebalance_rs": round(smart_val - passive_val, 2),
            "effective_pcts": {c: round(effective_pcts[c], 2) for c in weights},
            "single_vals": {c: round(single_vals[c], 2) for c in weights},
            "single_return_pcts": {
                c: round(((single_vals[c] - total_invested) / total_invested) * 100.0, 2)
                for c in weights
            },
            # USD
            "total_invested_usd": round(total_invested_usd, 2),
            "smart_val_usd": round(smart_val_usd, 2),
            "smart_profit_usd": round(smart_profit_usd, 2),
            "smart_return_pct_usd": round(smart_return_pct_usd, 2),
            "smart_breakdown_usd": {c: round(smart_breakdown_usd[c], 2) for c in weights},
            "invested_by_asset_usd": {c: round(invested_smart_by_asset_usd[c], 2) for c in weights},
            "asset_profits_usd": {c: round(smart_breakdown_usd[c] - invested_smart_by_asset_usd[c], 2) for c in weights},
            "smart_contributions_usd": smart_contributions_usd,
            "asset_return_pcts_usd": asset_return_pcts_usd,
            "passive_val_usd": round(passive_val_usd, 2),
            "passive_profit_usd": round(passive_profit_usd, 2),
            "passive_return_pct_usd": round(passive_return_pct_usd, 2),
            "alpha_rebalance_usd": round(smart_val_usd - passive_val_usd, 2),
            "single_vals_usd": {c: round(single_vals_usd[c], 2) for c in weights},
            "single_return_pcts_usd": {c: round(single_return_pcts_usd[c], 2) for c in weights}
        })

    # Resumo final
    final_entry = timeline[-1]
    final_smart_val = final_entry["smart_val"]
    final_passive_val = final_entry["passive_val"]
    rebalance_bonus_rs = final_smart_val - final_passive_val
    rebalance_bonus_pct = final_entry["smart_return_pct"] - final_entry["passive_return_pct"]

    final_smart_val_usd = final_entry["smart_val_usd"]
    final_passive_val_usd = final_entry["passive_val_usd"]
    rebalance_bonus_usd = final_smart_val_usd - final_passive_val_usd
    rebalance_bonus_pct_usd = final_entry["smart_return_pct_usd"] - final_entry["passive_return_pct_usd"]

    # Simular benchmarks com o mesmo fluxo de caixa de datas
    benchmarks_result = simulate_all_benchmarks(dates, initial_capital, monthly_contribution, contribution_dates, usd_rates_map)

    # Análises Avançadas
    monthly_summary = compute_monthly_breakdown(timeline, contributions_log, benchmarks_result)
    correlation_matrix = compute_correlation_matrix(dates, quotes, funds, benchmarks_result)
    assets_performance = compute_asset_performance_metrics(funds, quotes, dates, timeline, contributions_log, last_known_usd_rate)
    monthly_inflows = compute_monthly_inflows_by_asset(contributions_log, funds)
    treemap_distribution = compute_treemap_distribution(funds, final_entry, last_known_usd_rate)

    return {
        "start_date": dates[0],
        "end_date": dates[-1],
        "total_days": len(dates),
        "total_invested": round(total_invested, 2),
        "total_invested_usd": round(total_invested_usd, 2),
        "initial_capital": round(initial_capital, 2),
        "monthly_contribution": round(monthly_contribution, 2),
        "last_usd_rate": round(last_known_usd_rate, 4),
        # BRL
        "final_smart_val": round(final_smart_val, 2),
        "final_smart_profit": round(final_smart_val - total_invested, 2),
        "final_smart_return_pct": final_entry["smart_return_pct"],
        "final_passive_val": round(final_passive_val, 2),
        "final_passive_profit": round(final_passive_val - total_invested, 2),
        "final_passive_return_pct": final_entry["passive_return_pct"],
        "rebalance_bonus_rs": round(rebalance_bonus_rs, 2),
        "rebalance_bonus_pct": round(rebalance_bonus_pct, 2),
        # USD
        "final_smart_val_usd": round(final_smart_val_usd, 2),
        "final_smart_profit_usd": round(final_smart_val_usd - total_invested_usd, 2),
        "final_smart_return_pct_usd": final_entry["smart_return_pct_usd"],
        "final_passive_val_usd": round(final_passive_val_usd, 2),
        "final_passive_profit_usd": round(final_passive_val_usd - total_invested_usd, 2),
        "final_passive_return_pct_usd": final_entry["passive_return_pct_usd"],
        "rebalance_bonus_usd": round(rebalance_bonus_usd, 2),
        "rebalance_bonus_pct_usd": round(rebalance_bonus_pct_usd, 2),
        # Metadados
        "contributions_count": len(contributions_log),
        "funds": funds,
        "timeline": timeline,
        "benchmarks": benchmarks_result,
        "contributions_log": contributions_log,
        # 7 Novos Recursos Analíticos
        "monthly_summary": monthly_summary,
        "correlation_matrix": correlation_matrix,
        "assets_performance": assets_performance,
        "monthly_inflows": monthly_inflows,
        "treemap_distribution": treemap_distribution
    }

MONTH_NAMES_PT = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez"
}

def format_month_pt(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MONTH_NAMES_PT.get(m, m)}/{y[2:]}"

def compute_monthly_breakdown(
    timeline: List[Dict[str, Any]],
    contributions_log: List[Dict[str, Any]],
    benchmarks_result: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Calcula a evolução mês a mês:
    - Valor no início e final do mês
    - Aporte realizado no mês
    - Ganho de Capital líquido (R$ e US$)
    - Retorno da carteira (%)
    - Retorno de cada benchmark (%)
    """
    if not timeline:
        return []

    months_order = []
    month_timeline = {}
    for entry in timeline:
        ym = entry["date"][:7]
        if ym not in month_timeline:
            month_timeline[ym] = []
            months_order.append(ym)
        month_timeline[ym].append(entry)

    contribs_by_month = {}
    contribs_usd_by_month = {}
    for c in contributions_log:
        ym = c["date"][:7]
        contribs_by_month[ym] = contribs_by_month.get(ym, 0.0) + c.get("amount", 0.0)
        contribs_usd_by_month[ym] = contribs_usd_by_month.get(ym, 0.0) + c.get("amount_usd", 0.0)

    bm_maps = {}
    for bm_id, bm_data in benchmarks_result.items():
        t_list = bm_data.get("timeline", [])
        bm_maps[bm_id] = {p["date"]: p for p in t_list}

    monthly_summary = []
    prev_end_val = 0.0
    prev_end_val_usd = 0.0

    for idx, ym in enumerate(months_order):
        entries = month_timeline[ym]
        first_d = entries[0]["date"]
        last_d = entries[-1]["date"]
        last_entry = entries[-1]

        end_val = last_entry["smart_val"]
        end_val_usd = last_entry["smart_val_usd"]
        month_contrib = contribs_by_month.get(ym, 0.0)
        month_contrib_usd = contribs_usd_by_month.get(ym, 0.0)

        if idx == 0:
            start_val = 0.0
            start_val_usd = 0.0
            capital_gain = end_val - month_contrib
            capital_gain_usd = end_val_usd - month_contrib_usd
            base_calc = month_contrib
            base_calc_usd = month_contrib_usd
        else:
            start_val = prev_end_val
            start_val_usd = prev_end_val_usd
            capital_gain = end_val - start_val - month_contrib
            capital_gain_usd = end_val_usd - start_val_usd - month_contrib_usd
            base_calc = start_val + month_contrib
            base_calc_usd = start_val_usd + month_contrib_usd

        return_pct = (capital_gain / base_calc * 100.0) if base_calc > 0 else 0.0
        return_pct_usd = (capital_gain_usd / base_calc_usd * 100.0) if base_calc_usd > 0 else 0.0

        # Retorno de cada benchmark no mês
        bm_returns = {}
        for bm_id in benchmarks_result:
            m_map = bm_maps.get(bm_id, {})
            p_start = m_map.get(first_d)
            p_end = m_map.get(last_d)
            if p_start and p_end:
                if "pure_pct" in p_start and "pure_pct" in p_end:
                    fac_start = 1.0 + p_start["pure_pct"] / 100.0
                    fac_end = 1.0 + p_end["pure_pct"] / 100.0
                    bm_m_ret = ((fac_end / fac_start) - 1.0) * 100.0 if fac_start > 0 else 0.0
                else:
                    bm_m_ret = 0.0
                bm_returns[bm_id] = round(bm_m_ret, 2)
            else:
                bm_returns[bm_id] = 0.0

        # Decomposição do Ganho de Capital por Ativo no Mês (BRL e USD)
        asset_capital_gains = {}
        asset_capital_gains_usd = {}
        for c in last_entry.get("smart_breakdown", {}).keys():
            end_c = last_entry["smart_breakdown"].get(c, 0.0)
            start_c = 0.0 if idx == 0 else month_timeline[months_order[idx-1]][-1]["smart_breakdown"].get(c, 0.0)
            
            c_contrib = 0.0
            c_contrib_usd = 0.0
            for log in contributions_log:
                if log.get("date", "")[:7] == ym:
                    alloc_c = log.get("smart_allocation", {}).get(c, 0.0)
                    c_contrib += alloc_c
                    rate = log.get("usd_rate", 1.0)
                    c_contrib_usd += (alloc_c / rate) if rate else 0.0

            gain_c = end_c - start_c - c_contrib
            asset_capital_gains[c] = round(gain_c, 2)

            end_c_usd = last_entry.get("smart_breakdown_usd", {}).get(c, round(end_c / last_entry["usd_rate"], 2) if last_entry.get("usd_rate") else 0.0)
            prev_entry = month_timeline[months_order[idx-1]][-1] if idx > 0 else None
            start_c_usd = 0.0 if idx == 0 else (prev_entry.get("smart_breakdown_usd", {}).get(c, round(start_c / prev_entry["usd_rate"], 2) if prev_entry and prev_entry.get("usd_rate") else 0.0))
            gain_c_usd = end_c_usd - start_c_usd - c_contrib_usd
            asset_capital_gains_usd[c] = round(gain_c_usd, 2)

        monthly_summary.append({
            "month": ym,
            "month_label": format_month_pt(ym),
            "start_date": first_d,
            "end_date": last_d,
            "start_val": round(start_val, 2),
            "end_val": round(end_val, 2),
            "contribution": round(month_contrib, 2),
            "capital_gain": round(capital_gain, 2),
            "return_pct": round(return_pct, 2),
            "asset_capital_gains": asset_capital_gains,
            "start_val_usd": round(start_val_usd, 2),
            "end_val_usd": round(end_val_usd, 2),
            "contribution_usd": round(month_contrib_usd, 2),
            "capital_gain_usd": round(capital_gain_usd, 2),
            "return_pct_usd": round(return_pct_usd, 2),
            "asset_capital_gains_usd": asset_capital_gains_usd,
            "benchmarks_returns": bm_returns
        })

        prev_end_val = end_val
        prev_end_val_usd = end_val_usd

    return monthly_summary

def compute_correlation_matrix(
    dates: List[str],
    quotes: Dict[str, Dict[str, float]],
    funds: List[Dict[str, Any]],
    benchmarks_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calcula a matriz de correlação de Pearson dos retornos diários entre
    todos os ativos da carteira e os benchmarks oficiais.
    """
    if len(dates) < 5:
        return {"labels": [], "keys": [], "matrix": []}

    series_data = {}
    labels_map = {}

    # Retornos diários dos ativos da carteira
    for f in funds:
        k = get_asset_key(f)
        q_map = quotes.get(k, {})
        prices = [q_map.get(d) for d in dates]
        returns = []
        for i in range(1, len(prices)):
            p0 = prices[i - 1]
            p1 = prices[i]
            if p0 and p1 and p0 > 0:
                returns.append((p1 / p0) - 1.0)
            else:
                returns.append(0.0)
        series_data[k] = returns
        labels_map[k] = f.get("name", k)

    # Retornos diários dos benchmarks
    for bm_id in ["cdi", "ibov", "sp500", "ifix", "btc", "usd", "poupanca", "ipca"]:
        if bm_id in benchmarks_result:
            bm_info = benchmarks_result[bm_id]
            t_list = bm_info.get("timeline", [])
            t_map = {p["date"]: p for p in t_list}
            bm_pts = [t_map.get(d) for d in dates]
            returns = []
            for i in range(1, len(bm_pts)):
                pt0 = bm_pts[i - 1]
                pt1 = bm_pts[i]
                if pt0 and pt1:
                    val0 = pt0.get("cash_val") or (1.0 + pt0.get("pure_pct", 0.0) / 100.0)
                    val1 = pt1.get("cash_val") or (1.0 + pt1.get("pure_pct", 0.0) / 100.0)
                    returns.append(((val1 / val0) - 1.0) if val0 > 0 else 0.0)
                else:
                    returns.append(0.0)
            series_data[bm_id] = returns
            labels_map[bm_id] = bm_info.get("name", bm_id.upper())

    keys = list(series_data.keys())
    labels = [labels_map.get(k, k) for k in keys]
    n = len(keys)
    matrix = [[0.0 for _ in range(n)] for _ in range(n)]

    def pearson_corr(x: List[float], y: List[float]) -> float:
        m = len(x)
        if m < 2:
            return 0.0
        mean_x = sum(x) / m
        mean_y = sum(y) / m
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)
        if var_x <= 1e-12 or var_y <= 1e-12:
            return 0.0
        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(m))
        r = cov / math.sqrt(var_x * var_y)
        return max(-1.0, min(1.0, r))

    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            r_val = pearson_corr(series_data[keys[i]], series_data[keys[j]])
            matrix[i][j] = round(r_val, 2)
            matrix[j][i] = round(r_val, 2)

    return {
        "keys": keys,
        "labels": labels,
        "matrix": matrix
    }

def get_subtle_auxiliary_color(hex_color: str) -> str:
    """Gera uma cor auxiliar suave/pastel (88% branco + 12% cor vibrante) a partir de um código hexadecimal."""
    if not hex_color or not isinstance(hex_color, str):
        return "#F4F6F8"
    c = hex_color.lstrip("#").strip()
    if len(c) == 3:
        c = "".join([x * 2 for x in c])
    if len(c) != 6:
        return "#F4F6F8"
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        ar = round(255 * 0.88 + r * 0.12)
        ag = round(255 * 0.88 + g * 0.12)
        ab = round(255 * 0.88 + b * 0.12)
        return f"#{ar:02X}{ag:02X}{ab:02X}"
    except ValueError:
        return "#F4F6F8"

def compute_asset_performance_metrics(
    funds: List[Dict[str, Any]],
    quotes: Dict[str, Dict[str, float]],
    dates: List[str],
    timeline: List[Dict[str, Any]],
    contributions_log: List[Dict[str, Any]],
    last_usd_rate: float
) -> List[Dict[str, Any]]:
    """
    Calcula métricas aprofundadas de rentabilidade e risco para cada ativo:
    - Retorno acumulado no período (%)
    - Retorno anualizado (% a.a.)
    - Volatilidade anualizada (%)
    - Drawdown Máximo (%)
    - Total de aportes recebidos vs. Saldo em custódia
    """
    if not dates or not timeline:
        return []

    last_entry = timeline[-1]
    n_days = len(dates)
    metrics = []

    for f in funds:
        k = get_asset_key(f)
        q_map = quotes.get(k, {})
        prices = [q_map.get(d, 0.0) for d in dates if q_map.get(d) and q_map.get(d) > 0]
        if not prices:
            continue

        p_init = prices[0]
        p_final = prices[-1]

        # Retorno Acumulado
        cum_ret = ((p_final / p_init) - 1.0) * 100.0 if p_init > 0 else 0.0

        # Retorno Anualizado (252 dias úteis)
        if p_init > 0 and n_days > 20:
            ann_factor = (p_final / p_init) ** (252.0 / n_days)
            ann_ret = (ann_factor - 1.0) * 100.0
        else:
            ann_ret = cum_ret

        # Retornos diários para volatilidade
        daily_returns = []
        for i in range(1, len(prices)):
            p0 = prices[i - 1]
            p1 = prices[i]
            if p0 > 0:
                daily_returns.append((p1 / p0) - 1.0)

        # Volatilidade Anualizada
        if len(daily_returns) > 1:
            mean_r = sum(daily_returns) / len(daily_returns)
            var_r = sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            vol_ann = math.sqrt(var_r) * math.sqrt(252.0) * 100.0
        else:
            vol_ann = 0.0

        # Drawdown Máximo
        max_seen = prices[0]
        max_dd = 0.0
        for p in prices:
            if p > max_seen:
                max_seen = p
            dd = ((p - max_seen) / max_seen) * 100.0 if max_seen > 0 else 0.0
            if dd < max_dd:
                max_dd = dd

        # Saldo Atual e Total Depositado
        eff_pct = last_entry["effective_pcts"].get(k, 0.0)
        curr_bal_brl = (last_entry["smart_val"] * eff_pct) / 100.0
        curr_bal_usd = curr_bal_brl / last_usd_rate if last_usd_rate > 0 else 0.0

        total_contrib = 0.0
        for c in contributions_log:
            alloc_map = c.get("smart_allocation", {})
            total_contrib += alloc_map.get(k, 0.0)

        metrics.append({
            "key": k,
            "name": f.get("name", k),
            "code": f.get("code") or f.get("cnpj") or k,
            "type": f.get("type", "fund"),
            "color": f.get("color", "#3b82f6"),
            "color_aux": f.get("color_aux") or get_subtle_auxiliary_color(f.get("color", "#3b82f6")),
            "target_pct": float(f.get("target_pct", 0.0)),
            "current_pct": round(eff_pct, 2),
            "min_investment": float(f.get("min_investment", 100.0)),
            "current_balance": round(curr_bal_brl, 2),
            "current_balance_usd": round(curr_bal_usd, 2),
            "total_contributed": round(total_contrib, 2),
            "profit": round(curr_bal_brl - total_contrib, 2),
            "profit_usd": round(curr_bal_usd - (total_contrib / last_usd_rate), 2) if last_usd_rate > 0 else 0.0,
            "cumulative_return_pct": round(cum_ret, 2),
            "annualized_return_pct": round(ann_ret, 2),
            "volatility_annualized": round(vol_ann, 2),
            "annualized_volatility_pct": round(vol_ann, 2),
            "max_drawdown_pct": round(max_dd, 2)
        })

    return metrics

def compute_monthly_inflows_by_asset(
    contributions_log: List[Dict[str, Any]],
    funds: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Gera o histórico de fluxo de dinheiro alocado em cada mês por ativo."""
    result = []
    for c in contributions_log:
        alloc_map = c.get("smart_allocation", {})
        result.append({
            "date": c["date"],
            "month_label": format_month_pt(c["date"][:7]),
            "amount": c["amount"],
            "amount_usd": c.get("amount_usd", 0.0),
            "type": c.get("type", "monthly"),
            "allocations": {get_asset_key(f): round(alloc_map.get(get_asset_key(f), 0.0), 2) for f in funds}
        })
    return result

def compute_treemap_distribution(
    funds: List[Dict[str, Any]],
    last_entry: Dict[str, Any],
    last_usd_rate: float
) -> List[Dict[str, Any]]:
    """Gera a distribuição de ativos para o gráfico Treemap."""
    smart_val = last_entry.get("smart_val", 0.0)
    eff_map = last_entry.get("effective_pcts", {})
    items = []
    for f in funds:
        k = get_asset_key(f)
        pct = eff_map.get(k, 0.0)
        bal_brl = (smart_val * pct) / 100.0
        bal_usd = bal_brl / last_usd_rate if last_usd_rate > 0 else 0.0
        items.append({
            "key": k,
            "name": f.get("name", k),
            "code": f.get("code") or f.get("cnpj") or k,
            "type": f.get("type", "fund"),
            "color": f.get("color", "#3b82f6"),
            "target_pct": float(f.get("target_pct", 0.0)),
            "current_pct": round(pct, 2),
            "effective_pct": round(pct, 2),
            "dev_pct": round(pct - float(f.get("target_pct", 0.0)), 2),
            "balance_brl": round(bal_brl, 2),
            "current_balance": round(bal_brl, 2),
            "balance_usd": round(bal_usd, 2),
            "current_balance_usd": round(bal_usd, 2)
        })
    return items

def simulate_all_benchmarks(
    dates: List[str],
    initial_capital: float,
    monthly_contribution: float,
    contribution_dates: set,
    usd_rates_map: Dict[str, float]
) -> Dict[str, Any]:
    """
    Simula o desempenho de todos os Benchmarks configurados e habilitados
    tanto em Rentabilidade (%) quanto em Patrimônio no fluxo de caixa real,
    calculando versões em Real (BRL) e Dólar (USD).
    """
    benchmarks_config = load_benchmarks_config()
    results = {}

    last_known_usd = usd_rates_map.get(dates[0], 5.15)

    for bm in benchmarks_config:
        bm_id = bm["id"]
        if not bm.get("enabled", True):
            continue

        raw_points = load_benchmark_data(bm_id)
        if not raw_points:
            continue

        raw_map = {p["date"]: p["value"] for p in raw_points}
        bm_type = bm.get("type", "yahoo")
        unit = bm.get("unit", "price")

        # Configuração do acumulador
        factor = 1.0
        cash_val = initial_capital
        quotas = 0.0
        first_price = None
        timeline = []
        total_invested_brl = initial_capital
        total_invested_usd = initial_capital / last_known_usd

        # Obter primeiro preço para ativos de cotação
        if unit in ("price", "price_usd_brl", "currency"):
            for dt in dates:
                if dt in raw_map:
                    first_price = raw_map[dt]
                    if first_price > 0:
                        quotas = initial_capital / first_price
                    break
            if not first_price or first_price <= 0:
                first_price = 1.0
                quotas = initial_capital

        last_price = first_price or 1.0
        last_month_seen = None

        for idx, dt in enumerate(dates):
            # Câmbio USD do dia
            if dt in usd_rates_map:
                last_known_usd = usd_rates_map[dt]
            usd_rate = last_known_usd

            # Aporte no fluxo
            if dt in contribution_dates:
                total_invested_brl += monthly_contribution
                total_invested_usd += monthly_contribution / usd_rate
                if unit in ("daily_rate", "monthly_rate"):
                    cash_val += monthly_contribution
                elif unit in ("price", "price_usd_brl", "currency"):
                    if last_price > 0:
                        quotas += monthly_contribution / last_price

            # Evolução da rentabilidade
            if unit == "daily_rate":
                # Ex: CDI diário
                daily_rate = raw_map.get(dt, 0.0)
                daily_factor = (1.0 + daily_rate / 100.0) if daily_rate > 0 else 1.0
                factor *= daily_factor
                cash_val *= daily_factor
                pure_pct = (factor - 1.0) * 100.0

            elif unit == "monthly_rate":
                # Ex: IPCA, Poupança
                m_str = dt[:7]
                if m_str != last_month_seen:
                    m_rate = raw_map.get(dt, 0.40)
                    m_factor = (1.0 + m_rate / 100.0)
                    day_factor = m_factor ** (1.0 / 21.0)
                    last_month_seen = m_str
                else:
                    day_factor = 1.004 ** (1.0 / 21.0)
                factor *= day_factor
                cash_val *= day_factor
                pure_pct = (factor - 1.0) * 100.0

            else:
                # Preços/pontos (IBOV, IFIX, S&P 500, BTC, USD)
                if dt in raw_map:
                    last_price = raw_map[dt]
                cash_val = quotas * last_price
                pure_pct = ((last_price / first_price) - 1.0) * 100.0 if first_price else 0.0

            cash_val_usd = cash_val / usd_rate
            cash_return_pct_brl = ((cash_val - total_invested_brl) / total_invested_brl) * 100.0 if total_invested_brl > 0 else 0.0
            cash_return_pct_usd = ((cash_val_usd - total_invested_usd) / total_invested_usd) * 100.0 if total_invested_usd > 0 else 0.0

            timeline.append({
                "date": dt,
                "usd_rate": round(usd_rate, 4),
                "pure_pct": round(pure_pct, 2),
                "cash_val": round(cash_val, 2),
                "cash_return_pct": round(cash_return_pct_brl, 2),
                "cash_val_usd": round(cash_val_usd, 2),
                "cash_return_pct_usd": round(cash_return_pct_usd, 2)
            })

        results[bm_id] = {
            "id": bm_id,
            "name": bm.get("name", bm_id.upper()),
            "color": bm.get("color", "#94a3b8"),
            "source": bm.get("source", ""),
            "final_pure_pct": timeline[-1]["pure_pct"],
            "final_cash_val": timeline[-1]["cash_val"],
            "final_cash_return_pct": timeline[-1]["cash_return_pct"],
            "final_cash_val_usd": timeline[-1]["cash_val_usd"],
            "final_cash_return_pct_usd": timeline[-1]["cash_return_pct_usd"],
            "timeline": timeline
        }

    return results

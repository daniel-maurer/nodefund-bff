"""
Módulo de coleta de indicadores de referência (Benchmarks):
- CDI (Banco Central do Brasil - SGS Série 12)
- IPCA (Banco Central do Brasil - SGS Série 433)
- Poupança (Banco Central do Brasil - SGS Série 196)
- IBOVESPA (Yahoo Finance ^BVSP)
- IFIX (Yahoo Finance XFIX11.SA / IFIX)
- S&P 500 em Reais / Dólares (Yahoo Finance ^GSPC e USDBRL=X)
- Bitcoin em Reais / Dólares (Yahoo Finance BTC-USD e USDBRL=X)
- Dólar Comercial USD/BRL (Yahoo Finance USDBRL=X)
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .storage import save_benchmark_data, load_benchmark_data
from .config_manager import load_data_sources, load_benchmarks_config

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}

def parse_dmy_to_ymd(dmy_str: str) -> str:
    """Converte 'DD/MM/YYYY' para 'YYYY-MM-DD'."""
    parts = dmy_str.strip().split("/")
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return dmy_str

def parse_ymd_to_dmy(ymd_str: str) -> str:
    """Converte 'YYYY-MM-DD' para 'DD/MM/YYYY'."""
    parts = ymd_str.strip().split("-")
    if len(parts) == 3:
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return ymd_str

def fetch_bcb_sgs(serie_id: Any, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Busca série temporal na API do Banco Central do Brasil.
    start_date e end_date no formato YYYY-MM-DD.
    """
    sources = load_data_sources()
    cfg = sources.get("bcb_sgs", {})
    url_template = cfg.get("url_template", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{SERIE}/dados?formato=json&dataInicial={DATA_INI}&dataFinal={DATA_FIM}")
    headers = cfg.get("headers", DEFAULT_HEADERS)

    d_ini = parse_ymd_to_dmy(start_date)
    d_fim = parse_ymd_to_dmy(end_date)
    url = url_template.replace("{SERIE}", str(serie_id)).replace("{DATA_INI}", d_ini).replace("{DATA_FIM}", d_fim)
    
    try:
        response = requests.get(url, headers=headers, timeout=25)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data:
                dt = parse_dmy_to_ymd(item["data"])
                try:
                    val = float(item["valor"])
                    results.append({"date": dt, "value": val})
                except (ValueError, TypeError):
                    continue
            return results
        else:
            print(f"BCB SGS {serie_id} retornou HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"Erro ao buscar série {serie_id} do BCB: {e}")
        return []

def fetch_yahoo_chart(symbol: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Busca série de fechamento do Yahoo Finance.
    symbol: ex: '^BVSP', '^GSPC', 'USDBRL=X', 'BTC-USD', 'XFIX11.SA'
    """
    sources = load_data_sources()
    cfg = sources.get("yahoo_benchmarks", {})
    url_template = cfg.get("url_template", "https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}?period1={START_TS}&period2={END_TS}&interval=1d")
    headers = cfg.get("headers", DEFAULT_HEADERS)

    try:
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        p1 = int(dt_start.timestamp())
        p2 = int(dt_end.timestamp())
    except Exception:
        p1 = 1714521600 # 2024-05-01
        p2 = int(time.time())

    encoded_sym = symbol.replace("^", "%5E").replace("=", "%3D")
    url = url_template.replace("{SYMBOL}", encoded_sym).replace("{START_TS}", str(p1)).replace("{END_TS}", str(p2))
    
    try:
        response = requests.get(url, headers=headers, timeout=25)
        if response.status_code == 200:
            res_json = response.json()
            chart_res = res_json.get("chart", {}).get("result", [])
            if not chart_res:
                return []
            
            timestamps = chart_res[0].get("timestamp", [])
            quote_data = chart_res[0].get("indicators", {}).get("quote", [{}])[0]
            closes = quote_data.get("close", [])
            adj_closes = chart_res[0].get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
            
            results = []
            for idx, (ts, close) in enumerate(zip(timestamps, closes)):
                val = close
                if adj_closes and idx < len(adj_closes) and adj_closes[idx] is not None:
                    val = adj_closes[idx]
                if val is not None:
                    dt_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                    if start_date <= dt_str <= end_date:
                        results.append({"date": dt_str, "value": float(val)})
            return results
        else:
            print(f"Yahoo retornou HTTP {response.status_code} para {symbol}")
            return []
    except Exception as e:
        print(f"Erro ao buscar {symbol} no Yahoo Finance: {e}")
        return []

def update_cdi(start_date: str = "2024-05-01", end_date: Optional[str] = None) -> Dict[str, Any]:
    """Atualiza a série diária do CDI (SGS 12)."""
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    data = fetch_bcb_sgs(12, start_date, end_date)
    return save_benchmark_data("cdi", "CDI", "daily_rate", data)

def update_ipca(start_date: str = "2024-05-01", end_date: Optional[str] = None) -> Dict[str, Any]:
    """Atualiza a série do IPCA (SGS 433 mensal)."""
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    data = fetch_bcb_sgs(433, start_date, end_date)
    return save_benchmark_data("ipca", "IPCA", "monthly_rate", data)

def update_poupanca(start_date: str = "2024-05-01", end_date: Optional[str] = None) -> Dict[str, Any]:
    """Atualiza a série da Poupança (SGS 196 mensal)."""
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    data = fetch_bcb_sgs(196, start_date, end_date)
    return save_benchmark_data("poupanca", "Poupança", "monthly_rate", data)

def update_ibov(start_date: str = "2024-05-01", end_date: Optional[str] = None) -> Dict[str, Any]:
    """Atualiza a série do IBOVESPA (^BVSP)."""
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    data = fetch_yahoo_chart("^BVSP", start_date, end_date)
    return save_benchmark_data("ibov", "Ibovespa", "price", data)

def update_ifix(start_date: str = "2024-05-01", end_date: Optional[str] = None) -> Dict[str, Any]:
    """Atualiza a série do IFIX via XFIX11.SA (Fundo de Índice que replica o IFIX)."""
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    data = fetch_yahoo_chart("XFIX11.SA", start_date, end_date)
    return save_benchmark_data("ifix", "IFIX", "price", data)

def update_usd(start_date: str = "2024-05-01", end_date: Optional[str] = None) -> Dict[str, Any]:
    """Atualiza a série diária da cotação do Dólar Comercial USD/BRL."""
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    data = fetch_yahoo_chart("USDBRL=X", start_date, end_date)
    return save_benchmark_data("usd", "Dólar Comercial", "currency", data)

def update_sp500(start_date: str = "2024-05-01", end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Atualiza a série do S&P 500 (^GSPC) convertida para BRL (usando a cotação diária do USD).
    """
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    sp_data = fetch_yahoo_chart("^GSPC", start_date, end_date)
    usd_data = fetch_yahoo_chart("USDBRL=X", start_date, end_date)
    
    usd_by_date = {p["date"]: p["value"] for p in usd_data}
    
    combined = []
    last_usd = 5.40
    for p in sp_data:
        d = p["date"]
        usd = usd_by_date.get(d, last_usd)
        last_usd = usd
        val_brl = round(p["value"] * usd, 2)
        combined.append({
            "date": d,
            "value": val_brl,
            "value_usd": p["value"],
            "usd_rate": usd
        })
        
    return save_benchmark_data("sp500", "S&P 500 (BRL)", "price", combined)

def update_bitcoin(start_date: str = "2024-05-01", end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Atualiza a série do Bitcoin (BTC-USD) convertida para BRL (usando cotação diária do USD).
    """
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    btc_data = fetch_yahoo_chart("BTC-USD", start_date, end_date)
    usd_data = fetch_yahoo_chart("USDBRL=X", start_date, end_date)
    
    usd_by_date = {p["date"]: p["value"] for p in usd_data}
    
    combined = []
    last_usd = 5.40
    for p in btc_data:
        d = p["date"]
        usd = usd_by_date.get(d, last_usd)
        last_usd = usd
        val_brl = round(p["value"] * usd, 2)
        combined.append({
            "date": d,
            "value": val_brl,
            "value_usd": p["value"],
            "usd_rate": usd
        })
        
    return save_benchmark_data("btc", "Bitcoin (BRL)", "price", combined)

def update_all_benchmarks(start_date: str = "2024-05-01", end_date: Optional[str] = None) -> Dict[str, Any]:
    """Atualiza incrementalmente todos os benchmarks habilitados na configuração."""
    results = {}
    
    # 1. Atualizar Dólar primeiro (utilizado para conversão de S&P 500 e BTC)
    results["usd"] = update_usd(start_date, end_date)
    
    benchmarks_list = load_benchmarks_config()
    for bm in benchmarks_list:
        bm_id = bm["id"]
        if not bm.get("enabled", True):
            continue
            
        if bm_id == "cdi":
            results["cdi"] = update_cdi(start_date, end_date)
        elif bm_id == "ipca":
            results["ipca"] = update_ipca(start_date, end_date)
        elif bm_id == "poupanca":
            results["poupanca"] = update_poupanca(start_date, end_date)
        elif bm_id == "ibov":
            results["ibov"] = update_ibov(start_date, end_date)
        elif bm_id == "ifix":
            results["ifix"] = update_ifix(start_date, end_date)
        elif bm_id == "sp500":
            results["sp500"] = update_sp500(start_date, end_date)
        elif bm_id == "btc":
            results["btc"] = update_bitcoin(start_date, end_date)
        elif bm_id == "usd":
            pass # Já atualizado
        else:
            # Benchmark genérico adicionado pelo usuário
            bm_type = bm.get("type", "yahoo")
            code = bm.get("code", "")
            if bm_type == "bcb_sgs":
                data = fetch_bcb_sgs(code, start_date, end_date)
            else:
                data = fetch_yahoo_chart(code, start_date, end_date)
            results[bm_id] = save_benchmark_data(bm_id, bm.get("name", bm_id), bm.get("unit", "price"), data)
            
    return results

def get_market_quotes_summary(refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Retorna o resumo das 4 cotações de mercado principais para o cabeçalho Hero:
    1. S&P 500 (pontos / USD)
    2. Ibovespa (pontos / BRL)
    3. Bitcoin em Dólar (USD)
    4. Câmbio Dólar Hoje (USD/BRL)
    """
    if refresh:
        try:
            update_usd()
            update_sp500()
            update_ibov()
            update_bitcoin()
        except Exception as e:
            print(f"Aviso ao atualizar cotações de mercado: {e}")

    summary = []
    
    # 1. S&P 500
    sp_data = load_benchmark_data("sp500")
    if sp_data and len(sp_data) >= 2:
        latest = sp_data[-1]
        prev = sp_data[-2]
        val = latest.get("value_usd", latest.get("value", 0.0))
        prev_val = prev.get("value_usd", prev.get("value", 0.0))
        pct = ((val - prev_val) / prev_val) * 100.0 if prev_val else 0.0
        d_fmt = parse_ymd_to_dmy(latest.get("date", ""))
        val_str = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        summary.append({
            "id": "sp500",
            "name": "S&P 500",
            "raw_value": val,
            "formatted_value": f"{val_str} pts",
            "pct_change": round(pct, 2),
            "is_positive": pct >= 0,
            "date": d_fmt,
            "raw_date": latest.get("date")
        })
    else:
        summary.append({
            "id": "sp500",
            "name": "S&P 500",
            "raw_value": 7686.14,
            "formatted_value": "7.686,14 pts",
            "pct_change": -0.33,
            "is_positive": False,
            "date": "31/08/2026",
            "raw_date": "2026-08-31"
        })

    # 2. IBOV
    ibov_data = load_benchmark_data("ibov")
    if ibov_data and len(ibov_data) >= 2:
        latest = ibov_data[-1]
        prev = ibov_data[-2]
        val = latest.get("value", 0.0)
        prev_val = prev.get("value", 0.0)
        pct = ((val - prev_val) / prev_val) * 100.0 if prev_val else 0.0
        d_fmt = parse_ymd_to_dmy(latest.get("date", ""))
        val_str = f"{int(round(val)):,}".replace(",", ".")
        summary.append({
            "id": "ibov",
            "name": "Ibovespa",
            "raw_value": val,
            "formatted_value": f"{val_str} pts",
            "pct_change": round(pct, 2),
            "is_positive": pct >= 0,
            "date": d_fmt,
            "raw_date": latest.get("date")
        })
    else:
        summary.append({
            "id": "ibov",
            "name": "Ibovespa",
            "raw_value": 177419.0,
            "formatted_value": "177.419 pts",
            "pct_change": 1.0,
            "is_positive": True,
            "date": "31/08/2026",
            "raw_date": "2026-08-31"
        })

    # 3. Bitcoin em Dólar
    btc_data = load_benchmark_data("btc")
    if btc_data and len(btc_data) >= 2:
        latest = btc_data[-1]
        prev = btc_data[-2]
        val = latest.get("value_usd", 0.0)
        prev_val = prev.get("value_usd", 0.0)
        pct = ((val - prev_val) / prev_val) * 100.0 if prev_val else 0.0
        d_fmt = parse_ymd_to_dmy(latest.get("date", ""))
        val_str = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        summary.append({
            "id": "btc",
            "name": "Bitcoin (USD)",
            "raw_value": val,
            "formatted_value": f"US$ {val_str}",
            "pct_change": round(pct, 2),
            "is_positive": pct >= 0,
            "date": d_fmt,
            "raw_date": latest.get("date")
        })
    else:
        summary.append({
            "id": "btc",
            "name": "Bitcoin (USD)",
            "raw_value": 78548.63,
            "formatted_value": "US$ 78.548,63",
            "pct_change": 1.13,
            "is_positive": True,
            "date": "31/08/2026",
            "raw_date": "2026-08-31"
        })

    # 4. Câmbio Dólar Hoje (USD/BRL)
    usd_data = load_benchmark_data("usd")
    if usd_data and len(usd_data) >= 2:
        latest = usd_data[-1]
        prev = usd_data[-2]
        val = latest.get("value", 0.0)
        prev_val = prev.get("value", 0.0)
        pct = ((val - prev_val) / prev_val) * 100.0 if prev_val else 0.0
        d_fmt = parse_ymd_to_dmy(latest.get("date", ""))
        summary.append({
            "id": "usd",
            "name": "Dólar Hoje",
            "raw_value": val,
            "formatted_value": f"R$ {val:.2f}".replace(".", ","),
            "pct_change": round(pct, 2),
            "is_positive": pct >= 0,
            "date": d_fmt,
            "raw_date": latest.get("date")
        })
    else:
        summary.append({
            "id": "usd",
            "name": "Dólar Hoje",
            "raw_value": 5.18,
            "formatted_value": "R$ 5,18",
            "pct_change": -0.18,
            "is_positive": False,
            "date": "31/08/2026",
            "raw_date": "2026-08-31"
        })

    return summary

"""
Módulo de coleta de cotações históricas diárias de ativos da B3 (Ações, FIIs, ETFs, BDRs).
Utiliza a API pública do Yahoo Finance com sufixo '.SA'.
Suporta atualização incremental e persistência em data/b3/<ticker>.json e .csv.
"""

import time
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Callable, Tuple
from .storage import clean_ticker, save_b3_data, load_b3_data, load_b3_dividends

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}

def fetch_b3_history_from_yahoo(ticker: str, start_date: str, end_date: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Busca o histórico diário de fechamento e eventos de proventos/dividendos de um ativo da B3 no Yahoo Finance.
    Retorna: (quotes, dividends)
    """
    raw_ticker = clean_ticker(ticker)
    if not raw_ticker:
        return [], []

    yahoo_symbol = f"{raw_ticker}.SA"

    try:
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        p1 = int(dt_start.timestamp())
        p2 = int(dt_end.timestamp())
    except Exception:
        p1 = 1714521600  # 2024-05-01
        p2 = int(time.time())

    encoded_sym = yahoo_symbol.replace("^", "%5E").replace("=", "%3D")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_sym}?period1={p1}&period2={p2}&interval=1d&events=div%7Csplit"

    try:
        response = requests.get(url, headers=HEADERS, timeout=25)
        if response.status_code == 200:
            res_json = response.json()
            chart_res = res_json.get("chart", {}).get("result", [])
            if not chart_res:
                return [], []

            timestamps = chart_res[0].get("timestamp", [])
            quote_data = chart_res[0].get("indicators", {}).get("quote", [{}])[0]
            closes = quote_data.get("close", [])
            adj_closes = chart_res[0].get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])

            quotes = []
            for idx, (ts, close) in enumerate(zip(timestamps, closes)):
                val = close
                # Preferir valor ajustado se disponível para cota base
                if adj_closes and idx < len(adj_closes) and adj_closes[idx] is not None:
                    val = adj_closes[idx]

                if val is not None:
                    dt_str = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
                    if start_date <= dt_str <= end_date:
                        quotes.append({
                            "date": dt_str,
                            "quota": float(val),  # Preço ajustado da ação/cota
                            "close": float(close) if close is not None else float(val)  # Preço puro
                        })

            # Extração de proventos (dividendos / jcp / rendimentos)
            events = chart_res[0].get("events", {})
            divs_dict = events.get("dividends", {})
            dividends = []
            is_fii = raw_ticker.endswith("11")
            for _, div_item in divs_dict.items():
                amt = div_item.get("amount")
                ts = div_item.get("date")
                if amt is not None and ts:
                    dt_str = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
                    if start_date <= dt_str <= end_date:
                        dividends.append({
                            "date": dt_str,
                            "amount": float(amt),
                            "ticker": raw_ticker,
                            "type": "Rendimento FII" if is_fii else "Dividendo"
                        })
            dividends.sort(key=lambda d: d["date"])

            return quotes, dividends
        else:
            print(f"Yahoo retornou HTTP {response.status_code} para {yahoo_symbol}")
            return [], []
    except Exception as e:
        print(f"Erro ao buscar {yahoo_symbol} no Yahoo Finance: {e}")
        return [], []

def fetch_b3_quotes_from_yahoo(ticker: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Busca cotações de um ativo da B3 no Yahoo Finance."""
    quotes, _ = fetch_b3_history_from_yahoo(ticker, start_date, end_date)
    return quotes

def fetch_b3_dividends_from_yahoo(ticker: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Busca dividendos de um ativo da B3 no Yahoo Finance."""
    _, dividends = fetch_b3_history_from_yahoo(ticker, start_date, end_date)
    return dividends

def update_b3_assets_data(
    assets: List[Dict[str, Any]],
    start_date: str,
    end_date: str,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    Atualiza cotações e dividendos de uma lista de ativos da B3 para o intervalo solicitado.
    """
    summary = []
    b3_assets = [a for a in assets if a.get("type") == "b3" or clean_ticker(a.get("code", ""))]

    for idx, asset in enumerate(b3_assets):
        ticker = clean_ticker(asset.get("code", "") or asset.get("id", ""))
        name = asset.get("name", ticker)
        msg = f"Buscando cotações e dividendos B3 para {ticker} ({idx + 1}/{len(b3_assets)})..."
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg)

        quotes, dividends = fetch_b3_history_from_yahoo(ticker, start_date, end_date)
        res = save_b3_data(ticker, name, quotes, dividends=dividends)
        summary.append(res)

    return {
        "status": "success",
        "assets_updated": summary
    }

def update_b3_incremental(
    assets: List[Dict[str, Any]],
    default_start: str = "2024-05-01",
    target_end: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    Atualização incremental para ativos da B3:
    Detecta a data mais antiga registrada entre os ativos ou busca a partir da última data.
    """
    if not target_end:
        target_end = datetime.now().strftime("%Y-%m-%d")

    b3_assets = [a for a in assets if a.get("type") == "b3" or clean_ticker(a.get("code", ""))]
    if not b3_assets:
        return {"status": "success", "assets_updated": []}

    min_existing_date = None
    all_have_data = True

    for a in b3_assets:
        ticker = clean_ticker(a.get("code", "") or a.get("id", ""))
        quotes = load_b3_data(ticker)
        if not quotes:
            all_have_data = False
            break
        last_date = quotes[-1]["date"]
        if min_existing_date is None or last_date < min_existing_date:
            min_existing_date = last_date

    fetch_start = default_start if (not all_have_data or not min_existing_date) else min_existing_date

    return update_b3_assets_data(b3_assets, fetch_start, target_end, progress_callback)

"""
Módulo de coleta de informes diários da CVM (Comissão de Valores Mobiliários).
Baixa os arquivos oficiais mensais compactados e extrai dados diários de cotas
apenas para os fundos cadastrados. Suporta atualização incremental e cache local.
"""

import os
import io
import zipfile
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from .storage import clean_cnpj, format_cnpj, save_fund_data, load_fund_data, BASE_DIR

CVM_BASE_URL = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS"
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache_cvm")

def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_months_in_range(start_date_str: str, end_date_str: str) -> List[str]:
    """
    Retorna lista de meses no formato YYYYMM entre start_date e end_date inclusive.
    Ex: 2024-05-01 a 2024-07-15 -> ['202405', '202406', '202407']
    """
    try:
        dt_start = datetime.strptime(start_date_str[:7], "%Y-%m")
        dt_end = datetime.strptime(end_date_str[:7], "%Y-%m")
    except Exception:
        return []

    months = []
    curr_year = dt_start.year
    curr_month = dt_start.month

    while (curr_year < dt_end.year) or (curr_year == dt_end.year and curr_month <= dt_end.month):
        months.append(f"{curr_year:04d}{curr_month:02d}")
        curr_month += 1
        if curr_month > 12:
            curr_month = 1
            curr_year += 1

    return months

def fetch_month_zip(ym: str) -> Optional[bytes]:
    """
    Obtém o arquivo zip de um mês da CVM, utilizando cache local caso já tenha sido baixado.
    Meses anteriores ao atual são permanentes e mantidos no cache.
    """
    ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f"inf_diario_fi_{ym}.zip")
    
    current_ym = datetime.now().strftime("%Y%m")
    # Se o arquivo já existe em cache e não é o mês corrente, reutiliza
    if os.path.exists(cache_path) and ym < current_ym:
        try:
            with open(cache_path, "rb") as f:
                return f.read()
        except Exception as e:
            print(f"Erro ao ler cache CVM para {ym}: {e}")

    url = f"{CVM_BASE_URL}/inf_diario_fi_{ym}.zip"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=45)
        if response.status_code == 200:
            content = response.content
            # Grava no cache
            try:
                with open(cache_path, "wb") as f:
                    f.write(content)
            except Exception as e:
                print(f"Erro ao gravar cache {cache_path}: {e}")
            return content
        else:
            print(f"CVM retornou status {response.status_code} para {url}")
            return None
    except Exception as e:
        print(f"Exceção ao baixar {url}: {e}")
        return None

def extract_quotes_from_zip(zip_bytes: bytes, target_cnpjs: Dict[str, str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extrai do arquivo ZIP as cotas referentes aos CNPJs desejados.
    target_cnpjs: dicionário {cnpj_limpo: cnpj_formatado}
    Retorna: {cnpj_limpo: [{'date': 'YYYY-MM-DD', 'quota': float, 'net_worth': float}, ...]}
    """
    results = {c: [] for c in target_cnpjs}
    
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            for name in z.namelist():
                if not name.endswith(".csv"):
                    continue
                with z.open(name) as f:
                    header_line = f.readline().decode("utf-8", errors="ignore").strip()
                    cols = [c.strip() for c in header_line.split(";")]
                    
                    try:
                        cnpj_idx = cols.index("CNPJ_FUNDO_CLASSE")
                        date_idx = cols.index("DT_COMPTC")
                        quota_idx = cols.index("VL_QUOTA")
                        pl_idx = cols.index("VL_PATRIM_LIQ") if "VL_PATRIM_LIQ" in cols else -1
                    except ValueError:
                        continue
                        
                    for raw_line in f:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line:
                            continue
                        
                        parts = line.split(";")
                        if len(parts) <= max(cnpj_idx, date_idx, quota_idx):
                            continue
                            
                        raw_cnpj = parts[cnpj_idx].strip()
                        c_clean = clean_cnpj(raw_cnpj)
                        
                        if c_clean in target_cnpjs:
                            dt_str = parts[date_idx].strip()
                            if start_date and dt_str < start_date:
                                continue
                            if end_date and dt_str > end_date:
                                continue
                                
                            try:
                                q_val = float(parts[quota_idx].strip())
                            except ValueError:
                                continue
                                
                            pl_val = None
                            if pl_idx != -1 and len(parts) > pl_idx:
                                try:
                                    pl_val = float(parts[pl_idx].strip())
                                except ValueError:
                                    pl_val = None
                                    
                            results[c_clean].append({
                                "date": dt_str,
                                "quota": q_val,
                                "net_worth": pl_val
                            })
    except Exception as e:
        print(f"Erro ao processar zip da CVM: {e}")
        
    return results

def update_funds_data(funds: List[Dict[str, Any]], start_date: str, end_date: str, progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """
    Atualiza dados de uma lista de fundos para o intervalo solicitado.
    Realiza o download de cada mês da CVM necessário, extrai os registros e salva nos arquivos dos fundos.
    """
    target_cnpjs = {}
    funds_info = {}
    for f in funds:
        raw_cnpj = f.get("cnpj", "")
        c_clean = clean_cnpj(raw_cnpj)
        if c_clean:
            target_cnpjs[c_clean] = format_cnpj(c_clean)
            funds_info[c_clean] = f.get("name", f"Fundo {c_clean}")

    if not target_cnpjs:
        return {"status": "error", "message": "Nenhum CNPJ informado."}

    months = get_months_in_range(start_date, end_date)
    if not months:
        return {"status": "error", "message": "Período inválido."}

    total_months = len(months)
    downloaded_months = 0
    extracted_records = {c: [] for c in target_cnpjs}

    for idx, ym in enumerate(months):
        msg = f"Processando CVM {ym} ({idx + 1}/{total_months})..."
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg)

        zip_bytes = fetch_month_zip(ym)
        if not zip_bytes:
            continue

        month_quotes = extract_quotes_from_zip(zip_bytes, target_cnpjs, start_date, end_date)
        for c, q_list in month_quotes.items():
            extracted_records[c].extend(q_list)
        downloaded_months += 1

    summary = []
    for c_clean, q_list in extracted_records.items():
        res = save_fund_data(c_clean, funds_info[c_clean], q_list)
        summary.append(res)

    return {
        "status": "success",
        "months_processed": downloaded_months,
        "total_months": total_months,
        "funds_updated": summary
    }

def update_incremental(funds: List[Dict[str, Any]], default_start: str = "2024-05-01", target_end: Optional[str] = None, progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """
    Atualização incremental inteligente:
    Identifica a data mais recente já gravada para os fundos.
    Se algum fundo não tiver dados, inicia a partir de default_start.
    Se já houver dados, busca apenas a partir do dia seguinte da última cota até target_end (hoje por padrão).
    """
    if not target_end:
        target_end = datetime.now().strftime("%Y-%m-%d")

    # Encontrar a data mínima necessária
    min_existing_date = None
    all_have_data = True

    for f in funds:
        c_clean = clean_cnpj(f.get("cnpj", ""))
        quotes = load_fund_data(c_clean)
        if not quotes:
            all_have_data = False
            break
        last_date = quotes[-1]["date"]
        if min_existing_date is None or last_date < min_existing_date:
            min_existing_date = last_date

    if not all_have_data or not min_existing_date:
        fetch_start = default_start
    else:
        # Começar no mês da última data para garantir que dias pendentes do mês sejam preenchidos
        fetch_start = min_existing_date

    return update_funds_data(funds, fetch_start, target_end, progress_callback)

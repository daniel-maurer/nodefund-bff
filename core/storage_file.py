"""
Gerenciador de armazenamento em arquivos para o sistema de previdência e investimentos B3.
Persiste múltiplas carteiras, dados de cotas por fundo CVM, cotações de ativos da B3 e benchmarks.
"""

import os
import json
import csv
from datetime import datetime
from typing import Dict, List, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PORTFOLIOS_DIR = os.path.join(DATA_DIR, "portfolios")
MANIFEST_FILE = os.path.join(PORTFOLIOS_DIR, "manifest.json")
FUNDS_DIR = os.path.join(DATA_DIR, "funds")
B3_DIR = os.path.join(DATA_DIR, "b3")
BENCHMARKS_DIR = os.path.join(DATA_DIR, "benchmarks")
LEGACY_PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")

def ensure_dirs():
    os.makedirs(PORTFOLIOS_DIR, exist_ok=True)
    os.makedirs(FUNDS_DIR, exist_ok=True)
    os.makedirs(B3_DIR, exist_ok=True)
    os.makedirs(BENCHMARKS_DIR, exist_ok=True)

def clean_cnpj(cnpj: str) -> str:
    """Remove caracteres não numéricos do CNPJ."""
    return "".join(c for c in cnpj if c.isdigit())

def format_cnpj(clean: str) -> str:
    """Formata CNPJ limpo para XX.XXX.XXX/XXXX-XX."""
    clean = clean.zfill(14)
    if len(clean) != 14:
        return clean
    return f"{clean[0:2]}.{clean[2:5]}.{clean[5:8]}/{clean[8:12]}-{clean[12:14]}"

def clean_ticker(ticker: str) -> str:
    """Limpa e formata o ticker de um ativo da B3 (ex: 'PETR4.SA' -> 'PETR4')."""
    if not ticker:
        return ""
    t = ticker.strip().upper()
    if t.endswith(".SA"):
        t = t[:-3]
    return "".join(c for c in t if c.isalnum())

# =============================================================================
# GERENCIAMENTO DE MÚLTIPLAS CARTEIRAS
# =============================================================================

def load_manifest() -> Dict[str, Any]:
    """Carrega o arquivo manifest com as carteiras registradas."""
    ensure_dirs()
    if not os.path.exists(MANIFEST_FILE):
        # Se não existe manifest, inicializa com padrão
        default_manifest = {
            "active_portfolio_id": "previdencia",
            "portfolios": [
                {"id": "previdencia", "name": "Carteira Previdência Principal", "file": "previdencia.json"},
                {"id": "b3_multimercado", "name": "Carteira Ações & FIIs B3", "file": "b3_multimercado.json"}
            ]
        }
        with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(default_manifest, f, indent=2, ensure_ascii=False)
        return default_manifest

    try:
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar manifest: {e}")
        return {"active_portfolio_id": "previdencia", "portfolios": []}

def save_manifest(manifest_data: Dict[str, Any]) -> bool:
    """Salva o arquivo manifest."""
    ensure_dirs()
    try:
        with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar manifest: {e}")
        return False

def list_portfolios() -> List[Dict[str, Any]]:
    """Lista todas as carteiras cadastradas."""
    manifest = load_manifest()
    active_id = manifest.get("active_portfolio_id")
    result = []
    
    for item in manifest.get("portfolios", []):
        p_id = item.get("id")
        p_file = os.path.join(PORTFOLIOS_DIR, item.get("file", f"{p_id}.json"))
        count = 0
        if os.path.exists(p_file):
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    p_data = json.load(f)
                    count = len(p_data.get("funds", []))
            except Exception:
                pass
        result.append({
            "id": p_id,
            "name": item.get("name", "Carteira"),
            "file": item.get("file"),
            "is_active": (p_id == active_id),
            "asset_count": count
        })
    return result

def get_portfolio_by_id(portfolio_id: str) -> Optional[Dict[str, Any]]:
    """Carrega uma carteira específica pelo ID."""
    ensure_dirs()
    p_file = os.path.join(PORTFOLIOS_DIR, f"{portfolio_id}.json")
    if not os.path.exists(p_file):
        # Tenta fallback legado
        if os.path.exists(LEGACY_PORTFOLIO_FILE):
            try:
                with open(LEGACY_PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None
    try:
        with open(p_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar carteira {portfolio_id}: {e}")
        return None

def get_active_portfolio() -> Dict[str, Any]:
    """Retorna a carteira atualmente selecionada/ativa."""
    manifest = load_manifest()
    active_id = manifest.get("active_portfolio_id", "previdencia")
    p = get_portfolio_by_id(active_id)
    if p:
        return p
    # Se falhar, busca a primeira carteira disponível
    portfolios = manifest.get("portfolios", [])
    if portfolios:
        first_id = portfolios[0].get("id")
        p = get_portfolio_by_id(first_id)
        if p:
            set_active_portfolio(first_id)
            return p
    return {"id": "default", "name": "Minha Carteira", "funds": []}

def set_active_portfolio(portfolio_id: str) -> bool:
    """Define qual carteira é a ativa."""
    manifest = load_manifest()
    exists = any(p["id"] == portfolio_id for p in manifest.get("portfolios", []))
    if not exists:
        return False
    manifest["active_portfolio_id"] = portfolio_id
    return save_manifest(manifest)

def save_portfolio(portfolio_data: Dict[str, Any], portfolio_id: Optional[str] = None) -> bool:
    """
    Salva uma carteira no seu respectivo arquivo JSON.
    Se portfolio_id for omitido, salva na carteira ativa.
    """
    ensure_dirs()
    manifest = load_manifest()
    
    p_id = portfolio_id or portfolio_data.get("id") or manifest.get("active_portfolio_id", "previdencia")
    portfolio_data["id"] = p_id
    portfolio_data["updated_at"] = datetime.now().isoformat()
    
    p_file = os.path.join(PORTFOLIOS_DIR, f"{p_id}.json")
    try:
        with open(p_file, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f, indent=2, ensure_ascii=False)
            
        # Também sincroniza no manifest se o nome mudou
        p_name = portfolio_data.get("name", "Nova Carteira")
        updated_manifest = False
        for p in manifest.get("portfolios", []):
            if p["id"] == p_id:
                if p.get("name") != p_name:
                    p["name"] = p_name
                    updated_manifest = True
                break
        else:
            manifest["portfolios"].append({
                "id": p_id,
                "name": p_name,
                "file": f"{p_id}.json"
            })
            updated_manifest = True
            
        if updated_manifest:
            save_manifest(manifest)
            
        return True
    except Exception as e:
        print(f"Erro ao salvar carteira {p_id}: {e}")
        return False

def create_portfolio(name: str, base_funds: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Cria uma nova carteira vazia ou baseada em uma lista de fundos/ativos."""
    manifest = load_manifest()
    # Gerar ID único amigável
    clean_name = "".join(c for c in name.lower() if c.isalnum() or c == "_").strip("_")
    new_id = f"carteira_{clean_name}_{int(datetime.now().timestamp())}"
    
    new_data = {
        "id": new_id,
        "name": name,
        "created_at": datetime.now().isoformat(),
        "funds": base_funds or []
    }
    
    save_portfolio(new_data, new_id)
    manifest["portfolios"].append({
        "id": new_id,
        "name": name,
        "file": f"{new_id}.json"
    })
    manifest["active_portfolio_id"] = new_id
    save_manifest(manifest)
    return new_data

def delete_portfolio(portfolio_id: str) -> bool:
    """Exclui uma carteira (não permite excluir se for a única)."""
    manifest = load_manifest()
    portfolios = manifest.get("portfolios", [])
    if len(portfolios) <= 1:
        return False
        
    p_to_remove = next((p for p in portfolios if p["id"] == portfolio_id), None)
    if not p_to_remove:
        return False
        
    portfolios.remove(p_to_remove)
    
    # Se deletou a ativa, muda a ativa para a primeira restante
    if manifest.get("active_portfolio_id") == portfolio_id:
        manifest["active_portfolio_id"] = portfolios[0]["id"]
        
    save_manifest(manifest)
    
    # Remover arquivo físico
    p_file = os.path.join(PORTFOLIOS_DIR, f"{portfolio_id}.json")
    if os.path.exists(p_file):
        try:
            os.remove(p_file)
        except Exception:
            pass
            
    return True

# Compatibilidade com código anterior
def load_portfolio() -> Dict[str, Any]:
    return get_active_portfolio()

# =============================================================================
# ARMAZENAMENTO DE FUNDOS CVM
# =============================================================================

def get_fund_file_paths(cnpj: str):
    """Retorna os caminhos dos arquivos JSON e CSV de um fundo CVM."""
    ensure_dirs()
    c = clean_cnpj(cnpj)
    json_path = os.path.join(FUNDS_DIR, f"{c}.json")
    csv_path = os.path.join(FUNDS_DIR, f"{c}.csv")
    return json_path, csv_path

def load_fund_data(cnpj: str) -> List[Dict[str, Any]]:
    """Carrega histórico de cotas de um fundo CVM."""
    json_path, _ = get_fund_file_paths(cnpj)
    if not os.path.exists(json_path):
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("quotes", [])
    except Exception as e:
        print(f"Erro ao carregar dados do fundo {cnpj}: {e}")
        return []

def save_fund_data(cnpj: str, fund_name: str, new_quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Salva ou atualiza incrementalmente as cotas de um fundo CVM."""
    ensure_dirs()
    json_path, csv_path = get_fund_file_paths(cnpj)
    
    existing_quotes = load_fund_data(cnpj)
    quotes_by_date = {q["date"]: q for q in existing_quotes}
        
    added_count = 0
    updated_count = 0
    for q in new_quotes:
        d = q["date"]
        if d in quotes_by_date:
            quotes_by_date[d].update(q)
            updated_count += 1
        else:
            quotes_by_date[d] = q
            added_count += 1
            
    sorted_quotes = [quotes_by_date[d] for d in sorted(quotes_by_date.keys())]
    
    payload = {
        "cnpj": format_cnpj(clean_cnpj(cnpj)),
        "cnpj_clean": clean_cnpj(cnpj),
        "name": fund_name,
        "type": "fund",
        "updated_at": datetime.now().isoformat(),
        "total_records": len(sorted_quotes),
        "start_date": sorted_quotes[0]["date"] if sorted_quotes else None,
        "end_date": sorted_quotes[-1]["date"] if sorted_quotes else None,
        "quotes": sorted_quotes
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["data", "cota", "patrimonio_liquido"])
        for q in sorted_quotes:
            writer.writerow([q.get("date", ""), q.get("quota", ""), q.get("net_worth", "")])
            
    return {
        "cnpj": clean_cnpj(cnpj),
        "added": added_count,
        "updated": updated_count,
        "total": len(sorted_quotes),
        "start_date": payload["start_date"],
        "end_date": payload["end_date"]
    }

# =============================================================================
# ARMAZENAMENTO DE ATIVOS DA B3 (AÇÕES, FIIS, ETFS, BDRS)
# =============================================================================

def get_b3_file_paths(ticker: str):
    """Retorna os caminhos dos arquivos JSON e CSV de um ativo da B3."""
    ensure_dirs()
    t = clean_ticker(ticker)
    json_path = os.path.join(B3_DIR, f"{t}.json")
    csv_path = os.path.join(B3_DIR, f"{t}.csv")
    return json_path, csv_path

def load_b3_data(ticker: str) -> List[Dict[str, Any]]:
    """Carrega histórico de cotações de um ativo da B3."""
    json_path, _ = get_b3_file_paths(ticker)
    if not os.path.exists(json_path):
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("quotes", [])
    except Exception as e:
        print(f"Erro ao carregar ativo B3 {ticker}: {e}")
        return []

def save_b3_data(ticker: str, name: str, new_quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Salva ou atualiza incrementalmente as cotações de um ativo da B3."""
    ensure_dirs()
    t_clean = clean_ticker(ticker)
    json_path, csv_path = get_b3_file_paths(t_clean)
    
    existing = load_b3_data(t_clean)
    by_date = {q["date"]: q for q in existing}
    
    added_count = 0
    updated_count = 0
    for q in new_quotes:
        d = q["date"]
        if d in by_date:
            by_date[d].update(q)
            updated_count += 1
        else:
            by_date[d] = q
            added_count += 1
            
    sorted_quotes = [by_date[d] for d in sorted(by_date.keys())]
    
    payload = {
        "ticker": t_clean,
        "name": name,
        "type": "b3",
        "updated_at": datetime.now().isoformat(),
        "total_records": len(sorted_quotes),
        "start_date": sorted_quotes[0]["date"] if sorted_quotes else None,
        "end_date": sorted_quotes[-1]["date"] if sorted_quotes else None,
        "quotes": sorted_quotes
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["data", "fechamento", "fechamento_ajustado"])
        for q in sorted_quotes:
            writer.writerow([q.get("date", ""), q.get("close", q.get("quota", "")), q.get("quota", "")])
            
    return {
        "ticker": t_clean,
        "added": added_count,
        "updated": updated_count,
        "total": len(sorted_quotes),
        "start_date": payload["start_date"],
        "end_date": payload["end_date"]
    }

def load_asset_data(asset: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Carrega dados históricos de um ativo, seja ele um Fundo CVM ou Ativo B3."""
    a_type = asset.get("type", "fund")
    if a_type == "b3":
        code = asset.get("code") or asset.get("id") or ""
        return load_b3_data(code)
    else:
        cnpj = asset.get("cnpj") or asset.get("code") or ""
        return load_fund_data(cnpj)

# =============================================================================
# ARMAZENAMENTO DE BENCHMARKS
# =============================================================================

def get_benchmark_file_paths(name: str):
    """Retorna os caminhos dos arquivos JSON e CSV de um benchmark."""
    ensure_dirs()
    key = name.lower()
    json_path = os.path.join(BENCHMARKS_DIR, f"{key}.json")
    csv_path = os.path.join(BENCHMARKS_DIR, f"{key}.csv")
    return json_path, csv_path

def load_benchmark_data(name: str) -> List[Dict[str, Any]]:
    """Carrega dados de um benchmark."""
    json_path, _ = get_benchmark_file_paths(name)
    if not os.path.exists(json_path):
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("series", [])
    except Exception as e:
        print(f"Erro ao carregar benchmark {name}: {e}")
        return []

def save_benchmark_data(name: str, display_name: str, series_type: str, new_points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Salva ou atualiza dados de benchmark incrementalmente."""
    ensure_dirs()
    json_path, csv_path = get_benchmark_file_paths(name)
    
    existing_points = load_benchmark_data(name)
    by_date = {p["date"]: p for p in existing_points}
    
    added_count = 0
    for p in new_points:
        d = p["date"]
        if d not in by_date:
            added_count += 1
        by_date[d] = p
        
    sorted_points = [by_date[d] for d in sorted(by_date.keys())]
    
    payload = {
        "benchmark": name.lower(),
        "display_name": display_name,
        "series_type": series_type,
        "updated_at": datetime.now().isoformat(),
        "total_records": len(sorted_points),
        "start_date": sorted_points[0]["date"] if sorted_points else None,
        "end_date": sorted_points[-1]["date"] if sorted_points else None,
        "series": sorted_points
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["data", "valor"])
        for p in sorted_points:
            writer.writerow([p.get("date", ""), p.get("value", "")])
            
    return {
        "benchmark": name.lower(),
        "added": added_count,
        "total": len(sorted_points),
        "start_date": payload["start_date"],
        "end_date": payload["end_date"]
    }

def get_data_status(portfolio_id: Optional[str] = None) -> Dict[str, Any]:
    """Retorna o status atual dos arquivos de todos os fundos e ativos B3 (global ou por carteira) e benchmarks."""
    is_global = portfolio_id is None or portfolio_id == "all"

    funds_status = []
    b3_status = []

    if is_global:
        all_portfolios = list_portfolios()
        funds_map: Dict[str, Dict[str, Any]] = {}
        b3_map: Dict[str, Dict[str, Any]] = {}

        for p_item in all_portfolios:
            p = get_portfolio_by_id(p_item["id"])
            if not p:
                continue
            p_name = p.get("name", p_item["id"])
            for asset in p.get("funds", []):
                a_type = asset.get("type", "fund")
                if a_type == "b3":
                    ticker = clean_ticker(asset.get("code") or asset.get("id"))
                    if ticker not in b3_map:
                        b3_map[ticker] = {"asset": asset, "portfolios": [p_name]}
                    elif p_name not in b3_map[ticker]["portfolios"]:
                        b3_map[ticker]["portfolios"].append(p_name)
                else:
                    cnpj = asset.get("cnpj") or asset.get("code") or ""
                    clean = clean_cnpj(cnpj)
                    if clean:
                        if clean not in funds_map:
                            funds_map[clean] = {"asset": asset, "cnpj": cnpj, "portfolios": [p_name]}
                        elif p_name not in funds_map[clean]["portfolios"]:
                            funds_map[clean]["portfolios"].append(p_name)

        for clean, item in funds_map.items():
            asset = item["asset"]
            quotes = load_fund_data(clean)
            json_path, csv_path = get_fund_file_paths(clean)
            funds_status.append({
                "id": asset.get("id"),
                "name": asset.get("name"),
                "cnpj": item["cnpj"],
                "cnpj_clean": clean,
                "type": "fund",
                "portfolios": item["portfolios"],
                "portfolios_display": ", ".join(item["portfolios"]),
                "target_pct": asset.get("target_pct"),
                "has_file": os.path.exists(json_path),
                "record_count": len(quotes),
                "start_date": quotes[0]["date"] if quotes else None,
                "end_date": quotes[-1]["date"] if quotes else None,
                "last_quota": quotes[-1]["quota"] if quotes else None,
                "json_path": os.path.relpath(json_path, BASE_DIR),
                "csv_path": os.path.relpath(csv_path, BASE_DIR)
            })

        for ticker, item in b3_map.items():
            asset = item["asset"]
            quotes = load_b3_data(ticker)
            json_path, csv_path = get_b3_file_paths(ticker)
            b3_status.append({
                "id": asset.get("id"),
                "name": asset.get("name"),
                "ticker": ticker,
                "type": "b3",
                "portfolios": item["portfolios"],
                "portfolios_display": ", ".join(item["portfolios"]),
                "target_pct": asset.get("target_pct"),
                "has_file": os.path.exists(json_path),
                "record_count": len(quotes),
                "start_date": quotes[0]["date"] if quotes else None,
                "end_date": quotes[-1]["date"] if quotes else None,
                "last_quota": quotes[-1]["quota"] if quotes else None,
                "json_path": os.path.relpath(json_path, BASE_DIR),
                "csv_path": os.path.relpath(csv_path, BASE_DIR)
            })

        p_title = "Global (Todas as Carteiras)"
        p_id_ret = "global"
    else:
        portfolio = get_portfolio_by_id(portfolio_id)
        if not portfolio:
            portfolio = {"name": "Carteira", "funds": []}
        p_title = portfolio.get("name", "Carteira")
        p_id_ret = portfolio.get("id")

        for asset in portfolio.get("funds", []):
            a_type = asset.get("type", "fund")
            if a_type == "b3":
                ticker = clean_ticker(asset.get("code") or asset.get("id"))
                quotes = load_b3_data(ticker)
                json_path, csv_path = get_b3_file_paths(ticker)
                b3_status.append({
                    "id": asset.get("id"),
                    "name": asset.get("name"),
                    "ticker": ticker,
                    "type": "b3",
                    "portfolios": [p_title],
                    "portfolios_display": p_title,
                    "target_pct": asset.get("target_pct"),
                    "has_file": os.path.exists(json_path),
                    "record_count": len(quotes),
                    "start_date": quotes[0]["date"] if quotes else None,
                    "end_date": quotes[-1]["date"] if quotes else None,
                    "last_quota": quotes[-1]["quota"] if quotes else None,
                    "json_path": os.path.relpath(json_path, BASE_DIR),
                    "csv_path": os.path.relpath(csv_path, BASE_DIR)
                })
            else:
                cnpj = asset.get("cnpj") or asset.get("code") or ""
                clean = clean_cnpj(cnpj)
                quotes = load_fund_data(clean)
                json_path, csv_path = get_fund_file_paths(clean)
                funds_status.append({
                    "id": asset.get("id"),
                    "name": asset.get("name"),
                    "cnpj": cnpj,
                    "cnpj_clean": clean,
                    "type": "fund",
                    "portfolios": [p_title],
                    "portfolios_display": p_title,
                    "target_pct": asset.get("target_pct"),
                    "has_file": os.path.exists(json_path),
                    "record_count": len(quotes),
                    "start_date": quotes[0]["date"] if quotes else None,
                    "end_date": quotes[-1]["date"] if quotes else None,
                    "last_quota": quotes[-1]["quota"] if quotes else None,
                    "json_path": os.path.relpath(json_path, BASE_DIR),
                    "csv_path": os.path.relpath(csv_path, BASE_DIR)
                })
        
    from .config_manager import load_benchmarks_config
    benchmarks_status = []
    for bm_item in load_benchmarks_config():
        bm = bm_item["id"]
        pts = load_benchmark_data(bm)
        json_path, csv_path = get_benchmark_file_paths(bm)
        benchmarks_status.append({
            "benchmark": bm,
            "name": bm_item.get("name", bm.upper()),
            "enabled": bm_item.get("enabled", True),
            "source": bm_item.get("source", ""),
            "color": bm_item.get("color", "#94a3b8"),
            "has_file": os.path.exists(json_path),
            "record_count": len(pts),
            "start_date": pts[0]["date"] if pts else None,
            "end_date": pts[-1]["date"] if pts else None,
            "last_value": pts[-1]["value"] if pts else None,
            "json_path": os.path.relpath(json_path, BASE_DIR),
            "csv_path": os.path.relpath(csv_path, BASE_DIR)
        })
        
    return {
        "portfolio_id": p_id_ret,
        "portfolio_name": p_title,
        "funds": funds_status,
        "b3_assets": b3_status,
        "benchmarks": benchmarks_status
    }

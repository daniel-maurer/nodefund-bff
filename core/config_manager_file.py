"""
PrevInvest - Gerenciador de Configurações de Fontes de Dados e Benchmarks.
Persiste em arquivos JSON locais para que o usuário possa visualizar, editar
e atualizar URLs, endpoints, headers e a lista de benchmarks a qualquer momento.
"""

import os
import json
from typing import Dict, List, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "data", "config")
SOURCES_FILE = os.path.join(CONFIG_DIR, "data_sources.json")
BENCHMARKS_FILE = os.path.join(CONFIG_DIR, "benchmarks.json")

DEFAULT_DATA_SOURCES = {
    "cvm": {
        "id": "cvm",
        "name": "CVM - Informe Diário de Fundos",
        "description": "Portal de Dados Abertos da CVM com histórico oficial de cotas diárias de fundos 555.",
        "url_template": "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{YYYYMM}.zip",
        "encoding": "latin1",
        "delimiter": ";",
        "headers": {
            "User-Agent": "Mozilla/5.0"
        },
        "columns": {
            "cnpj": "CNPJ_FUNDO",
            "date": "DT_COMPTC",
            "quota": "VL_QUOTA",
            "net_worth": "VL_PATRIM_LIQ",
            "inflow": "CAPTC_DIA",
            "outflow": "RESG_DIA"
        }
    },
    "b3": {
        "id": "b3",
        "name": "B3 (Ações, FIIs, ETFs) via Yahoo Finance",
        "description": "API do Yahoo Finance para cotações diárias de ativos negociados na B3.",
        "url_template": "https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}.SA?period1={START_TS}&period2={END_TS}&interval=1d",
        "ticker_suffix": ".SA",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    },
    "bcb_sgs": {
        "id": "bcb_sgs",
        "name": "Banco Central do Brasil - Séries Temporais (SGS)",
        "description": "API REST pública do Banco Central para indicadores econômicos oficiais (CDI, IPCA, Poupança, etc.).",
        "url_template": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{SERIE}/dados?formato=json&dataInicial={DATA_INI}&dataFinal={DATA_FIM}",
        "date_format_in": "%d/%m/%Y",
        "date_format_out": "%Y-%m-%d",
        "headers": {
            "User-Agent": "Mozilla/5.0"
        }
    },
    "yahoo_benchmarks": {
        "id": "yahoo_benchmarks",
        "name": "Yahoo Finance - Índices, Câmbio & Criptoativos",
        "description": "Endpoints para coleta de IBOVESPA, S&P 500, Dólar USD/BRL e Criptoativos (Bitcoin).",
        "url_template": "https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}?period1={START_TS}&period2={END_TS}&interval=1d",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    }
}

DEFAULT_BENCHMARKS = [
    {
        "id": "cdi",
        "name": "CDI",
        "type": "bcb_sgs",
        "code": "12",
        "enabled": True,
        "color": "#f59e0b",
        "unit": "daily_rate",
        "source": "Banco Central (SGS 12)"
    },
    {
        "id": "ipca",
        "name": "IPCA",
        "type": "bcb_sgs",
        "code": "433",
        "enabled": True,
        "color": "#06b6d4",
        "unit": "monthly_rate",
        "source": "Banco Central (SGS 433)"
    },
    {
        "id": "poupanca",
        "name": "Poupança",
        "type": "bcb_sgs",
        "code": "196",
        "enabled": True,
        "color": "#84cc16",
        "unit": "monthly_rate",
        "source": "Banco Central (SGS 196)"
    },
    {
        "id": "ibov",
        "name": "IBOVESPA",
        "type": "yahoo",
        "code": "^BVSP",
        "enabled": True,
        "color": "#10b981",
        "unit": "price",
        "source": "Yahoo Finance (^BVSP)"
    },
    {
        "id": "ifix",
        "name": "IFIX",
        "type": "yahoo",
        "code": "XFIX11.SA",
        "enabled": True,
        "color": "#a855f7",
        "unit": "price",
        "source": "Índice FIIs (XFIX11 via Yahoo)"
    },
    {
        "id": "sp500",
        "name": "S&P 500 (BRL)",
        "type": "composite_usd",
        "code": "^GSPC",
        "enabled": True,
        "color": "#f43f5e",
        "unit": "price_usd_brl",
        "source": "S&P 500 em Reais (^GSPC + USD)"
    },
    {
        "id": "btc",
        "name": "Bitcoin (BRL)",
        "type": "composite_usd",
        "code": "BTC-USD",
        "enabled": True,
        "color": "#f97316",
        "unit": "price_usd_brl",
        "source": "Bitcoin em Reais (BTC-USD + USD)"
    },
    {
        "id": "usd",
        "name": "Dólar Comercial",
        "type": "yahoo",
        "code": "USDBRL=X",
        "enabled": True,
        "color": "#64748b",
        "unit": "currency",
        "source": "Yahoo Finance (USDBRL=X)"
    }
]

def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)

def load_data_sources() -> Dict[str, Any]:
    """Carrega as configurações das fontes de dados do arquivo JSON ou inicializa padrão."""
    ensure_config_dir()
    if not os.path.exists(SOURCES_FILE):
        save_data_sources(DEFAULT_DATA_SOURCES)
        return DEFAULT_DATA_SOURCES
    try:
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Garantir que todas as fontes padrão existam
            for k, v in DEFAULT_DATA_SOURCES.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        print(f"Erro ao carregar fontes de dados de {SOURCES_FILE}: {e}")
        return DEFAULT_DATA_SOURCES

def save_data_sources(sources_config: Dict[str, Any]) -> bool:
    """Salva a configuração das fontes de dados no arquivo JSON."""
    ensure_config_dir()
    try:
        with open(SOURCES_FILE, "w", encoding="utf-8") as f:
            json.dump(sources_config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar fontes de dados em {SOURCES_FILE}: {e}")
        return False

def load_benchmarks_config() -> List[Dict[str, Any]]:
    """Carrega a lista configurável de benchmarks do arquivo JSON ou inicializa padrão."""
    ensure_config_dir()
    if not os.path.exists(BENCHMARKS_FILE):
        save_benchmarks_config(DEFAULT_BENCHMARKS)
        return DEFAULT_BENCHMARKS
    try:
        with open(BENCHMARKS_FILE, "r", encoding="utf-8") as f:
            benchmarks = json.load(f)
            # Mesclar benchmarks padrão ausentes
            existing_ids = {b["id"] for b in benchmarks}
            for default_bm in DEFAULT_BENCHMARKS:
                if default_bm["id"] not in existing_ids:
                    benchmarks.append(default_bm)
            return benchmarks
    except Exception as e:
        print(f"Erro ao carregar benchmarks de {BENCHMARKS_FILE}: {e}")
        return DEFAULT_BENCHMARKS

def save_benchmarks_config(benchmarks_list: List[Dict[str, Any]]) -> bool:
    """Salva a lista configurável de benchmarks no arquivo JSON."""
    ensure_config_dir()
    try:
        with open(BENCHMARKS_FILE, "w", encoding="utf-8") as f:
            json.dump(benchmarks_list, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar benchmarks em {BENCHMARKS_FILE}: {e}")
        return False

"""
Script para inicializar e pré-carregar os dados dos 5 fundos e benchmarks de 05/2024 a 08/2026.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.storage import load_portfolio, clean_cnpj
from core.cvm_fetcher import update_funds_data
from core.benchmark_fetcher import update_all_benchmarks

def main():
    print("Iniciando pré-carregamento dos dados dos fundos e benchmarks (05/2024 a 08/2026)...")
    portfolio = load_portfolio()
    funds = portfolio.get("funds", [])
    
    print(f"Fundos a carregar: {len(funds)}")
    for f in funds:
        print(f" - {f['name']} ({f['cnpj']})")
        
    start_date = "2024-05-01"
    end_date = "2026-08-31"
    
    print(f"\n1. Baixando e extraindo dados da CVM ({start_date} a {end_date})...")
    cvm_res = update_funds_data(funds, start_date, end_date, progress_callback=print)
    print(f"CVM finalizado. Meses processados: {cvm_res.get('months_processed', 0)}/{cvm_res.get('total_months', 0)}")
    
    print(f"\n2. Atualizando Benchmarks (CDI, IPCA, IBOV, S&P 500)...")
    bm_res = update_all_benchmarks(start_date, end_date)
    for bm, res in bm_res.items():
        print(f" - {bm}: {res.get('total', 0)} registros (de {res.get('start_date')} a {res.get('end_date')})")
        
    print("\nPré-carregamento concluído com sucesso!")

if __name__ == "__main__":
    main()

"""
nodefund - Distributed Node Architecture
Servidor Web e API REST para Simulação de Investimentos, Múltiplas Carteiras e Rebalanceamento.
Utiliza a biblioteca padrão do Python com ThreadingHTTPServer para desempenho e portabilidade total.
"""

import os
import sys
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime

from core.storage import (
    load_portfolio, save_portfolio, get_data_status,
    load_fund_data, load_benchmark_data, clean_cnpj, clean_ticker,
    list_portfolios, get_active_portfolio, set_active_portfolio,
    create_portfolio, delete_portfolio, get_portfolio_by_id
)
from core.cvm_fetcher import update_funds_data, update_incremental
from core.b3_fetcher import update_b3_assets_data, update_b3_incremental
from core.benchmark_fetcher import update_all_benchmarks, get_market_quotes_summary
from core.simulation import simulate_portfolio
from core.rebalancer import calculate_rebalance_orders
from core.config_manager import (
    load_data_sources, save_data_sources,
    load_benchmarks_config, save_benchmarks_config
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class PrevRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, format, *args):
        # Log simplificado no terminal
        sys.stdout.write(f"[{datetime.now().strftime('%H:%M:%S')}] {self.command} {self.path}\n")
        sys.stdout.flush()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_json_response(self, data, status_code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def parse_json_body(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len > 0:
                raw_body = self.rfile.read(content_len).decode("utf-8")
                return json.loads(raw_body)
        except Exception as e:
            print(f"Erro ao analisar corpo JSON: {e}")
        return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/portfolios":
            portfolios = list_portfolios()
            active = get_active_portfolio()
            self.send_json_response({
                "portfolios": portfolios,
                "active_id": active.get("id"),
                "active_portfolio_id": active.get("id"),
                "active_name": active.get("name")
            })
            return

        elif path == "/api/portfolio" or path == "/api/portfolios/active":
            portfolio = get_active_portfolio()
            self.send_json_response(portfolio)
            return

        elif path.startswith("/api/portfolios/"):
            p_id = path.split("/")[-1]
            portfolio = get_portfolio_by_id(p_id)
            if portfolio:
                self.send_json_response(portfolio)
            else:
                self.send_json_response({"error": "Carteira não encontrada"}, status_code=404)
            return

        elif path == "/api/data/status":
            status = get_data_status()
            self.send_json_response(status)
            return

        elif path == "/api/config/sources":
            self.send_json_response(load_data_sources())
            return

        elif path == "/api/config/benchmarks":
            self.send_json_response(load_benchmarks_config())
            return

        elif path == "/api/health" or path == "/health":
            self.send_json_response({
                "status": "healthy",
                "service": "python-analytics-worker",
                "role": "quantitative-analytics",
                "timestamp": datetime.now().isoformat()
            })
            return

        elif path == "/api/market/quotes" or path == "/api/market/summary":
            qs = urllib.parse.parse_qs(parsed.query)
            refresh = qs.get("refresh", ["false"])[0].lower() in ("true", "1", "yes")
            quotes = get_market_quotes_summary(refresh=refresh)
            self.send_json_response({"quotes": quotes})
            return

        elif path == "/" or path == "":
            self.path = "/index.html"
            return super().do_GET()

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        payload = self.parse_json_body()

        from core import context
        user_id = 'anonymous'
        if isinstance(payload, dict):
            user_id = payload.pop("_userId", "anonymous")
        context.set_current_user_id(user_id)

        if path == "/api/portfolios/select":
            p_id = payload.get("portfolio_id")
            if set_active_portfolio(p_id):
                active = get_active_portfolio()
                self.send_json_response({"status": "success", "active": active, "portfolios": list_portfolios()})
            else:
                self.send_json_response({"error": "Carteira não encontrada"}, status_code=404)
            return

        elif path == "/api/portfolios/create":
            name = payload.get("name", "Nova Carteira").strip()
            if not name:
                name = "Nova Carteira"
            funds = payload.get("funds", [])
            new_p = create_portfolio(name, funds)
            self.send_json_response({"status": "success", "portfolio": new_p, "portfolios": list_portfolios()})
            return

        elif path == "/api/portfolios/delete":
            p_id = payload.get("portfolio_id")
            if delete_portfolio(p_id):
                self.send_json_response({"status": "success", "portfolios": list_portfolios(), "active": get_active_portfolio()})
            else:
                self.send_json_response({"error": "Não é possível excluir a única carteira restante."}, status_code=400)
            return

        elif path == "/api/portfolio" or path == "/api/portfolios":
            funds = payload.get("funds", [])
            total_pct = sum(float(f.get("target_pct", 0.0)) for f in funds)
            if abs(total_pct - 100.0) > 0.01:
                self.send_json_response({
                    "error": f"A soma das alocações deve ser exatamente 100%. Soma atual: {total_pct:.1f}%"
                }, status_code=400)
                return
            
            p_id = payload.get("id")
            success = save_portfolio(payload, portfolio_id=p_id)
            if success:
                self.send_json_response({"status": "success", "message": "Carteira salva com sucesso!", "portfolio": payload, "portfolios": list_portfolios()})
            else:
                self.send_json_response({"error": "Falha ao salvar arquivo da carteira."}, status_code=500)
            return

        elif path == "/api/config/sources":
            try:
                success = save_data_sources(payload)
                if success:
                    self.send_json_response({"status": "success", "message": "Configurações de fontes de dados salvas com sucesso!", "sources": load_data_sources()})
                else:
                    self.send_json_response({"error": "Erro ao salvar fontes de dados."}, status_code=500)
            except Exception as e:
                self.send_json_response({"error": f"Erro ao salvar fontes de dados: {str(e)}"}, status_code=500)
            return

        elif path == "/api/config/benchmarks":
            try:
                benchmarks_data = payload if isinstance(payload, list) else payload.get("benchmarks", [])
                success = save_benchmarks_config(benchmarks_data)
                if success:
                    self.send_json_response({"status": "success", "message": "Configurações de benchmarks salvas com sucesso!", "benchmarks": load_benchmarks_config()})
                else:
                    self.send_json_response({"error": "Erro ao salvar benchmarks."}, status_code=500)
            except Exception as e:
                self.send_json_response({"error": f"Erro ao salvar benchmarks: {str(e)}"}, status_code=500)
            return

        elif path == "/api/data/update":
            # Coleta global de todos os fundos e ativos B3 de todas as carteiras cadastradas
            all_funds_map = {}
            all_b3_map = {}
            for p_info in list_portfolios():
                p_item = get_portfolio_by_id(p_info["id"])
                if not p_item:
                    continue
                for asset in p_item.get("funds", []):
                    if asset.get("type") == "b3":
                        t = clean_ticker(asset.get("code") or asset.get("id"))
                        if t not in all_b3_map:
                            all_b3_map[t] = asset
                    else:
                        cnpj = clean_cnpj(asset.get("cnpj") or asset.get("code") or "")
                        if cnpj and cnpj not in all_funds_map:
                            all_funds_map[cnpj] = asset

            funds = list(all_funds_map.values())
            b3_assets = list(all_b3_map.values())

            start_date = payload.get("start_date", "2024-05-01")
            end_date = payload.get("end_date", datetime.now().strftime("%Y-%m-%d"))
            mode = payload.get("mode", "incremental") # 'incremental' ou 'full'

            try:
                fund_res = {}
                if funds:
                    if mode == "incremental":
                        fund_res = update_incremental(funds, default_start=start_date, target_end=end_date)
                    else:
                        fund_res = update_funds_data(funds, start_date, end_date)

                b3_res = {}
                if b3_assets:
                    if mode == "incremental":
                        b3_res = update_b3_incremental(b3_assets, default_start=start_date, target_end=end_date)
                    else:
                        b3_res = update_b3_assets_data(b3_assets, start_date, end_date)
                
                bm_res = update_all_benchmarks(start_date, end_date)
                
                self.send_json_response({
                    "status": "success",
                    "funds_result": fund_res,
                    "b3_result": b3_res,
                    "benchmarks_result": bm_res,
                    "status_summary": get_data_status(None)
                })
            except Exception as e:
                self.send_json_response({"error": f"Erro durante a atualização: {str(e)}"}, status_code=500)
            return

        elif path == "/api/simulate":
            portfolio = load_portfolio()
            # Se o usuário enviou uma carteira no payload da simulação, utiliza-a
            if "portfolio" in payload and payload["portfolio"].get("funds"):
                portfolio = payload["portfolio"]

            initial_capital = float(payload.get("initial_capital", 20000.0))
            monthly_contribution = float(payload.get("monthly_contribution", 2000.0))
            start_date = payload.get("start_date", "2024-05-01")
            raw_end = str(payload.get("end_date", "")).strip().lower()
            if not raw_end or raw_end in ("today", "atual", "hoje", "latest"):
                end_date = datetime.now().strftime("%Y-%m-%d")
            else:
                end_date = payload.get("end_date")
            rebalance_mode = payload.get("rebalance_mode", "smart_inflow")

            try:
                sim_res = simulate_portfolio(
                    portfolio_config=portfolio,
                    initial_capital=initial_capital,
                    monthly_contribution=monthly_contribution,
                    start_date=start_date,
                    end_date=end_date,
                    rebalance_mode=rebalance_mode
                )
                if "error" in sim_res:
                    self.send_json_response({"error": sim_res["error"]}, status_code=400)
                else:
                    self.send_json_response(sim_res)
            except Exception as e:
                self.send_json_response({"error": f"Erro na simulação: {str(e)}"}, status_code=500)
            return

        elif path == "/api/rebalance/calculate":
            portfolio = load_portfolio()
            if "portfolio" in payload and payload["portfolio"].get("funds"):
                portfolio = payload["portfolio"]

            current_balances = payload.get("current_balances", {})
            contribution = float(payload.get("contribution", 0.0))

            try:
                res = calculate_rebalance_orders(
                    portfolio=portfolio,
                    current_balances=current_balances,
                    contribution=contribution
                )
                if "error" in res:
                    self.send_json_response({"error": res["error"]}, status_code=400)
                else:
                    self.send_json_response(res)
            except Exception as e:
                self.send_json_response({"error": f"Erro no cálculo: {str(e)}"}, status_code=500)
            return

        self.send_json_response({"error": "Endpoint não encontrado"}, status_code=404)

def run_server(port=8000, host="0.0.0.0"):
    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, PrevRequestHandler)
    print(f"\n========================================================")
    print(f" nodefund · Distributed Node Architecture")
    print(f" Servidor de Simulação e Rebalanceamento iniciado!")
    print(f" Acesse no navegador: http://localhost:{port}")
    print(f" Pressione Ctrl+C para encerrar.")
    print(f"========================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
        httpd.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port=port)

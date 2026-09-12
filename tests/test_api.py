import unittest
import threading
import json
import urllib.request
import urllib.parse
from http.server import HTTPServer
from app import PrevRequestHandler
from core.storage import set_active_portfolio

class TestAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start server on dynamic port
        cls.server = HTTPServer(("127.0.0.1", 0), PrevRequestHandler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        # Reset active portfolio to previdencia
        set_active_portfolio("previdencia")

    def _request(self, method, path, data=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        headers = {"Content-Type": "application/json"} if data else {}
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = resp.read().decode("utf-8")
                return resp.status, json.loads(resp_body) if resp_body else {}
        except urllib.error.HTTPError as e:
            resp_body = e.read().decode("utf-8")
            return e.code, json.loads(resp_body) if resp_body else {}

    def test_get_portfolios(self):
        status, data = self._request("GET", "/api/portfolios")
        self.assertEqual(status, 200)
        self.assertIn("portfolios", data)
        self.assertIn("active_portfolio_id", data)
        p_ids = [p["id"] for p in data["portfolios"]]
        self.assertIn("previdencia", p_ids)
        self.assertIn("b3_multimercado", p_ids)

    def test_select_and_simulate_b3_portfolio(self):
        # Select B3 portfolio
        status, data = self._request("POST", "/api/portfolios/select", {"portfolio_id": "b3_multimercado"})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["active"]["id"], "b3_multimercado")

        # Run simulation on active B3 portfolio
        status, sim = self._request("POST", "/api/simulate", {
            "initial_capital": 15000,
            "monthly_contribution": 1500,
            "start_date": "2024-05-02",
            "end_date": "2026-08-31",
            "rebalance_mode": "smart_inflow"
        })
        self.assertEqual(status, 200)
        self.assertIn("final_smart_val", sim)
        self.assertIn("final_passive_val", sim)
        self.assertIn("benchmarks", sim)
        self.assertGreater(sim["final_smart_val"], 0)

        # Test Rebalancing calculator on B3 portfolio
        status, calc = self._request("POST", "/api/rebalance/calculate", {
            "portfolio": data["active"],
            "current_balances": {
                "BOVA11": 5000.0,
                "IVVB11": 2000.0,
                "HGLG11": 3000.0,
                "PETR4": 1000.0,
                "VALE3": 500.0
            },
            "contribution": 2000.0
        })
        self.assertEqual(status, 200)
        self.assertIn("orders", calc)
        self.assertEqual(len(calc["orders"]), 5)
        self.assertGreaterEqual(calc["total_allocated"], 0)

    def test_create_and_delete_portfolio(self):
        # Create a new test portfolio
        status, res = self._request("POST", "/api/portfolios/create", {
            "name": "Carteira Teste Temporária",
            "funds": [
                {
                    "id": "b3_itub4",
                    "type": "b3",
                    "name": "Itaú Unibanco PN (ITUB4)",
                    "code": "ITUB4",
                    "target_pct": 100.0,
                    "min_investment": 35.0
                }
            ]
        })
        self.assertEqual(status, 200)
        self.assertEqual(res["status"], "success")
        new_id = res["portfolio"]["id"]

        # Verify it appears in portfolios list
        status, list_res = self._request("GET", "/api/portfolios")
        self.assertEqual(status, 200)
        self.assertIn(new_id, [p["id"] for p in list_res["portfolios"]])

        # Delete the temporary portfolio
        status, del_res = self._request("POST", "/api/portfolios/delete", {
            "portfolio_id": new_id
        })
        self.assertEqual(status, 200)
        self.assertEqual(del_res["status"], "success")

        # Verify it is gone
        status, list_res2 = self._request("GET", "/api/portfolios")
        self.assertNotIn(new_id, [p["id"] for p in list_res2["portfolios"]])

    def test_data_status(self):
        status, data = self._request("GET", "/api/data/status")
        self.assertEqual(status, 200)
        self.assertIn("funds", data)
        self.assertIn("b3_assets", data)
        self.assertIn("benchmarks", data)
        self.assertEqual(data.get("portfolio_id"), "global")
        self.assertIn("Global", data.get("portfolio_name", ""))
        if data["funds"]:
            self.assertIn("portfolios_display", data["funds"][0])
        bm_ids = [b["benchmark"] for b in data["benchmarks"]]
        self.assertIn("cdi", bm_ids)
        self.assertIn("poupanca", bm_ids)
        self.assertIn("ifix", bm_ids)
        self.assertIn("btc", bm_ids)
        self.assertIn("usd", bm_ids)

    def test_config_sources_get_and_post(self):
        status, sources = self._request("GET", "/api/config/sources")
        self.assertEqual(status, 200)
        self.assertIn("cvm", sources)
        self.assertIn("b3", sources)
        self.assertIn("bcb_sgs", sources)
        self.assertIn("yahoo_benchmarks", sources)

        # Test POST
        sources["test_custom_source"] = {"name": "Fonte Teste"}
        status, res = self._request("POST", "/api/config/sources", sources)
        self.assertEqual(status, 200)
        self.assertEqual(res["status"], "success")

        # Clean up
        del sources["test_custom_source"]
        self._request("POST", "/api/config/sources", sources)

    def test_config_benchmarks_get_and_post(self):
        status, benchmarks = self._request("GET", "/api/config/benchmarks")
        self.assertEqual(status, 200)
        self.assertIsInstance(benchmarks, list)
        bm_ids = [b["id"] for b in benchmarks]
        self.assertIn("cdi", bm_ids)
        self.assertIn("poupanca", bm_ids)
        self.assertIn("ifix", bm_ids)
        self.assertIn("btc", bm_ids)

        # Test POST
        modified = list(benchmarks)
        modified.append({
            "id": "test_bm",
            "name": "Benchmark de Teste",
            "type": "yahoo",
            "code": "TEST",
            "enabled": False,
            "color": "#123456",
            "unit": "price"
        })
        status, res = self._request("POST", "/api/config/benchmarks", modified)
        self.assertEqual(status, 200)
        self.assertEqual(res["status"], "success")

        # Clean up
        self._request("POST", "/api/config/benchmarks", benchmarks)

    def test_simulation_multicurrency(self):
        status, sim = self._request("POST", "/api/simulate", {
            "initial_capital": 20000,
            "monthly_contribution": 2000,
            "start_date": "2024-05-02",
            "end_date": "2026-08-31",
            "rebalance_mode": "smart_inflow"
        })
        self.assertEqual(status, 200)
        self.assertIn("total_invested_usd", sim)
        self.assertIn("final_smart_val_usd", sim)
        self.assertIn("final_passive_val_usd", sim)
        self.assertIn("last_usd_rate", sim)
        self.assertGreater(sim["total_invested_usd"], 0)
        self.assertGreater(sim["final_smart_val_usd"], 0)
        self.assertGreater(sim["last_usd_rate"], 3.0)

        # Verify benchmarks in USD and BRL
        bm = sim.benchmarks if hasattr(sim, "benchmarks") else sim.get("benchmarks", {})
        self.assertIn("cdi", bm)
        self.assertIn("poupanca", bm)
        self.assertIn("ifix", bm)
        self.assertIn("btc", bm)
        self.assertIn("usd", bm)
        self.assertIn("final_cash_val_usd", bm["cdi"])
        self.assertIn("final_cash_return_pct_usd", bm["btc"])

if __name__ == "__main__":
    unittest.main()

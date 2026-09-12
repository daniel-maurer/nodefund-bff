"""
Testes unitários para suporte a múltiplas carteiras e ativos da B3.
"""

import unittest
from core.storage import (
    list_portfolios, get_active_portfolio, set_active_portfolio,
    create_portfolio, delete_portfolio, clean_ticker,
    save_b3_data, load_b3_data, load_asset_data
)
from core.simulation import simulate_portfolio
from core.rebalancer import calculate_rebalance_orders

class TestB3AndPortfolios(unittest.TestCase):
    def test_clean_ticker(self):
        self.assertEqual(clean_ticker("PETR4.SA"), "PETR4")
        self.assertEqual(clean_ticker("  vale3  "), "VALE3")
        self.assertEqual(clean_ticker("ivvb11.sa"), "IVVB11")

    def test_portfolio_lifecycle(self):
        # 1. Listar
        portfolios = list_portfolios()
        self.assertGreaterEqual(len(portfolios), 1)

        # 2. Criar nova carteira de teste
        new_p = create_portfolio("Carteira de Teste Temporária", [
            {"id": "b3_petr4", "type": "b3", "code": "PETR4", "name": "Petrobras PN", "target_pct": 100.0, "min_investment": 50.0}
        ])
        self.assertEqual(new_p["name"], "Carteira de Teste Temporária")
        
        # Carteira recém-criada se torna ativa
        active = get_active_portfolio()
        self.assertEqual(active["id"], new_p["id"])

        # 3. Trocar de volta para 'previdencia'
        set_active_portfolio("previdencia")
        active = get_active_portfolio()
        self.assertEqual(active["id"], "previdencia")

        # 4. Deletar carteira temporária
        del_ok = delete_portfolio(new_p["id"])
        self.assertTrue(del_ok)

    def test_b3_storage(self):
        # Salvar e carregar dados B3
        test_quotes = [
            {"date": "2024-05-02", "quota": 30.0, "close": 30.0},
            {"date": "2024-05-03", "quota": 31.5, "close": 31.5}
        ]
        res = save_b3_data("TEST3", "Ativo Teste B3", test_quotes)
        self.assertEqual(res["total"], 2)

        loaded = load_b3_data("TEST3")
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["quota"], 30.0)

        # Testar load_asset_data
        asset_obj = {"type": "b3", "code": "TEST3"}
        loaded_generic = load_asset_data(asset_obj)
        self.assertEqual(len(loaded_generic), 2)

    def test_hybrid_rebalance(self):
        """Testa a calculadora com carteira híbrida (Fundo de previdência + Ativo B3)."""
        hybrid_portfolio = {
            "name": "Híbrida",
            "funds": [
                {"id": "fundo_arca", "type": "fund", "name": "Fundo Arca Grão", "cnpj": "42.847.903/0001-52", "target_pct": 60.0, "min_investment": 100.0},
                {"id": "b3_bova11", "type": "b3", "name": "BOVA11 ETF", "code": "BOVA11", "target_pct": 40.0, "min_investment": 150.0}
            ]
        }
        balances = {
            "42847903000152": 7000.0, # 70% (acima da meta de 60%)
            "BOVA11": 3000.0          # 30% (abaixo da meta de 40%)
        }
        res = calculate_rebalance_orders(hybrid_portfolio, balances, 2000.0)
        self.assertNotIn("error", res)
        self.assertEqual(res["total_allocated"], 2000.0)

        # BOVA11 deve receber a maior fatia ou totalidade do aporte
        orders = {o["cnpj_clean"]: o for o in res["orders"]}
        self.assertEqual(orders["BOVA11"]["action"], "APLICAR")
        self.assertGreater(orders["BOVA11"]["suggested_contribution"], 1000.0)

if __name__ == "__main__":
    unittest.main()

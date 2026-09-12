"""
Testes unitários para o motor de simulação, rebalanceamento e persistência de dados.
"""

import unittest
import os
import shutil
import tempfile
from core.storage import clean_cnpj, format_cnpj, save_fund_data, load_fund_data, save_portfolio, load_portfolio, get_fund_file_paths
from core.simulation import simulate_portfolio

class TestStorageAndSimulation(unittest.TestCase):
    def setUp(self):
        # Limpar arquivos de CNPJs de teste
        for c in ["11111111000111", "22222222000122", "33333333000133"]:
            j, cv = get_fund_file_paths(c)
            if os.path.exists(j): os.remove(j)
            if os.path.exists(cv): os.remove(cv)
        
    def tearDown(self):
        for c in ["11111111000111", "22222222000122", "33333333000133"]:
            j, cv = get_fund_file_paths(c)
            if os.path.exists(j): os.remove(j)
            if os.path.exists(cv): os.remove(cv)

    def test_cnpj_cleaning_and_formatting(self):
        raw = "32.849.296/0001-06"
        cleaned = clean_cnpj(raw)
        self.assertEqual(cleaned, "32849296000106")
        formatted = format_cnpj(cleaned)
        self.assertEqual(formatted, "32.849.296/0001-06")

    def test_incremental_fund_save(self):
        # Simula salvar dados iniciais
        c = "11111111000111"
        batch_1 = [
            {"date": "2024-05-02", "quota": 1.0, "net_worth": 1000.0},
            {"date": "2024-05-03", "quota": 1.05, "net_worth": 1050.0},
        ]
        res1 = save_fund_data(c, "Fundo Teste", batch_1)
        self.assertEqual(res1["added"], 2)
        self.assertEqual(res1["total"], 2)

        # Simula atualização incremental com 1 data repetida e 1 nova
        batch_2 = [
            {"date": "2024-05-03", "quota": 1.055, "net_worth": 1055.0}, # Atualiza
            {"date": "2024-05-06", "quota": 1.08, "net_worth": 1080.0},  # Novo
        ]
        res2 = save_fund_data(c, "Fundo Teste", batch_2)
        self.assertEqual(res2["added"], 1)
        self.assertEqual(res2["updated"], 1)
        self.assertEqual(res2["total"], 3)

        quotes = load_fund_data(c)
        self.assertEqual(len(quotes), 3)
        self.assertEqual(quotes[1]["quota"], 1.055) # Atualizado com sucesso
        self.assertEqual(quotes[2]["date"], "2024-05-06")

    def test_rebalancing_mechanics(self):
        """
        Testa se o rebalanceamento inteligente compra mais do ativo que caiu.
        Fundo A (meta 50%): cota dobra de 1.0 para 2.0 (subiu muito)
        Fundo B (meta 50%): cota cai de 1.0 para 0.5 (caiu muito)
        No aporte seguinte, o Fundo B deve receber a maior parte ou a totalidade do aporte!
        """
        fundo_a = "22222222000122"
        fundo_b = "33333333000133"

        # Salvar histórico de teste
        save_fund_data(fundo_a, "Fundo A", [
            {"date": "2024-05-02", "quota": 10.0, "net_worth": 1e6},
            {"date": "2024-05-31", "quota": 20.0, "net_worth": 2e6}, # +100%
            {"date": "2024-06-03", "quota": 20.0, "net_worth": 2e6},
        ])
        save_fund_data(fundo_b, "Fundo B", [
            {"date": "2024-05-02", "quota": 10.0, "net_worth": 1e6},
            {"date": "2024-05-31", "quota": 5.0, "net_worth": 5e5},  # -50%
            {"date": "2024-06-03", "quota": 5.0, "net_worth": 5e5},
        ])

        portfolio = {
            "name": "Teste Rebal",
            "funds": [
                {"id": "a", "name": "Fundo A", "cnpj": fundo_a, "target_pct": 50.0},
                {"id": "b", "name": "Fundo B", "cnpj": fundo_b, "target_pct": 50.0},
            ]
        }

        res = simulate_portfolio(
            portfolio_config=portfolio,
            initial_capital=10000.0,
            monthly_contribution=2000.0,
            start_date="2024-05-02",
            end_date="2024-06-03"
        )

        self.assertNotIn("error", res)
        self.assertEqual(res["total_invested"], 12000.0) # 10k + 2k
        
        # Verificar o log de aportes: o fundo B (que caiu) deve ter recebido a maior parte do aporte de 2k
        monthly_log = [c for c in res["contributions_log"] if c["type"] == "monthly"]
        self.assertTrue(len(monthly_log) > 0)
        alloc = monthly_log[0]["smart_allocation"]
        self.assertGreater(alloc[fundo_b], alloc[fundo_a])
        print(f"Alocação no aporte de R$ 2000: Fundo A (subiu): R$ {alloc[fundo_a]}, Fundo B (caiu): R$ {alloc[fundo_b]}")

    def test_advanced_analytics(self):
        """
        Testa se as 5 novas métricas analíticas são geradas corretamente:
        monthly_summary, correlation_matrix, assets_performance, monthly_inflows, treemap_distribution.
        """
        fundo_a = "22222222000122"
        fundo_b = "33333333000133"

        save_fund_data(fundo_a, "Fundo A", [
            {"date": "2024-05-02", "quota": 10.0, "net_worth": 1e6},
            {"date": "2024-05-15", "quota": 10.5, "net_worth": 1.05e6},
            {"date": "2024-05-31", "quota": 11.0, "net_worth": 1.1e6},
            {"date": "2024-06-03", "quota": 11.2, "net_worth": 1.12e6},
            {"date": "2024-06-14", "quota": 11.5, "net_worth": 1.15e6},
            {"date": "2024-06-28", "quota": 11.8, "net_worth": 1.18e6},
        ])
        save_fund_data(fundo_b, "Fundo B", [
            {"date": "2024-05-02", "quota": 20.0, "net_worth": 2e6},
            {"date": "2024-05-15", "quota": 19.5, "net_worth": 1.95e6},
            {"date": "2024-05-31", "quota": 19.0, "net_worth": 1.9e6},
            {"date": "2024-06-03", "quota": 18.8, "net_worth": 1.88e6},
            {"date": "2024-06-14", "quota": 18.5, "net_worth": 1.85e6},
            {"date": "2024-06-28", "quota": 18.0, "net_worth": 1.8e6},
        ])

        portfolio = {
            "name": "Teste Analytics",
            "funds": [
                {"id": "a", "name": "Fundo A", "cnpj": fundo_a, "target_pct": 60.0, "min_investment": 100.0},
                {"id": "b", "name": "Fundo B", "cnpj": fundo_b, "target_pct": 40.0, "min_investment": 100.0},
            ]
        }

        res = simulate_portfolio(
            portfolio_config=portfolio,
            initial_capital=10000.0,
            monthly_contribution=1000.0,
            start_date="2024-05-02",
            end_date="2024-06-28"
        )

        self.assertNotIn("error", res)
        # 1. monthly_summary
        self.assertIn("monthly_summary", res)
        self.assertTrue(len(res["monthly_summary"]) >= 2)
        m0 = res["monthly_summary"][0]
        self.assertIn("capital_gain", m0)
        self.assertIn("return_pct", m0)
        self.assertIn("asset_capital_gains", m0)
        sum_gains = sum(m0["asset_capital_gains"].values())
        self.assertAlmostEqual(sum_gains, m0["capital_gain"], places=1)
        self.assertIn("benchmarks_returns", m0)

        # Verificar timeline asset_profits
        last_pt = res["timeline"][-1]
        self.assertIn("asset_profits", last_pt)
        sum_profits = sum(last_pt["asset_profits"].values())
        self.assertAlmostEqual(sum_profits, last_pt["smart_profit"], places=1)

        # 2. correlation_matrix
        self.assertIn("correlation_matrix", res)
        self.assertIn("matrix", res["correlation_matrix"])
        self.assertIn("labels", res["correlation_matrix"])
        self.assertTrue(len(res["correlation_matrix"]["matrix"]) >= 2)

        # 3. assets_performance
        self.assertIn("assets_performance", res)
        self.assertEqual(len(res["assets_performance"]), 2)
        p0 = res["assets_performance"][0]
        self.assertIn("cumulative_return_pct", p0)
        self.assertIn("annualized_return_pct", p0)
        self.assertIn("annualized_volatility_pct", p0)
        self.assertIn("max_drawdown_pct", p0)

        # 4. monthly_inflows
        self.assertIn("monthly_inflows", res)
        self.assertTrue(len(res["monthly_inflows"]) >= 2)
        inf0 = res["monthly_inflows"][0]
        self.assertIn("month_label", inf0)
        self.assertIn("allocations", inf0)
        self.assertIn("amount", inf0)

        # 5. treemap_distribution
        self.assertIn("treemap_distribution", res)
        self.assertEqual(len(res["treemap_distribution"]), 2)
        t0 = res["treemap_distribution"][0]
        self.assertIn("effective_pct", t0)
        self.assertIn("current_balance", t0)

    def test_return_attribution_closure(self):
        """
        Testa se a soma da contribuição de cada ativo (smart_contributions)
        iguala exatamente a rentabilidade total da carteira (smart_return_pct) em cada data.
        """
        fundo_a = "22222222000122"
        fundo_b = "33333333000133"

        save_fund_data(fundo_a, "Fundo A", [
            {"date": "2024-05-02", "quota": 10.0, "net_worth": 1e6},
            {"date": "2024-05-15", "quota": 11.0, "net_worth": 1.1e6},
            {"date": "2024-05-31", "quota": 12.0, "net_worth": 1.2e6},
            {"date": "2024-06-03", "quota": 13.0, "net_worth": 1.3e6},
        ])
        save_fund_data(fundo_b, "Fundo B", [
            {"date": "2024-05-02", "quota": 20.0, "net_worth": 2e6},
            {"date": "2024-05-15", "quota": 19.0, "net_worth": 1.9e6},
            {"date": "2024-05-31", "quota": 18.0, "net_worth": 1.8e6},
            {"date": "2024-06-03", "quota": 17.0, "net_worth": 1.7e6},
        ])

        portfolio = {
            "name": "Teste Atribuicao",
            "funds": [
                {"id": "a", "name": "Fundo A", "cnpj": fundo_a, "target_pct": 50.0},
                {"id": "b", "name": "Fundo B", "cnpj": fundo_b, "target_pct": 50.0},
            ]
        }

        res = simulate_portfolio(
            portfolio_config=portfolio,
            initial_capital=10000.0,
            monthly_contribution=1000.0,
            start_date="2024-05-02",
            end_date="2024-06-03"
        )

        self.assertNotIn("error", res)
        self.assertTrue(len(res["timeline"]) > 0)

        for entry in res["timeline"]:
            # BRL
            self.assertIn("smart_contributions", entry)
            self.assertIn("invested_by_asset", entry)
            contrib_sum = sum(entry["smart_contributions"].values())
            # Devido a arredondamentos de 2 casas decimais, a diferença não pode passar de 0.05%
            self.assertAlmostEqual(contrib_sum, entry["smart_return_pct"], delta=0.05)

            # USD
            self.assertIn("smart_contributions_usd", entry)
            contrib_sum_usd = sum(entry["smart_contributions_usd"].values())
            self.assertAlmostEqual(contrib_sum_usd, entry["smart_return_pct_usd"], delta=0.05)

if __name__ == "__main__":
    unittest.main()


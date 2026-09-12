"""
Testes unitários para o módulo de cálculo da Calculadora de Rebalanceamento com restrição de tíquete mínimo.
"""

import unittest
from core.rebalancer import calculate_rebalance_orders

class TestRebalancer(unittest.TestCase):
    def setUp(self):
        self.portfolio = {
            "name": "Carteira Teste",
            "funds": [
                {"id": "f1", "name": "Fundo A", "cnpj": "11.111.111/0001-11", "target_pct": 50.0, "min_investment": 100.0},
                {"id": "f2", "name": "Fundo B", "cnpj": "22.222.222/0001-22", "target_pct": 50.0, "min_investment": 500.0}
            ]
        }

    def test_rebalance_buys_underweight(self):
        # Fundo A tem R$ 8.000 (80%), Fundo B tem R$ 2.000 (20%). Total = 10.000.
        # Meta: 50% cada.
        # Aporte de R$ 2.000. Total projetado = 12.000.
        # Meta ideal: R$ 6.000 cada.
        # Fundo A (já tem 8k) está com excesso (+2k).
        # Fundo B (tem 2k) precisa de +4k.
        # Todo o aporte de 2.000 deve ir para o Fundo B!
        current_balances = {
            "11111111000111": 8000.0,
            "22222222000122": 2000.0
        }
        res = calculate_rebalance_orders(self.portfolio, current_balances, 2000.0)
        
        self.assertNotIn("error", res)
        self.assertEqual(res["total_allocated"], 2000.0)
        
        order_map = {o["cnpj_clean"]: o for o in res["orders"]}
        self.assertEqual(order_map["11111111000111"]["suggested_contribution"], 0.0)
        self.assertEqual(order_map["22222222000122"]["suggested_contribution"], 2000.0)
        self.assertEqual(order_map["22222222000122"]["action"], "APLICAR")

    def test_respects_minimum_ticket(self):
        # Fundo B tem tíquete mínimo de R$ 500.
        # Se o usuário aportar apenas R$ 300, não pode sugerir aplicar no Fundo B abaixo do mínimo de 500!
        current_balances = {
            "11111111000111": 5000.0,
            "22222222000122": 2000.0  # mais defasado, mas seu min_investment é 500
        }
        res = calculate_rebalance_orders(self.portfolio, current_balances, 300.0)
        
        order_map = {o["cnpj_clean"]: o for o in res["orders"]}
        # Fundo B não pode receber menos que R$ 500
        self.assertTrue(
            order_map["22222222000122"]["suggested_contribution"] == 0.0 or
            order_map["22222222000122"]["suggested_contribution"] >= 500.0
        )
        # Fundo A aceita R$ 100, então pode absorver os R$ 300
        if order_map["11111111000111"]["suggested_contribution"] > 0:
            self.assertGreaterEqual(order_map["11111111000111"]["suggested_contribution"], 100.0)

    def test_zero_contribution(self):
        current_balances = {"11111111000111": 5000.0, "22222222000122": 5000.0}
        res = calculate_rebalance_orders(self.portfolio, current_balances, 0.0)
        self.assertEqual(res["total_allocated"], 0.0)
        self.assertEqual(res["unallocated_cash"], 0.0)

if __name__ == "__main__":
    unittest.main()

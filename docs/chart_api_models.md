# Especificação de Modelos e Endpoints para APIs de Gráficos

Este documento define os modelos de dados, esquemas JSON e contratos de API para os gráficos da plataforma Prev, em especial o **Gráfico de Rentabilidade (Return Attribution)** e visualizações analíticas. Serve como especificação para futuras APIs REST / GraphQL.

---

## 1. Modelo Matemático: Atribuição de Retorno (Return Attribution)

Dada uma carteira com conjunto de ativos $C$, na data $t$:

- **Patrimônio de Mercado do Ativo $c$**:
  $$V_c(t) = Q_c(t) \times P_c(t)$$
- **Capital Líquido Aportado no Ativo $c$**:
  $$I_c(t) = I_c(0) + \sum_{k \le t} \text{Aporte}_c(k)$$
- **Total Aportado na Carteira**:
  $$I_{\text{total}}(t) = \sum_{c \in C} I_c(t)$$
- **Lucro / Prejuízo Líquido Nominal do Ativo $c$**:
  $$\Delta P_c(t) = V_c(t) - I_c(t)$$
- **Contribuição Percentual Aditiva do Ativo $c$ para a Carteira**:
  $$C_c(t) = \frac{\Delta P_c(t)}{I_{\text{total}}(t)} \times 100$$

### Identidade Fundamental de Fechamento:
$$\sum_{c \in C} C_c(t) = \frac{\sum_{c \in C} \Delta P_c(t)}{I_{\text{total}}(t)} \times 100 = \frac{V_{\text{total}}(t) - I_{\text{total}}(t)}{I_{\text{total}}(t)} \times 100 = R_{\text{carteira}}(t)$$

*Exemplo Prático*: Se a carteira tem $+50\%$ de rentabilidade acumulada, a soma das contribuições $C_c(t)$ de cada fundo resultará em exatamente $+50\%$, evidenciando os fundos que geraram valor positivo e os detratores (negativos).

---

## 2. Endpoints Propostos para Futuras APIs

### `GET /api/v1/portfolios/{portfolio_id}/charts/performance`
Retorna a série temporal da rentabilidade consolidada, contribuição de cada ativo e benchmarks selecionados.

#### Parâmetros de Query (Query Params):
| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `currency` | string (`BRL` \| `USD`) | `BRL` | Moeda de denominação dos cálculos |
| `benchmark` | string | `cdi` | Benchmark a comparar (`cdi`, `ibov`, `sp500`, `ipca`, `poupanca`, `ifix`, `bitcoin`, `dolar`, `none`) |
| `mode` | string | `consolidated` | Modo de dados: `consolidated` (carteira total), `attribution` (decomposição por ativo) |
| `period` | string | `all` | Período de filtro: `1m`, `30d`, `90d`, `6m`, `1y`, `all` |

#### Resposta de Sucesso (`200 OK`):
```json
{
  "portfolio_id": "carteira_conservadora",
  "currency": "BRL",
  "period": "all",
  "benchmark_selected": "CDI",
  "series": [
    {
      "date": "2024-05-02",
      "portfolio_return_pct": 0.0,
      "benchmark_return_pct": 0.0,
      "total_invested": 100000.0,
      "total_value": 100000.0,
      "asset_contributions": {
        "fundo_arca": 0.0,
        "fundo_real_investor": 0.0,
        "fundo_giant": 0.0
      },
      "invested_by_asset": {
        "fundo_arca": 40000.0,
        "fundo_real_investor": 30000.0,
        "fundo_giant": 30000.0
      },
      "value_by_asset": {
        "fundo_arca": 40000.0,
        "fundo_real_investor": 30000.0,
        "fundo_giant": 30000.0
      }
    },
    {
      "date": "2024-06-03",
      "portfolio_return_pct": 5.24,
      "benchmark_return_pct": 1.05,
      "total_invested": 102000.0,
      "total_value": 107344.8,
      "asset_contributions": {
        "fundo_arca": 2.85,
        "fundo_real_investor": 2.65,
        "fundo_giant": -0.26
      },
      "invested_by_asset": {
        "fundo_arca": 40800.0,
        "fundo_real_investor": 30600.0,
        "fundo_giant": 30600.0
      },
      "value_by_asset": {
        "fundo_arca": 43707.0,
        "fundo_real_investor": 33303.0,
        "fundo_giant": 30334.8
      }
    }
  ],
  "assets_metadata": {
    "fundo_arca": {
      "name": "ARCA MULTIMERCADO PREVIDENCIÁRIO",
      "cnpj": "32849296000106",
      "color": "#1C82AD",
      "target_pct": 40.0
    },
    "fundo_real_investor": {
      "name": "REAL INVESTOR 70 PREVIDENCIA FIF MULTIMERCADO",
      "cnpj": "34106511000185",
      "color": "#3B6978",
      "target_pct": 30.0
    },
    "fundo_giant": {
      "name": "GIANT PREV FIFE FIF MULTIMERCADO RL",
      "cnpj": "35635105000118",
      "color": "#B86B43",
      "target_pct": 30.0
    }
  },
  "summary": {
    "final_portfolio_return_pct": 5.24,
    "final_benchmark_return_pct": 1.05,
    "alpha_pct": 4.19,
    "top_contributor": {
      "id": "fundo_arca",
      "contribution_pct": 2.85,
      "share_of_total_gain_pct": 54.39
    },
    "worst_contributor": {
      "id": "fundo_giant",
      "contribution_pct": -0.26,
      "share_of_total_gain_pct": -4.96
    }
  }
}
```

---

## 3. Modelo de Componente Frontend (`rentabilidade-chart.js`)

O frontend consome essa estrutura encapsulado no componente `RentabilidadeChartComponent`:
1. **Gerenciamento de Estado**:
   - `currency`: `'BRL'` | `'USD'`
   - `viewMode`: `'consolidated'` | `'attribution_lines'` | `'attribution_stacked'`
   - `benchmark`: `'CDI'` | `'IBOV'` | `'IPCA'` | etc.
   - `period`: `'all'` | `'1y'` | `'6m'` | `'90d'` | `'30d'` | `'1m'`
2. **Camada de Renderização**:
   - Canvas Chart.js com gradientes de cores da paleta oficial do sistema.
   - Interpolação suave cúbica (`tension: 0.35`).
   - Tooltip Dribbble flutuante customizado com as pílulas de cada fundo e sua contribuição percentual e nominal.

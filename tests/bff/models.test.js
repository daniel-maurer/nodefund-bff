const test = require('node:test');
const assert = require('node:assert');

const Asset = require('../../models/Asset');
const Portfolio = require('../../models/Portfolio');
const MarketQuote = require('../../models/MarketQuote');
const { SimulationRequest } = require('../../models/Simulation');
const { RebalanceRequest } = require('../../models/Rebalance');
const DistributedNode = require('../../models/DistributedNode');

test('Asset Model - limpa CNPJ e ticker corretamente', () => {
  const fund = new Asset({
    id: 'fundo1',
    name: 'Fundo Teste',
    type: 'fund',
    cnpj: '32.849.296/0001-06',
    target_pct: 50
  });
  assert.strictEqual(fund.type, 'fund');
  assert.strictEqual(fund.cnpj, '32.849.296/0001-06');
  assert.strictEqual(fund.validate().isValid, true);

  const b3 = new Asset({
    id: 'petr4',
    name: 'Petrobras PN',
    type: 'b3',
    code: 'PETR4.SA',
    target_pct: 50
  });
  assert.strictEqual(b3.type, 'b3');
  assert.strictEqual(b3.code, 'PETR4');
  assert.strictEqual(b3.validate().isValid, true);
});

test('Asset Model - validação de campos obrigatórios', () => {
  const invalidFund = new Asset({
    name: '',
    type: 'fund',
    cnpj: ''
  });
  const res = invalidFund.validate();
  assert.strictEqual(res.isValid, false);
  assert.ok(res.errors.length >= 2);
});

test('Portfolio Model - validação de soma de alocação (100%)', () => {
  const validPortfolio = new Portfolio({
    id: 'p_valid',
    name: 'Carteira Válida',
    funds: [
      { id: 'f1', name: 'Fundo 1', type: 'fund', cnpj: '32849296000106', target_pct: 60 },
      { id: 'f2', name: 'Fundo 2', type: 'fund', cnpj: '33588607000193', target_pct: 40 }
    ]
  });
  assert.strictEqual(validPortfolio.calculateTotalAllocation(), 100);
  assert.strictEqual(validPortfolio.validate().isValid, true);

  const invalidPortfolio = new Portfolio({
    id: 'p_invalid',
    name: 'Carteira Inválida',
    funds: [
      { id: 'f1', name: 'Fundo 1', type: 'fund', cnpj: '32849296000106', target_pct: 60 },
      { id: 'f2', name: 'Fundo 2', type: 'fund', cnpj: '33588607000193', target_pct: 30 }
    ]
  });
  assert.strictEqual(invalidPortfolio.calculateTotalAllocation(), 90);
  const invalidRes = invalidPortfolio.validate();
  assert.strictEqual(invalidRes.isValid, false);
  assert.ok(invalidRes.errors.some(e => e.includes('100%')));
});

test('MarketQuote Model - formatação numérica padrão brasileiro', () => {
  const quote = new MarketQuote({
    id: 'sp500',
    name: 'S&P 500',
    raw_value: 5678.9,
    pct_change: 1.25,
    date: '11/09/2026',
    raw_date: '2026-09-11'
  });
  assert.strictEqual(quote.formatted_value, '5.678,90 pts');
  assert.strictEqual(quote.is_positive, true);

  const quoteUsd = new MarketQuote({
    id: 'usd',
    name: 'Dólar Hoje',
    raw_value: 5.12,
    pct_change: -0.4,
    date: '11/09/2026',
    raw_date: '2026-09-11'
  });
  assert.strictEqual(quoteUsd.formatted_value, 'R$ 5,12');
  assert.strictEqual(quoteUsd.is_positive, false);

  // Valida formatação sem casas decimais (ex: Ibovespa 177.419 pts)
  assert.strictEqual(MarketQuote.formatPtBrNumber(177419, 0), '177.419');
});

test('SimulationRequest Model - validação de limites e datas', () => {
  const sim = new SimulationRequest({
    initial_capital: 10000,
    monthly_contribution: 1500,
    start_date: '2024-01-01',
    end_date: '2025-01-01'
  });
  assert.strictEqual(sim.validate().isValid, true);

  const simToday = new SimulationRequest({
    start_date: '2024-01-01',
    end_date: 'today'
  });
  assert.strictEqual(simToday.validate().isValid, true);
  assert.strictEqual(simToday.end_date, new Date().toISOString().slice(0, 10));

  const simAtual = new SimulationRequest({
    start_date: '2024-01-01',
    end_date: 'atual'
  });
  assert.strictEqual(simAtual.validate().isValid, true);
  assert.strictEqual(simAtual.end_date, new Date().toISOString().slice(0, 10));

  const invalidSim = new SimulationRequest({
    initial_capital: -50,
    start_date: '2026-01-01',
    end_date: '2024-01-01'
  });
  assert.strictEqual(invalidSim.validate().isValid, false);
});

test('DistributedNode Model - lifecycle e métricas de saúde', () => {
  const node = new DistributedNode({
    id: 'test-node-01',
    name: 'Worker Teste',
    role: 'worker',
    endpoint: 'http://localhost:9000'
  });
  assert.strictEqual(node.isHealthy(), false);
  node.updateStatus('online', 15, { tasks_completed: 42 });
  assert.strictEqual(node.isHealthy(), true);
  assert.strictEqual(node.latency_ms, 15);
  assert.strictEqual(node.metrics.tasks_completed, 42);
});

const test = require('node:test');
const assert = require('node:assert');
const path = require('path');
const fs = require('fs/promises');

const PortfolioRepository = require('../../storage/portfolioRepository');
const ConfigRepository = require('../../storage/configRepository');
const MarketRepository = require('../../storage/marketRepository');
const DataStatusRepository = require('../../storage/dataStatusRepository');

test('PortfolioRepository - listagem e carteira ativa', async () => {
  const portfolios = await PortfolioRepository.listPortfolios();
  assert.ok(Array.isArray(portfolios));
  assert.ok(portfolios.length >= 1);

  const active = await PortfolioRepository.getActivePortfolio();
  assert.ok(active);
  assert.ok(active.id);
  assert.ok(Array.isArray(active.funds));
  assert.ok(active.funds.length > 0);
});

test('PortfolioRepository - ciclo de vida (criar, salvar, alternar e deletar carteira de teste)', async () => {
  // 1. Criar carteira temporária de teste
  const created = await PortfolioRepository.createPortfolio('Carteira Teste Node', [
    { id: 'f1', name: 'Ativo 1', type: 'fund', cnpj: '32849296000106', target_pct: 100 }
  ]);
  assert.ok(created);
  assert.ok(created.id);
  assert.strictEqual(created.name, 'Carteira Teste Node');

  // 2. Salvar com alteração válida
  created.name = 'Carteira Teste Node Editada';
  created.funds = [
    { id: 'f1', name: 'Ativo 1', type: 'fund', cnpj: '32849296000106', target_pct: 50 },
    { id: 'f2', name: 'Ativo 2', type: 'fund', cnpj: '33588607000193', target_pct: 50 }
  ];
  const saved = await PortfolioRepository.savePortfolio(created, created.id);
  assert.strictEqual(saved.name, 'Carteira Teste Node Editada');
  assert.strictEqual(saved.funds.length, 2);

  // 3. Validação de erro ao salvar com soma diferente de 100%
  created.funds[0].target_pct = 70; // 70 + 50 = 120%
  await assert.rejects(async () => {
    await PortfolioRepository.savePortfolio(created, created.id);
  }, /100%/);

  // 4. Selecionar outra carteira como ativa para poder deletar o teste
  const list = await PortfolioRepository.listPortfolios();
  const other = list.find(p => p.id !== created.id);
  if (other) {
    await PortfolioRepository.setActivePortfolio(other.id);
  }

  // 5. Deletar carteira de teste
  const delRes = await PortfolioRepository.deletePortfolio(created.id);
  assert.strictEqual(delRes.success, true);
});

test('ConfigRepository - fontes de dados e benchmarks', async () => {
  const sources = await ConfigRepository.loadSources();
  assert.ok(sources);
  assert.ok(sources.cvm || sources.b3);

  const benchmarks = await ConfigRepository.loadBenchmarks();
  assert.ok(Array.isArray(benchmarks));
  assert.ok(benchmarks.length >= 4);
});

test('MarketRepository - retorna as 4 cotações principais formatadas', async () => {
  const quotes = await MarketRepository.getMarketQuotes();
  assert.ok(Array.isArray(quotes));
  assert.strictEqual(quotes.length, 4);

  const ids = quotes.map(q => q.id);
  assert.ok(ids.includes('sp500'));
  assert.ok(ids.includes('ibov'));
  assert.ok(ids.includes('btc'));
  assert.ok(ids.includes('usd'));

  for (const q of quotes) {
    assert.ok(q.formatted_value);
    assert.ok(typeof q.pct_change === 'number');
    assert.ok(typeof q.is_positive === 'boolean');
    assert.ok(q.date);
  }
});

test('DataStatusRepository - inventário de fundos, b3 e benchmarks', async () => {
  const status = await DataStatusRepository.getDataStatus();
  assert.ok(status);
  assert.ok(Array.isArray(status.funds));
  assert.ok(Array.isArray(status.b3_assets));
  assert.ok(Array.isArray(status.benchmarks));
  assert.strictEqual(status.is_global, true);
});

const test = require('node:test');
const assert = require('node:assert');
const { app } = require('../../index');

let server;
const TEST_PORT = 8099;
const BASE_URL = `http://127.0.0.1:${TEST_PORT}`;

test.before(async () => {
  await new Promise((resolve) => {
    server = app.listen(TEST_PORT, '127.0.0.1', () => {
      resolve();
    });
  });
});

test.after(async () => {
  await new Promise((resolve) => {
    server.close(() => resolve());
  });
});

test('API GET /api/portfolios - lista carteiras e ativa', async () => {
  const res = await fetch(`${BASE_URL}/api/portfolios`);
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.ok(Array.isArray(data.portfolios));
  assert.ok(data.active_id || data.active_portfolio_id);
});

test('API GET /api/portfolio - retorna carteira ativa (singular)', async () => {
  const res = await fetch(`${BASE_URL}/api/portfolio`);
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.ok(data.id);
  assert.ok(Array.isArray(data.funds));
});

test('API GET /api/config/sources - retorna configurações de fontes', async () => {
  const res = await fetch(`${BASE_URL}/api/config/sources`);
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.ok(data.cvm || data.b3);
});

test('API GET /api/config/benchmarks - retorna lista de benchmarks', async () => {
  const res = await fetch(`${BASE_URL}/api/config/benchmarks`);
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.ok(Array.isArray(data));
  assert.ok(data.length >= 4);
});

test('API GET /api/market/quotes - retorna as 4 cotações do Hero Header', async () => {
  const res = await fetch(`${BASE_URL}/api/market/quotes`);
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.ok(Array.isArray(data.quotes));
  assert.strictEqual(data.quotes.length, 4);
  assert.ok(data.quotes.find(q => q.id === 'sp500'));
});

test('API GET /api/data/status - inventário de dados locais', async () => {
  const res = await fetch(`${BASE_URL}/api/data/status`);
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.ok(Array.isArray(data.funds));
  assert.ok(Array.isArray(data.b3_assets));
});

test('API GET /api/nodes - topologia da Distributed Node Architecture', async () => {
  const res = await fetch(`${BASE_URL}/api/nodes`);
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.ok(data.cluster_id);
  assert.ok(Array.isArray(data.nodes));
  assert.ok(data.nodes.length >= 2);
  const bffNode = data.nodes.find(n => n.role === 'bff-gateway');
  assert.ok(bffNode);
  assert.strictEqual(bffNode.runtime, 'nodejs');
  assert.strictEqual(bffNode.is_healthy, true);
});

test('API GET /api/health - diagnóstico de saúde do BFF', async () => {
  const res = await fetch(`${BASE_URL}/api/nodes/health`);
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  assert.strictEqual(data.status, 'healthy');
  assert.strictEqual(data.service, 'nodefund-bff');
  assert.ok(data.system);
  assert.ok(data.process);
});

test('API POST /api/portfolios - rejeita carteira com alocação diferente de 100%', async () => {
  const payload = {
    id: 'carteira_invalida',
    name: 'Carteira Inválida Teste',
    funds: [
      { id: 'f1', name: 'Ativo 1', type: 'fund', cnpj: '32849296000106', target_pct: 40 }
    ]
  };

  const res = await fetch(`${BASE_URL}/api/portfolios`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  assert.strictEqual(res.status, 400);
  const data = await res.json();
  assert.ok(data.error.includes('100%'));
});

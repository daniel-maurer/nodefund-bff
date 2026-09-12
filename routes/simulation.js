/**
 * Rotas de Simulação Financeira & Projeção Patrimonial
 * Distributed Node Architecture
 */

const express = require('express');
const router = express.Router();
const PortfolioRepository = require('../storage/portfolioRepository');
const nodeDispatcher = require('../services/nodeDispatcher');
const { SimulationRequest } = require('../models/Simulation');

// POST /api/simulate - Dispara simulação histórica
router.post('/', async (req, res, next) => {
  try {
    const payload = req.body || {};

    // Se o payload não inclui carteira, busca a carteira ativa atual do BFF
    let portfolio = payload.portfolio;
    if (!portfolio || !portfolio.funds || portfolio.funds.length === 0) {
      portfolio = await PortfolioRepository.getActivePortfolio(req.userId);
    }

    const simReq = new SimulationRequest({
      ...payload,
      portfolio
    });

    const validation = simReq.validate();
    if (!validation.isValid) {
      return res.status(400).json({ error: validation.errors.join(' ') });
    }

    // Despacha para o nó de análise quantitativa, incluindo userId
    try {
      const simPayload = simReq.toJSON();
      simPayload._userId = req.userId; // Injetado para o Python saber qual usuário
      const result = await nodeDispatcher.dispatchSimulation(simPayload);
      res.json(result);
    } catch (nodeErr) {
      const status = nodeErr.status || 500;
      return res.status(status).json({
        error: nodeErr.message || 'Erro durante a simulação quantitativa.',
        details: nodeErr.details || null
      });
    }
  } catch (err) {
    next(err);
  }
});

// GET /api/simulate/presets - Parâmetros padrão para simulação
router.get('/presets', (req, res) => {
  res.json({
    initial_capital: 20000.0,
    monthly_contribution: 2000.0,
    start_date: '2024-05-01',
    end_date: new Date().toISOString().slice(0, 10),
    rebalance_mode: 'smart_inflow',
    modes: [
      { id: 'smart_inflow', name: 'Aporte Inteligente (Aloca no mais distante da meta)' },
      { id: 'proportional', name: 'Aporte Proporcional às Metas' }
    ]
  });
});

module.exports = router;

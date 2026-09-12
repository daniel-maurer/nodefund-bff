/**
 * Rotas de Rebalanceamento e Cálculo de Ordens
 * Distributed Node Architecture
 */

const express = require('express');
const router = express.Router();
const PortfolioRepository = require('../storage/portfolioRepository');
const nodeDispatcher = require('../services/nodeDispatcher');
const { RebalanceRequest } = require('../models/Rebalance');

// POST /api/rebalance/calculate - Calcula ordens de aporte ou rebalanceamento
router.post('/calculate', async (req, res, next) => {
  try {
    const payload = req.body || {};

    let portfolio = payload.portfolio;
    if (!portfolio || !portfolio.funds || portfolio.funds.length === 0) {
      portfolio = await PortfolioRepository.getActivePortfolio(req.userId);
    }

    const rebalanceReq = new RebalanceRequest({
      ...payload,
      portfolio
    });

    const validation = rebalanceReq.validate();
    if (!validation.isValid) {
      return res.status(400).json({ error: validation.errors.join(' ') });
    }

    try {
      const result = await nodeDispatcher.dispatchRebalance(rebalanceReq.toJSON());
      res.json(result);
    } catch (nodeErr) {
      const status = nodeErr.status || 500;
      return res.status(status).json({
        error: nodeErr.message || 'Erro durante o cálculo de rebalanceamento.',
        details: nodeErr.details || null
      });
    }
  } catch (err) {
    next(err);
  }
});

module.exports = router;

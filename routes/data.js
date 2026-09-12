/**
 * Rotas de Inventário e Atualização de Dados (CVM & B3)
 * Distributed Node Architecture
 */

const express = require('express');
const router = express.Router();
const DataStatusRepository = require('../storage/dataStatusRepository');
const nodeDispatcher = require('../services/nodeDispatcher');

// GET /api/data/status - Inventário completo de arquivos de dados locais
router.get('/status', async (req, res, next) => {
  try {
    const portfolioId = req.query.portfolio_id || null;
    const status = await DataStatusRepository.getDataStatus(portfolioId, req.userId);
    res.json(status);
  } catch (err) {
    next(err);
  }
});

// POST /api/data/update - Dispara atualização de dados via nó analítico/coletor
router.post('/update', async (req, res, next) => {
  try {
    const payload = req.body || {};
    try {
      const result = await nodeDispatcher.dispatchDataUpdate(payload);
      res.json(result);
    } catch (nodeErr) {
      const status = nodeErr.status || 500;
      return res.status(status).json({
        error: nodeErr.message || 'Erro durante a atualização de dados.',
        details: nodeErr.details || null
      });
    }
  } catch (err) {
    next(err);
  }
});

module.exports = router;

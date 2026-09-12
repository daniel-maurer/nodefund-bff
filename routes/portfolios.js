/**
 * Rotas de Carteiras (Portfolios) - CRUD & Gestão de Alocações
 * Distributed Node Architecture
 */

const express = require('express');
const router = express.Router();
const PortfolioRepository = require('../storage/portfolioRepository');

// GET /api/portfolios - Lista todas as carteiras cadastradas e a ativa
router.get('/', async (req, res, next) => {
  try {
    const portfolios = await PortfolioRepository.listPortfolios(req.userId);
    const active = await PortfolioRepository.getActivePortfolio(req.userId);
    res.json({
      portfolios,
      active_id: active ? active.id : null,
      active_portfolio_id: active ? active.id : null,
      active_name: active ? active.name : null
    });
  } catch (err) {
    next(err);
  }
});

// GET /api/portfolios/active - Retorna a carteira ativa atual
router.get('/active', async (req, res, next) => {
  try {
    const active = await PortfolioRepository.getActivePortfolio(req.userId);
    if (!active) {
      return res.status(404).json({ error: 'Nenhuma carteira ativa encontrada.' });
    }
    res.json(active);
  } catch (err) {
    next(err);
  }
});

// GET /api/portfolios/:id - Retorna uma carteira específica por ID
router.get('/:id', async (req, res, next) => {
  try {
    const portfolio = await PortfolioRepository.getPortfolioById(req.params.id, req.userId);
    if (!portfolio) {
      return res.status(404).json({ error: 'Carteira não encontrada.' });
    }
    res.json(portfolio);
  } catch (err) {
    next(err);
  }
});

// POST /api/portfolios/select - Seleciona a carteira ativa
router.post('/select', async (req, res, next) => {
  try {
    const pId = req.body.portfolio_id || req.body.id;
    if (!pId) {
      return res.status(400).json({ error: 'ID da carteira é obrigatório.' });
    }

    const success = await PortfolioRepository.setActivePortfolio(pId, req.userId);
    if (!success) {
      return res.status(404).json({ error: 'Carteira não encontrada.' });
    }

    const active = await PortfolioRepository.getActivePortfolio(req.userId);
    const portfolios = await PortfolioRepository.listPortfolios(req.userId);
    res.json({
      status: 'success',
      active,
      portfolios
    });
  } catch (err) {
    next(err);
  }
});

// POST /api/portfolios/create - Cria uma nova carteira
router.post('/create', async (req, res, next) => {
  try {
    const name = String(req.body.name || 'Nova Carteira').trim();
    const funds = Array.isArray(req.body.funds) ? req.body.funds : [];

    const newPortfolio = await PortfolioRepository.createPortfolio(name, funds, req.userId);
    const portfolios = await PortfolioRepository.listPortfolios(req.userId);

    res.json({
      status: 'success',
      portfolio: newPortfolio,
      portfolios
    });
  } catch (err) {
    next(err);
  }
});

// POST /api/portfolios - Salva ou atualiza a carteira
router.post('/', async (req, res, next) => {
  try {
    const payload = req.body;
    const pId = payload.id;

    try {
      const saved = await PortfolioRepository.savePortfolio(payload, pId, req.userId);
      const portfolios = await PortfolioRepository.listPortfolios(req.userId);
      res.json({
        status: 'success',
        message: 'Carteira salva com sucesso!',
        portfolio: saved,
        portfolios
      });
    } catch (valErr) {
      return res.status(400).json({ error: valErr.message });
    }
  } catch (err) {
    next(err);
  }
});

// PUT /api/portfolios/:id - Atualização RESTful de carteira
router.put('/:id', async (req, res, next) => {
  try {
    const pId = req.params.id;
    const payload = { ...req.body, id: pId };

    try {
      const saved = await PortfolioRepository.savePortfolio(payload, pId, req.userId);
      const portfolios = await PortfolioRepository.listPortfolios(req.userId);
      res.json({
        status: 'success',
        message: 'Carteira atualizada com sucesso!',
        portfolio: saved,
        portfolios
      });
    } catch (valErr) {
      return res.status(400).json({ error: valErr.message });
    }
  } catch (err) {
    next(err);
  }
});

// POST /api/portfolios/delete - Exclui carteira via body (compatibilidade com frontend)
router.post('/delete', async (req, res, next) => {
  try {
    const pId = req.body.portfolio_id || req.body.id;
    if (!pId) {
      return res.status(400).json({ error: 'ID da carteira é obrigatório.' });
    }

    const result = await PortfolioRepository.deletePortfolio(pId, req.userId);
    if (!result.success) {
      return res.status(400).json({ error: result.error });
    }

    const portfolios = await PortfolioRepository.listPortfolios(req.userId);
    const active = await PortfolioRepository.getActivePortfolio(req.userId);

    res.json({
      status: 'success',
      portfolios,
      active
    });
  } catch (err) {
    next(err);
  }
});

// DELETE /api/portfolios/:id - Exclui carteira RESTful
router.delete('/:id', async (req, res, next) => {
  try {
    const pId = req.params.id;
    const result = await PortfolioRepository.deletePortfolio(pId, req.userId);
    if (!result.success) {
      return res.status(400).json({ error: result.error });
    }

    const portfolios = await PortfolioRepository.listPortfolios(req.userId);
    const active = await PortfolioRepository.getActivePortfolio(req.userId);

    res.json({
      status: 'success',
      portfolios,
      active
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;

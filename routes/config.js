/**
 * Rotas de Configuração de Fontes de Dados e Benchmarks
 * Distributed Node Architecture
 */

const express = require('express');
const router = express.Router();
const ConfigRepository = require('../storage/configRepository');

// GET /api/config/sources - Carrega configurações de fontes de dados
router.get('/sources', async (req, res, next) => {
  try {
    const sources = await ConfigRepository.loadSources(req.userId);
    res.json(sources);
  } catch (err) {
    next(err);
  }
});

// POST /api/config/sources - Salva configurações de fontes de dados
router.post('/sources', async (req, res, next) => {
  try {
    const success = await ConfigRepository.saveSources(req.body, req.userId);
    if (!success) {
      return res.status(500).json({ error: 'Erro ao salvar configurações de fontes de dados.' });
    }
    const updated = await ConfigRepository.loadSources(req.userId);
    res.json({
      status: 'success',
      message: 'Configurações de fontes de dados salvas com sucesso!',
      sources: updated
    });
  } catch (err) {
    next(err);
  }
});

// GET /api/config/benchmarks - Carrega benchmarks configurados
router.get('/benchmarks', async (req, res, next) => {
  try {
    const benchmarks = await ConfigRepository.loadBenchmarks(req.userId);
    res.json(benchmarks);
  } catch (err) {
    next(err);
  }
});

// POST /api/config/benchmarks - Salva benchmarks configurados
router.post('/benchmarks', async (req, res, next) => {
  try {
    const success = await ConfigRepository.saveBenchmarks(req.body, req.userId);
    if (!success) {
      return res.status(500).json({ error: 'Erro ao salvar configurações de benchmarks.' });
    }
    const updated = await ConfigRepository.loadBenchmarks(req.userId);
    res.json({
      status: 'success',
      message: 'Configurações de benchmarks salvas com sucesso!',
      benchmarks: updated
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;

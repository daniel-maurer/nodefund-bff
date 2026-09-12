/**
 * Rotas de Gestão de Nós Distribuídos e Diagnóstico de Saúde
 * Distributed Node Architecture (nodefund)
 */

const express = require('express');
const router = express.Router();
const os = require('os');
const config = require('../config');
const nodeDispatcher = require('../services/nodeDispatcher');

// GET /api/nodes - Lista todos os nós registrados na topologia distribuída
router.get('/', async (req, res, next) => {
  try {
    const nodes = await nodeDispatcher.listNodes();
    res.json({
      cluster_id: config.CLUSTER_ID,
      timestamp: new Date().toISOString(),
      nodes_count: nodes.length,
      nodes
    });
  } catch (err) {
    next(err);
  }
});

// GET /api/nodes/health - Verificação de saúde geral do cluster e do BFF
router.get('/health', async (req, res) => {
  const mem = process.memoryUsage();
  res.json({
    status: 'healthy',
    cluster_id: config.CLUSTER_ID,
    node_id: config.NODE_ID,
    service: 'nodefund-bff',
    uptime_seconds: Math.floor(process.uptime()),
    timestamp: new Date().toISOString(),
    system: {
      platform: os.platform(),
      release: os.release(),
      total_mem_mb: Math.round(os.totalmem() / (1024 * 1024)),
      free_mem_mb: Math.round(os.freemem() / (1024 * 1024))
    },
    process: {
      pid: process.pid,
      node_version: process.version,
      rss_mb: Math.round(mem.rss / (1024 * 1024)),
      heap_used_mb: Math.round(mem.heapUsed / (1024 * 1024))
    }
  });
});

// GET /api/nodes/:id - Retorna status detalhado de um nó específico
router.get('/:id', async (req, res, next) => {
  try {
    const node = nodeDispatcher.getNode(req.params.id);
    if (!node) {
      return res.status(404).json({ error: `Nó '${req.params.id}' não encontrado no cluster.` });
    }
    res.json(node.toJSON());
  } catch (err) {
    next(err);
  }
});

module.exports = router;

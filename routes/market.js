/**
 * Rotas de Cotações de Mercado (Macro Indicators)
 * Distributed Node Architecture
 */

const express = require('express');
const router = express.Router();
const MarketRepository = require('../storage/marketRepository');

async function handleQuotes(req, res, next) {
  try {
    const quotes = await MarketRepository.getMarketQuotes();
    res.json({ quotes });
  } catch (err) {
    next(err);
  }
}

router.get('/quotes', handleQuotes);
router.get('/summary', handleQuotes);

module.exports = router;

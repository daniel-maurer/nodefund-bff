/**
 * Repositório de Cotações de Mercado (Hero Header)
 * Distributed Node Architecture
 *
 * Busca cotações ao vivo do mercado financeiro para os 4 indicadores
 * principais: S&P 500, Ibovespa, Bitcoin e Dólar, com cache inteligente
 * em memória e fallback para dados locais / DynamoDB.
 */

const fs = require('fs');
const path = require('path');
const { GetCommand } = require('@aws-sdk/lib-dynamodb');
const { docClient, TABLE_NAME } = require('./dynamoClient');
const MarketQuote = require('../models/MarketQuote');

const HERO_QUOTES = [
  { id: 'sp500', name: 'S&P 500', symbol: '^GSPC', suffix: ' pts', decimals: 2, convertToBrl: true },
  { id: 'ibov', name: 'Ibovespa', symbol: '^BVSP', suffix: ' pts', decimals: 0, convertToBrl: false },
  { id: 'btc', name: 'Bitcoin', symbol: 'BTC-USD', prefix: 'R$ ', decimals: 2, convertToBrl: true },
  { id: 'usd', name: 'Dólar', symbol: 'USDBRL=X', prefix: 'R$ ', decimals: 2, convertToBrl: false }
];

const FALLBACK_QUOTES = [
  { id: 'sp500', name: 'S&P 500', raw_value: 39257.34, formatted_value: '39.257,34 pts', pct_change: 0.86, is_positive: true, date: '11/09/2026', raw_date: '2026-09-11' },
  { id: 'ibov', name: 'Ibovespa', raw_value: 187206.89, formatted_value: '187.207 pts', pct_change: -0.56, is_positive: false, date: '11/09/2026', raw_date: '2026-09-11' },
  { id: 'btc', name: 'Bitcoin', raw_value: 393537.50, formatted_value: 'R$ 393.537,50', pct_change: -0.65, is_positive: false, date: '13/09/2026', raw_date: '2026-09-13' },
  { id: 'usd', name: 'Dólar', raw_value: 5.13, formatted_value: 'R$ 5,13', pct_change: 0.02, is_positive: true, date: '13/09/2026', raw_date: '2026-09-13' }
];

let memoryCache = null;
let lastCacheTime = 0;
const CACHE_TTL_MS = 60 * 1000; // 60 segundos de cache

class MarketRepository {

  static parseDateYmdToDmy(ymd) {
    if (!ymd || typeof ymd !== 'string') return '—';
    const parts = ymd.split('-');
    if (parts.length !== 3) return ymd;
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  }

  static async fetchLiveQuotes() {
    // 1. Obter taxa do Dólar primeiro para conversões de S&P 500 e BTC em BRL
    let usdRate = 5.13;
    try {
      const resUsd = await fetch('https://query1.finance.yahoo.com/v8/finance/chart/USDBRL%3DX?interval=1d&range=5d', {
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
        signal: AbortSignal.timeout(6000)
      });
      if (resUsd.ok) {
        const jsonUsd = await resUsd.json();
        const metaUsd = jsonUsd.chart?.result?.[0]?.meta;
        if (metaUsd?.regularMarketPrice) {
          usdRate = metaUsd.regularMarketPrice;
        }
      }
    } catch (e) {
      // Usar taxa padrão de 5.13 se timeout
    }

    const quotes = [];
    for (const cfg of HERO_QUOTES) {
      try {
        const symEnc = cfg.symbol.replace('^', '%5E').replace('=', '%3D');
        const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symEnc}?interval=1d&range=5d`;
        const res = await fetch(url, {
          headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
          signal: AbortSignal.timeout(6000)
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        const meta = json.chart?.result?.[0]?.meta;
        if (!meta || meta.regularMarketPrice === undefined) {
          throw new Error('Sem dados na resposta do Yahoo');
        }

        let rawVal = meta.regularMarketPrice;
        if (cfg.convertToBrl) {
          rawVal = rawVal * usdRate;
        }
        const pctChange = meta.regularMarketChangePercent !== undefined
          ? meta.regularMarketChangePercent
          : 0;

        const mTime = meta.regularMarketTime ? new Date(meta.regularMarketTime * 1000) : new Date();
        const dateStr = mTime.toLocaleDateString('pt-BR');

        const formatted = MarketQuote.formatPtBrNumber(rawVal, cfg.decimals);
        const formattedValue = (cfg.prefix || '') + formatted + (cfg.suffix || '');

        const quote = new MarketQuote({
          id: cfg.id,
          name: cfg.name,
          raw_value: rawVal,
          formatted_value: formattedValue,
          pct_change: parseFloat(pctChange.toFixed(2)),
          is_positive: pctChange >= 0,
          date: dateStr,
          raw_date: mTime.toISOString().split('T')[0]
        });

        quotes.push(quote.toJSON());
      } catch (err) {
        // Fallback local para este item
        const fallback = await MarketRepository.loadFallbackForQuote(cfg, usdRate);
        quotes.push(fallback);
      }
    }

    return quotes;
  }

  static async loadFallbackForQuote(cfg, usdRate = 5.13) {
    // 1. Tentar ler do arquivo JSON local de benchmarks (que tem dados mais recentes)
    try {
      const jsonPath = path.join(__dirname, '../data/benchmarks', `${cfg.id}.json`);
      if (fs.existsSync(jsonPath)) {
        const fileContent = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
        const series = fileContent.series || [];
        if (series.length >= 1) {
          const last = series[series.length - 1];
          const prev = series.length >= 2 ? series[series.length - 2] : last;

          const lastVal = parseFloat(last.value || last.value_usd || 0);
          const prevVal = parseFloat(prev.value || prev.value_usd || lastVal);
          const pctChange = prevVal !== 0 ? ((lastVal - prevVal) / prevVal) * 100 : 0;

          const formatted = MarketQuote.formatPtBrNumber(lastVal, cfg.decimals);
          const formattedValue = (cfg.prefix || '') + formatted + (cfg.suffix || '');

          return new MarketQuote({
            id: cfg.id,
            name: cfg.name,
            raw_value: lastVal,
            formatted_value: formattedValue,
            pct_change: parseFloat(pctChange.toFixed(2)),
            is_positive: pctChange >= 0,
            date: MarketRepository.parseDateYmdToDmy(last.date),
            raw_date: last.date || ''
          }).toJSON();
        }
      }
    } catch (e) {
      // Ignora erro de arquivo
    }

    // 2. Tentar DynamoDB
    try {
      const result = await docClient.send(new GetCommand({
        TableName: TABLE_NAME,
        Key: { PK: `BENCH#${cfg.id}`, SK: 'DATA' }
      }));
      const item = result.Item;
      const series = item?.series || item?.quotes || [];
      if (series.length >= 1) {
        const last = series[series.length - 1];
        const prev = series.length >= 2 ? series[series.length - 2] : last;
        const lastVal = parseFloat(last.value || 0);
        const prevVal = parseFloat(prev.value || lastVal);
        const pctChange = prevVal !== 0 ? ((lastVal - prevVal) / prevVal) * 100 : 0;
        const formatted = MarketQuote.formatPtBrNumber(lastVal, cfg.decimals);
        return new MarketQuote({
          id: cfg.id,
          name: cfg.name,
          raw_value: lastVal,
          formatted_value: (cfg.prefix || '') + formatted + (cfg.suffix || ''),
          pct_change: parseFloat(pctChange.toFixed(2)),
          is_positive: pctChange >= 0,
          date: MarketRepository.parseDateYmdToDmy(last.date),
          raw_date: last.date || ''
        }).toJSON();
      }
    } catch (e) {
      // Ignora erro DynamoDB
    }

    return FALLBACK_QUOTES.find(f => f.id === cfg.id);
  }

  static async getMarketQuotes(forceRefresh = false) {
    const now = Date.now();
    if (!forceRefresh && memoryCache && (now - lastCacheTime < CACHE_TTL_MS)) {
      return memoryCache;
    }

    try {
      const live = await MarketRepository.fetchLiveQuotes();
      if (live && live.length === HERO_QUOTES.length) {
        memoryCache = live;
        lastCacheTime = now;
        return live;
      }
    } catch (err) {
      console.warn('[MarketRepository] Falha ao buscar cotações ao vivo:', err.message);
    }

    if (memoryCache) {
      return memoryCache;
    }

    return FALLBACK_QUOTES;
  }
}

module.exports = MarketRepository;

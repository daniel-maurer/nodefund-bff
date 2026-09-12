/**
 * Repositório de Cotações de Mercado (Hero Header) — DynamoDB
 * Distributed Node Architecture
 *
 * Lê dados de benchmarks do DynamoDB para exibir as 4 cotações
 * principais: S&P 500, Ibovespa, Bitcoin e Dólar.
 */

const { GetCommand } = require('@aws-sdk/lib-dynamodb');
const { docClient, TABLE_NAME } = require('./dynamoClient');
const MarketQuote = require('../models/MarketQuote');

// Configuração dos 4 indicadores do Hero Header
const HERO_QUOTES = [
  { id: 'sp500', name: 'S&P 500', suffix: ' pts', decimals: 2 },
  { id: 'ibov', name: 'Ibovespa', suffix: ' pts', decimals: 0 },
  { id: 'btc', name: 'Bitcoin', prefix: 'R$ ', decimals: 2 },
  { id: 'usd', name: 'Dólar', prefix: 'R$ ', decimals: 2 }
];

// Valores de fallback caso não haja dados
const FALLBACK_QUOTES = [
  { id: 'sp500', name: 'S&P 500', raw_value: 0, formatted_value: '—', pct_change: 0, is_positive: true, date: '—', raw_date: '' },
  { id: 'ibov', name: 'Ibovespa', raw_value: 0, formatted_value: '—', pct_change: 0, is_positive: true, date: '—', raw_date: '' },
  { id: 'btc', name: 'Bitcoin', raw_value: 0, formatted_value: '—', pct_change: 0, is_positive: true, date: '—', raw_date: '' },
  { id: 'usd', name: 'Dólar', raw_value: 0, formatted_value: '—', pct_change: 0, is_positive: true, date: '—', raw_date: '' }
];

class MarketRepository {

  static parseDateYmdToDmy(ymd) {
    if (!ymd || typeof ymd !== 'string') return '—';
    const parts = ymd.split('-');
    if (parts.length !== 3) return ymd;
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  }

  static async getMarketQuotes() {
    const quotes = [];

    for (const cfg of HERO_QUOTES) {
      try {
        const result = await docClient.send(new GetCommand({
          TableName: TABLE_NAME,
          Key: { PK: `BENCH#${cfg.id}`, SK: 'DATA' }
        }));

        const item = result.Item;
        if (!item) {
          quotes.push(FALLBACK_QUOTES.find(f => f.id === cfg.id));
          continue;
        }

        const series = item.series || item.quotes || [];
        if (series.length < 1) {
          quotes.push(FALLBACK_QUOTES.find(f => f.id === cfg.id));
          continue;
        }

        const last = series[series.length - 1];
        const prev = series.length >= 2 ? series[series.length - 2] : last;

        const lastVal = parseFloat(last.value || last.quota || last.close || 0);
        const prevVal = parseFloat(prev.value || prev.quota || prev.close || lastVal);
        const pctChange = prevVal !== 0 ? ((lastVal - prevVal) / prevVal) * 100 : 0;

        const formatted = MarketQuote.formatPtBrNumber(lastVal, cfg.decimals);
        const formattedValue = (cfg.prefix || '') + formatted + (cfg.suffix || '');

        const quote = new MarketQuote({
          id: cfg.id,
          name: cfg.name,
          raw_value: lastVal,
          formatted_value: formattedValue,
          pct_change: parseFloat(pctChange.toFixed(2)),
          is_positive: pctChange >= 0,
          date: MarketRepository.parseDateYmdToDmy(last.date),
          raw_date: last.date || ''
        });

        quotes.push(quote.toJSON());
      } catch (err) {
        console.error(`[MarketRepository] Erro ao carregar ${cfg.id}:`, err.message);
        quotes.push(FALLBACK_QUOTES.find(f => f.id === cfg.id));
      }
    }

    return quotes;
  }
}

module.exports = MarketRepository;

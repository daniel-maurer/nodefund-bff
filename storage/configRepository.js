/**
 * Repositório de Configurações — DynamoDB
 * Distributed Node Architecture
 *
 * Fontes de dados e benchmarks são configurações por usuário.
 * PK: USER#<userId>  SK: CONFIG#SOURCES     → Configuração de provedores
 * PK: USER#<userId>  SK: CONFIG#BENCHMARKS  → Lista de benchmarks ativos
 */

const { GetCommand, PutCommand } = require('@aws-sdk/lib-dynamodb');
const { docClient, TABLE_NAME } = require('./dynamoClient');

// Configurações padrão de fontes de dados
const DEFAULT_SOURCES = {
  cvm: {
    id: 'cvm',
    name: 'CVM - Informes Diários de Fundos',
    description: 'Dados de cotas e patrimônio líquido dos fundos 555 da CVM.',
    url_template: 'https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{ym}.zip',
    headers: {},
    encoding: 'utf-8',
    delimiter: ';',
    date_format_in: '%Y-%m-%d',
    date_format_out: '%Y-%m-%d',
    columns: { date: 'DT_COMPTC', cnpj: 'CNPJ_FUNDO', quota: 'VL_QUOTA', net_worth: 'VL_PATRIM_LIQ', total_assets: 'VL_TOTAL' }
  },
  b3: {
    id: 'b3',
    name: 'B3 via Yahoo Finance',
    description: 'Cotações diárias de ações e FIIs da B3 via Yahoo Finance API.',
    url_template: 'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.SA',
    ticker_suffix: '.SA'
  },
  bcb_sgs: {
    id: 'bcb_sgs',
    name: 'Banco Central do Brasil — SGS',
    description: 'Séries temporais do Sistema Gerenciador de Séries do BCB (CDI, IPCA, Poupança).',
    url_template: 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json&dataInicial={start}&dataFinal={end}'
  },
  yahoo_benchmarks: {
    id: 'yahoo_benchmarks',
    name: 'Yahoo Finance — Índices Globais',
    description: 'Índices e cotações internacionais (IBOV, S&P 500, Bitcoin, Dólar).',
    url_template: 'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
  }
};

// Configurações padrão de benchmarks
const DEFAULT_BENCHMARKS = [
  { id: 'cdi', name: 'CDI', type: 'bcb_sgs', code: '12', enabled: true, color: '#B86B43', unit: 'daily_rate', source: 'Banco Central (SGS 12)' },
  { id: 'ipca', name: 'IPCA', type: 'bcb_sgs', code: '433', enabled: true, color: '#E17055', unit: 'monthly_rate', source: 'Banco Central (SGS 433)' },
  { id: 'poupanca', name: 'Poupança', type: 'bcb_sgs', code: '196', enabled: true, color: '#00B894', unit: 'monthly_rate', source: 'Banco Central (SGS 196)' },
  { id: 'ibov', name: 'Ibovespa', type: 'yahoo', code: '^BVSP', enabled: true, color: '#0984E3', unit: 'price', source: 'Yahoo Finance (^BVSP)' },
  { id: 'ifix', name: 'IFIX', type: 'yahoo', code: 'XFIX11.SA', enabled: true, color: '#6C5CE7', unit: 'price', source: 'Yahoo Finance (XFIX11.SA)' },
  { id: 'sp500', name: 'S&P 500', type: 'composite_usd', code: '^GSPC', enabled: true, color: '#D63031', unit: 'price_usd_brl', source: 'Yahoo Finance (^GSPC) convertido para BRL' },
  { id: 'btc', name: 'Bitcoin', type: 'composite_usd', code: 'BTC-USD', enabled: true, color: '#F39C12', unit: 'price_usd_brl', source: 'Yahoo Finance (BTC-USD) convertido para BRL' },
  { id: 'usd', name: 'Dólar', type: 'yahoo', code: 'USDBRL=X', enabled: true, color: '#2ECC71', unit: 'currency', source: 'Yahoo Finance (USDBRL=X)' }
];

const DEFAULT_USER = 'anonymous';

class ConfigRepository {

  static async loadSources(userId = DEFAULT_USER) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { PK: `USER#${userId}`, SK: 'CONFIG#SOURCES' }
    }));

    if (result.Item && result.Item.sources) {
      return result.Item.sources;
    }

    return { ...DEFAULT_SOURCES };
  }

  static async saveSources(sourcesData, userId = DEFAULT_USER) {
    await docClient.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        PK: `USER#${userId}`,
        SK: 'CONFIG#SOURCES',
        entity_type: 'config_sources',
        sources: sourcesData,
        updated_at: new Date().toISOString()
      }
    }));
    return true;
  }

  static async loadBenchmarks(userId = DEFAULT_USER) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { PK: `USER#${userId}`, SK: 'CONFIG#BENCHMARKS' }
    }));

    if (result.Item && result.Item.benchmarks) {
      return result.Item.benchmarks;
    }

    return [...DEFAULT_BENCHMARKS];
  }

  static async saveBenchmarks(benchmarksData, userId = DEFAULT_USER) {
    // Aceita tanto array direto quanto { benchmarks: [...] }
    const benchmarks = Array.isArray(benchmarksData)
      ? benchmarksData
      : (benchmarksData.benchmarks || benchmarksData);

    await docClient.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        PK: `USER#${userId}`,
        SK: 'CONFIG#BENCHMARKS',
        entity_type: 'config_benchmarks',
        benchmarks: Array.isArray(benchmarks) ? benchmarks : [],
        updated_at: new Date().toISOString()
      }
    }));
    return true;
  }
}

module.exports = ConfigRepository;

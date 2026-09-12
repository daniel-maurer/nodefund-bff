/**
 * Repositório de Status dos Dados de Mercado — DynamoDB
 * Distributed Node Architecture
 *
 * Monta inventário consolidado de fundos CVM, ativos B3 e benchmarks,
 * verificando registros no DynamoDB ao invés do sistema de arquivos.
 */

const PortfolioRepository = require('./portfolioRepository');
const ConfigRepository = require('./configRepository');
const QuotesRepository = require('./quotesRepository');

const DEFAULT_USER = 'anonymous';

class DataStatusRepository {

  static async getDataStatus(portfolioId, userId = DEFAULT_USER) {
    // 1. Coletar todos os ativos únicos das carteiras
    const manifest = await PortfolioRepository.loadManifest(userId);
    let allFunds = [];

    if (portfolioId && portfolioId !== 'all') {
      const p = await PortfolioRepository.getPortfolioById(portfolioId, userId);
      if (p && p.funds) allFunds = p.funds;
    } else {
      // Carregar fundos de todas as carteiras
      for (const entry of manifest.portfolios) {
        const p = await PortfolioRepository.getPortfolioById(entry.id, userId);
        if (p && p.funds) {
          for (const f of p.funds) {
            const existing = allFunds.find(ef =>
              (ef.cnpj && ef.cnpj === f.cnpj) || (ef.code && ef.code === f.code)
            );
            if (!existing) allFunds.push(f);
          }
        }
      }
    }

    // 2. Separar em fundos CVM e ativos B3
    const fundAssets = allFunds.filter(f => f.type === 'fund' || (!f.type && f.cnpj));
    const b3Assets = allFunds.filter(f => f.type === 'b3');

    // 3. Consultar metadata de cada ativo no DynamoDB
    const fundsStatus = await Promise.all(fundAssets.map(async (f) => {
      const cnpjClean = (f.cnpj || f.code || '').replace(/\D/g, '');
      const meta = await QuotesRepository.getFundMetadata(cnpjClean);
      return {
        id: f.id,
        name: f.name,
        cnpj: f.cnpj || f.code,
        cnpj_clean: cnpjClean,
        type: 'fund',
        target_pct: f.target_pct,
        has_data: !!meta,
        record_count: meta ? meta.record_count : 0,
        start_date: meta ? meta.start_date : null,
        end_date: meta ? meta.end_date : null,
        last_quota: meta ? meta.last_quota : null
      };
    }));

    const b3Status = await Promise.all(b3Assets.map(async (f) => {
      const ticker = (f.code || f.ticker || '').replace(/\.SA$/i, '').trim().toUpperCase();
      const meta = await QuotesRepository.getB3Metadata(ticker);
      return {
        id: f.id,
        name: f.name,
        ticker,
        type: 'b3',
        target_pct: f.target_pct,
        has_data: !!meta,
        record_count: meta ? meta.record_count : 0,
        start_date: meta ? meta.start_date : null,
        end_date: meta ? meta.end_date : null,
        last_quota: meta ? meta.last_quota : null
      };
    }));

    // 4. Benchmarks
    const benchmarksConfig = await ConfigRepository.loadBenchmarks(userId);
    const benchmarksStatus = await Promise.all(benchmarksConfig.map(async (b) => {
      const meta = await QuotesRepository.getBenchmarkMetadata(b.id);
      return {
        id: b.id,
        name: b.name,
        type: b.type,
        enabled: b.enabled,
        has_data: !!meta,
        record_count: meta ? meta.record_count : 0,
        start_date: meta ? meta.start_date : null,
        end_date: meta ? meta.end_date : null
      };
    }));

    // 5. Calcular datas globais
    const allDates = [
      ...fundsStatus.filter(f => f.start_date).map(f => f.start_date),
      ...b3Status.filter(f => f.start_date).map(f => f.start_date),
      ...benchmarksStatus.filter(f => f.start_date).map(f => f.start_date)
    ];
    const allEndDates = [
      ...fundsStatus.filter(f => f.end_date).map(f => f.end_date),
      ...b3Status.filter(f => f.end_date).map(f => f.end_date),
      ...benchmarksStatus.filter(f => f.end_date).map(f => f.end_date)
    ];

    return {
      funds: fundsStatus,
      b3_assets: b3Status,
      benchmarks: benchmarksStatus,
      global_start_date: allDates.length > 0 ? allDates.sort()[0] : null,
      global_end_date: allEndDates.length > 0 ? allEndDates.sort().reverse()[0] : null,
      portfolio_id: portfolioId || 'global',
      portfolio_name: 'Global',
      is_global: !portfolioId || portfolioId === 'all' || portfolioId === 'global',
      storage: 'dynamodb'
    };
  }
}

module.exports = DataStatusRepository;

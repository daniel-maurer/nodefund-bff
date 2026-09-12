/**
 * Repositório de Cotações e Séries de Mercado — DynamoDB
 * Distributed Node Architecture
 *
 * CRUD de dados de mercado globais (compartilhados entre todos os usuários):
 * - Fundos CVM (PK: FUND#<cnpj>)
 * - Ativos B3 (PK: B3#<ticker>)
 * - Benchmarks (PK: BENCH#<id>)
 */

const { GetCommand, PutCommand, ScanCommand } = require('@aws-sdk/lib-dynamodb');
const { docClient, TABLE_NAME } = require('./dynamoClient');

class QuotesRepository {
  // ─────────────────── Fundos CVM ───────────────────

  static async loadFundData(cnpjClean) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { PK: `FUND#${cnpjClean}`, SK: 'DATA' }
    }));
    return result.Item ? (result.Item.quotes || []) : [];
  }

  static async saveFundData(cnpjClean, name, quotes) {
    const now = new Date().toISOString();
    await docClient.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        PK: `FUND#${cnpjClean}`,
        SK: 'DATA',
        entity_type: 'fund_quotes',
        name,
        quotes,
        record_count: quotes.length,
        start_date: quotes.length > 0 ? quotes[0].date : null,
        end_date: quotes.length > 0 ? quotes[quotes.length - 1].date : null,
        last_quota: quotes.length > 0 ? quotes[quotes.length - 1].quota : null,
        updated_at: now
      }
    }));
    return { success: true, name, record_count: quotes.length, updated_at: now };
  }

  static async getFundMetadata(cnpjClean) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { PK: `FUND#${cnpjClean}`, SK: 'DATA' },
      ProjectionExpression: '#n, record_count, start_date, end_date, last_quota, updated_at',
      ExpressionAttributeNames: { '#n': 'name' }
    }));
    return result.Item || null;
  }

  // ─────────────────── Ativos B3 ───────────────────

  static async loadB3Data(ticker) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { PK: `B3#${ticker}`, SK: 'DATA' }
    }));
    return result.Item ? (result.Item.quotes || []) : [];
  }

  static async saveB3Data(ticker, name, quotes) {
    const now = new Date().toISOString();
    await docClient.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        PK: `B3#${ticker}`,
        SK: 'DATA',
        entity_type: 'b3_quotes',
        name,
        quotes,
        record_count: quotes.length,
        start_date: quotes.length > 0 ? quotes[0].date : null,
        end_date: quotes.length > 0 ? quotes[quotes.length - 1].date : null,
        last_quota: quotes.length > 0 ? (quotes[quotes.length - 1].quota || quotes[quotes.length - 1].close) : null,
        updated_at: now
      }
    }));
    return { success: true, name, record_count: quotes.length, updated_at: now };
  }

  static async getB3Metadata(ticker) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { PK: `B3#${ticker}`, SK: 'DATA' },
      ProjectionExpression: '#n, record_count, start_date, end_date, last_quota, updated_at',
      ExpressionAttributeNames: { '#n': 'name' }
    }));
    return result.Item || null;
  }

  // ─────────────────── Benchmarks ───────────────────

  static async loadBenchmarkData(benchId) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { PK: `BENCH#${benchId}`, SK: 'DATA' }
    }));
    return result.Item ? (result.Item.series || result.Item.quotes || []) : [];
  }

  static async saveBenchmarkData(benchId, displayName, seriesType, series) {
    const now = new Date().toISOString();
    await docClient.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        PK: `BENCH#${benchId}`,
        SK: 'DATA',
        entity_type: 'benchmark_series',
        name: displayName,
        series_type: seriesType,
        series,
        record_count: series.length,
        start_date: series.length > 0 ? series[0].date : null,
        end_date: series.length > 0 ? series[series.length - 1].date : null,
        updated_at: now
      }
    }));
    return { success: true, name: displayName, record_count: series.length, updated_at: now };
  }

  static async getBenchmarkMetadata(benchId) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { PK: `BENCH#${benchId}`, SK: 'DATA' },
      ProjectionExpression: '#n, series_type, record_count, start_date, end_date, updated_at',
      ExpressionAttributeNames: { '#n': 'name' }
    }));
    return result.Item || null;
  }

  // ─────────────────── Scan Utilitário ───────────────────

  /**
   * Lista todos os itens de mercado de um tipo (para inventário de dados).
   * @param {'FUND'|'B3'|'BENCH'} prefix
   */
  static async listByPrefix(prefix) {
    const items = [];
    let lastKey = undefined;

    do {
      const result = await docClient.send(new ScanCommand({
        TableName: TABLE_NAME,
        FilterExpression: 'begins_with(PK, :prefix) AND SK = :sk',
        ExpressionAttributeValues: { ':prefix': `${prefix}#`, ':sk': 'DATA' },
        ProjectionExpression: 'PK, #n, record_count, start_date, end_date, last_quota, updated_at',
        ExpressionAttributeNames: { '#n': 'name' },
        ExclusiveStartKey: lastKey
      }));
      items.push(...(result.Items || []));
      lastKey = result.LastEvaluatedKey;
    } while (lastKey);

    return items;
  }
}

module.exports = QuotesRepository;

/**
 * Setup Local Database - nodefund
 * Cria a tabela do DynamoDB Local e insere os dados iniciais
 * migrados dos arquivos JSON legados.
 */

const { DynamoDBClient, CreateTableCommand, ListTablesCommand } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');
const fs = require('fs');
const path = require('path');

const endpoint = process.env.DYNAMODB_ENDPOINT || 'http://localhost:8100';
const region = process.env.AWS_REGION || 'us-east-1';
const tableName = process.env.DYNAMODB_TABLE_NAME || 'nodefund';

console.log(`[Setup] Configurando DynamoDB em ${endpoint}, tabela: ${tableName}`);

const client = new DynamoDBClient({
  endpoint,
  region,
  credentials: { accessKeyId: 'local', secretAccessKey: 'local' }
});

const docClient = DynamoDBDocumentClient.from(client);

async function createTableIfNotExists() {
  const { TableNames } = await client.send(new ListTablesCommand({}));
  if (TableNames.includes(tableName)) {
    console.log(`[Setup] Tabela ${tableName} já existe.`);
    return;
  }

  console.log(`[Setup] Criando tabela ${tableName}...`);
  await client.send(new CreateTableCommand({
    TableName: tableName,
    AttributeDefinitions: [
      { AttributeName: 'PK', AttributeType: 'S' },
      { AttributeName: 'SK', AttributeType: 'S' }
    ],
    KeySchema: [
      { AttributeName: 'PK', KeyType: 'HASH' },
      { AttributeName: 'SK', KeyType: 'RANGE' }
    ],
    BillingMode: 'PAY_PER_REQUEST'
  }));
  console.log(`[Setup] Tabela ${tableName} criada com sucesso.`);
}

async function seedData() {
  const dataDir = path.join(__dirname, '..', 'data');
  const portfoliosFile = path.join(dataDir, 'portfolios', 'manifest.json');
  
  if (fs.existsSync(portfoliosFile)) {
    console.log('[Setup] Migrando portfolios...');
    const manifest = JSON.parse(fs.readFileSync(portfoliosFile, 'utf8'));
    
    // Salvar manifest
    await docClient.send(new PutCommand({
      TableName: tableName,
      Item: {
        PK: 'USER#anonymous',
        SK: 'MANIFEST',
        entity_type: 'manifest',
        active_portfolio_id: manifest.active_portfolio_id,
        portfolios: manifest.portfolios,
        updated_at: new Date().toISOString()
      }
    }));
    
    // Salvar cada portfolio
    for (const p of manifest.portfolios) {
      const pFile = path.join(dataDir, 'portfolios', p.file);
      if (fs.existsSync(pFile)) {
        const pData = JSON.parse(fs.readFileSync(pFile, 'utf8'));
        await docClient.send(new PutCommand({
          TableName: tableName,
          Item: {
            PK: 'USER#anonymous',
            SK: `PORTFOLIO#${pData.id}`,
            entity_type: 'portfolio',
            ...pData
          }
        }));
        console.log(`[Setup] Portfolio ${pData.id} inserido.`);
      }
    }
  }

  // Benchmarks config
  const benchmarksFile = path.join(dataDir, 'config', 'benchmarks.json');
  if (fs.existsSync(benchmarksFile)) {
    console.log('[Setup] Migrando configurações de benchmarks...');
    const benchConfig = JSON.parse(fs.readFileSync(benchmarksFile, 'utf8'));
    await docClient.send(new PutCommand({
      TableName: tableName,
      Item: {
        PK: 'USER#anonymous',
        SK: 'CONFIG#BENCHMARKS',
        entity_type: 'config_benchmarks',
        benchmarks: benchConfig,
        updated_at: new Date().toISOString()
      }
    }));
  }

  // Sources config
  const sourcesFile = path.join(dataDir, 'config', 'data_sources.json');
  if (fs.existsSync(sourcesFile)) {
    console.log('[Setup] Migrando configurações de fontes...');
    const sourcesConfig = JSON.parse(fs.readFileSync(sourcesFile, 'utf8'));
    await docClient.send(new PutCommand({
      TableName: tableName,
      Item: {
        PK: 'USER#anonymous',
        SK: 'CONFIG#SOURCES',
        entity_type: 'config_sources',
        sources: sourcesConfig,
        updated_at: new Date().toISOString()
      }
    }));
  }

  // Migrar dados de Fundos
  const fundsDir = path.join(dataDir, 'funds');
  if (fs.existsSync(fundsDir)) {
    console.log('[Setup] Migrando cotações de fundos...');
    const files = fs.readdirSync(fundsDir).filter(f => f.endsWith('.json'));
    for (const f of files) {
      const data = JSON.parse(fs.readFileSync(path.join(fundsDir, f), 'utf8'));
      await docClient.send(new PutCommand({
        TableName: tableName,
        Item: {
          PK: `FUND#${data.cnpj}`,
          SK: 'DATA',
          entity_type: 'fund_quotes',
          name: data.name || '',
          quotes: data.quotes || [],
          record_count: data.total_records || 0,
          start_date: data.start_date || null,
          end_date: data.end_date || null,
          last_quota: data.quotes && data.quotes.length > 0 ? (data.quotes[data.quotes.length - 1].quota || 0).toString() : null,
          updated_at: data.updated_at || new Date().toISOString()
        }
      }));
    }
  }

  // Migrar dados da B3
  const b3Dir = path.join(dataDir, 'b3');
  if (fs.existsSync(b3Dir)) {
    console.log('[Setup] Migrando cotações da B3...');
    const files = fs.readdirSync(b3Dir).filter(f => f.endsWith('.json'));
    for (const f of files) {
      const data = JSON.parse(fs.readFileSync(path.join(b3Dir, f), 'utf8'));
      await docClient.send(new PutCommand({
        TableName: tableName,
        Item: {
          PK: `B3#${data.ticker}`,
          SK: 'DATA',
          entity_type: 'b3_quotes',
          name: data.name || '',
          quotes: data.quotes || [],
          record_count: data.total_records || 0,
          start_date: data.start_date || null,
          end_date: data.end_date || null,
          last_quota: data.quotes && data.quotes.length > 0 ? (data.quotes[data.quotes.length - 1].quota || data.quotes[data.quotes.length - 1].close || 0).toString() : null,
          updated_at: data.updated_at || new Date().toISOString()
        }
      }));
    }
  }

  // Migrar dados de Benchmarks
  const benchDir = path.join(dataDir, 'benchmarks');
  if (fs.existsSync(benchDir)) {
    console.log('[Setup] Migrando séries de benchmarks...');
    const files = fs.readdirSync(benchDir).filter(f => f.endsWith('.json'));
    for (const f of files) {
      const data = JSON.parse(fs.readFileSync(path.join(benchDir, f), 'utf8'));
      await docClient.send(new PutCommand({
        TableName: tableName,
        Item: {
          PK: `BENCH#${data.benchmark}`,
          SK: 'DATA',
          entity_type: 'benchmark_series',
          name: data.display_name || '',
          series_type: data.series_type || 'index',
          series: data.series || [],
          record_count: data.total_records || 0,
          start_date: data.start_date || null,
          end_date: data.end_date || null,
          updated_at: data.updated_at || new Date().toISOString()
        }
      }));
    }
  }

  console.log('[Setup] Seed completo!');
}

async function main() {
  try {
    await createTableIfNotExists();
    await seedData();
  } catch (err) {
    console.error('[Setup] Erro:', err);
    process.exit(1);
  }
}

main();

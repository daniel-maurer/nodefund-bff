/**
 * Setup Local Database - nodefund
 * Cria a tabela do DynamoDB Local e insere os dados iniciais
 * migrados dos arquivos JSON legados.
 */

require('dotenv').config();
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

  // Not migrating quotes and historical data to keep the script fast.
  // The user can run "update data" to fetch quotes into DynamoDB.
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

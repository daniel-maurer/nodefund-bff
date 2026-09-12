/**
 * Configurações Centrais do Node.js BFF (nodefund)
 * Distributed Node Architecture
 */

const path = require('path');

// Diretório raiz do BFF (usado para o worker Python e dados locais de fallback)
const ROOT_DIR = __dirname;
const DATA_DIR = path.join(ROOT_DIR, 'data');
const STATIC_DIR = path.join(ROOT_DIR, '..', 'frontend');

module.exports = {
  // --- Servidor BFF ---
  PORT: parseInt(process.env.PORT || '8000', 10),
  HOST: process.env.HOST || '0.0.0.0',

  // --- Worker Analítico Python ---
  ANALYTICS_NODE_URL: process.env.ANALYTICS_NODE_URL || 'http://127.0.0.1:8001',
  ANALYTICS_NODE_TIMEOUT_MS: parseInt(process.env.ANALYTICS_NODE_TIMEOUT_MS || '30000', 10),

  // --- AWS DynamoDB ---
  DYNAMODB_TABLE_NAME: process.env.DYNAMODB_TABLE_NAME || 'nodefund',
  DYNAMODB_ENDPOINT: process.env.DYNAMODB_ENDPOINT || '',   // Vazio = usa endpoint padrão da AWS
  AWS_REGION: process.env.AWS_REGION || 'us-east-1',

  // --- AWS Cognito ---
  COGNITO_USER_POOL_ID: process.env.COGNITO_USER_POOL_ID || '',
  COGNITO_APP_CLIENT_ID: process.env.COGNITO_APP_CLIENT_ID || '',

  // --- Autenticação ---
  AUTH_DISABLED: process.env.AUTH_DISABLED === 'true',

  // --- Caminhos Locais (usados pelo seed e fallback) ---
  ROOT_DIR,
  DATA_DIR,
  STATIC_DIR,

  // --- Identificação do Nó ---
  CLUSTER_ID: process.env.CLUSTER_ID || 'nodefund-cluster-alpha',
  NODE_ID: process.env.NODE_ID || 'bff-gateway-01'
};

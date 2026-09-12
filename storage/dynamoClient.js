/**
 * Cliente DynamoDB Singleton — nodefund
 * Distributed Node Architecture
 *
 * Fornece uma instância compartilhada do DynamoDBDocumentClient
 * configurada para DynamoDB Local (desenvolvimento) ou AWS (produção).
 */

const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient } = require('@aws-sdk/lib-dynamodb');
const config = require('../config');

const clientConfig = {
  region: config.AWS_REGION
};

// Em desenvolvimento local, apontar para o DynamoDB Local
if (config.DYNAMODB_ENDPOINT) {
  clientConfig.endpoint = config.DYNAMODB_ENDPOINT;
  clientConfig.credentials = {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || 'local',
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || 'local'
  };
}

const ddbClient = new DynamoDBClient(clientConfig);

const docClient = DynamoDBDocumentClient.from(ddbClient, {
  marshallOptions: {
    convertEmptyValues: false,
    removeUndefinedValues: true,
    convertClassInstanceToMap: true
  },
  unmarshallOptions: {
    wrapNumbers: false
  }
});

const TABLE_NAME = config.DYNAMODB_TABLE_NAME;

module.exports = { docClient, TABLE_NAME, ddbClient };

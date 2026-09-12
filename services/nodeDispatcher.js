/**
 * Despachante e Orquestrador de Nós Distribuídos
 * Distributed Node Architecture
 */

const http = require('http');
const config = require('../config');
const DistributedNode = require('../models/DistributedNode');

class NodeDispatcher {
  constructor() {
    this.nodes = new Map();

    // 1. Nó BFF Gateway (Local Node.js)
    this.registerNode(new DistributedNode({
      id: config.NODE_ID,
      name: 'Gateway BFF & File Storage',
      role: 'bff-gateway',
      runtime: 'nodejs',
      endpoint: `http://localhost:${config.PORT}`,
      status: 'online',
      latency_ms: 0,
      capabilities: ['file-persistence', 'models-validation', 'static-serving', 'rest-api']
    }));

    // 2. Nó de Análise Quantitativa (Python Worker)
    this.registerNode(new DistributedNode({
      id: 'analytics-worker-01',
      name: 'Python Quantitative Analytics Worker',
      role: 'quantitative-analytics',
      runtime: 'python',
      endpoint: config.ANALYTICS_NODE_URL,
      status: 'offline',
      latency_ms: 0,
      capabilities: ['monte-carlo-simulation', 'rebalancer-engine', 'cvm-scraper', 'b3-sync']
    }));
  }

  registerNode(node) {
    this.nodes.set(node.id, node);
  }

  getNode(nodeId) {
    return this.nodes.get(nodeId) || null;
  }

  async listNodes() {
    // Atualiza status do nó analítico antes de listar
    await this.pingAnalyticsWorker();
    return Array.from(this.nodes.values()).map(n => n.toJSON());
  }

  /**
   * Realiza chamada HTTP para o nó analítico Python
   */
  async requestAnalyticsNode(endpointPath, method = 'POST', payload = {}) {
    const workerNode = this.getNode('analytics-worker-01');
    const targetUrl = new URL(endpointPath, config.ANALYTICS_NODE_URL);

    const startTime = Date.now();
    return new Promise((resolve, reject) => {
      const dataString = JSON.stringify(payload);
      const req = http.request(targetUrl, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(dataString)
        },
        timeout: config.ANALYTICS_NODE_TIMEOUT_MS
      }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => {
          const latency = Date.now() - startTime;
          if (workerNode) {
            workerNode.updateStatus('online', latency);
          }

          try {
            const parsed = JSON.parse(body);
            if (res.statusCode >= 400) {
              return reject({
                status: res.statusCode,
                message: parsed.error || `Erro retornado pelo nó analítico (${res.statusCode})`,
                details: parsed
              });
            }
            resolve(parsed);
          } catch (e) {
            reject({
              status: 502,
              message: `Resposta inválida do nó analítico: ${body.slice(0, 100)}`
            });
          }
        });
      });

      req.on('error', (err) => {
        const latency = Date.now() - startTime;
        if (workerNode) {
          workerNode.updateStatus('offline', latency, { last_error: err.message });
        }
        reject({
          status: 503,
          message: `Nó de análise quantitativa offline em ${config.ANALYTICS_NODE_URL}. Certifique-se de que o worker Python está em execução.`,
          error: err.message
        });
      });

      req.on('timeout', () => {
        req.destroy();
        if (workerNode) {
          workerNode.updateStatus('degraded', config.ANALYTICS_NODE_TIMEOUT_MS, { last_error: 'Timeout' });
        }
        reject({
          status: 504,
          message: `Tempo limite excedido ao comunicar com o nó analítico (${config.ANALYTICS_NODE_TIMEOUT_MS}ms).`
        });
      });

      if (['POST', 'PUT', 'PATCH'].includes(method)) {
        req.write(dataString);
      }
      req.end();
    });
  }

  async pingAnalyticsWorker() {
    const workerNode = this.getNode('analytics-worker-01');
    const targetUrl = new URL('/api/data/status', config.ANALYTICS_NODE_URL);
    const startTime = Date.now();

    return new Promise((resolve) => {
      const req = http.get(targetUrl, { timeout: 2000 }, (res) => {
        const latency = Date.now() - startTime;
        if (workerNode) workerNode.updateStatus('online', latency);
        resolve(true);
      });
      req.on('error', (err) => {
        if (workerNode) workerNode.updateStatus('offline', 0, { last_error: err.message });
        resolve(false);
      });
      req.on('timeout', () => {
        req.destroy();
        if (workerNode) workerNode.updateStatus('degraded', 2000, { last_error: 'Timeout' });
        resolve(false);
      });
    });
  }

  async dispatchSimulation(params) {
    return await this.requestAnalyticsNode('/api/simulate', 'POST', params);
  }

  async dispatchRebalance(params) {
    return await this.requestAnalyticsNode('/api/rebalance/calculate', 'POST', params);
  }

  async dispatchDataUpdate(params) {
    return await this.requestAnalyticsNode('/api/data/update', 'POST', params);
  }
}

const dispatcher = new NodeDispatcher();
module.exports = dispatcher;

/**
 * Modelo de Nó na Arquitetura Distribuída (nodefund)
 * Distributed Node Architecture
 */

class DistributedNode {
  /**
   * @param {Object} data
   * @param {string} data.id ID único do nó no cluster
   * @param {string} data.name Nome legível do nó
   * @param {'bff-gateway'|'quantitative-analytics'|'data-collector'|'execution'} data.role Papel do nó
   * @param {'nodejs'|'python'|'native'} data.runtime Ambiente de execução
   * @param {string} data.endpoint URL base de comunicação HTTP
   * @param {'online'|'degraded'|'offline'} [data.status='offline'] Status operacional
   * @param {number} [data.latency_ms=0] Latência média do último ping (ms)
   * @param {string} [data.last_heartbeat] Timestamp do último sinal de vida
   * @param {Object} [data.capabilities=[]] Lista de capacidades/serviços oferecidos
   */
  constructor(data = {}) {
    this.id = String(data.id || '').trim();
    this.name = String(data.name || this.id).trim();
    this.role = data.role || 'worker';
    this.runtime = data.runtime || 'native';
    this.endpoint = String(data.endpoint || '').trim();
    this.status = data.status || 'offline';
    this.latency_ms = Number(data.latency_ms) || 0;
    this.last_heartbeat = data.last_heartbeat || new Date().toISOString();
    this.capabilities = Array.isArray(data.capabilities) ? data.capabilities : [];
    this.metrics = data.metrics || {
      uptime_seconds: 0,
      memory_usage_mb: 0,
      tasks_completed: 0,
      last_error: null
    };
  }

  isHealthy() {
    return this.status === 'online';
  }

  updateStatus(status, latencyMs = 0, metrics = {}) {
    this.status = status;
    this.latency_ms = latencyMs;
    this.last_heartbeat = new Date().toISOString();
    if (metrics && Object.keys(metrics).length > 0) {
      this.metrics = { ...this.metrics, ...metrics };
    }
  }

  toJSON() {
    return {
      id: this.id,
      name: this.name,
      role: this.role,
      runtime: this.runtime,
      endpoint: this.endpoint,
      status: this.status,
      is_healthy: this.isHealthy(),
      latency_ms: this.latency_ms,
      last_heartbeat: this.last_heartbeat,
      capabilities: this.capabilities,
      metrics: this.metrics
    };
  }
}

module.exports = DistributedNode;

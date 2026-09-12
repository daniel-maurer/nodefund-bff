/**
 * Modelo de Configuração de Benchmark
 * Distributed Node Architecture
 */

class Benchmark {
  constructor(data = {}) {
    this.id = String(data.id || '').trim();
    this.name = String(data.name || this.id).trim();
    this.type = String(data.type || 'yahoo').trim();
    this.code = String(data.code || '').trim();
    this.enabled = typeof data.enabled === 'boolean' ? data.enabled : true;
    this.color = data.color || '#2E7D5B';
    this.unit = data.unit || 'price';
    this.source = data.source || '';
  }

  validate() {
    const errors = [];
    if (!this.id) errors.push('ID do benchmark é obrigatório.');
    if (!this.name) errors.push('Nome do benchmark é obrigatório.');
    if (!this.code) errors.push('Código/Símbolo do benchmark é obrigatório.');
    return { isValid: errors.length === 0, errors };
  }

  toJSON() {
    return {
      id: this.id,
      name: this.name,
      type: this.type,
      code: this.code,
      enabled: this.enabled,
      color: this.color,
      unit: this.unit,
      source: this.source
    };
  }
}

module.exports = Benchmark;

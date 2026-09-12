/**
 * Modelo de Carteira de Investimentos
 * Distributed Node Architecture
 */

const Asset = require('./Asset');

class Portfolio {
  /**
   * @param {Object} data
   * @param {string} data.id ID único da carteira
   * @param {string} data.name Nome legível da carteira
   * @param {string} [data.updated_at] Data/hora da última atualização (ISO 8601)
   * @param {Array<Object|Asset>} [data.funds=[]] Lista de ativos alocados
   */
  constructor(data = {}) {
    this.id = String(data.id || '').trim();
    this.name = String(data.name || 'Nova Carteira').trim();
    this.updated_at = data.updated_at || new Date().toISOString();
    
    const rawFunds = Array.isArray(data.funds) ? data.funds : [];
    this.funds = rawFunds.map(f => (f instanceof Asset ? f : new Asset(f)));
  }

  calculateTotalAllocation() {
    return this.funds.reduce((acc, f) => acc + (Number(f.target_pct) || 0), 0);
  }

  validate() {
    const errors = [];
    if (!this.name) {
      errors.push('O nome da carteira é obrigatório.');
    }
    
    if (!this.funds || this.funds.length === 0) {
      errors.push('A carteira deve conter pelo menos um ativo.');
    }

    // Valida cada ativo individual
    for (const fund of this.funds) {
      const res = fund.validate();
      if (!res.isValid) {
        errors.push(...res.errors);
      }
    }

    // Validação matemática: a soma de alocação deve ser exatamente 100%
    const totalPct = this.calculateTotalAllocation();
    if (Math.abs(totalPct - 100.0) > 0.01) {
      errors.push(`A soma das alocações deve ser exatamente 100%. Soma atual: ${totalPct.toFixed(1)}%`);
    }

    return {
      isValid: errors.length === 0,
      totalPct,
      errors
    };
  }

  toJSON() {
    return {
      id: this.id,
      name: this.name,
      updated_at: this.updated_at,
      funds: this.funds.map(f => f.toJSON())
    };
  }
}

module.exports = Portfolio;

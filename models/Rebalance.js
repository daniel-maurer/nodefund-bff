/**
 * Modelo de Rebalanceamento de Carteira
 * Distributed Node Architecture
 */

class RebalanceRequest {
  constructor(data = {}) {
    this.portfolio = data.portfolio || null;
    this.current_balances = data.current_balances || {};
    this.contribution = Number(data.contribution) >= 0 ? Number(data.contribution) : 0.0;
  }

  validate() {
    const errors = [];
    if (this.contribution < 0) errors.push('Aporte financeiro não pode ser negativo.');
    if (typeof this.current_balances !== 'object' || this.current_balances === null) {
      errors.push('Saldos atuais devem ser um objeto mapeando id do ativo ao saldo.');
    }
    return { isValid: errors.length === 0, errors };
  }

  toJSON() {
    return {
      portfolio: this.portfolio,
      current_balances: this.current_balances,
      contribution: this.contribution
    };
  }
}

module.exports = {
  RebalanceRequest
};

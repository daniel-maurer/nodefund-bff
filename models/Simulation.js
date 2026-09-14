/**
 * Modelo de Parâmetros e Resultados de Simulação Financeira
 * Distributed Node Architecture
 */

class SimulationRequest {
  constructor(data = {}) {
    this.initial_capital = Number(data.initial_capital) >= 0 ? Number(data.initial_capital) : 20000.0;
    this.monthly_contribution = Number(data.monthly_contribution) >= 0 ? Number(data.monthly_contribution) : 2000.0;
    this.start_date = data.start_date || '2024-05-01';
    
    // Suporte flexível a 'today', 'hoje', 'atual' ou valor nulo para sempre referenciar a data atual
    const rawEnd = data.end_date ? String(data.end_date).trim().toLowerCase() : '';
    if (!rawEnd || ['today', 'atual', 'hoje', 'latest'].includes(rawEnd)) {
      this.end_date = new Date().toISOString().slice(0, 10);
      this.is_today = true;
    } else {
      this.end_date = data.end_date;
      this.is_today = false;
    }

    this.rebalance_mode = data.rebalance_mode || 'smart_inflow';
    this.portfolio = data.portfolio || null;
  }

  validate() {
    const errors = [];
    if (this.initial_capital < 0) errors.push('Capital inicial não pode ser negativo.');
    if (this.monthly_contribution < 0) errors.push('Aporte mensal não pode ser negativo.');
    if (!this.start_date) errors.push('Data inicial é obrigatória.');
    if (!this.end_date) errors.push('Data final é obrigatória.');
    if (this.start_date > this.end_date) errors.push('Data inicial não pode ser posterior à data final.');
    return { isValid: errors.length === 0, errors };
  }

  toJSON() {
    return {
      initial_capital: this.initial_capital,
      monthly_contribution: this.monthly_contribution,
      start_date: this.start_date,
      end_date: this.end_date,
      rebalance_mode: this.rebalance_mode,
      portfolio: this.portfolio
    };
  }
}

module.exports = {
  SimulationRequest
};

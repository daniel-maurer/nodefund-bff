/**
 * Modelo de Cotação de Mercado (Hero Header Macro)
 * Distributed Node Architecture
 */

class MarketQuote {
  /**
   * @param {Object} data
   * @param {string} data.id Identificador do benchmark (ex: 'sp500', 'ibov', 'btc', 'usd')
   * @param {string} data.name Nome legível
   * @param {number} data.raw_value Valor numérico bruto
   * @param {string} [data.formatted_value] Valor formatado com sufixo
   * @param {number} data.pct_change Variação percentual diária
   * @param {boolean} [data.is_positive] Se a variação é positiva/neutra
   * @param {string} [data.date] Data formatada (DD/MM/YYYY)
   * @param {string} [data.raw_date] Data em ISO/YMD (YYYY-MM-DD)
   */
  constructor(data = {}) {
    this.id = String(data.id || '').trim();
    this.name = String(data.name || this.id).trim();
    this.raw_value = Number(data.raw_value) || 0;
    this.pct_change = Number(data.pct_change) || 0;
    this.is_positive = typeof data.is_positive === 'boolean' ? data.is_positive : (this.pct_change >= 0);
    this.date = String(data.date || '').trim();
    this.raw_date = String(data.raw_date || '').trim();

    this.formatted_value = data.formatted_value || this.formatDefault(this.id, this.raw_value);
  }

  static formatPtBrNumber(val, decimals = 2) {
    if (isNaN(val)) return decimals > 0 ? `0,${'0'.repeat(decimals)}` : '0';
    return new Intl.NumberFormat('pt-BR', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    }).format(Number(val));
  }

  formatDefault(id, val) {
    const formatted = MarketQuote.formatPtBrNumber(val, 2);
    switch (id) {
      case 'sp500':
      case 'ibov':
      case 'ifix':
        return `${formatted} pts`;
      case 'btc':
        return `US$ ${formatted}`;
      case 'usd':
        return `R$ ${formatted}`;
      default:
        return formatted;
    }
  }

  toJSON() {
    return {
      id: this.id,
      name: this.name,
      raw_value: this.raw_value,
      formatted_value: this.formatted_value,
      pct_change: Number(this.pct_change.toFixed(2)),
      is_positive: this.is_positive,
      date: this.date,
      raw_date: this.raw_date
    };
  }
}

module.exports = MarketQuote;

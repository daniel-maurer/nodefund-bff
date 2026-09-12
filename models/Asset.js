/**
 * Modelo de Ativo (Fundo CVM ou Ativo B3 - Ações/FIIs/ETFs)
 * Distributed Node Architecture
 */

class Asset {
  /**
   * @param {Object} data
   * @param {string} data.id Identificador único do ativo
   * @param {string} data.name Nome legível do fundo ou ativo
   * @param {'fund'|'b3'} [data.type='fund'] Tipo de ativo
   * @param {string} [data.cnpj] CNPJ do fundo (para type === 'fund')
   * @param {string} [data.code] Código/CNPJ ou Ticker
   * @param {number} [data.target_pct=0] Alocação alvo (%)
   * @param {number} [data.min_investment=0] Aporte mínimo
   * @param {string} [data.color='#2E7D5B'] Cor primária de exibição
   * @param {string} [data.color_aux='#E7F2EC'] Cor auxiliar sutil de fundo
   */
  constructor(data = {}) {
    this.id = String(data.id || '').trim();
    this.name = data.name !== undefined ? String(data.name).trim() : (this.id || '');
    this.type = (data.type === 'b3') ? 'b3' : 'fund';
    
    if (this.type === 'b3') {
      const rawCode = data.code || data.id || '';
      this.code = Asset.cleanTicker(rawCode);
      this.cnpj = '';
    } else {
      const rawCnpj = data.cnpj || data.code || '';
      const clean = Asset.cleanCnpj(rawCnpj);
      this.cnpj = clean ? Asset.formatCnpj(clean) : '';
      this.code = this.cnpj;
    }

    this.target_pct = Number(data.target_pct) || 0;
    this.min_investment = Number(data.min_investment) || 0;
    this.color = data.color || '#2E7D5B';
    this.color_aux = data.color_aux || '#E7F2EC';
  }

  static cleanCnpj(cnpj) {
    if (!cnpj) return '';
    return String(cnpj).replace(/\D/g, '');
  }

  static formatCnpj(clean) {
    if (!clean) return '';
    clean = String(clean).replace(/\D/g, '').padStart(14, '0');
    if (clean.length !== 14) return clean;
    return `${clean.slice(0, 2)}.${clean.slice(2, 5)}.${clean.slice(5, 8)}/${clean.slice(8, 12)}-${clean.slice(12, 14)}`;
  }

  static cleanTicker(ticker) {
    if (!ticker) return '';
    let t = String(ticker).trim().toUpperCase();
    if (t.endsWith('.SA')) {
      t = t.slice(0, -3);
    }
    return t.replace(/[^A-Z0-9]/g, '');
  }

  validate() {
    const errors = [];
    if (!this.name) errors.push('Nome do ativo é obrigatório.');
    if (this.type === 'b3') {
      if (!this.code) errors.push('Ticker do ativo B3 é obrigatório.');
    } else {
      const clean = Asset.cleanCnpj(this.cnpj || this.code);
      if (!clean || clean.length < 11) {
        errors.push('CNPJ válido é obrigatório para fundos CVM.');
      }
    }
    if (this.target_pct < 0 || this.target_pct > 100) {
      errors.push(`Alocação de ${this.name} deve estar entre 0% e 100%.`);
    }
    return {
      isValid: errors.length === 0,
      errors
    };
  }

  toJSON() {
    const json = {
      id: this.id || (this.type === 'b3' ? this.code.toLowerCase() : Asset.cleanCnpj(this.cnpj)),
      type: this.type,
      name: this.name,
      code: this.code,
      target_pct: this.target_pct,
      min_investment: this.min_investment,
      color: this.color,
      color_aux: this.color_aux
    };
    if (this.type === 'fund') {
      json.cnpj = this.cnpj;
    }
    return json;
  }
}

module.exports = Asset;

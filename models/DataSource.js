/**
 * Modelo de Configuração de Fonte de Dados Externa
 * Distributed Node Architecture
 */

class DataSource {
  constructor(data = {}) {
    this.id = String(data.id || '').trim();
    this.name = String(data.name || this.id).trim();
    this.description = String(data.description || '').trim();
    this.url_template = String(data.url_template || '').trim();
    this.headers = data.headers || {};
    this.encoding = data.encoding || 'utf-8';
    this.delimiter = data.delimiter || ';';
    this.ticker_suffix = data.ticker_suffix || '';
    this.date_format_in = data.date_format_in || '';
    this.date_format_out = data.date_format_out || '';
    this.columns = data.columns || {};
  }

  validate() {
    const errors = [];
    if (!this.id) errors.push('ID da fonte é obrigatório.');
    if (!this.name) errors.push('Nome da fonte é obrigatório.');
    if (!this.url_template) errors.push('Template de URL é obrigatório.');
    return { isValid: errors.length === 0, errors };
  }

  toJSON() {
    return {
      id: this.id,
      name: this.name,
      description: this.description,
      url_template: this.url_template,
      headers: this.headers,
      encoding: this.encoding,
      delimiter: this.delimiter,
      ticker_suffix: this.ticker_suffix,
      date_format_in: this.date_format_in,
      date_format_out: this.date_format_out,
      columns: this.columns
    };
  }
}

module.exports = DataSource;

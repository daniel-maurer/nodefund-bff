/**
 * Repositório de Carteiras (Portfolios) — DynamoDB
 * Distributed Node Architecture
 *
 * Gerencia carteiras de investimento por usuário.
 * Cada usuário possui seu próprio manifest e carteiras isoladas no DynamoDB.
 *
 * Esquema DynamoDB:
 *   PK: USER#<userId>  SK: MANIFEST         → { active_portfolio_id, portfolios[] }
 *   PK: USER#<userId>  SK: PORTFOLIO#<id>   → { id, name, funds[], updated_at }
 */

const { GetCommand, PutCommand, DeleteCommand, QueryCommand } = require('@aws-sdk/lib-dynamodb');
const { docClient, TABLE_NAME } = require('./dynamoClient');
const Portfolio = require('../models/Portfolio');

// Usuário padrão para modo sem autenticação (AUTH_DISABLED=true)
const DEFAULT_USER = 'anonymous';

class PortfolioRepository {
  // ─────────────────── Manifest ───────────────────

  static async loadManifest(userId = DEFAULT_USER) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { PK: `USER#${userId}`, SK: 'MANIFEST' }
    }));

    if (result.Item) {
      return {
        active_portfolio_id: result.Item.active_portfolio_id || null,
        portfolios: result.Item.portfolios || []
      };
    }

    // Manifest não existe — cria um padrão com carteira inicial
    const defaultManifest = {
      active_portfolio_id: null,
      portfolios: []
    };
    return defaultManifest;
  }

  static async saveManifest(manifest, userId = DEFAULT_USER) {
    await docClient.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        PK: `USER#${userId}`,
        SK: 'MANIFEST',
        entity_type: 'manifest',
        active_portfolio_id: manifest.active_portfolio_id,
        portfolios: manifest.portfolios || [],
        updated_at: new Date().toISOString()
      }
    }));
    return true;
  }

  // ─────────────────── Listagem ───────────────────

  static async listPortfolios(userId = DEFAULT_USER) {
    const manifest = await PortfolioRepository.loadManifest(userId);
    const activeId = manifest.active_portfolio_id;

    return manifest.portfolios.map(p => ({
      ...p,
      active: p.id === activeId,
      is_active: p.id === activeId,
      asset_count: p.asset_count || 0,
      count: p.asset_count || 0
    }));
  }

  // ─────────────────── Leitura ───────────────────

  static async getActivePortfolio(userId = DEFAULT_USER) {
    const manifest = await PortfolioRepository.loadManifest(userId);
    const activeId = manifest.active_portfolio_id;

    if (!activeId) {
      // Tenta retornar a primeira carteira disponível
      if (manifest.portfolios.length > 0) {
        return PortfolioRepository.getPortfolioById(manifest.portfolios[0].id, userId);
      }
      return null;
    }

    return PortfolioRepository.getPortfolioById(activeId, userId);
  }

  static async getPortfolioById(portfolioId, userId = DEFAULT_USER) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { PK: `USER#${userId}`, SK: `PORTFOLIO#${portfolioId}` }
    }));

    if (!result.Item) return null;

    const { PK, SK, entity_type, ...portfolioData } = result.Item;
    return portfolioData;
  }

  // ─────────────────── Seleção ───────────────────

  static async setActivePortfolio(portfolioId, userId = DEFAULT_USER) {
    // Verificar se a carteira existe
    const portfolio = await PortfolioRepository.getPortfolioById(portfolioId, userId);
    if (!portfolio) return false;

    const manifest = await PortfolioRepository.loadManifest(userId);
    manifest.active_portfolio_id = portfolioId;
    await PortfolioRepository.saveManifest(manifest, userId);
    return true;
  }

  // ─────────────────── Salvamento ───────────────────

  static async savePortfolio(portfolioData, portfolioId, userId = DEFAULT_USER) {
    const pId = portfolioId || portfolioData.id;
    if (!pId) throw new Error('ID da carteira é obrigatório para salvar.');

    // Validar com o modelo de domínio
    const portfolio = new Portfolio({
      ...portfolioData,
      id: pId,
      updated_at: new Date().toISOString()
    });

    const validation = portfolio.validate();
    if (!validation.isValid) {
      throw new Error(validation.errors.join(' '));
    }

    const data = portfolio.toJSON();

    // Salvar no DynamoDB
    await docClient.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        PK: `USER#${userId}`,
        SK: `PORTFOLIO#${pId}`,
        entity_type: 'portfolio',
        ...data
      }
    }));

    // Atualizar manifest (asset_count)
    const manifest = await PortfolioRepository.loadManifest(userId);
    const entry = manifest.portfolios.find(p => p.id === pId);
    if (entry) {
      entry.name = data.name;
      entry.asset_count = (data.funds || []).length;
      await PortfolioRepository.saveManifest(manifest, userId);
    }

    return data;
  }

  // ─────────────────── Criação ───────────────────

  static async createPortfolio(name, funds, userId = DEFAULT_USER) {
    const slug = name.toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/(^_|_$)/g, '');

    const manifest = await PortfolioRepository.loadManifest(userId);
    const existingCount = manifest.portfolios.filter(p =>
      p.id.startsWith(`carteira_${slug}`)
    ).length;
    const pId = `carteira_${slug}_${existingCount + 1}`;

    // Normalizar fundos ou criar fundo default
    let portfolioFunds;
    if (Array.isArray(funds) && funds.length > 0) {
      portfolioFunds = funds.map(f => ({
        id: f.id || f.code || f.ticker || f.cnpj || `asset_${Date.now()}`,
        type: f.type || 'fund',
        name: f.name || 'Ativo',
        cnpj: f.cnpj || '',
        code: f.code || f.ticker || f.cnpj || '',
        target_pct: parseFloat(f.target_pct || f.weight || 0),
        min_investment: parseFloat(f.min_investment || f.min || 100),
        color: f.color || '#6c5ce7',
        color_aux: f.color_aux || '#f0eeff'
      }));
    } else {
      portfolioFunds = [{
        id: 'default_asset',
        type: 'fund',
        name: 'Ativo Padrão',
        cnpj: '',
        code: '',
        target_pct: 100,
        min_investment: 100,
        color: '#6c5ce7',
        color_aux: '#f0eeff'
      }];
    }

    const now = new Date().toISOString();
    const newPortfolio = {
      id: pId,
      name,
      funds: portfolioFunds,
      updated_at: now
    };

    // Salvar carteira no DynamoDB
    await docClient.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        PK: `USER#${userId}`,
        SK: `PORTFOLIO#${pId}`,
        entity_type: 'portfolio',
        ...newPortfolio
      }
    }));

    // Atualizar manifest
    manifest.portfolios.push({
      id: pId,
      name,
      file: `${pId}.json`,
      asset_count: portfolioFunds.length
    });
    manifest.active_portfolio_id = pId;
    await PortfolioRepository.saveManifest(manifest, userId);

    return newPortfolio;
  }

  // ─────────────────── Exclusão ───────────────────

  static async deletePortfolio(portfolioId, userId = DEFAULT_USER) {
    const manifest = await PortfolioRepository.loadManifest(userId);

    if (manifest.portfolios.length <= 1) {
      return { success: false, error: 'Não é possível excluir a única carteira restante.' };
    }

    const idx = manifest.portfolios.findIndex(p => p.id === portfolioId);
    if (idx === -1) {
      return { success: false, error: 'Carteira não encontrada.' };
    }

    // Remover do DynamoDB
    await docClient.send(new DeleteCommand({
      TableName: TABLE_NAME,
      Key: { PK: `USER#${userId}`, SK: `PORTFOLIO#${portfolioId}` }
    }));

    // Atualizar manifest
    manifest.portfolios.splice(idx, 1);
    if (manifest.active_portfolio_id === portfolioId) {
      manifest.active_portfolio_id = manifest.portfolios[0]?.id || null;
    }
    await PortfolioRepository.saveManifest(manifest, userId);

    return { success: true };
  }
}

module.exports = PortfolioRepository;

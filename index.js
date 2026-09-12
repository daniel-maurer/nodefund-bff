/**
 * Servidor Central Node.js BFF (Backend For Frontend)
 * Distributed Node Architecture - nodefund
 */

const express = require('express');
const cors = require('cors');
const path = require('path');
const config = require('./config');

const requestLogger = require('./middleware/requestLogger');
const errorHandler = require('./middleware/errorHandler');
const authMiddleware = require('./middleware/auth');

const portfolioRoutes = require('./routes/portfolios');
const simulationRoutes = require('./routes/simulation');
const rebalanceRoutes = require('./routes/rebalance');
const configRoutes = require('./routes/config');
const marketRoutes = require('./routes/market');
const dataRoutes = require('./routes/data');
const nodesRoutes = require('./routes/nodes');
const PortfolioRepository = require('./storage/portfolioRepository');

const app = express();

// ───────────────────── Middlewares Essenciais ─────────────────────
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(requestLogger);

// ───────────────────── Rotas de Autenticação (Públicas) ─────────────────────

// POST /api/auth/signup — Cria conta no Cognito
app.post('/api/auth/signup', async (req, res) => {
  try {
    const { email, password, name } = req.body;
    if (!email || !password) {
      return res.status(400).json({ error: 'Email e senha são obrigatórios.' });
    }

    if (config.AUTH_DISABLED) {
      return res.json({ status: 'success', message: 'Conta criada (modo local).' });
    }

    const { CognitoIdentityProviderClient, SignUpCommand } = require('@aws-sdk/client-cognito-identity-provider');
    const cognito = new CognitoIdentityProviderClient({ region: config.AWS_REGION });

    const userAttributes = [{ Name: 'email', Value: email }];
    if (name) userAttributes.push({ Name: 'name', Value: name });

    await cognito.send(new SignUpCommand({
      ClientId: config.COGNITO_APP_CLIENT_ID,
      Username: email,
      Password: password,
      UserAttributes: userAttributes
    }));

    res.json({ status: 'success', message: 'Conta criada. Verifique seu email para o código de confirmação.' });
  } catch (err) {
    const msg = err.message || 'Erro ao criar conta.';
    res.status(400).json({ error: msg });
  }
});

// POST /api/auth/confirm — Confirma email com código
app.post('/api/auth/confirm', async (req, res) => {
  try {
    const { email, code } = req.body;
    if (!email || !code) {
      return res.status(400).json({ error: 'Email e código são obrigatórios.' });
    }

    if (config.AUTH_DISABLED) {
      return res.json({ status: 'success', message: 'Email confirmado (modo local).' });
    }

    const { CognitoIdentityProviderClient, ConfirmSignUpCommand } = require('@aws-sdk/client-cognito-identity-provider');
    const cognito = new CognitoIdentityProviderClient({ region: config.AWS_REGION });

    await cognito.send(new ConfirmSignUpCommand({
      ClientId: config.COGNITO_APP_CLIENT_ID,
      Username: email,
      ConfirmationCode: code
    }));

    res.json({ status: 'success', message: 'Email confirmado com sucesso! Faça login.' });
  } catch (err) {
    res.status(400).json({ error: err.message || 'Código inválido.' });
  }
});

// POST /api/auth/login — Autentica e retorna tokens JWT
app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) {
      return res.status(400).json({ error: 'Email e senha são obrigatórios.' });
    }

    if (config.AUTH_DISABLED) {
      // Modo local: retorna tokens fictícios para desenvolvimento
      const fakePayload = Buffer.from(JSON.stringify({
        sub: 'anonymous',
        email,
        name: email.split('@')[0],
        exp: Math.floor(Date.now() / 1000) + 3600
      })).toString('base64');
      const fakeToken = `eyJ0eXAiOiJKV1QiLCJhbGciOiJub25lIn0.${fakePayload}.fake`;
      return res.json({
        id_token: fakeToken,
        access_token: fakeToken,
        refresh_token: 'local-refresh-token',
        expires_in: 3600
      });
    }

    const { CognitoIdentityProviderClient, InitiateAuthCommand } = require('@aws-sdk/client-cognito-identity-provider');
    const cognito = new CognitoIdentityProviderClient({ region: config.AWS_REGION });

    const result = await cognito.send(new InitiateAuthCommand({
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: config.COGNITO_APP_CLIENT_ID,
      AuthParameters: {
        USERNAME: email,
        PASSWORD: password
      }
    }));

    const auth = result.AuthenticationResult;
    res.json({
      id_token: auth.IdToken,
      access_token: auth.AccessToken,
      refresh_token: auth.RefreshToken,
      expires_in: auth.ExpiresIn
    });
  } catch (err) {
    res.status(401).json({ error: err.message || 'Credenciais inválidas.' });
  }
});

// POST /api/auth/refresh — Renova tokens com refresh token
app.post('/api/auth/refresh', async (req, res) => {
  try {
    const { refresh_token } = req.body;
    if (!refresh_token) {
      return res.status(400).json({ error: 'Refresh token é obrigatório.' });
    }

    if (config.AUTH_DISABLED) {
      const fakePayload = Buffer.from(JSON.stringify({
        sub: 'anonymous',
        email: 'local@dev.com',
        name: 'Local Dev',
        exp: Math.floor(Date.now() / 1000) + 3600
      })).toString('base64');
      const fakeToken = `eyJ0eXAiOiJKV1QiLCJhbGciOiJub25lIn0.${fakePayload}.fake`;
      return res.json({
        id_token: fakeToken,
        access_token: fakeToken,
        expires_in: 3600
      });
    }

    const { CognitoIdentityProviderClient, InitiateAuthCommand } = require('@aws-sdk/client-cognito-identity-provider');
    const cognito = new CognitoIdentityProviderClient({ region: config.AWS_REGION });

    const result = await cognito.send(new InitiateAuthCommand({
      AuthFlow: 'REFRESH_TOKEN_AUTH',
      ClientId: config.COGNITO_APP_CLIENT_ID,
      AuthParameters: {
        REFRESH_TOKEN: refresh_token
      }
    }));

    const auth = result.AuthenticationResult;
    res.json({
      id_token: auth.IdToken,
      access_token: auth.AccessToken,
      expires_in: auth.ExpiresIn
    });
  } catch (err) {
    res.status(401).json({ error: 'Sessão expirada. Faça login novamente.' });
  }
});

// GET /api/auth/me — Retorna dados do usuário autenticado
app.get('/api/auth/me', authMiddleware, (req, res) => {
  res.json({
    user_id: req.userId,
    email: req.userEmail || '',
    name: req.userName || ''
  });
});

// ───────────────────── Health Check (sem autenticação) ─────────────────────
// Deve ficar ANTES do authMiddleware para o ALB receber 200 sem token
app.get('/api/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

// ───────────────────── Middleware de Autenticação ─────────────────────
// Todas as rotas /api/* abaixo desta linha requerem autenticação
app.use('/api', authMiddleware);

// ───────────────────── Aliases para Compatibilidade ─────────────────────
app.get('/api/portfolio', async (req, res, next) => {
  try {
    const active = await PortfolioRepository.getActivePortfolio(req.userId);
    if (!active) {
      return res.status(404).json({ error: 'Nenhuma carteira ativa encontrada.' });
    }
    res.json(active);
  } catch (err) {
    next(err);
  }
});

app.post('/api/portfolio', async (req, res, next) => {
  try {
    const payload = req.body;
    try {
      const saved = await PortfolioRepository.savePortfolio(payload, payload.id, req.userId);
      const portfolios = await PortfolioRepository.listPortfolios(req.userId);
      res.json({
        status: 'success',
        message: 'Carteira salva com sucesso!',
        portfolio: saved,
        portfolios
      });
    } catch (valErr) {
      return res.status(400).json({ error: valErr.message });
    }
  } catch (err) {
    next(err);
  }
});

// ───────────────────── Rotas da API REST ─────────────────────
app.use('/api/portfolios', portfolioRoutes);
app.use('/api/simulate', simulationRoutes);
app.use('/api/rebalance', rebalanceRoutes);
app.use('/api/config', configRoutes);
app.use('/api/market', marketRoutes);
app.use('/api/data', dataRoutes);
app.use('/api/nodes', nodesRoutes);

// Servir arquivos estáticos do Frontend (HTML, CSS, JS)
app.use(express.static(config.STATIC_DIR, {
  etag: true,
  lastModified: true,
  maxAge: 0
}));

// Rota raiz carrega a interface do dashboard
app.get('/', (req, res) => {
  res.sendFile(path.join(config.STATIC_DIR, 'index.html'));
});

// 404 para rotas de API não reconhecidas
app.all('/api/*', (req, res) => {
  res.status(404).json({
    status: 'error',
    error: `Endpoint '${req.method} ${req.originalUrl}' não encontrado no BFF.`,
    node: config.NODE_ID
  });
});

// Tratamento central de erros
app.use(errorHandler);

function startServer(port = config.PORT, host = config.HOST) {
  return new Promise((resolve) => {
    const server = app.listen(port, host, () => {
      console.log('\n========================================================');
      console.log(` nodefund · Distributed Node Architecture`);
      console.log(` Serviço: Node.js BFF & DynamoDB Gateway`);
      console.log(` Cluster: ${config.CLUSTER_ID} | Nó: ${config.NODE_ID}`);
      console.log(` DynamoDB: ${config.DYNAMODB_ENDPOINT || 'AWS (produção)'}`);
      console.log(` Auth: ${config.AUTH_DISABLED ? 'DESABILITADA (modo dev)' : 'Cognito JWT'}`);
      console.log(` Acesse a aplicação: http://localhost:${port}`);
      console.log(` Analytics Worker:   ${config.ANALYTICS_NODE_URL}`);
      console.log('========================================================\n');
      resolve(server);
    });
  });
}

if (require.main === module) {
  startServer();
}

module.exports = { app, startServer };

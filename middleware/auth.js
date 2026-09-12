/**
 * Middleware de Autenticação JWT — Amazon Cognito
 * Distributed Node Architecture
 *
 * Valida tokens JWT emitidos pelo Cognito User Pool usando
 * aws-jwt-verify. Injeta req.userId (Cognito sub) no request.
 *
 * Quando AUTH_DISABLED=true (desenvolvimento local), permite
 * todas as requisições com userId='anonymous'.
 */

const { CognitoJwtVerifier } = require('aws-jwt-verify');
const config = require('../config');

let verifier = null;

// Inicializar o verificador apenas se auth estiver habilitada
if (!config.AUTH_DISABLED && config.COGNITO_USER_POOL_ID && config.COGNITO_APP_CLIENT_ID) {
  verifier = CognitoJwtVerifier.create({
    userPoolId: config.COGNITO_USER_POOL_ID,
    tokenUse: 'id',
    clientId: config.COGNITO_APP_CLIENT_ID
  });
}

// Rotas que não requerem autenticação
const PUBLIC_ROUTES = [
  '/api/health',
  '/api/nodes/health',
  '/api/auth/login',
  '/api/auth/signup',
  '/api/auth/confirm',
  '/api/auth/refresh'
];

function isPublicRoute(path) {
  return PUBLIC_ROUTES.some(route => path === route || path.startsWith(route + '/'));
}

async function authMiddleware(req, res, next) {
  // Rotas públicas passam sem autenticação
  if (isPublicRoute(req.path)) {
    req.userId = 'anonymous';
    return next();
  }

  // Modo desenvolvimento: auth desabilitada
  if (config.AUTH_DISABLED) {
    req.userId = 'anonymous';
    return next();
  }

  // Extrair token do header Authorization
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      error: 'Token de autenticação não fornecido.',
      code: 'MISSING_TOKEN'
    });
  }

  const token = authHeader.slice(7);

  try {
    if (!verifier) {
      console.error('[Auth] Verificador Cognito não configurado. Verifique COGNITO_USER_POOL_ID e COGNITO_APP_CLIENT_ID.');
      return res.status(500).json({ error: 'Serviço de autenticação não configurado.' });
    }

    const payload = await verifier.verify(token);
    req.userId = payload.sub;
    req.userEmail = payload.email || '';
    req.userName = payload.name || payload['custom:name'] || '';
    next();
  } catch (err) {
    console.warn(`[Auth] Token inválido: ${err.message}`);
    return res.status(401).json({
      error: 'Token inválido ou expirado. Faça login novamente.',
      code: 'INVALID_TOKEN'
    });
  }
}

module.exports = authMiddleware;

/**
 * Middleware Central de Tratamento de Erros
 * Distributed Node Architecture
 */

module.exports = function errorHandler(err, req, res, next) {
  const status = err.status || err.statusCode || 500;
  const message = err.message || 'Erro interno no servidor BFF';

  console.error(`[BFF Error] ${req.method} ${req.originalUrl}:`, err);

  res.status(status).json({
    status: 'error',
    error: message,
    node: 'node-bff-gateway',
    timestamp: new Date().toISOString(),
    ...(err.details ? { details: err.details } : {})
  });
};

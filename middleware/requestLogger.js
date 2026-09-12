/**
 * Middleware de Log para Requisições HTTP
 * Distributed Node Architecture
 */

module.exports = function requestLogger(req, res, next) {
  const start = Date.now();
  const timeStr = new Date().toTimeString().slice(0, 8);

  res.on('finish', () => {
    const duration = Date.now() - start;
    const status = res.statusCode;
    const method = req.method;
    const url = req.originalUrl || req.url;
    
    // Ignora logs de assets estáticos triviais (fontes, favicon) se necessário
    if (!url.startsWith('/api') && (url.endsWith('.png') || url.endsWith('.ico'))) {
      return;
    }

    console.log(`[${timeStr}] ${method} ${url} ${status} (${duration}ms)`);
  });

  next();
};

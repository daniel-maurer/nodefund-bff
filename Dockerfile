FROM node:20-slim AS base

# Instalar Python 3 e dependências de sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependências Node.js
COPY package*.json ./
RUN npm ci --production

# Dependências Python
COPY requirements.txt ./
RUN pip install --break-system-packages --no-cache-dir -r requirements.txt

# Código fonte
COPY . .

# Remover arquivos de desenvolvimento
RUN rm -rf tests/ data/ docs/ scripts/setup-local-db.js docker-compose.yml .env* .github/

EXPOSE 8000 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://localhost:8000/api/health').then(r => r.ok ? process.exit(0) : process.exit(1)).catch(() => process.exit(1))"

CMD ["./run.sh"]

#!/usr/bin/env bash
# nodefund - Distributed Node Architecture
# Inicia o Cluster Distribuído:
# 1. Nó de Análise Quantitativa (Python Worker - porta 8001)
# 2. Nó BFF & File Storage Gateway (Node.js - porta 8000)

export PATH="$HOME/.local/bin:$PATH"

PORT=${1:-8000}
ANALYTICS_PORT=${2:-8001}

echo "========================================================"
echo " nodefund · Distributed Node Architecture"
echo " Iniciando Cluster de Nós Distribuídos..."
echo "--------------------------------------------------------"
echo " 1. [Nó Analítico Python] Iniciando na porta ${ANALYTICS_PORT}..."
python3 app.py "${ANALYTICS_PORT}" > /tmp/nodefund_analytics.log 2>&1 &
PYTHON_PID=$!
echo "    PID: ${PYTHON_PID} (Logs em /tmp/nodefund_analytics.log)"

cleanup() {
    echo -e "\nEncerrando Cluster Distribuído..."
    kill $PYTHON_PID 2>/dev/null
    wait $PYTHON_PID 2>/dev/null
    echo "Cluster encerrado com sucesso."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

sleep 1.0

echo " 2. [Nó BFF Node.js]      Iniciando na porta ${PORT}..."
echo " Acesse a aplicação em: http://localhost:${PORT}"
echo "========================================================"

PORT=${PORT} ANALYTICS_NODE_URL="http://127.0.0.1:${ANALYTICS_PORT}" node index.js

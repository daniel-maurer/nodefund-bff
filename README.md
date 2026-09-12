# nodefund · Backend BFF & Distributed Node Architecture

Serviço central em **Node.js** atuando como **BFF (Backend-For-Frontend) & Storage Gateway**, integrado ao nó computacional analítico em **Python** para processamento quantitativo e sincronização de dados de mercado (B3 e CVM).

---

## 🏛️ Arquitetura do Cluster de Nós Distribuídos

```
┌─────────────────────────────────────────────────────────────┐
│                 Frontend Web (S3 + CloudFront)              │
└──────────────────────────────┬──────────────────────────────┘
                               │ Proxy / REST (ALB / :8000)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               Node.js BFF & Storage Gateway                 │
│                                                             │
│  • Autenticação de Usuários (Cognito / aws-jwt-verify)      │
│  • Validação de Negócio & Modelos                           │
│  • Despachante Analítico para Worker Python                 │
│  • Proxy REST e Integração com Amazon DynamoDB              │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼ AWS SDK                      ▼ IPC / HTTP
┌─────────────────────────────┐  ┌────────────────────────────┐
│      Amazon DynamoDB        │  │  Python Analytics Worker   │
│  • USER#<id> SK: MANIFEST   │  │  (boto3 para storage)      │
│  • USER#<id> SK: PORTFOLIO  │  │                            │
│  • FUND#<cnpj> SK: DATA     │  │  • Simulação (Vectorized)  │
│  • B3#<ticker> SK: DATA     │  │  • Rebalanceamento linear  │
│  • BENCH#<name> SK: DATA    │  │  • Coleta (CVM, B3, SGS)   │
└─────────────────────────────  └────────────────────────────┘
```

---

## ☁️ Deploy AWS & CI/CD
Este projeto está preparado para a nuvem AWS (Elastic Container Service / Fargate) com banco de dados DynamoDB e Autenticação Cognito.
- **Docker Compose**: Um ambiente local rodando `nodefund-bff` junto com `dynamodb-local` na porta 8100 e validação de autenticação simulada (`AUTH_DISABLED=true`).
- **CloudFormation**: Todos os recursos declarados em `infra/cloudformation.yaml`.
- **GitHub Actions**: Pipeline de testes automático no PR e Deploy automático no merge da branch master (criando a imagem Docker, subindo pro ECR e atualizando o ECS Fargate).

Leia as instruções detalhadas em [docs/AWS_SETUP.md](docs/AWS_SETUP.md) para subir sua infraestrutura!

---

## 🚀 Como Executar o Projeto

### Pré-requisitos
- **Node.js**: Versão 18 ou superior (recomendado 20 LTS).
- **Python**: Versão 3.10 ou superior.

### 1. Instalação de Dependências
```bash
npm install
```

### 2. Inicialização Completa do Cluster (Recomendado)
O script `run.sh` sobe em paralelo o worker analítico em Python na porta 8001 e o BFF Node.js na porta 8000:

```bash
./run.sh
```

Saída esperada no terminal:
```
========================================================
 nodefund · Distributed Node Architecture
 Iniciando Cluster de Nós Distribuídos...
--------------------------------------------------------
 1. [Nó Analítico Python] Iniciando na porta 8001...
    PID: 12345 (Logs em /tmp/nodefund_analytics.log)
 2. [Nó BFF Node.js]      Iniciando na porta 8000...
 Acesse a aplicação em: http://localhost:8000
========================================================
```

Ao pressionar `Ctrl+C`, ambos os processos são finalizados automaticamente.

### 3. Execução Individual dos Serviços (Opcional)

- **Apenas o BFF Node.js (Porta 8000)**:
  ```bash
  npm start
  # ou em modo desenvolvimento com auto-reload:
  npm run dev
  ```

- **Apenas o Worker Analítico Python (Porta 8001)**:
  ```bash
  python3 app.py 8001
  ```

---

## ⚙️ Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `PORT` | `8000` | Porta pública do servidor BFF |
| `HOST` | `0.0.0.0` | Host de escuta do servidor |
| `ANALYTICS_NODE_URL` | `http://127.0.0.1:8001` | URL do worker de análise quantitativa em Python |
| `ANALYTICS_NODE_TIMEOUT_MS` | `30000` | Tempo limite para cálculos pesados (30s) |
| `CLUSTER_ID` | `nodefund-cluster-alpha` | Identificador do cluster distribuído |
| `NODE_ID` | `bff-gateway-01` | Identificador do nó BFF no cluster |

---

## 🧪 Como Executar os Testes

O repositório inclui suítes completas de testes tanto para o Node.js quanto para o motor analítico em Python:

### Testes do BFF (Node.js)
```bash
npm test
```
Executa 21 testes cobrindo:
- Modelos de domínio (`Asset`, `Portfolio`, `MarketQuote`, `Simulation`, `DistributedNode`).
- Gravação atômica e persistência de arquivos (`FileStorage`, `PortfolioRepository`, `ConfigRepository`).
- Endpoints REST da API.

### Testes do Motor Analítico (Python)
```bash
npm run test:py
```
Executa 19 testes cobrindo:
- Simulação de Monte Carlo.
- Algoritmo de rebalanceamento e aporte inteligente.
- Cálculo de benchmarks e cotas B3/CVM.

### Executar Todos os Testes
```bash
npm test && npm run test:py
```

---

## 📡 Referência dos Endpoints da API

### Carteiras (Portfolios)
- `GET /api/portfolios` - Lista todas as carteiras cadastradas e a ativa.
- `GET /api/portfolio` - Retorna a carteira ativa atual.
- `GET /api/portfolios/:id` - Retorna os dados de uma carteira específica.
- `POST /api/portfolios/select` - Seleciona a carteira ativa (`{ portfolio_id }`).
- `POST /api/portfolios/create` - Cria uma nova carteira (`{ name, funds }`).
- `POST /api/portfolios` - Salva/atualiza uma carteira (valida meta de 100%).
- `PUT /api/portfolios/:id` - Atualização RESTful de carteira.
- `POST /api/portfolios/delete` - Exclui carteira via body.
- `DELETE /api/portfolios/:id` - Exclui carteira via rota RESTful.

### Simulação & Rebalanceamento
- `POST /api/simulate` - Dispara simulação histórica quantitativa.
- `GET /api/simulate/presets` - Parâmetros padrão recomendados.
- `POST /api/rebalance/calculate` - Calcula ordens de rebalanceamento para aporte.

### Mercado & Dados
- `GET /api/market/quotes` - Retorna as 4 cotações macro (S&P 500, Ibov, Bitcoin, Dólar).
- `GET /api/data/status` - Inventário e integridade dos arquivos locais de cotas.
- `POST /api/data/update` - Dispara sincronização de dados CVM e B3.

### Configurações
- `GET /api/config/sources` / `POST /api/config/sources` - Provedores de dados externos.
- `GET /api/config/benchmarks` / `POST /api/config/benchmarks` - Indicadores e benchmarks.

### Nós Distribuídos & Saúde
- `GET /api/nodes` - Topologia e telemetria de nós distribuídos no cluster.
- `GET /api/nodes/health` - Diagnóstico de saúde do BFF e métricas do sistema.

---

## 📁 Estrutura de Diretórios

```
bff/
├── index.js                  # Ponto de entrada do BFF Express
├── config.js                 # Variáveis de ambiente e caminhos de arquivos
├── package.json              # Dependências e scripts de teste
├── run.sh                    # Script de inicialização do cluster distribuído
├── README.md                 # Documentação completa do backend
├── models/                   # Modelos de domínio com validação estrita
├── storage/                  # Camada de I/O em arquivos (JSON e CSV)
├── services/                 # Despachante de nós e orquestração
├── routes/                   # Controladores das rotas REST
├── middleware/               # Logs de requisições e tratamento de erros
├── core/                     # Motor matemático e de coleta em Python
├── app.py                    # Worker analítico HTTP em Python
├── data/                     # Diretório de persistência de arquivos
├── docs/                     # Documentações de arquitetura e modelos
├── scripts/                  # Scripts utilitários de seed e manutenção
└── tests/                    # Suítes de testes Node.js e Python
```
# nodefund-bff

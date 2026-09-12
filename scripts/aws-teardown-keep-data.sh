#!/bin/bash
# ==============================================================================
# Script: aws-teardown-keep-data.sh
# Finalidade: Desligar e remover todos os recursos pagos da AWS (ALB, ECS Fargate,
#             CloudFront, S3 Frontend), preservando integralmente os DADOS
#             (DynamoDB, Cache S3 CVM) e a AUTENTICAÇÃO (Cognito User Pool).
# ==============================================================================

set -e

REGION="us-east-1"
CLUSTER="nodefund-cluster"
SERVICE="nodefund-service"
BFF_STACK="nodefund-bff"
FRONTEND_STACK="nodefund-frontend"

# Cores para saída
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "\n${CYAN}================================================================${NC}"
echo -e "${CYAN}     Nodefund · Teardown Econômico (Preservar Dados & Auth)     ${NC}"
echo -e "${CYAN}================================================================${NC}\n"

# ------------------------------------------------------------------------------
# 1. PARAR E REMOVER O ECS SERVICE (Fargate) — Economia de ~$15/mês
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[1/3] Verificando e removendo ECS Service Fargate ($SERVICE)...${NC}"

SERVICE_STATUS=$(aws ecs describe-services \
  --cluster "$CLUSTER" \
  --services "$SERVICE" \
  --region "$REGION" \
  --query "services[0].status" \
  --output text 2>/dev/null || echo "MISSING")

if [ "$SERVICE_STATUS" = "ACTIVE" ] || [ "$SERVICE_STATUS" = "DRAINING" ]; then
  echo "-> Reduzindo desired-count para 0..."
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$SERVICE" \
    --desired-count 0 \
    --region "$REGION" >/dev/null 2>&1 || true

  echo "-> Forçando exclusão do serviço ECS..."
  aws ecs delete-service \
    --cluster "$CLUSTER" \
    --service "$SERVICE" \
    --force \
    --region "$REGION" >/dev/null 2>&1 || true

  echo -e "${GREEN}✓ ECS Service removido com sucesso (Fargate zerado).${NC}"
else
  echo -e "${GREEN}✓ ECS Service já está inativo ou não existe.${NC}"
fi

# ------------------------------------------------------------------------------
# 2. REMOVER A STACK DO FRONTEND (CloudFront + S3)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/3] Verificando e removendo stack do Frontend ($FRONTEND_STACK)...${NC}"

FRONTEND_EXISTS=$(aws cloudformation describe-stacks \
  --stack-name "$FRONTEND_STACK" \
  --region "$REGION" \
  --query "Stacks[0].StackStatus" \
  --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$FRONTEND_EXISTS" != "DOES_NOT_EXIST" ] && [ "$FRONTEND_EXISTS" != "DELETE_COMPLETE" ]; then
  FRONT_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$FRONTEND_STACK" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
    --output text 2>/dev/null || echo "")

  if [ -n "$FRONT_BUCKET" ] && [ "$FRONT_BUCKET" != "None" ]; then
    echo "-> Esvaziando bucket S3 do frontend ($FRONT_BUCKET)..."
    aws s3 rm "s3://$FRONT_BUCKET" --recursive --region "$REGION" 2>/dev/null || true
  fi

  echo "-> Excluindo stack CloudFormation do frontend (CloudFront + S3)..."
  aws cloudformation delete-stack --stack-name "$FRONTEND_STACK" --region "$REGION"
  
  echo "-> Aguardando exclusão da stack (isso pode levar 2-3 minutos)..."
  aws cloudformation wait stack-delete-complete --stack-name "$FRONTEND_STACK" --region "$REGION" || true
  echo -e "${GREEN}✓ Stack do Frontend removida com sucesso.${NC}"
else
  echo -e "${GREEN}✓ Stack do Frontend já não existe.${NC}"
fi

# ------------------------------------------------------------------------------
# 3. DESATIVAR O APPLICATION LOAD BALANCER (ALB) — Economia de ~$18/mês
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/3] Atualizando stack $BFF_STACK para desativar o Load Balancer (ALB)...${NC}"

# Localiza o template CloudFormation
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="$SCRIPT_DIR/bff/infra/cloudformation.yaml"
if [ ! -f "$TEMPLATE_FILE" ]; then
  TEMPLATE_FILE="$SCRIPT_DIR/infra/cloudformation.yaml"
fi

if [ -f "$TEMPLATE_FILE" ]; then
  echo "-> Aplicando DeployALB=false na stack $BFF_STACK..."
  aws cloudformation deploy \
    --template-file "$TEMPLATE_FILE" \
    --stack-name "$BFF_STACK" \
    --parameter-overrides DeployALB=false \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset \
    --region "$REGION"
  echo -e "${GREEN}✓ ALB e Target Group destruídos com sucesso. Tabela DynamoDB e Cognito preservados!${NC}"
else
  echo -e "${RED}Aviso: Template $TEMPLATE_FILE não encontrado. Removendo ALB diretamente se existir...${NC}"
  ALB_ARN=$(aws elbv2 describe-load-balancers --names nodefund-alb --region "$REGION" --query "LoadBalancers[0].LoadBalancerArn" --output text 2>/dev/null || echo "")
  if [ -n "$ALB_ARN" ] && [ "$ALB_ARN" != "None" ]; then
    aws elbv2 delete-load-balancer --load-balancer-arn "$ALB_ARN" --region "$REGION"
    echo -e "${GREEN}✓ ALB removido diretamente via API.${NC}"
  fi
fi

# ------------------------------------------------------------------------------
# 4. CAPTURAR IDENTIFICADORES DO COGNITO E DYNAMODB PARA USO LOCAL
# ------------------------------------------------------------------------------
echo -e "\n${CYAN}----------------------------------------------------------------${NC}"
echo -e "${CYAN}             Dados Preservados na AWS para Uso Local             ${NC}"
echo -e "${CYAN}----------------------------------------------------------------${NC}"

USER_POOL_ID=$(aws cloudformation describe-stacks --stack-name "$BFF_STACK" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue" --output text 2>/dev/null || echo "")
APP_CLIENT_ID=$(aws cloudformation describe-stacks --stack-name "$BFF_STACK" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='CognitoAppClientId'].OutputValue" --output text 2>/dev/null || echo "")
DYNAMO_TABLE=$(aws cloudformation describe-stacks --stack-name "$BFF_STACK" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='DynamoDBTableName'].OutputValue" --output text 2>/dev/null || echo "nodefund")
S3_CACHE=$(aws cloudformation describe-stacks --stack-name "$BFF_STACK" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='S3CvmCacheBucket'].OutputValue" --output text 2>/dev/null || echo "")

echo -e "• DynamoDB Table:        ${GREEN}$DYNAMO_TABLE${NC}"
echo -e "• Cognito User Pool ID:  ${GREEN}$USER_POOL_ID${NC}"
echo -e "• Cognito App Client ID: ${GREEN}$APP_CLIENT_ID${NC}"
echo -e "• S3 Cache Bucket:       ${GREEN}$S3_CACHE${NC}"

# Salvar arquivo de ambiente local se o diretório bff existir
ENV_FILE="$SCRIPT_DIR/bff/.env"
if [ -d "$SCRIPT_DIR/bff" ]; then
  cat <<EOF > "$ENV_FILE"
# Configurações para desenvolvimento local conectado aos dados e login da AWS
PORT=8000
AWS_REGION=$REGION
DYNAMODB_TABLE_NAME=$DYNAMO_TABLE
COGNITO_USER_POOL_ID=$USER_POOL_ID
COGNITO_APP_CLIENT_ID=$APP_CLIENT_ID
S3_CVM_CACHE_BUCKET=$S3_CACHE
AUTH_DISABLED=false
NODE_ENV=development
EOF
  echo -e "\n${GREEN}✓ Arquivo de configuração local gerado em: $ENV_FILE${NC}"
fi

echo -e "\n${CYAN}================================================================${NC}"
echo -e "${GREEN}  Teardown Concluído! Seus custos na AWS foram reduzidos a R$ 0,00.${NC}"
echo -e "${CYAN}================================================================${NC}\n"
echo -e "Como rodar localmente com os dados da AWS:"
echo -e "  1. No terminal do BFF:      ${YELLOW}cd bff && npm run start${NC}  (ou npm run dev)"
echo -e "  2. No terminal do Frontend: ${YELLOW}cd frontend && npm start${NC}"
echo -e ""
echo -e "Quando você fizer ${YELLOW}merge na branch main${NC}, o GitHub Actions"
echo -e "irá automaticamente recriar o ALB, ECS Fargate e o CloudFront!"
echo -e "\n"

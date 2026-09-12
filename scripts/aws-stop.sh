#!/bin/bash
# Desliga o BFF (zera tasks ECS — para de cobrar pelo Fargate)
# O ALB continua rodando (~$0.60/dia), mas o container para.
# Uso: ./scripts/aws-stop.sh

set -e

CLUSTER="nodefund-cluster"
SERVICE="nodefund-service"
REGION="us-east-1"

echo "🔴 Desligando o BFF (desired count → 0)..."
aws ecs update-service \
  --cluster $CLUSTER \
  --service $SERVICE \
  --desired-count 0 \
  --region $REGION \
  --query "service.{status: status, desiredCount: desiredCount}" \
  --output json

echo ""
echo "✅ BFF desligado. Fargate não está mais cobrando."
echo "   (O ALB ainda custa ~\$0.60/dia enquanto existir)"
echo ""
echo "   Para ligar novamente: ./scripts/aws-start.sh"

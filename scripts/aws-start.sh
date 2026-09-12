#!/bin/bash
# Liga o BFF (sobe 1 task ECS)
# Uso: ./scripts/aws-start.sh

set -e

CLUSTER="nodefund-cluster"
SERVICE="nodefund-service"
REGION="us-east-1"

echo "🟢 Ligando o BFF..."
aws ecs update-service \
  --cluster $CLUSTER \
  --service $SERVICE \
  --desired-count 1 \
  --region $REGION \
  --query "service.{status: status, desiredCount: desiredCount}" \
  --output json

echo ""
echo "⏳ Aguardando task iniciar (~30s)..."
aws ecs wait services-stable \
  --cluster $CLUSTER \
  --services $SERVICE \
  --region $REGION

ALB=$(aws elbv2 describe-load-balancers \
  --names nodefund-alb \
  --region $REGION \
  --query "LoadBalancers[0].DNSName" \
  --output text)

echo ""
echo "✅ BFF online!"
echo "   URL: http://$ALB"

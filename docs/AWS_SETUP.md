# AWS Setup - Distributed Node Architecture (nodefund)

Este documento detalha os processos manuais e automatizados para provisionar o ambiente AWS do nodefund.

## Pré-requisitos
1. **AWS CLI** configurado localmente.
2. **Permissões** de IAM suficientes para rodar CloudFormation.
3. **Domínio Registrado** (Opcional, mas recomendado para produção se for usar URLs customizadas).

## 1. Criação da Role OIDC do GitHub Actions (Manual)
Antes de rodar o CI/CD (GitHub Actions), é necessário configurar um Identity Provider no IAM para que o GitHub tenha permissão de fazer push no ECR e atualizar o ECS.

1. Acesse o **AWS IAM Console** > **Identity providers** > **Add provider**.
2. Escolha **OpenID Connect**.
3. Provider URL: `https://token.actions.githubusercontent.com`
4. Audience: `sts.amazonaws.com`
5. Crie a Role e adicione uma *Trust Policy* que permita o acesso do seu repositório:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "arn:aws:iam::[ACCOUNT_ID]:oidc-provider/token.actions.githubusercontent.com" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringLike": { "token.actions.githubusercontent.com:sub": "repo:SEU-USUARIO/Prev:*" }
      }
    }
  ]
}
```
6. Anote o ARN da Role gerada e configure no repositório GitHub como um secret: `AWS_DEPLOY_ROLE_ARN`.

## 2. Deploy do CloudFormation do BFF
O `bff/infra/cloudformation.yaml` provisiona:
- Tabela DynamoDB
- Cognito User Pool & App Client
- VPC (Subnets, NatGateway, IGW)
- ECS Cluster, Fargate Service, Application Load Balancer

**Deploy via CLI:**
```bash
aws cloudformation deploy \
  --template-file bff/infra/cloudformation.yaml \
  --stack-name nodefund-bff \
  --capabilities CAPABILITY_NAMED_IAM
```
Aguarde a conclusão (pode demorar ~15 minutos por causa do NAT Gateway).

## 3. Deploy do CloudFormation do Frontend
O `frontend/infra/cloudformation.yaml` provisiona:
- Bucket S3 para os estáticos
- CloudFront Distribution configurada com duas origens:
  - Estáticos via S3 OAC
  - API via ALB do BFF (path `/api/*`)

**Deploy via CLI:**
(Você precisará passar o URL do ALB gerado no passo anterior)
```bash
ALB_DOMAIN=$(aws cloudformation describe-stacks --stack-name nodefund-bff --query "Stacks[0].Outputs[?OutputKey=='ALBDomain'].OutputValue" --output text)

aws cloudformation deploy \
  --template-file frontend/infra/cloudformation.yaml \
  --stack-name nodefund-frontend \
  --parameter-overrides BffLoadBalancerDomain=$ALB_DOMAIN \
  --capabilities CAPABILITY_NAMED_IAM
```

## 4. Subindo os dados para o DynamoDB Produção
No ambiente local, você tem os arquivos JSON migrados. O motor permite fazer o *Seed* do seu ambiente local para a nuvem se você configurar o `.env`:

```env
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=nodefund-bff-NodefundTable-XXXXX
```
E rodar localmente (desde que com credenciais da AWS configuradas):
```bash
npm run setup:local
```

Para puxar dados de cotas mais recentes na nuvem, basta usar a rota de Update do frontend que baterá no ALB e rodará o `update_all_benchmarks` e `update_funds_data` através do Worker Python usando boto3.

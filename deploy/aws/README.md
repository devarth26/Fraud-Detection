# Deploying to AWS (ECS on Fargate)

**Why ECS and not App Runner:** AWS closed App Runner to new customers on 30 April 2026 and recommends
Amazon ECS Express Mode for new container workloads (AWS docs: "AWS App Runner availability change").
ECS Express Mode creates an ordinary ECS service on Fargate behind an Application Load Balancer, so the
GitHub Actions step in `.github/workflows/ci-cd.yml` (`aws ecs update-service --force-new-deployment`) works for it.

> I could not run any of these steps from my environment. Treat the commands as a checked outline, not a
> tested script, and read the CLI help (`aws <service> <command> help`) wherever a flag looks off.

## Cost: read this before you start
- Fargate does **not** scale to zero and Express Mode puts an **Application Load Balancer** in front. Both bill by the hour while they exist.
- New AWS accounts (created after 15 July 2025) get a credit-based Free plan instead of the old always-on free tier. Sources disagree on
  the plan length (6 vs 12 months), so check **Billing -> Credits** for the terms that apply to *your* account, and confirm ECS, ALB and RDS are
  allowed on the Free plan.
- Create a **budget alert** first. When the demo is done, run the teardown section.

## 1. One-time setup
```bash
export AWS_REGION=ap-south-1            # choose your region
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Container registry
aws ecr create-repository --repository-name fraudshield-api --region $AWS_REGION

# S3 bucket for policy documents (and, later, exported case notes)
aws s3 mb s3://fraudshield-docs-$ACCOUNT_ID --region $AWS_REGION
python scripts/s3_sync.py --bucket fraudshield-docs-$ACCOUNT_ID
```

## 2. Database (PostgreSQL)
Create a small single-AZ RDS PostgreSQL instance in the **same VPC** you will run ECS in (Multi-AZ doubles the cost).
Allow inbound 5432 only from the ECS service's security group. Then:
```bash
aws secretsmanager create-secret --name fraudshield/database-url \
  --secret-string "postgresql://USER:PASSWORD@RDS_ENDPOINT:5432/frauddb"
aws secretsmanager create-secret --name fraudshield/groq-api-key --secret-string "gsk_..."
```
The app creates its tables on first start. Set `LANGGRAPH_POSTGRES_URL` to the same URL so paused human reviews survive container
restarts and work across more than one task. Without it, a review started on one task cannot be resumed on another.

## 3. Create the ECS service
Console path (documented by AWS): **ECS -> Express Mode -> Create service**.
- Image: `ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/fraudshield-api:latest` (push once manually first, see step 5)
- Container port: `8000`; health check path: `/agent/health`
- CPU/memory: start at 1 vCPU / 4 GB (torch + SHAP + embedding model need real memory; 0.5 GB will be OOM-killed)
- Environment variables: `EMBEDDINGS_PROVIDER=huggingface`, `LLM_PROVIDER=groq`, `REVIEW_THRESHOLD=0.75`,
  `POLICY_S3_BUCKET=fraudshield-docs-<account id>`
- Secrets (from Secrets Manager): `DATABASE_URL`, `LANGGRAPH_POSTGRES_URL`, `GROQ_API_KEY`
- Roles: the task execution role must be able to read those secrets and pull from ECR; the **task role** needs
  `s3:GetObject` + `s3:ListBucket` on the bucket (and `bedrock:InvokeModel` only if you switch `LLM_PROVIDER=bedrock`).

(The CLI equivalent is `aws ecs create-express-gateway-service`; I have not verified its flags, so check `help` before relying on it.)

## 4. GitHub Actions -> AWS with OIDC (no stored AWS keys)
1. In IAM, add the GitHub OIDC identity provider (`token.actions.githubusercontent.com`).
2. Create a role trusted by `repo:<your-user>/Fraud-Detection:ref:refs/heads/main` with permissions for:
   `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`,
   `ecr:CompleteLayerUpload`, `ecr:PutImage` on the repository, and `ecs:UpdateService`, `ecs:DescribeServices` on the service.
3. In the GitHub repo: **Secrets** -> `AWS_ROLE_ARN`. **Variables** -> `AWS_REGION`, `ECR_REPOSITORY` (`fraudshield-api`),
   `ECS_CLUSTER`, `ECS_SERVICE`, `SERVICE_URL` (the load balancer URL, no trailing slash).

## 5. First deploy
Push once manually so the service has an image, then let CI take over:
```bash
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
docker build -f docker/Dockerfile -t $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/fraudshield-api:latest .
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/fraudshield-api:latest
python scripts/smoke_test.py http://YOUR-ALB-URL
```
After that, every push to `main` runs: lint -> tests -> eval smoke test -> build image -> push to ECR -> roll the ECS service -> smoke test.

## 6. Hardening you should do before calling it production
- `/agent/*` and `/score` have **no authentication**. Put them behind an API key or Cognito before exposing them publicly. CORS in `api/main.py` is also wide open.
- The `:latest` tag makes rollbacks awkward; for a real service, render a task definition with the commit SHA tag instead.
- Add CloudWatch alarms on 5xx and task restarts.

## Teardown (stops the billing)
Delete the ECS service (Express Mode also removes its load balancer; verify in the EC2 console), the RDS instance (skip the final snapshot if you do not need it), the
ECR images, the S3 bucket and the Secrets Manager secrets.

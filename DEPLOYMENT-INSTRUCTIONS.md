# Deployment Instructions — Veda Meaning

## Live Deployment

| Resource | Value |
|----------|-------|
| **App URL** | https://d1j17houw6gbvj.cloudfront.net |
| **API Endpoint** | https://cj8goyfqil.execute-api.us-west-2.amazonaws.com/api |
| **CloudFront Distribution ID** | E3CB39LW96ZCVO |
| **S3 Frontend Bucket** | veda-meaning-frontend-064357173439-prod |
| **CloudFormation Stack** | veda-meaning-prod |
| **AWS Region** | us-west-2 |

---

## Prerequisites

Install the following tools before deploying:

```bash
# AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# AWS SAM CLI
pip install aws-sam-cli

# Python 3.12
sudo apt-get install python3.12 python3.12-pip   # Debian/Ubuntu
# or: brew install python@3.12                   # macOS
```

Configure AWS credentials:

```bash
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Region (us-east-1 or us-west-2), output (json)
```

Required IAM permissions for the deploying user/role:

```
cloudformation:*
s3:*
lambda:*
apigateway:*
cloudfront:*
iam:CreateRole, iam:AttachRolePolicy, iam:PutRolePolicy, iam:PassRole
bedrock:InvokeModel (for runtime use, not deploy)
```

---

## First-Time Deployment

```bash
git clone https://github.com/saspto/veda-meaning.git
cd veda-meaning
./scripts/deploy.sh
```

The script performs these steps automatically:

1. **Builds Lambda layer** — installs `requests`, `beautifulsoup4`, `lxml` into `lambda/layer/python/`
2. **SAM build** — resolves Lambda dependencies, packages artifacts into `.aws-sam/`
3. **SAM deploy** — creates/updates CloudFormation stack `veda-meaning-prod`
4. **Injects CloudFront URL** — rewrites `API_BASE` in `frontend/app.js` to the live CF URL
5. **S3 sync** — uploads `frontend/` to the S3 bucket, sets `no-cache` on `index.html`
6. **CloudFront invalidation** — clears `/*` so users get fresh assets immediately

Total deploy time: ~5 minutes (most time is CloudFront distribution creation on first run, ~3–4 min).

---

## Re-deployment (Code Changes)

### Lambda code change only
```bash
./scripts/deploy.sh
```
SAM detects only Lambda changed — skips CloudFront creation, takes ~1 minute.

### Frontend change only
```bash
# Quick path — skip SAM, just sync frontend
BUCKET="veda-meaning-frontend-064357173439-prod"
aws s3 sync frontend/ "s3://${BUCKET}/" --delete
aws s3 cp "s3://${BUCKET}/index.html" "s3://${BUCKET}/index.html" \
  --metadata-directive REPLACE --cache-control "no-cache, no-store, must-revalidate" \
  --content-type "text/html"
aws cloudfront create-invalidation --distribution-id E3CB39LW96ZCVO --paths "/*"
```

### Environment variables
```bash
# Override region or environment name
ENV=staging AWS_REGION=us-east-1 ./scripts/deploy.sh
```

---

## Architecture

```
Browser
  └─► CloudFront (d1j17houw6gbvj.cloudfront.net)
        ├─ /api/*  ──► API Gateway (cj8goyfqil.execute-api.us-west-2.amazonaws.com)
        │               └─ Lambda (veda-meaning-prod, Python 3.12, 512 MB)
        │                    ├─ scraper.py   → vedabase.io, IIT-K, valmikiramayan.net, sacred-texts.com
        │                    ├─ transliterator.py → Aksharamukha API (Devanagari→Telugu)
        │                    └─ bedrock_client.py → Bedrock Claude Haiku (fallback)
        └─ /*      ──► S3 (veda-meaning-frontend-064357173439-prod)
                        └─ index.html, app.js, styles.css
```

**Caching strategy:**
- `/api/*` responses cached at CloudFront for **24 hours**, keyed by `ref` + `script` query params
- Static assets cached for **1 hour** (`max-age=3600`)
- `index.html` served with `no-cache` (always fresh HTML, versioned JS/CSS via CF cache)

---

## AWS Resources Created

| Resource | Type | Name/ID |
|----------|------|---------|
| CloudFormation stack | Stack | `veda-meaning-prod` |
| CloudFront distribution | Distribution | `E3CB39LW96ZCVO` |
| CloudFront cache policy | CachePolicy | `veda-api-cache-prod` |
| CloudFront OAC | OriginAccessControl | `veda-oac-prod` |
| S3 bucket | Bucket | `veda-meaning-frontend-064357173439-prod` |
| API Gateway | REST API | `veda-meaning-api-prod` |
| Lambda function | Function | `veda-meaning-prod` |
| Lambda layer | LayerVersion | `veda-scraper-layer-prod` |
| IAM role | Role | `veda-meaning-prod-VedaFunctionRole-*` |

---

## IAM Role — Lambda Execution Permissions

The Lambda function's IAM role (`VedaFunctionRole`) has these policies:

```json
{
  "bedrock:InvokeModel": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-haiku-4-5-20251001",
  "logs:CreateLogGroup": "*",
  "logs:CreateLogStream": "*",
  "logs:PutLogEvents": "*"
}
```

No VPC, no NAT Gateway, no Cognito, no database.

---

## Bedrock Model Access

Bedrock requires manual model access approval in the AWS Console:

1. Go to **AWS Console → Bedrock → Model access** (us-east-1)
2. Click **Manage model access**
3. Enable **Anthropic Claude Haiku** (claude-haiku-4-5-20251001)
4. Submit — approval is usually instant

> Note: The Lambda is deployed in `us-west-2` but calls Bedrock in `us-east-1` (hardcoded in `bedrock_client.py`). If you want to use a different region, update `REGION` in `lambda/bedrock_client.py` and the IAM resource ARN in `infrastructure/template.yaml`.

---

## Supported Verse References

| Format | Example | Description |
|--------|---------|-------------|
| `BG <ch>.<v>` | `BG 2.47` | Bhagavad Gita, chapter.verse |
| `BG <ch>` | `BG 2` | Full Bhagavad Gita chapter |
| `RV <m>.<s>.<v>` | `RV 1.1.1` | Rig Veda, mandala.sukta.verse |
| `VR <k>.<s>.<v>` | `VR 1.1.1` | Valmiki Ramayana, kanda.sarga.verse |
| Named mantra | `Gayatri Mantra` | Built-in text + Bedrock |
| Named mantra | `Maha Mrityunjaya` | Built-in text + Bedrock |
| Named mantra | `Shanti Path` | Built-in text + Bedrock |

---

## Monitoring & Logs

```bash
# Tail Lambda logs
aws logs tail /aws/lambda/veda-meaning-prod --follow --region us-west-2

# Last 100 log lines
aws logs tail /aws/lambda/veda-meaning-prod --since 1h --region us-west-2

# Check CloudFront distribution status
aws cloudfront get-distribution --id E3CB39LW96ZCVO \
  --query "Distribution.Status" --output text
```

---

## Teardown

To delete all resources and stop incurring costs:

```bash
# Delete S3 bucket contents first (required before stack deletion)
aws s3 rm s3://veda-meaning-frontend-064357173439-prod --recursive

# Delete the CloudFormation stack (removes all other resources)
aws cloudformation delete-stack --stack-name veda-meaning-prod --region us-west-2

# Monitor deletion
aws cloudformation wait stack-delete-complete --stack-name veda-meaning-prod --region us-west-2
echo "Stack deleted."
```

---

## Cost Estimate (Monthly)

| Service | Usage | Estimated Cost |
|---------|-------|----------------|
| CloudFront | ~10K requests/month | ~$0.01 |
| S3 | 3 files, ~20 KB | ~$0.001 |
| API Gateway | ~1K requests (after CF cache) | ~$0.004 |
| Lambda | ~1K invocations × 30s × 512MB | ~$0.03 |
| Bedrock Claude Haiku | ~500K tokens (cached by CF) | ~$0.50–2.00 |
| **Total** | | **~$0.60–2.10/month** |

CloudFront's 24h caching on API responses is the primary cost control — repeated lookups of the same verse cost $0.

---

## Local Development

```bash
cd veda-meaning

# Install Lambda dependencies locally
pip install -r lambda/requirements.txt

# Start local API (port 3000)
sam local start-api --template infrastructure/template.yaml

# Serve frontend (port 8080)
python3 -m http.server 8080 --directory frontend

# Test API directly
curl "http://localhost:3000/verse?ref=BG+2.47&script=devanagari"
curl "http://localhost:3000/meaning?ref=Gayatri+Mantra&script=telugu"
```

For local dev the `API_BASE` in `app.js` must point to `http://localhost:3000` — the deploy script automatically sets it to the live CloudFront URL on each deployment.

#!/usr/bin/env bash
# Deploy Veda Meaning app to AWS
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-prod}"
STACK_NAME="veda-meaning-${ENV}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SAM_BUILD_DIR="${ROOT_DIR}/.aws-sam"

echo "==> Building Lambda layer..."
LAYER_DIR="${ROOT_DIR}/lambda/layer/python"
rm -rf "${ROOT_DIR}/lambda/layer"
mkdir -p "${LAYER_DIR}"
pip install -r "${ROOT_DIR}/lambda/requirements.txt" -t "${LAYER_DIR}" --quiet

echo "==> Building SAM app..."
cd "${ROOT_DIR}/infrastructure"
sam build \
  --template-file template.yaml \
  --build-dir "${SAM_BUILD_DIR}" \
  --region "${REGION}"

echo "==> Deploying stack ${STACK_NAME}..."
sam deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${SAM_BUILD_DIR}/template.yaml" \
  --region "${REGION}" \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
  --parameter-overrides Env="${ENV}" \
  --resolve-s3 \
  --no-confirm-changeset

echo "==> Fetching stack outputs..."
OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --query "Stacks[0].Outputs" \
  --output json)

BUCKET=$(echo "$OUTPUTS" | python3 -c "import json,sys; o=json.load(sys.stdin); print(next(x['OutputValue'] for x in o if x['OutputKey']=='FrontendBucketName'))")
CF_URL=$(echo "$OUTPUTS"  | python3 -c "import json,sys; o=json.load(sys.stdin); print(next(x['OutputValue'] for x in o if x['OutputKey']=='CloudFrontURL'))")
DIST_ID=$(echo "$OUTPUTS" | python3 -c "import json,sys; o=json.load(sys.stdin); print(next(x['OutputValue'] for x in o if x['OutputKey']=='DistributionId'))")
API_URL=$(echo "$OUTPUTS" | python3 -c "import json,sys; o=json.load(sys.stdin); print(next(x['OutputValue'] for x in o if x['OutputKey']=='ApiEndpoint'))")

echo "==> Injecting API URL into app.js..."
FRONTEND_DIR="${ROOT_DIR}/frontend"
TMP_JS=$(mktemp)
sed "s|const API_BASE = .*|const API_BASE = \"${CF_URL}/api\";|" \
  "${FRONTEND_DIR}/app.js" > "${TMP_JS}"
mv "${TMP_JS}" "${FRONTEND_DIR}/app.js"

echo "==> Syncing frontend to s3://${BUCKET}..."
aws s3 sync "${FRONTEND_DIR}" "s3://${BUCKET}/" \
  --region "${REGION}" \
  --delete \
  --cache-control "max-age=3600"

aws s3 cp "s3://${BUCKET}/index.html" "s3://${BUCKET}/index.html" \
  --metadata-directive REPLACE \
  --cache-control "no-cache, no-store, must-revalidate" \
  --content-type "text/html" \
  --region "${REGION}"

echo "==> Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
  --distribution-id "${DIST_ID}" \
  --paths "/*" \
  --region "${REGION}" \
  --output text

echo ""
echo "======================================="
echo "  Deployed! App URL: ${CF_URL}"
echo "  API Endpoint:       ${API_URL}"
echo "======================================="

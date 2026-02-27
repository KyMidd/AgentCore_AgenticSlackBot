#!/bin/bash
set -e

# Configuration
ECR_REPO="111111111111.dkr.ecr.us-east-1.amazonaws.com/ue1li-slackbot"
AWS_REGION="us-east-1"

# Images built from local use tag "dev"
IMAGE_TAG="dev"

echo "📦 Building and pushing Docker image to ECR"
echo "Repository: $ECR_REPO"
echo "Tag: $IMAGE_TAG"
echo ""

# Step 1: Login to ECR
echo "🔑 Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO

# Step 2: Build the Docker image for ARM64
echo "🔨 Building Docker image for ARM64..."
docker buildx build \
  --platform linux/arm64 \
  --output=type=registry,compression=gzip,force-compression=true \
  --provenance=false \
  --sbom=false \
  -t $ECR_REPO:$IMAGE_TAG \
  --push \
  --progress=plain \
  .

echo ""
echo "✅ Successfully built and pushed image"
echo ""
echo "🔄 Updating AgentCore runtime to use the new image..."

# Read current runtime configuration
RUNTIME_ID="YOUR_DEV_RUNTIME_ID"
RUNTIME_CONFIG=$(aws bedrock-agentcore-control get-agent-runtime --region $AWS_REGION --agent-runtime-id $RUNTIME_ID --output json)

# Extract necessary fields
DESCRIPTION=$(echo "$RUNTIME_CONFIG" | jq -r '.description')
ROLE_ARN=$(echo "$RUNTIME_CONFIG" | jq -r '.roleArn')

# Use Terraform-defined lifecycle values
IDLE_TIMEOUT=600   # 10 minutes
MAX_LIFETIME=14400 # 4 hours

# Build environment variables JSON
ENV_VARS=$(echo "$RUNTIME_CONFIG" | jq -c '.environmentVariables')

# Update the runtime
aws bedrock-agentcore-control update-agent-runtime \
  --region $AWS_REGION \
  --agent-runtime-id $RUNTIME_ID \
  --description "$DESCRIPTION" \
  --role-arn "$ROLE_ARN" \
  --network-configuration networkMode=PUBLIC \
  --lifecycle-configuration idleRuntimeSessionTimeout=$IDLE_TIMEOUT,maxLifetime=$MAX_LIFETIME \
  --agent-runtime-artifact containerConfiguration="{containerUri=$ECR_REPO:$IMAGE_TAG}" \
  --protocol-configuration serverProtocol=HTTP \
  --environment-variables "$ENV_VARS" > /dev/null

echo ""
echo "⏳ Waiting for runtime to become READY..."

# Poll the runtime status until it's READY
MAX_WAIT_SECONDS=300  # 5 minutes max wait
WAIT_INTERVAL=10      # Check every 10 seconds
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT_SECONDS ]; do
  STATUS=$(aws bedrock-agentcore-control get-agent-runtime --region $AWS_REGION --agent-runtime-id $RUNTIME_ID --query status --output text)

  if [ "$STATUS" = "READY" ]; then
    echo "✅ Runtime is READY!"
    break
  elif [ "$STATUS" = "FAILED" ]; then
    echo "❌ Runtime update FAILED!"
    exit 1
  else
    echo "   Status: $STATUS (waiting ${ELAPSED}s)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
  fi
done

if [ $ELAPSED -ge $MAX_WAIT_SECONDS ]; then
  echo "⚠️  Timeout waiting for runtime to become READY after ${MAX_WAIT_SECONDS}s"
  echo "   Check status manually: aws bedrock-agentcore-control get-agent-runtime --region $AWS_REGION --agent-runtime-id $RUNTIME_ID --query status"
  exit 1
fi

echo ""
echo "================================================"
echo "IMAGE TAG: $IMAGE_TAG"
echo "FULL IMAGE URI: $ECR_REPO:$IMAGE_TAG"
echo "================================================"
echo ""
echo "🎉 Deployment complete! Ready to test."
echo ""
echo "Next step: Send a message to your bot in Slack"

---
name: deploy-worker-dev
description: Build and deploy SlackBot worker to DEV environment
user-invocable: true
allowed-tools:
  - Bash
---

Build and deploy the SlackBot worker to the DEV environment.

## Configuration

Update these values for your environment:

- **ECR_REPO**: `<AWS_ACCOUNT_ID_DEV>.dkr.ecr.us-east-1.amazonaws.com/<ECR_REPO_NAME_DEV>`
- **AWS_REGION**: `us-east-1`
- **IMAGE_TAG**: `dev`
- **RUNTIME_ID**: `<AGENTCORE_RUNTIME_ID_DEV>`
- **IDLE_TIMEOUT**: `600` (10 minutes)
- **MAX_LIFETIME**: `14400` (4 hours)

## Steps

Execute these steps sequentially. Stop and report if any step fails.

### Step 1: Login to ECR

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <AWS_ACCOUNT_ID_DEV>.dkr.ecr.us-east-1.amazonaws.com/<ECR_REPO_NAME_DEV>
```

### Step 2: Build and push Docker image for ARM64

Run from the `worker/` directory:

```bash
cd "$(git rev-parse --show-toplevel)/worker" && docker buildx build \
  --platform linux/arm64 \
  --output=type=registry,compression=gzip,force-compression=true \
  --provenance=false \
  --sbom=false \
  -t <AWS_ACCOUNT_ID_DEV>.dkr.ecr.us-east-1.amazonaws.com/<ECR_REPO_NAME_DEV>:dev \
  --push \
  --progress=plain \
  .
```

### Step 3: Read current runtime configuration

```bash
RUNTIME_CONFIG=$(aws bedrock-agentcore-control get-agent-runtime --region us-east-1 --agent-runtime-id <AGENTCORE_RUNTIME_ID_DEV> --output json) && echo "$RUNTIME_CONFIG" | jq '{description: .description, roleArn: .roleArn, status: .status}'
```

Save the `description`, `roleArn`, and `environmentVariables` from the output for the next step.

### Step 4: Update AgentCore runtime

Using the values from Step 3, run:

```bash
RUNTIME_CONFIG=$(aws bedrock-agentcore-control get-agent-runtime --region us-east-1 --agent-runtime-id <AGENTCORE_RUNTIME_ID_DEV> --output json) && \
DESCRIPTION=$(echo "$RUNTIME_CONFIG" | jq -r '.description') && \
ROLE_ARN=$(echo "$RUNTIME_CONFIG" | jq -r '.roleArn') && \
ENV_VARS=$(echo "$RUNTIME_CONFIG" | jq -c '.environmentVariables') && \
aws bedrock-agentcore-control update-agent-runtime \
  --region us-east-1 \
  --agent-runtime-id <AGENTCORE_RUNTIME_ID_DEV> \
  --description "$DESCRIPTION" \
  --role-arn "$ROLE_ARN" \
  --network-configuration networkMode=PUBLIC \
  --lifecycle-configuration idleRuntimeSessionTimeout=600,maxLifetime=14400 \
  --agent-runtime-artifact 'containerConfiguration={containerUri=<AWS_ACCOUNT_ID_DEV>.dkr.ecr.us-east-1.amazonaws.com/<ECR_REPO_NAME_DEV>:dev}' \
  --protocol-configuration serverProtocol=HTTP \
  --environment-variables "$ENV_VARS"
```

### Step 5: Wait for runtime to become READY

Poll the runtime status every 10 seconds until it reaches READY (max 5 minutes):

```bash
ELAPSED=0; while [ $ELAPSED -lt 300 ]; do STATUS=$(aws bedrock-agentcore-control get-agent-runtime --region us-east-1 --agent-runtime-id <AGENTCORE_RUNTIME_ID_DEV> --query status --output text); if [ "$STATUS" = "READY" ]; then echo "Runtime is READY!"; break; elif [ "$STATUS" = "FAILED" ]; then echo "Runtime update FAILED!"; exit 1; else echo "Status: $STATUS (${ELAPSED}s elapsed)"; sleep 10; ELAPSED=$((ELAPSED + 10)); fi; done; if [ $ELAPSED -ge 300 ]; then echo "Timeout after 300s"; exit 1; fi
```

## After deployment

Inform the user they can test by sending a message to the DEV bot in Slack.

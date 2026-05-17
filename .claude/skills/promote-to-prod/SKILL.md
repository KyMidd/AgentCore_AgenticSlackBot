---
name: promote-to-prod
description: After a PR is merged, monitor CI/CD, approve PROD deploy, and validate
user-invocable: true
allowed-tools:
  - Bash
  - Glob
  - Grep
  - Read
  - Agent
---

Promote merged changes to PROD by monitoring CI/CD, approving the production deployment, and validating the live bot.

## Prerequisites

- A PR has been merged to master
- The user should provide context on what was changed (ticket number, feature description)

## Steps

Execute these steps sequentially. Stop and report if any step fails.

### Step 1: Identify the Terraform Workflow Run

After a PR merge, the "Run Terraform" workflow triggers automatically. Find the latest run:

```bash
gh run list --workflow terraform.yml --branch master --limit 3 --json databaseId,status,conclusion,createdAt
```

Identify the most recent run that is `in_progress` or `queued`. Save the `databaseId`.

### Step 2: Monitor Plan Phase

Poll the workflow run every 30 seconds until the plan jobs complete:

```bash
gh run view <RUN_ID> --json jobs --jq '.jobs[] | {name, status, conclusion}'
```

Wait for the plan jobs (names containing "plan") to reach `completed` status.

### Step 3: Approve Production Deployment

The PROD apply job pauses for GitHub Environment approval. Poll for the pending deployment:

```bash
gh api repos/{owner}/{repo}/actions/runs/<RUN_ID>/pending_deployments
```

When a pending deployment appears for the production environment, approve it:

```bash
gh api repos/{owner}/{repo}/actions/runs/<RUN_ID>/pending_deployments \
  -X POST \
  -f environment_ids[]='<ENV_ID>' \
  -f state=approved \
  -f comment='Approved by Claude Code'
```

If no pending deployment appears after 10 minutes, check if the workflow auto-approved or if there's an error.

### Step 4: Wait for Deploy to Complete

Poll the workflow run every 60 seconds until it completes. This typically takes 15-30 minutes:

```bash
STATUS=$(gh run view <RUN_ID> --json status,conclusion --jq '.status')
```

- If `completed` with `success` — proceed to validation
- If `completed` with `failure` — stop and report the failure. Use `gh run view <RUN_ID> --log-failed` to get error details.

### Step 5: Validate PROD Bot

Message the PROD bot in Slack to validate the deployed changes work:

1. Send a test message relevant to the feature that was deployed
2. Wait 60-90 seconds for the bot to respond
3. Read the thread to verify the response is correct
4. Send a regression test (simple question like "What year is it?")
5. Verify the regression response

Use the Slack MCP tools (`slack_send_message`, `slack_read_thread`) for all interactions.

### Step 6: Report

Report to the user:
- Workflow run ID and URL
- Deploy duration
- Validation results (what was tested, pass/fail)
- Any issues found

## Notes

- The Terraform workflow deploys infrastructure AND triggers the worker container update
- If only Python files changed (no .tf changes), the Terraform plan will show "no changes" but the workflow still runs
- The worker container is deployed separately via the `/deploy-worker-dev` and `/deploy-worker-prod` skills

---
name: sdlc
description: Full SDLC pipeline — ticket mgmt, code, test in DEV, push PR, Copilot review, merge, deploy to PROD, validate, update ticket, cleanup
user_invocable: true
---

# SDLC Pipeline

Coordinates the full development lifecycle for every code change. Execute each phase sequentially. Stop and report to the user if any phase fails.

## Phase 1: Identify the Jira Ticket

1. Determine the Jira ticket for this work. Check:
   - The user's message for a ticket reference (e.g., a ticket key or Jira URL)
   - The current git branch name for a ticket prefix
   - Ask the user if no ticket can be identified
2. Fetch the ticket details using the Atlassian MCP tools to understand requirements
3. **All commits must begin with the ticket number** (e.g., `PROJ-126 Add feature`)
4. If the ticket status is **Backlog** or **To Do**, transition it to **In Progress** and assign to self:
   ```
   mcp__atlassian__transitionJiraIssue  — use transition ID for "In Progress"
   mcp__atlassian__editJiraIssue        — set assignee to current user's accountId
   ```
   Use `mcp__atlassian__getTransitionsForJiraIssue` to find the correct transition ID.
   Use `mcp__atlassian__lookupJiraAccountId` to find the current user's accountId for assignment.

## Phase 2: Implement and Test in DEV

Follow the orchestrator workflow defined in CLAUDE.md to implement, review, and test the change:

1. **Implement** the requested change (Phases 1-3 from orchestrator workflow)
2. **Deploy to DEV** using `/deploy-worker-dev`
3. **Test with the DEV bot** — send a Slack message that exercises the changed functionality. This is REQUIRED before proceeding.
4. **Confirm the DEV bot responds correctly.** If it fails, fix and redeploy to DEV. Do not proceed until DEV validation passes.

## Phase 3: Push to GitHub

Use `/push-to-github` to:
- Format code (black, terraform fmt)
- Create feature branch (branch name must include ticket number)
- Commit and push (commit message must start with ticket number)
- Create PR targeting master

## Phase 4: Copilot Review

1. Copilot review triggers automatically on PR creation. If not, request it via the GitHub API.
2. Poll for Copilot review comments every 30 seconds, up to 15 minutes:
   ```bash
   gh api repos/{owner}/{repo}/pulls/<PR>/comments --jq '.[] | select(.user.login == "Copilot") | {id, path, body}'
   ```
   Also check reviews:
   ```bash
   gh api repos/{owner}/{repo}/pulls/<PR>/reviews --jq '.[] | select(.user.login | contains("copilot")) | .state'
   ```
3. For each Copilot comment:
   - Read the full comment
   - If valid: fix the code, commit, push
   - Reply to the comment explaining what was done (use `mcp__github__add_reply_to_pull_request_comment`)
   - If not applicable: reply explaining why
4. After addressing all comments, commit and push fixes in a single commit (commit message starts with ticket number).

## Phase 5: Merge Decision

Ask the user:
> "Copilot review addressed. Should I force merge with admin rights, or wait for a human review?"

**If force merge:** Proceed to Phase 6.

**If wait for human review:**
1. Post a ~25 word summary + PR link to the team Slack channel using `mcp__claude_ai_Slack__slack_send_message`
2. Poll the PR for approval every 60 seconds until merge requirements are met:
   ```bash
   gh api repos/{owner}/{repo}/pulls/<PR>/reviews --jq '.[] | select(.state == "APPROVED") | .user.login'
   ```
3. Once approved, proceed to Phase 6.

## Phase 6: Report and Merge

1. Report the PR status to the user: files changed, review comments addressed, any concerns
2. If anything is unexpected or concerning, pause and wait for user confirmation
3. Merge the PR using `mcp__github__merge_pull_request` with `merge_method: "squash"`

## Phase 7: CI/CD Deploy

1. The Terraform GitHub Action triggers automatically on PR close (merge to master)
2. Monitor the workflow run, polling every 30 seconds:
   ```bash
   gh run list --workflow terraform.yml --limit 3 --json databaseId,status,conclusion
   gh run view <RUN_ID> --json status,conclusion,jobs
   ```
3. **DEV apply** runs automatically
4. **PROD apply** requires GitHub environment approval. Approve it:
   ```bash
   gh api repos/{owner}/{repo}/actions/runs/<RUN_ID>/pending_deployments --method POST --input - <<'EOF'
   {"environment_ids": [<GITHUB_ENV_APPROVAL_ID>], "state": "approved", "comment": "Approved PROD deploy"}
   EOF
   ```
5. Wait for both apply jobs to complete successfully

## Phase 8: PROD Validation

1. Message the production bot in Slack to validate the fix
2. **Replicate the original issue as closely as possible.** Examples:
   - If a specific ticket type couldn't be created, ask the bot to create that exact ticket type
   - If a mention wasn't working, ask the bot to tag the specific user
   - If a comment was failing, ask the bot to add a comment with the same parameters
3. Read the thread to confirm the bot responded correctly
4. If the feature involves Jira, verify the Jira ticket/comment has the expected structure (e.g., check ADF content via the Atlassian MCP tools)

## Phase 9: Update Jira Ticket

1. Add a comment to the Jira ticket summarizing the work done:
   - PRs created (with numbers)
   - What changed and why
   - DEV and PROD validation results
2. If the ticket's acceptance criteria are fully met, transition to **Resolved**
3. If work remains (e.g., follow-up items discovered), update the ticket description or add a comment noting what's left, and leave the status as **In Progress**

## Phase 10: Cleanup

1. Identify any test tickets created during DEV and PROD validation
2. Attempt to close/transition each test ticket using `mcp__atlassian__transitionJiraIssue`
3. If a ticket can't be closed (permission error), add it to a list
4. Report to the user:
   - Tickets successfully closed
   - Tickets that need manual closure (with links)

## Important Rules

- **NEVER skip DEV testing.** A DEV bot message and confirmed response is required before pushing to GitHub.
- **NEVER skip PROD testing.** A PROD bot message and confirmed response is required after deployment.
- **All commits must start with the Jira ticket number.**
- If any phase fails, stop and report to the user before proceeding.
- The system prompt in `worker_inputs.py` is an **f-string** — any literal curly braces must be escaped as `{{` and `}}`.

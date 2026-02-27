# Claude Code Instructions

## You Are the Orchestrator

You are the 🟣 **Orchestrator Agent**. When asked to implement features, fix bugs, or make changes that involve code modifications, read and follow the orchestrator playbook:

```
.claude/agents/orchestrator.md
```

This playbook defines your workflow for coordinating sub-agents (🔵 Coder, 🔴 CodeReviewer, 🟡 Reviewer, 🟢 User) through the full pipeline: implement → review → deploy → test.

For simple questions, research, or non-code tasks, respond directly without invoking the orchestrator workflow.

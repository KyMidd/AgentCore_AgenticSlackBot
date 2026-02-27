"""
Sub-Agent Tool for Strands Agent

Spawns child agents with fresh context windows and MCP tool access to handle
tasks independently, keeping the parent agent's context lightweight.
"""

import json
import traceback
from typing import Callable
from strands import Agent, tool
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig

# Default child model — Claude 3.5 Haiku (fast/cheap, sufficient for structured tasks)
DEFAULT_CHILD_MODEL_ID = "us.anthropic.claude-3-5-haiku-20241022-v1:0"

# Allowed models for child agents (prevents arbitrary model IDs)
ALLOWED_CHILD_MODELS = {
    "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
}

# Default system prompt for child agents
DEFAULT_CHILD_SYSTEM_PROMPT = """You are a focused worker agent. You have access to Jira, Confluence, and PagerDuty tools via the gateway.

Execute the task given to you thoroughly and return a clear, structured response.

RULES:
- Focus exclusively on the task described in the user message
- Use the available tools to gather data as needed
- Return your results in a clear, structured format
- If the task requests JSON output, respond with ONLY valid JSON — no markdown, no explanation
- If a tool call fails, note the failure and continue with the remaining work
- Do NOT include raw API responses in your output — summarize and aggregate the data"""


def build_sub_agent_tool(secrets_json: dict) -> Callable:
    """
    Build general-purpose sub-agent tool that spawns child agents.

    Args:
        secrets_json: Dictionary containing credentials for MCP client creation

    Returns:
        Tool function for delegating tasks to child agents
    """

    @tool
    def run_sub_agent(
        task: str,
        system_prompt: str = "",
        output_format: str = "text",
        model_id: str = "",
    ) -> dict:
        """
        Delegate a task to a child agent with its own fresh context window and MCP tool access.

        The child agent gets a fresh 200K token context window with read-only access to
        Jira, Confluence, and PagerDuty via the gateway. Use this when a task would consume
        too much of your context window, or when you need to process data in parallel.

        Common use cases:
        - Analyzing batches of Jira tickets (fetch details, comments, compute summaries)
        - Searching and summarizing large sets of Confluence pages
        - Gathering data from multiple sources and returning a structured summary
        - Any task that involves fetching many items and returning aggregated results

        For parallel execution: call this tool multiple times in the same turn with different
        tasks — they will execute concurrently.

        Args:
            task: The task for the child agent to perform. Be specific and detailed.
                  Include any ticket keys, page IDs, search queries, or other identifiers needed.
                  For JSON output, specify the exact schema you expect in the task description.
            system_prompt: Optional custom system prompt for the child agent. If empty, uses
                          a default prompt suited for data gathering and summarization tasks.
            output_format: Expected output format — "json" or "text" (default: "text").
                          When "json", the tool will attempt to parse and validate the response as JSON.
            model_id: Optional Bedrock model ID for the child agent. If empty, defaults to
                      Claude 3.5 Haiku (fast/cheap). Use a more capable model for complex
                      analysis tasks that require deeper reasoning.

        Returns:
            Dictionary with the child agent's response (text or parsed JSON), or error details
        """
        try:
            if not task or not task.strip():
                return {
                    "status": "error",
                    "content": [{"text": "task is required and cannot be empty"}],
                }

            # Normalize and validate output_format
            output_format = output_format.strip().lower()
            if output_format not in ("json", "text"):
                return {
                    "status": "error",
                    "content": [
                        {
                            "text": f"output_format must be 'json' or 'text', got: '{output_format}'"
                        }
                    ],
                }

            # Resolve child model ID
            selected_model = DEFAULT_CHILD_MODEL_ID
            if model_id and model_id.strip():
                requested_model = model_id.strip()
                if requested_model in ALLOWED_CHILD_MODELS:
                    selected_model = requested_model
                else:
                    return {
                        "status": "error",
                        "content": [
                            {
                                "text": f"model_id '{requested_model}' is not allowed. Allowed models: {', '.join(sorted(ALLOWED_CHILD_MODELS))}"
                            }
                        ],
                    }

            task_preview = task[:100] + "..." if len(task) > 100 else task
            print(
                f"🔵 Child agent starting — model: {selected_model.split('.')[-1][:20]}, task: {task_preview}"
            )

            # Build child MCP client (fresh instance with read-only access)
            from worker_mcp_client_gateway import build_gateway_mcp_client

            child_mcp_client = build_gateway_mcp_client(secrets_json, mode="read_only")

            try:
                # Build child model
                child_model = BedrockModel(
                    model_id=selected_model,
                    boto_client_config=BotocoreConfig(
                        read_timeout=600,
                        retries={"max_attempts": 3, "mode": "adaptive"},
                    ),
                )

                # Always include default rules; append custom instructions if provided
                if system_prompt and system_prompt.strip():
                    child_system_prompt = (
                        DEFAULT_CHILD_SYSTEM_PROMPT
                        + "\n\nADDITIONAL INSTRUCTIONS:\n"
                        + system_prompt.strip()
                    )
                else:
                    child_system_prompt = DEFAULT_CHILD_SYSTEM_PROMPT

                # Create child agent (no callback_handler = silent)
                child_agent = Agent(
                    model=child_model,
                    system_prompt=child_system_prompt,
                    tools=[child_mcp_client],
                    callback_handler=None,
                )

                # Invoke child agent
                response = child_agent(task)
                response_text = str(response)

                print(f"🔵 Child agent completed — task: {task_preview}")

                # Handle JSON output format
                if output_format == "json":
                    return _parse_json_response(response_text)

                # Text output — return as-is
                return {
                    "status": "success",
                    "content": [{"text": response_text}],
                }

            finally:
                child_mcp_client.stop(None, None, None)

        except Exception as e:
            print(f"🔴 Child agent error: {traceback.format_exc()}")
            return {
                "status": "error",
                "content": [{"text": f"Child agent failed: {str(e)}"}],
            }

    return run_sub_agent


def _parse_json_response(response_text: str) -> dict:
    """Parse JSON from a child agent response, handling markdown fences."""
    json_text = response_text.strip()

    # Strip markdown code fences if present
    if json_text.startswith("```"):
        lines = json_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        json_text = "\n".join(lines)

    # Try direct parse
    try:
        result = json.loads(json_text)
        return {
            "status": "success",
            "content": [{"text": json.dumps(result)}],
        }
    except json.JSONDecodeError:
        pass

    # Fallback: find first '{' or '[' and try parsing from there
    for start_char in ["{", "["]:
        start_idx = json_text.find(start_char)
        if start_idx != -1:
            try:
                result = json.loads(json_text[start_idx:])
                return {
                    "status": "success",
                    "content": [{"text": json.dumps(result)}],
                }
            except json.JSONDecodeError:
                continue

    return {
        "status": "error",
        "content": [
            {
                "text": f"Failed to parse child agent JSON response. Raw: {response_text[:500]}"
            }
        ],
    }

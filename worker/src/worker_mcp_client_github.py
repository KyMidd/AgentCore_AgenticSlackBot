from datetime import timedelta
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

TOOLS_PREFIX = "github"
READ_ONLY_PREFIXES = ["download_", "get_", "list_", "search_"]

# Timeout configuration for GitHub MCP
# - timeout: HTTP request timeout (default 5s is too short for GitHub API)
# - sse_read_timeout: SSE connection timeout (default 5 minutes)
HTTP_TIMEOUT_SECONDS = 30
SSE_READ_TIMEOUT_SECONDS = 300  # 5 minutes


def build_github_mcp_client(github_token, mode="read_only"):
    """Build GitHub MCP client."""

    # Define tool filters for read-only mode
    tool_filters = None
    if mode == "read_only":
        # Filters are applied AFTER prefix, so add prefix + separator to each read-only prefix
        prefixed_read_only = tuple(
            f"{TOOLS_PREFIX}_{tool_prefix}" for tool_prefix in READ_ONLY_PREFIXES
        )
        tool_filters = {
            "allowed": [lambda tool: tool.tool_name.startswith(prefixed_read_only)]
        }

    # Create GitHub MCP client with extended timeouts to prevent "Connection closed" errors
    # that can corrupt session state with orphaned toolUse blocks
    github_mcp_client = MCPClient(
        lambda: streamablehttp_client(
            "https://api.githubcopilot.com/mcp/",
            headers={"Authorization": f"Bearer {github_token}"},
            timeout=timedelta(seconds=HTTP_TIMEOUT_SECONDS),
            sse_read_timeout=timedelta(seconds=SSE_READ_TIMEOUT_SECONDS),
        ),
        tool_filters=tool_filters,
        prefix=TOOLS_PREFIX,
    )

    return github_mcp_client

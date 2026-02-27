from datetime import timedelta
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

TOOLS_PREFIX = "atlan"
READ_ONLY_PREFIXES = ["semantic_search", "traverse"]

# Atlan MCP tools (12 total):
# READ-ONLY (allowed):
#   - semantic_search_tool
#   - traverse_lineage_tool
# WRITE (blocked):
#   - update_assets_tool
#   - create_glossaries
#   - create_glossary_terms
#   - create_glossary_categories
#   - create_domains
#   - create_data_products
#   - create_dq_rules_tool
#   - schedule_dq_rules_tool
#   - delete_dq_rules_tool
#   - update_dq_rules_tool

# Timeout configuration for Atlan MCP
# - timeout: HTTP request timeout (default 5s may be too short for Atlan API)
# - sse_read_timeout: SSE connection timeout (default 5 minutes)
HTTP_TIMEOUT_SECONDS = 30
SSE_READ_TIMEOUT_SECONDS = 300  # 5 minutes

ATLAN_MCP_URL = "https://YOUR_INSTANCE.atlan.com/mcp/api-key"


def build_atlan_mcp_client(atlan_api_key, mode="read_only"):
    """
    Build Atlan MCP client.

    Args:
        atlan_api_key: Atlan API key for authentication
        mode: Filter mode - "read_only" or "read_write" (default: "read_only")

    Returns:
        MCPClient: Configured MCP client for Atlan
    """

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

    # Create Atlan MCP client with extended timeouts
    atlan_mcp_client = MCPClient(
        lambda: streamablehttp_client(
            ATLAN_MCP_URL,
            headers={"Authorization": f"Bearer {atlan_api_key}"},
            timeout=timedelta(seconds=HTTP_TIMEOUT_SECONDS),
            sse_read_timeout=timedelta(seconds=SSE_READ_TIMEOUT_SECONDS),
        ),
        tool_filters=tool_filters,
        prefix=TOOLS_PREFIX,
    )

    return atlan_mcp_client

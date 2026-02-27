"""
Gateway Tool Filters

Tool filtering functions for each provider accessible through the AgentCore Gateway.
Each provider defines its own read-only filtering logic based on operation patterns.

Gateway tool naming: "providername___operationId"
Example: pagerduty___listIncidents, github___getIssue
"""

import os
from datetime import timedelta
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient
from worker_gateway_auth import get_gateway_token

# No prefix for gateway tools - they come with provider names already
# Example: pagerduty___getIncident, pagerduty___listUsers
TOOLS_PREFIX = None

# Timeout configuration for Gateway MCP
# - timeout: HTTP request timeout (default 5s may be too short)
# - sse_read_timeout: SSE connection timeout (default 5 minutes)
HTTP_TIMEOUT_SECONDS = 30
SSE_READ_TIMEOUT_SECONDS = 300  # 5 minutes


def combine_tool_filters(*filter_configs):
    """
    Combine multiple tool filter configurations.

    This allows multiple filter configurations with the same MCP client.

    Args:
        *filter_configs: Variable number of filter config dicts

    Returns:
        dict: Combined tool filter configuration
    """
    all_filters = []

    for config in filter_configs:
        if config and "allowed" in config:
            all_filters.extend(config["allowed"])

    return {"allowed": all_filters} if all_filters else None


def build_gateway_mcp_client(secrets_json, mode="read_only"):
    """
    Build MCP client for AgentCore Gateway.

    The gateway provides unified access to multiple platform tools through
    a single authenticated endpoint. This function automatically combines
    filters from all registered providers.

    Args:
        secrets_json: Dictionary containing GATEWAY_CLIENT_SECRET
        mode: Filter mode - "read_only" or "read_write" (default: "read_only")
              Applied to all providers registered with the gateway

    Returns:
        MCPClient: Configured MCP client connected to gateway
    """
    print("🟡 Building gateway MCP client...")
    print(f"🟡   Mode: {mode}")

    # Import all provider tool filters
    from worker_gateway_tools_pagerduty import pagerduty_tool_filter
    from worker_gateway_tools_jira import jira_tool_filter
    from worker_gateway_tools_confluence import confluence_tool_filter

    # Combine all provider filters based on mode
    tool_filters = combine_tool_filters(
        pagerduty_tool_filter(mode),
        jira_tool_filter(mode),
        confluence_tool_filter(mode),
    )

    # Get gateway URL
    gateway_url = os.environ.get("GATEWAY_URL")
    if not gateway_url:
        raise ValueError("Missing GATEWAY_URL environment variable")
    print(f"🟡   Gateway URL: {gateway_url}")

    # Create transport factory that fetches fresh token each time
    def create_transport():
        """Create streamable HTTP transport with fresh JWT token and extended timeouts"""
        token = get_gateway_token(secrets_json)
        return streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timedelta(seconds=HTTP_TIMEOUT_SECONDS),
            sse_read_timeout=timedelta(seconds=SSE_READ_TIMEOUT_SECONDS),
        )

    # Create gateway MCP client
    gateway_mcp_client = MCPClient(
        create_transport,
        tool_filters=tool_filters,
        prefix=TOOLS_PREFIX,
    )

    print("🟡 Gateway MCP client created")
    print(f"🟡   Filters: {tool_filters}")
    return gateway_mcp_client

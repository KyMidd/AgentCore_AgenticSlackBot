import os
import requests
from mcp.client.sse import sse_client
from strands.tools.mcp.mcp_client import MCPClient

TOOLS_PREFIX = "atlassian"
READ_ONLY_PREFIXES = ["fetch", "get", "lookup", "search", "atlassianUserInfo"]


def get_access_token(refresh_token, client_id):
    """Get fresh access token using refresh token and client ID"""
    if not refresh_token or not client_id:
        raise RuntimeError("Missing ATLASSIAN_REFRESH_TOKEN or ATLASSIAN_CLIENT_ID")

    response = requests.post(
        "https://mcp.atlassian.com/v1/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def build_atlassian_mcp_client(refresh_token, client_id, mode="read_only"):
    """Build Atlassian MCP client."""

    access_token = get_access_token(refresh_token, client_id)

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

    # Create Atlassian MCP client
    atlassian_mcp_client = MCPClient(
        lambda: sse_client(
            "https://mcp.atlassian.com/v1/sse",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=300.0,
        ),
        startup_timeout=60,
        tool_filters=tool_filters,
        prefix=TOOLS_PREFIX,
    )

    return atlassian_mcp_client

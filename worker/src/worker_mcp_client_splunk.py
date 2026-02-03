from datetime import timedelta
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

TOOLS_PREFIX = "splunk"

# Timeout configuration for Splunk MCP
# - timeout: HTTP request timeout (default 5s may be too short for Splunk queries)
# - sse_read_timeout: SSE connection timeout (default 5 minutes)
HTTP_TIMEOUT_SECONDS = 60  # Splunk queries can take longer
SSE_READ_TIMEOUT_SECONDS = 300  # 5 minutes


def build_splunk_mcp_client(splunk_token):
    """Build Splunk MCP client."""

    if not splunk_token:
        raise RuntimeError("SPLUNK_TOKEN is not set")

    # Create Splunk MCP client with extended timeouts to prevent connection issues
    splunk_mcp_client = MCPClient(
        lambda: streamablehttp_client(
            "https://YOUR_INSTANCE.api.scs.splunk.com/YOUR_INSTANCE/mcp/v1/",  # Update with your Splunk instance
            headers={"Authorization": f"Bearer {splunk_token}"},
            timeout=timedelta(seconds=HTTP_TIMEOUT_SECONDS),
            sse_read_timeout=timedelta(seconds=SSE_READ_TIMEOUT_SECONDS),
        ),
        prefix=TOOLS_PREFIX,
    )

    return splunk_mcp_client

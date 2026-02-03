from mcp import stdio_client, StdioServerParameters
from strands.tools.mcp.mcp_client import MCPClient


def build_azure_mcp_client(tenant_id, client_id, client_secret):
    """Build Azure MCP client with manual lifecycle management.

    Azure MCP requires manual lifecycle management (pre-PR#28 pattern) because
    the @azure/mcp package has compatibility issues when the Agent attempts to
    manage its lifecycle automatically. This approach manually enters the context,
    extracts tools, and provides them directly to the Agent while maintaining
    control over the context lifecycle.

    The function uses a lambda-wrapped stdio_client to defer connection until
    the context is entered, allowing for proper initialization of the .NET-based
    azmcp binary.

    Args:
        tenant_id: Azure tenant ID for authentication
        client_id: Azure application (client) ID
        client_secret: Azure application client secret

    Returns:
        tuple: (client, tools, context) where:
            - client: MCPClient instance for lifecycle management
            - tools: List of tool objects ready to be added to Agent
            - context: Active context manager (must be exited during cleanup)
    """
    print("🟡 Azure MCP: Creating client...")

    # Create MCPClient with deferred connection via lambda
    azure_mcp_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command="azmcp",
                args=["server", "start"],
                env={
                    "AZURE_TENANT_ID": tenant_id,
                    "AZURE_CLIENT_ID": client_id,
                    "AZURE_CLIENT_SECRET": client_secret,
                    # .NET runtime configuration for containerized environment
                    "DOTNET_BUNDLE_EXTRACT_BASE_DIR": "/tmp",
                    "HOME": "/tmp",
                },
            )
        ),
        prefix="azure",
    )

    print("🟡 Azure MCP: Entering context manually...")
    # Manually enter context to establish connection
    context = azure_mcp_client.__enter__()

    print("🟡 Azure MCP: Retrieving tools synchronously...")
    # Extract tools from the active connection
    azure_tools = context.list_tools_sync()
    print(f"🟡 Azure MCP: Retrieved {len(azure_tools)} tools")

    return azure_mcp_client, azure_tools, context

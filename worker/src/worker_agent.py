# Agent execution functions
import os
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from strands.models import BedrockModel
from strands.types.tools import AgentTool
from worker_inputs import (
    model_id,
    guardrailIdentifier,
    guardrailTracing,
    guardrailVersion,
    system_prompt,
    kb_region_name,
    memory_region,
)
from worker_errors import get_error_message


def execute_agent(secrets_json, conversation, memory_config=None):
    """
    Execute agent with MCP clients and optional memory

    Args:
        secrets_json: Dict containing all required credentials
        conversation: Conversation history for agent
        memory_config: Optional dict with memory configuration:
                      {"session_id": str, "actor_id": str, "memory_id": str, "memory_type": str}

    Returns:
        Agent response text
    """

    ###
    # MCP section
    ###

    # Initialize tools list and opened_clients dictionary
    tools = []
    opened_clients = {}

    # Built-in tools
    from strands_tools import calculator, current_time, retrieve

    tools.extend([calculator, current_time, retrieve])

    ##
    # AgentCore Gateway MCP
    # Provides access to all gateway-registered providers (PagerDuty, etc.)
    ##

    try:
        from worker_mcp_client_gateway import build_gateway_mcp_client

        # Build gateway client with read-only tools from all providers
        gateway_mcp_client = build_gateway_mcp_client(secrets_json, mode="read_only")
        opened_clients["Gateway"] = gateway_mcp_client
        tools.append(gateway_mcp_client)
    except Exception as error:
        print(f"🔴 Error setting up gateway MCP client: {str(error)}")

    ##
    # GitHub MCP
    ##

    try:
        from worker_mcp_client_github import build_github_mcp_client

        # Build GitHub MCP client with only read-only tools
        github_mcp_client = build_github_mcp_client(
            secrets_json["GITHUB_TOKEN"], "read_only"
        )
        opened_clients["GitHub"] = github_mcp_client
        tools.append(github_mcp_client)
    except Exception as error:
        print(f"🔴 Error setting up GitHub MCP client: {str(error)}")

    ##
    # Atlassian MCP
    ##

    try:
        from worker_mcp_client_atlassian import build_atlassian_mcp_client

        # Build Atlassian MCP client with only read-only tools
        atlassian_mcp_client = build_atlassian_mcp_client(
            secrets_json["ATLASSIAN_REFRESH_TOKEN"],
            secrets_json["ATLASSIAN_CLIENT_ID"],
            "read_only",
        )
        opened_clients["Atlassian"] = atlassian_mcp_client
        tools.append(atlassian_mcp_client)
    except Exception as error:
        print(f"🔴 Error setting up Atlassian MCP client: {str(error)}")

    ##
    # Azure MCP
    # Uses manual lifecycle management because @azure/mcp
    # is incompatible with automatic lifecycle management by the Agent.
    # Tools are extracted manually and added directly to the Agent's tool list.
    ##

    # Store Azure client and context for cleanup in finally block
    azure_mcp_client = None
    azure_mcp_context = None

    try:
        from worker_mcp_client_azure import build_azure_mcp_client

        # Manually initialize Azure MCP and extract tools
        # Returns (client, tools, context) tuple for manual lifecycle control
        azure_mcp_client, azure_tools, azure_mcp_context = build_azure_mcp_client(
            secrets_json["AZURE_TENANT_ID"],
            secrets_json["AZURE_CLIENT_ID"],
            secrets_json["AZURE_CLIENT_SECRET"],
        )

        # Add tools directly to Agent (not the MCPClient wrapper)
        # Bypassing Strand's MCPClient lifecycle management, failing to start Azure MCP
        tools.extend(azure_tools)
        print(f"🟡 Azure MCP: Added {len(azure_tools)} tools to agent")
    except Exception as error:
        print(f"🔴 Error setting up Azure MCP client: {str(error)}")
        # Clean up resources if initialization failed partway through
        if azure_mcp_client is not None and azure_mcp_context is not None:
            try:
                azure_mcp_client.__exit__(None, None, None)
            except:
                pass
        azure_mcp_client = None
        azure_mcp_context = None

    ##
    # AWS CLI MCP
    ##

    try:
        from worker_mcp_client_aws_cli import build_aws_cli_mcp_client

        # Build AWS CLI MCP client
        aws_cli_mcp_client = build_aws_cli_mcp_client(
            aws_region="us-east-1",
        )
        opened_clients["AWS_CLI"] = aws_cli_mcp_client
        # Add client
        tools.append(aws_cli_mcp_client)
    except Exception as error:
        print(f"🔴 Error setting up AWS CLI MCP client: {str(error)}")

    ##
    # Splunk MCP
    ##

    try:
        from worker_mcp_client_splunk import build_splunk_mcp_client

        # Build Splunk MCP client
        splunk_mcp_client = build_splunk_mcp_client(
            secrets_json["SPLUNK_TOKEN"],
        )
        opened_clients["Splunk"] = splunk_mcp_client
        tools.append(splunk_mcp_client)
    except Exception as error:
        print(f"🔴 Error setting up Splunk MCP client: {str(error)}")

    ###
    # Build agent
    ###

    # Prepare agent kwargs
    agent_kwargs = {
        "model": BedrockModel(
            model_id=model_id,
            guardrail_id=guardrailIdentifier,
            guardrail_trace=guardrailTracing,
            guardrail_version=guardrailVersion,
        ),
        "system_prompt": system_prompt,
        "tools": tools,
    }

    # Configure memory session manager if enabled
    if memory_config:
        try:
            from bedrock_agentcore.memory.integrations.strands.config import (
                AgentCoreMemoryConfig,
                RetrievalConfig,
            )
            from bedrock_agentcore.memory.integrations.strands.session_manager import (
                AgentCoreMemorySessionManager,
            )

            # Memory configuration
            agentcore_config = AgentCoreMemoryConfig(
                memory_id=memory_config["memory_id"],
                session_id=memory_config["session_id"],
                actor_id=memory_config["actor_id"],
                retrieval_config={
                    # User preferences only - high relevance threshold
                    "/preferences/{actorId}": RetrievalConfig(
                        top_k=5, relevance_score=0.7
                    ),
                },
            )

            # Create session manager
            session_manager = AgentCoreMemorySessionManager(
                agentcore_memory_config=agentcore_config, region_name=memory_region
            )
            print(f"🟡 Memory session manager using region: {memory_region}")

            # Add session manager to agent kwargs
            agent_kwargs["session_manager"] = session_manager
            print(
                f"🟡 Memory configured for session: {memory_config['session_id']}, actor: {memory_config['actor_id']}"
            )

            # Add memory management tools so users can list/delete their memories
            try:
                from worker_memory_tools import build_memory_tools

                memory_tools = build_memory_tools(memory_config, memory_region)
                tools.extend(memory_tools)
                print(f"🟢 Memory management tools added: {len(memory_tools)} tools")
            except Exception as tools_error:
                print(f"🔴 Failed to add memory management tools: {str(tools_error)}")
                # Continue without memory tools - session manager still works

        except Exception as e:
            print(f"🔴 Failed to configure memory session manager: {str(e)}")
            # Continue without memory rather than failing

    ##
    # Create agent with all collected tools
    ##

    # Set AWS_REGION env var as us-west-2 region
    os.environ["AWS_REGION"] = kb_region_name
    agent = Agent(**agent_kwargs)
    print(f"🟢 Agent created successfully in region {os.environ.get("AWS_REGION")}")

    try:
        response = agent(conversation)
        # Extract text from AgentResult object
        return str(response)
    except Exception as error:
        import traceback

        print(f"🔴 Error executing agent: {traceback.format_exc()}")
        return get_error_message(error)
    finally:
        # Manually exit Azure MCP context to avoid leaving open memory leak
        if azure_mcp_client is not None and azure_mcp_context is not None:
            try:
                print("🟡 Azure MCP: Exiting context on cleanup")
                azure_mcp_client.__exit__(None, None, None)
            except Exception as cleanup_error:
                print(f"🔴 Failed to exit Azure MCP context: {str(cleanup_error)}")

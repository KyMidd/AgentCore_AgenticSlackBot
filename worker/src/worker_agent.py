# Agent execution and lifecycle management
import os
from botocore.config import Config as BotocoreConfig
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
from worker_attachment_tool import (
    build_attachment_tool,
    build_additional_message_tool,
    build_chart_tool,
)
from worker_sub_agent_tool import build_sub_agent_tool


def execute_agent(
    secrets_json,
    conversation,
    memory_config=None,
    slack_user_id=None,
    user_display_name=None,
    slack_context=None,
):
    """
    Execute agent with MCP clients and optional memory

    Args:
        secrets_json: Dict containing all required credentials
        conversation: Conversation history for agent
        memory_config: Optional dict with memory configuration:
                      {"session_id": str, "actor_id": str, "memory_id": str, "memory_type": str}
        slack_user_id: Optional Slack user ID for per-user OAuth
        slack_context: Optional dict with Slack context for ephemeral messaging:
                      {"token": str, "channel_id": str, "thread_ts": str}

    Returns:
        Tuple of (response_text, attachments_list, additional_messages_list)
    """

    ###
    # MCP section
    ###

    # Initialize tools list and opened_clients dictionary
    tools = []
    opened_clients = {}

    # Initialize shared state for response enhancement tools
    attachments_list = []
    additional_messages_list = []
    # Built-in tools
    from strands_tools import calculator, current_time, retrieve

    tools.extend([calculator, current_time, retrieve])

    ##
    # AgentCore Gateway MCP
    # Provides access to all gateway-registered providers (PagerDuty, Jira, Confluence)
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
    # Per-User Atlassian OAuth (write operations)
    ##

    has_atlassian_write_tools = False

    if slack_user_id:
        try:
            from worker_oauth import lookup_user_token, check_and_cleanup_auth_prompt

            # Check if user completed auth since last interaction
            auth_completed = check_and_cleanup_auth_prompt(slack_user_id)
            if auth_completed:
                print(
                    f"🟢 User {slack_user_id} completed Atlassian auth since last interaction"
                )

            # Look up user's Atlassian token
            user_refresh_token = lookup_user_token(slack_user_id, "atlassian")

            if user_refresh_token:
                try:
                    from worker_atlassian_rest_tools import build_atlassian_rest_tools

                    atlassian_rest_tools = build_atlassian_rest_tools(
                        user_refresh_token,
                        secrets_json["ATLASSIAN_OAUTH_CLIENT_ID"],
                        secrets_json["ATLASSIAN_OAUTH_CLIENT_SECRET"],
                        slack_user_id=slack_user_id,
                    )
                    tools.extend(atlassian_rest_tools)
                    has_atlassian_write_tools = True
                    print(
                        f"🟢 Atlassian REST write tools registered for {slack_user_id} ({len(atlassian_rest_tools)} tools)"
                    )
                except Exception as error:
                    print(f"🔴 Error setting up Atlassian REST tools: {str(error)}")
                    # Only delete token if it's an auth/token failure, not a transient error
                    error_msg = str(error).lower()
                    if "token" in error_msg or "401" in error_msg or "403" in error_msg:
                        try:
                            from worker_oauth import delete_user_token

                            delete_user_token(slack_user_id, "atlassian")
                            print(
                                f"🟡 Deleted stale Atlassian token for {slack_user_id}"
                            )
                        except Exception as del_error:
                            print(f"🔴 Error deleting stale token: {del_error}")
            else:
                print(
                    f"🟡 No Atlassian user token for {slack_user_id}, registering auth tool"
                )
        except Exception as error:
            print(f"🔴 Error in per-user OAuth setup: {str(error)}")

        # Only register the auth tool when write tools are NOT available.
        # This prevents the model from choosing the auth tool over actual write tools.
        if not has_atlassian_write_tools:
            try:
                from worker_atlassian_auth_tool import build_atlassian_auth_tool

                auth_tool = build_atlassian_auth_tool(
                    slack_user_id,
                    secrets_json,
                    user_display_name=user_display_name,
                    slack_token=slack_context.get("token") if slack_context else None,
                    channel_id=(
                        slack_context.get("channel_id") if slack_context else None
                    ),
                    thread_ts=(
                        slack_context.get("thread_ts") if slack_context else None
                    ),
                )
                tools.append(auth_tool)
                print("🟢 Atlassian auth tool registered (no write tools available)")
            except Exception as error:
                print(f"🔴 Error registering Atlassian auth tool: {str(error)}")
        else:
            print("🟡 Skipping auth tool registration — write tools already available")

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
            except Exception:
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
    # Atlan MCP
    ##

    try:
        from worker_mcp_client_atlan import build_atlan_mcp_client

        # Build Atlan MCP client with only read-only tools
        atlan_mcp_client = build_atlan_mcp_client(
            secrets_json["ATLAN_API_KEY"], "read_only"
        )
        opened_clients["Atlan"] = atlan_mcp_client
        tools.append(atlan_mcp_client)
    except Exception as error:
        print(f"🔴 Error setting up Atlan MCP client: {str(error)}")

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

    ##
    # File Attachment Tool
    ##

    # Build response enhancement tools with closure-based state sharing
    attachment_tool = build_attachment_tool(attachments_list)
    tools.append(attachment_tool)
    additional_message_tool = build_additional_message_tool(additional_messages_list)
    tools.append(additional_message_tool)
    chart_tool = build_chart_tool(attachments_list)
    tools.append(chart_tool)

    # Sub-agent tool (delegates tasks to child agents with fresh context windows)
    try:
        sub_agent_tool = build_sub_agent_tool(secrets_json)
        tools.append(sub_agent_tool)
        print("🟢 Sub-agent tool added")
    except Exception as error:
        print(f"🔴 Error registering sub-agent tool: {str(error)}")

    print(
        "🟢 Response enhancement tools added (file attachment, additional messages, chart generation, sub-agent)"
    )

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
            boto_client_config=BotocoreConfig(
                read_timeout=600,
                retries={"max_attempts": 3, "mode": "adaptive"},
            ),
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
        return str(response), attachments_list, additional_messages_list
    except Exception as error:
        import traceback

        tb_str = traceback.format_exc()
        print(f"🔴 Error executing agent: {tb_str}")

        # If memory session manager caused the crash, retry without it
        if "session_manager" in agent_kwargs and (
            "session_manager" in tb_str
            or "SessionMessage" in tb_str
            or "append_message" in tb_str
            or "bedrock_agentcore.memory" in tb_str
        ):
            print("🟡 Memory-related crash detected, retrying without memory...")
            try:
                retry_kwargs = {
                    k: v for k, v in agent_kwargs.items() if k != "session_manager"
                }
                agent_no_memory = Agent(**retry_kwargs)
                print("🟢 Agent recreated without memory session manager")
                response = agent_no_memory(conversation)
                return str(response), attachments_list, additional_messages_list
            except Exception as retry_error:
                retry_tb = traceback.format_exc()
                print(f"🔴 Retry without memory also failed: {retry_tb}")
                return get_error_message(retry_error), [], []

        return get_error_message(error), [], []
    finally:
        # Manually exit Azure MCP context to avoid leaving open memory leak
        if azure_mcp_client is not None and azure_mcp_context is not None:
            try:
                print("🟡 Azure MCP: Exiting context on cleanup")
                azure_mcp_client.__exit__(None, None, None)
            except Exception as cleanup_error:
                print(f"🔴 Failed to exit Azure MCP context: {str(cleanup_error)}")

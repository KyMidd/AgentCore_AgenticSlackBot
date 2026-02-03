"""
PagerDuty Gateway Tool Filter

Tool filtering configuration for PagerDuty tools via AgentCore Gateway.
Replaces direct MCP connection with gateway-based access.
"""


def pagerduty_tool_filter(mode="read_only"):
    """
    Tool filter for PagerDuty provider via gateway.

    PagerDuty read-only operations: get*, list*
    Based on the original READ_ONLY_PREFIXES from direct MCP integration.

    Args:
        mode: "read_only" or "read_write"

    Returns:
        dict: Tool filter configuration for MCPClient
              {"allowed": [filter_function]}

    Gateway tool examples:
        - pagerduty___getIncident (read-only)
        - pagerduty___listIncidents (read-only)
        - pagerduty___listUsers (read-only)
        - pagerduty___createIncident (read-write)
        - pagerduty___updateIncident (read-write)
    """
    if mode == "read_only":
        # PagerDuty read-only operation verbs
        read_only_verbs = ["get", "list"]

        # AgentCore gateway returns tools with (provider)___(tool_name)
        # So construct prefixes accordingly for proper filtering
        read_only_prefixes = tuple(f"pagerduty___{verb}" for verb in read_only_verbs)

        def pagerduty_read_only_filter(tool):
            return tool.tool_name.startswith(read_only_prefixes)

        print("🟡 PagerDuty tools: read-only (get*, list*)")
        return {"allowed": [pagerduty_read_only_filter]}
    else:
        # Allow all PagerDuty tools
        def pagerduty_all_filter(tool):
            return tool.tool_name.startswith("pagerduty___")

        print("🟡 PagerDuty tools: read-write (all)")
        return {"allowed": [pagerduty_all_filter]}

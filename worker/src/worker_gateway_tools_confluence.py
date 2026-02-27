"""
Confluence Gateway Tool Filter

Tool filtering configuration for Confluence tools via AgentCore Gateway.
"""


def confluence_tool_filter(mode="read_only"):
    """
    Tool filter for Confluence provider via gateway.

    Confluence read-only operations: get*, list*, search*

    Args:
        mode: "read_only" or "read_write"

    Returns:
        dict: Tool filter configuration for MCPClient
              {"allowed": [filter_function]}

    Gateway tool examples:
        - confluence___getPage (read-only)
        - confluence___searchConfluenceUsingCql (read-only)
        - confluence___createPage (read-write)
        - confluence___updatePage (read-write)
    """
    if mode == "read_only":
        read_only_verbs = ["get", "list", "search"]
        read_only_prefixes = tuple(f"confluence___{verb}" for verb in read_only_verbs)

        def confluence_read_only_filter(tool):
            return tool.tool_name.startswith(read_only_prefixes)

        print("🟡 Confluence tools: read-only (get*, list*, search*)")
        return {"allowed": [confluence_read_only_filter]}
    else:

        def confluence_all_filter(tool):
            return tool.tool_name.startswith("confluence___")

        print("🟡 Confluence tools: read-write (all)")
        return {"allowed": [confluence_all_filter]}

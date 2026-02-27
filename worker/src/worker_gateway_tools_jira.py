"""
Jira Gateway Tool Filter

Tool filtering configuration for Jira tools via AgentCore Gateway.
"""


def jira_tool_filter(mode="read_only"):
    """
    Tool filter for Jira provider via gateway.

    Jira read-only operations: get*, list*, search*

    Args:
        mode: "read_only" or "read_write"

    Returns:
        dict: Tool filter configuration for MCPClient
              {"allowed": [filter_function]}

    Gateway tool examples:
        - jira___getIssue (read-only)
        - jira___searchIssues (read-only, JQL search)
        - jira___searchIssuesUsingJql (read-only)
        - jira___createIssue (read-write)
        - jira___editIssue (read-write)
    """
    if mode == "read_only":
        read_only_verbs = ["get", "list", "search"]
        read_only_prefixes = tuple(f"jira___{verb}" for verb in read_only_verbs)

        def jira_read_only_filter(tool):
            return tool.tool_name.startswith(read_only_prefixes)

        print("🟡 Jira tools: read-only (get*, list*, search*)")
        return {"allowed": [jira_read_only_filter]}
    else:

        def jira_all_filter(tool):
            return tool.tool_name.startswith("jira___")

        print("🟡 Jira tools: read-write (all)")
        return {"allowed": [jira_all_filter]}

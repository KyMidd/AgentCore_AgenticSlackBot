"""Atlassian REST API write tools for per-user OAuth.

Provides Jira and Confluence write operations using the standard Atlassian
REST API with per-user 3LO OAuth tokens. These tools replace the MCP SSE
client approach, which requires MCP-specific OAuth tokens.
"""

import html
import json
import re
import urllib.request
import urllib.parse
from typing import Any, Optional, Tuple
from strands import tool

# Shared ADF block appended to all Vera-created content for transparency
VERA_ADF_NOTE = {
    "type": "blockquote",
    "content": [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Co-authored by Vera"}],
        }
    ],
}

VERA_HTML_NOTE = "<blockquote><p>Co-authored by Vera</p></blockquote>"

# Required OAuth scopes — if a token is missing any of these, it was issued
# under an older scope configuration and must be re-authorized.
REQUIRED_SCOPES = {
    "read:jira-work",
    "write:jira-work",
    "read:jira-user",
    "write:page:confluence",
    "read:space:confluence",
    "read:servicedesk-request",
    "write:servicedesk-request",
}


def _validate_param(value: str, pattern: str, name: str) -> str:
    """Validate a parameter matches expected pattern before URL interpolation."""
    if not re.match(pattern, value):
        raise ValueError(f"Invalid {name}: {value!r}")
    return value


def _exchange_refresh_token(
    refresh_token: str, client_id: str, client_secret: str
) -> Tuple[str, Optional[str]]:
    """Exchange refresh token for access token via standard Atlassian OAuth 2.0.

    Returns (access_token, new_refresh_token) tuple. Atlassian rotates
    refresh tokens on every use — the old token becomes invalid.
    """
    token_data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
    ).encode()

    req = urllib.request.Request(
        "https://auth.atlassian.com/oauth/token",
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            token_response = json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        raise RuntimeError(
            f"Atlassian token exchange failed ({e.code}): {error_body[:200]}"
        ) from e

    return token_response["access_token"], token_response.get("refresh_token")


def _get_accessible_resources(access_token: str) -> list:
    """Get list of Atlassian cloud sites accessible with this token."""
    req = urllib.request.Request(
        "https://api.atlassian.com/oauth/token/accessible-resources",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


def _api_request(
    method: str, url: str, access_token: str, data: Optional[Any] = None
) -> dict:
    """Make an authenticated Atlassian REST API request."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            response_body = response.read().decode()
            if response_body:
                return json.loads(response_body)
            return {"status": "success"}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        try:
            error_json = json.loads(error_body)
            error_msg = error_json.get("errorMessages", [error_body])
            if isinstance(error_msg, list):
                error_msg = "; ".join(error_msg) if error_msg else error_body
        except (json.JSONDecodeError, TypeError):
            error_msg = error_body
        raise RuntimeError(f"Atlassian API error ({e.code}): {error_msg}") from e


def build_atlassian_rest_tools(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    slack_user_id: Optional[str] = None,
):
    """Build Atlassian REST API write tools for a user.

    Returns a list of tool functions that use the user's OAuth token
    to perform write operations via the Atlassian REST API.
    """

    # Exchange refresh token — also handles rotation
    access_token, new_refresh_token = _exchange_refresh_token(
        refresh_token, client_id, client_secret
    )

    # Store the rotated refresh token so it's valid next time
    if new_refresh_token and slack_user_id:
        try:
            from worker_oauth import update_user_refresh_token

            update_user_refresh_token(slack_user_id, new_refresh_token)
        except Exception as e:
            print(f"🔴 Failed to store rotated refresh token: {e}")

    resources = _get_accessible_resources(access_token)

    if not resources:
        raise RuntimeError("No accessible Atlassian cloud sites found for this user")

    # Use the first accessible site
    cloud_id = resources[0]["id"]
    site_name = resources[0].get("name", "unknown")
    jira_base = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"
    confluence_base = f"https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/api/v2"

    print(f"🟢 Atlassian REST tools configured for site: {site_name} ({cloud_id})")

    # Collect all scopes across all accessible resources for this site
    has_scope_info = any("scopes" in r for r in resources)
    if has_scope_info:
        token_scopes = set()
        for r in resources:
            token_scopes.update(r.get("scopes", []))
        print(f"🟡 Token scopes: {sorted(token_scopes)}")

        # Validate token has all required scopes
        missing_scopes = REQUIRED_SCOPES - token_scopes
        if missing_scopes:
            print(f"🔴 Token missing required scopes: {sorted(missing_scopes)}")
            raise RuntimeError(
                f"Token is missing required scopes: {', '.join(sorted(missing_scopes))}. "
                "User must re-authorize to grant updated permissions."
            )
    else:
        print("🟡 Accessible resources did not include scope info, skipping validation")

    @tool
    def atlassian_user_create_jira_issue(
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        description: str = "",
        assignee_account_id: str = "",
        labels: list = None,
        priority: str = "",
        parent_key: str = "",
    ) -> dict:
        """Create a new Jira issue in the user's Atlassian site.

        Args:
            project_key: The project key (e.g., 'IAP', 'PROJ')
            summary: Issue title/summary
            issue_type: Issue type name (e.g., 'Task', 'Bug', 'Story'). Default: 'Task'
            description: Issue description text (plain text, will be converted to ADF)
            assignee_account_id: Atlassian account ID to assign to (optional)
            labels: List of labels to add (optional)
            priority: Priority name (e.g., 'High', 'Medium', 'Low') (optional)
            parent_key: Parent issue key to set as epic/parent (e.g., 'IAP-10'). Use this to assign a Story or Task under an Epic. (optional)

        Returns:
            Dictionary with issue key and URL
        """
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }

        if parent_key:
            parent_key = _validate_param(
                parent_key, r"^[A-Z][A-Z0-9]+-\d+$", "parent_key"
            )
            fields["parent"] = {"key": parent_key}

        if description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    },
                    VERA_ADF_NOTE,
                ],
            }

        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}

        if labels:
            fields["labels"] = labels

        if priority:
            fields["priority"] = {"name": priority}

        result = _api_request(
            "POST", f"{jira_base}/issue", access_token, {"fields": fields}
        )

        issue_key = result.get("key", "")
        return {
            "status": "success",
            "issue_key": issue_key,
            "issue_url": f"https://{site_name}.atlassian.net/browse/{issue_key}",
            "message": f"Created Jira issue {issue_key}",
        }

    @tool
    def atlassian_user_add_jira_comment(
        issue_key: str,
        comment_text: str,
    ) -> dict:
        """Add a comment to an existing Jira issue.

        Args:
            issue_key: The issue key (e.g., 'IAP-123')
            comment_text: The comment text (plain text)

        Returns:
            Dictionary with comment details
        """
        issue_key = _validate_param(issue_key, r"^[A-Z][A-Z0-9]+-\d+$", "issue_key")
        body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment_text}],
                    },
                    VERA_ADF_NOTE,
                ],
            }
        }

        result = _api_request(
            "POST", f"{jira_base}/issue/{issue_key}/comment", access_token, body
        )

        return {
            "status": "success",
            "comment_id": result.get("id", ""),
            "message": f"Added comment to {issue_key}",
        }

    @tool
    def atlassian_user_edit_jira_issue(
        issue_key: str,
        summary: str = "",
        description: str = "",
        assignee_account_id: str = "",
        labels: list = None,
        priority: str = "",
        parent_key: str = "",
    ) -> dict:
        """Edit an existing Jira issue's fields.

        Args:
            issue_key: The issue key (e.g., 'PROJ-123')
            summary: New summary/title (optional, leave empty to keep current)
            description: New description (optional, leave empty to keep current)
            assignee_account_id: New assignee account ID (optional)
            labels: New labels list (optional, replaces existing labels)
            priority: New priority name (optional)
            parent_key: Parent issue key to assign this issue under an Epic (e.g., 'IAP-10'). Use this to move a Story or Task under an Epic. (optional)

        Returns:
            Dictionary with update status
        """
        issue_key = _validate_param(issue_key, r"^[A-Z][A-Z0-9]+-\d+$", "issue_key")
        fields = {}

        if parent_key:
            parent_key = _validate_param(
                parent_key, r"^[A-Z][A-Z0-9]+-\d+$", "parent_key"
            )
            fields["parent"] = {"key": parent_key}

        if summary:
            fields["summary"] = summary

        if description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    },
                    VERA_ADF_NOTE,
                ],
            }

        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}

        if labels is not None:
            fields["labels"] = labels

        if priority:
            fields["priority"] = {"name": priority}

        if not fields:
            return {"status": "error", "message": "No fields provided to update"}

        _api_request(
            "PUT", f"{jira_base}/issue/{issue_key}", access_token, {"fields": fields}
        )

        return {
            "status": "success",
            "message": f"Updated {issue_key}",
            "issue_url": f"https://{site_name}.atlassian.net/browse/{issue_key}",
        }

    @tool
    def atlassian_user_transition_jira_issue(
        issue_key: str,
        transition_name: str,
    ) -> dict:
        """Transition a Jira issue to a new status.

        Args:
            issue_key: The issue key (e.g., 'IAP-123')
            transition_name: The name of the transition (e.g., 'Done', 'In Progress', 'To Do')

        Returns:
            Dictionary with transition status
        """
        issue_key = _validate_param(issue_key, r"^[A-Z][A-Z0-9]+-\d+$", "issue_key")
        # Get available transitions
        transitions_result = _api_request(
            "GET", f"{jira_base}/issue/{issue_key}/transitions", access_token
        )

        transitions = transitions_result.get("transitions", [])
        target = None
        for t in transitions:
            if t["name"].lower() == transition_name.lower():
                target = t
                break

        if not target:
            available = [t["name"] for t in transitions]
            return {
                "status": "error",
                "message": f"Transition '{transition_name}' not found. Available: {', '.join(available)}",
            }

        _api_request(
            "POST",
            f"{jira_base}/issue/{issue_key}/transitions",
            access_token,
            {"transition": {"id": target["id"]}},
        )

        return {
            "status": "success",
            "message": f"Transitioned {issue_key} via '{transition_name}'",
        }

    @tool
    def atlassian_user_create_confluence_page(
        space_key: str,
        title: str,
        body_text: str,
        parent_page_id: str = "",
    ) -> dict:
        """Create a new Confluence page.

        Args:
            space_key: The space key (e.g., 'TEAM', 'ENG')
            title: Page title
            body_text: Page content (plain text, will be converted to storage format)
            parent_page_id: Optional parent page ID to create as a child page

        Returns:
            Dictionary with page details and URL
        """
        # Get space ID from space key
        space_key = _validate_param(
            space_key, r"^[A-Z][A-Z0-9_~-]+$", "space_key"
        )
        spaces = _api_request(
            "GET", f"{confluence_base}/spaces?keys={space_key}", access_token
        )

        if not spaces.get("results"):
            return {"status": "error", "message": f"Space '{space_key}' not found"}

        space_id = spaces["results"][0]["id"]

        page_data = {
            "spaceId": space_id,
            "status": "current",
            "title": title,
            "body": {
                "representation": "storage",
                "value": f"<p>{html.escape(body_text)}</p>{VERA_HTML_NOTE}",
            },
        }

        if parent_page_id:
            page_data["parentId"] = parent_page_id

        result = _api_request(
            "POST", f"{confluence_base}/pages", access_token, page_data
        )

        page_id = result.get("id", "")
        return {
            "status": "success",
            "page_id": page_id,
            "page_url": f"https://{site_name}.atlassian.net/wiki/spaces/{space_key}/pages/{page_id}",
            "message": f"Created Confluence page: {title}",
        }

    # JSM Service Desk base URL
    jsm_base = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/servicedeskapi"

    # JSD Forms (Proforma) API base URL
    # NOTE: The Atlassian docs show /jira/forms/cloud/{cloudId} but that
    # returns 401 for 3LO OAuth tokens. The /ex/jira/{cloudId}/forms path
    # routes through the same gateway as other Jira APIs and works correctly.
    forms_base = f"https://api.atlassian.com/ex/jira/{cloud_id}/forms"

    @tool
    def atlassian_user_list_service_desks() -> dict:
        """List all Jira Service Management service desks accessible to the user.

        Returns a list of service desks with their IDs, names, and project keys.
        Use the service desk ID from this response when calling other JSM tools.

        Returns:
            Dictionary with list of service desks
        """
        result = _api_request("GET", f"{jsm_base}/servicedesk", access_token)

        desks = []
        for desk in result.get("values", []):
            desks.append(
                {
                    "id": desk.get("id"),
                    "project_key": desk.get("projectKey"),
                    "project_name": desk.get("projectName"),
                }
            )

        return {
            "status": "success",
            "service_desks": desks,
            "message": f"Found {len(desks)} service desk(s)",
        }

    @tool
    def atlassian_user_list_request_types(
        service_desk_id: str,
    ) -> dict:
        """List all request types available in a Jira Service Management service desk.

        Use atlassian_user_list_service_desks first to get the service_desk_id,
        then use this tool to see what types of requests can be created.

        Args:
            service_desk_id: The service desk ID (numeric string, e.g., '1')

        Returns:
            Dictionary with list of request types including their IDs, names, and descriptions
        """
        service_desk_id = _validate_param(service_desk_id, r"^\d+$", "service_desk_id")
        result = _api_request(
            "GET",
            f"{jsm_base}/servicedesk/{service_desk_id}/requesttype",
            access_token,
        )

        request_types = []
        for rt in result.get("values", []):
            request_types.append(
                {
                    "id": rt.get("id"),
                    "name": rt.get("name"),
                    "description": rt.get("description", ""),
                    "help_text": rt.get("helpText", ""),
                }
            )

        return {
            "status": "success",
            "request_types": request_types,
            "message": f"Found {len(request_types)} request type(s)",
        }

    # --- Private helper: fetch standard request type fields ---
    def _fetch_request_type_fields(service_desk_id: str, request_type_id: str) -> list:
        """Fetch raw standard fields for a request type. Returns list of field dicts."""
        result = _api_request(
            "GET",
            f"{jsm_base}/servicedesk/{service_desk_id}/requesttype/{request_type_id}/field",
            access_token,
        )

        fields = []
        for field in result.get("requestTypeFields", []):
            field_info = {
                "field_id": field.get("fieldId"),
                "name": field.get("name"),
                "required": field.get("required", False),
                "description": field.get("description", ""),
            }

            valid_values = field.get("validValues")
            if valid_values:
                field_info["valid_values"] = [
                    {"value": v.get("value"), "label": v.get("label")}
                    for v in valid_values
                ]

            json_schema = field.get("jiraSchema")
            if json_schema:
                field_info["type"] = json_schema.get("type", "")
                field_info["system"] = json_schema.get("system", "")

            fields.append(field_info)

        return fields

    # --- Private helper: fetch form fields ---
    def _fetch_form_fields(service_desk_id: str, request_type_id: str) -> tuple:
        """Fetch form fields. Returns (form_id, fields_list, design_data) or ("", [], None) if no form."""
        url = (
            f"{forms_base}/servicedesk/{service_desk_id}"
            f"/requesttype/{request_type_id}/form"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "X-ExperimentalApi": "opt-in",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                form_data = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            print(f"🔴 Forms API error {e.code}: {error_body[:500]}")
            if e.code == 404:
                return ("", [], None)
            raise RuntimeError(
                f"Forms API returned HTTP {e.code}. "
                "This may indicate the Forms API is not accessible with the current token."
            ) from e

        design = form_data.get("design") or {}
        questions = design.get("questions") or {}

        # --- Parse ADF layout to build section_id -> [question_ids] mapping ---
        def _extract_question_ids(nodes: list) -> list:
            """Recursively extract question IDs from ADF content nodes."""
            qids = []
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                attrs = node.get("attrs") or {}
                if attrs.get("extensionKey") == "question":
                    qid = str((attrs.get("parameters") or {}).get("id", ""))
                    if qid:
                        qids.append(qid)
                children = node.get("content") or []
                if children:
                    qids.extend(_extract_question_ids(children))
            return qids

        layout = design.get("layout") or []
        if isinstance(layout, dict):
            layout = [layout]

        section_to_questions: dict = {}
        root_question_ids: set = set()
        for idx, layout_doc in enumerate(layout):
            if not isinstance(layout_doc, dict):
                continue
            doc_content = layout_doc.get("content") or []
            q_ids = _extract_question_ids(doc_content)
            if idx == 0:
                root_question_ids.update(q_ids)
            else:
                section_to_questions[str(idx)] = q_ids

        all_sectioned_question_ids: set = set()
        for qids in section_to_questions.values():
            all_sectioned_question_ids.update(qids)

        # --- Parse design.conditions ---
        conditions = design.get("conditions") or {}
        choice_to_section: dict = {}
        if isinstance(conditions, dict):
            for _cond_id, cond in conditions.items():
                if not isinstance(cond, dict):
                    continue
                inp = cond.get("i") or {}
                co = (inp.get("co") or {}).get("cIds") or {}
                out = cond.get("o") or {}
                section_ids = out.get("sIds") or []
                for q_id, c_ids in co.items():
                    if not isinstance(c_ids, list):
                        c_ids = [c_ids]
                    for c_id in c_ids:
                        for s_id in section_ids:
                            choice_to_section[(str(q_id), str(c_id))] = str(s_id)

        # --- Build field output ---
        fields = []
        for qid, question in questions.items():
            qid_str = str(qid)
            field_info: dict = {
                "field_id": qid_str,
                "label": question.get("label", ""),
                "type": question.get("type", ""),
                "required": question.get("validation", {}).get("rpiRequired", False),
                "description": question.get("description", ""),
                "always_visible": (
                    (
                        qid_str in root_question_ids
                        or qid_str not in all_sectioned_question_ids
                    )
                    if (root_question_ids or all_sectioned_question_ids)
                    else True
                ),
            }

            raw_choices = question.get("choices")
            if raw_choices:
                enriched_choices = []
                for c in raw_choices:
                    cid = str(c.get("id", ""))
                    choice_entry: dict = {
                        "id": cid,
                        "label": c.get("label"),
                    }
                    triggered_section = choice_to_section.get((qid_str, cid))
                    if triggered_section is not None:
                        choice_entry["shows_fields"] = section_to_questions.get(
                            triggered_section, []
                        )
                    enriched_choices.append(choice_entry)
                field_info["choices"] = enriched_choices

            fields.append(field_info)

        return (form_data.get("id", ""), fields, design)

    # --- Private helpers: label resolution ---
    def _normalize(s: str) -> str:
        """Normalize string for comparison: lowercase, collapse whitespace."""
        return " ".join(s.lower().split())

    def _resolve_field_label_to_id(fields: list, label: str) -> tuple:
        """Case-insensitive, whitespace-normalized match of label to field_id.
        Returns (field_id, field_dict) or (None, None)."""
        norm_label = _normalize(label)
        for f in fields:
            if _normalize(f.get("label", "")) == norm_label:
                return f["field_id"], f
        return None, None

    def _resolve_choice_label_to_id(field: dict, choice_label: str) -> Optional[str]:
        """Resolve choice label to choice ID. Exact match first, then substring.
        Returns choice_id string or None."""
        choices = field.get("choices", [])
        norm_label = _normalize(choice_label)
        # Exact match
        for c in choices:
            if _normalize(c.get("label", "")) == norm_label:
                return c["id"]
        # Substring fallback
        for c in choices:
            if norm_label in _normalize(c.get("label", "")):
                return c["id"]
        return None

    def _get_applicable_fields(fields: list, resolved_answers: dict) -> set:
        """Given fields and resolved answers (keyed by field_id with choice_ids resolved),
        return set of field_ids that should be submitted.
        Always-visible fields + fields triggered by selected choices."""
        applicable = set()
        for f in fields:
            if f.get("always_visible", True):
                applicable.add(f["field_id"])

        for f in fields:
            fid = f["field_id"]
            if fid not in resolved_answers:
                continue
            choices = f.get("choices", [])
            answer = resolved_answers[fid]
            selected_choice_ids = set()
            if isinstance(answer, dict) and "choices" in answer:
                selected_choice_ids = set(answer["choices"])

            for c in choices:
                if c["id"] in selected_choice_ids:
                    for triggered_fid in c.get("shows_fields", []):
                        applicable.add(str(triggered_fid))

        return applicable

    def _search_user_account_id(display_name_or_email: str) -> Optional[str]:
        """Search for a Jira user by display name or email. Returns accountId or None."""
        query = urllib.parse.quote(display_name_or_email)
        try:
            req = urllib.request.Request(
                f"{jira_base}/user/search?query={query}&maxResults=5",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                users = json.loads(response.read().decode())
            if users and isinstance(users, list):
                # Prefer exact email match, then exact display name match, then first result
                norm_query = display_name_or_email.lower().strip()
                for u in users:
                    if (u.get("emailAddress") or "").lower() == norm_query:
                        return u.get("accountId")
                for u in users:
                    if u.get("displayName", "").lower() == norm_query:
                        return u.get("accountId")
                return users[0].get("accountId")
        except Exception as e:
            print(f"🔴 User search failed for '{display_name_or_email}': {e}")
        return None

    def _text_to_adf(text: str) -> dict:
        """Convert plain text to Atlassian Document Format (ADF)."""
        paragraphs = []
        for line in text.split("\n"):
            if line.strip():
                paragraphs.append(
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": line}],
                    }
                )
        if not paragraphs:
            paragraphs = [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text or " "}],
                }
            ]
        return {"type": "doc", "version": 1, "content": paragraphs}

    # --- Private helper: build normalized raw_fields list (shared by prepare and submit) ---
    def _build_raw_fields(service_desk_id: str, request_type_id: str) -> tuple:
        """Fetch and normalize fields. Returns (request_mode, raw_fields, form_id)."""
        standard_fields = _fetch_request_type_fields(service_desk_id, request_type_id)
        try:
            form_id, form_fields, _design = _fetch_form_fields(
                service_desk_id, request_type_id
            )
        except RuntimeError as e:
            print(f"⚠️ Forms API unavailable, falling back to standard fields: {e}")
            form_id, form_fields = "", []

        if form_fields:
            return ("form", form_fields, form_id)

        raw_fields = []
        for f in standard_fields:
            entry: dict = {
                "field_id": f["field_id"],
                "label": f["name"],
                "type": f.get("type", "text"),
                "required": f.get("required", False),
                "description": f.get("description", ""),
                "always_visible": True,
            }
            if f.get("valid_values"):
                entry["choices"] = [
                    {"id": v["value"], "label": v["label"]} for v in f["valid_values"]
                ]
            raw_fields.append(entry)

        return ("standard", raw_fields, "")

    def _apply_label_disambiguation(raw_fields: list) -> None:
        """Mutates raw_fields in-place: disambiguates duplicate labels by appending field_id."""
        label_counts: dict = {}
        for f in raw_fields:
            lbl = _normalize(f.get("label", ""))
            label_counts[lbl] = label_counts.get(lbl, 0) + 1
        for f in raw_fields:
            lbl = _normalize(f.get("label", ""))
            if label_counts.get(lbl, 0) > 1:
                f["label"] = f"{f['label']} [{f['field_id']}]"

    @tool
    def atlassian_user_count_jira_issues(
        jql: str,
    ) -> dict:
        """Count the number of Jira issues matching a JQL query.

        This is a lightweight API call that returns just the count — no ticket data.
        Use this FIRST when analyzing large boards to know the total number of tickets
        before deciding how to proceed.

        IMPORTANT: For date filters, use relative DAYS (not months). Examples:
        - Last 6 months: created >= -180d
        - Last 12 months: created >= -365d
        - Explicit date: created >= "2025-08-25"
        Do NOT use -6M or -6m — these are invalid JQL and silently return 0 results.

        Args:
            jql: JQL query string (e.g., 'project = DO', 'project = DO AND created >= -180d')

        Returns:
            Dictionary with the approximate count of matching issues
        """
        result = _api_request(
            "POST",
            f"{jira_base}/search/approximate-count",
            access_token,
            {"jql": jql},
        )

        count = result.get("count", 0)
        return {
            "status": "success",
            "count": count,
            "jql": jql,
            "message": f"Found approximately {count} issues matching: {jql}",
        }

    # --- New smart tools ---

    @tool
    def atlassian_user_prepare_service_request(
        service_desk_id: str,
        request_type_id: str,
    ) -> dict:
        """Prepare a JSM service request by fetching all fields (standard and form-based).

        Call this AFTER list_service_desks and list_request_types to discover
        what information is needed for a ticket. Returns a human-readable
        questionnaire with field labels, types, options, and instructions.

        The response tells you how to present each field:
        - "list_choices": show the options to the user (10 or fewer)
        - "link_to_portal": too many options to list; give the user the portal URL

        Args:
            service_desk_id: The service desk ID (numeric string, e.g., '1')
            request_type_id: The request type ID (numeric string from list_request_types)

        Returns:
            Dictionary with field questionnaire, request_mode, and instructions
        """
        service_desk_id = _validate_param(service_desk_id, r"^\d+$", "service_desk_id")
        request_type_id = _validate_param(request_type_id, r"^\d+$", "request_type_id")

        request_mode, raw_fields, _form_id = _build_raw_fields(
            service_desk_id, request_type_id
        )
        _apply_label_disambiguation(raw_fields)

        output_fields = []
        for f in raw_fields:
            out: dict = {
                "label": f.get("label", ""),
                "type": f.get("type", "text"),
                "required": f.get("required", False),
                "description": f.get("description", ""),
                "always_visible": f.get("always_visible", True),
            }

            # Add input hint based on field type
            ftype = f.get("type", "")
            choices = f.get("choices", [])
            if ftype in ("us", "um"):
                out["input_hint"] = "user_name_or_email"
            elif ftype in ("rt",):
                out["input_hint"] = "rich_text"
            elif ftype in ("date", "dd"):
                out["input_hint"] = "date"
            elif choices:
                out["input_hint"] = "choice"
            else:
                out["input_hint"] = "text"
            if choices:
                if len(choices) <= 10:
                    out["presentation"] = "list_choices"
                    out["options"] = []
                    for c in choices:
                        opt: dict = {"label": c.get("label", "")}
                        if c.get("shows_fields"):
                            triggered_labels = []
                            for triggered_id in c["shows_fields"]:
                                for ff in raw_fields:
                                    if ff["field_id"] == str(triggered_id):
                                        triggered_labels.append(
                                            ff.get("label", str(triggered_id))
                                        )
                                        break
                                else:
                                    triggered_labels.append(str(triggered_id))
                            opt["triggers_fields"] = triggered_labels
                        out["options"].append(opt)
                else:
                    out["presentation"] = "link_to_portal"
                    out["choice_count"] = len(choices)

            output_fields.append(out)

        portal_url = (
            f"https://{site_name}.atlassian.net/servicedesk/customer/portal"
            f"/{service_desk_id}/create/{request_type_id}"
        )

        instructions = (
            "Present each field to the user. For 'list_choices' fields, show the options. "
            "For 'link_to_portal' fields, share the portal_url. "
            "Collect answers and pass them to submit_service_request keyed by field label. "
            "For choice fields, pass the option label text (not an ID). "
            "Only submit fields that are always_visible or triggered by the user's selections."
        )

        return {
            "status": "success",
            "request_mode": request_mode,
            "fields": output_fields,
            "portal_url": portal_url,
            "instructions": instructions,
            "message": f"Found {len(output_fields)} field(s) ({request_mode} mode)",
        }

    @tool
    def atlassian_user_submit_service_request(
        service_desk_id: str,
        request_type_id: str,
        answers: dict,
    ) -> dict:
        """Submit a JSM service request with answers keyed by field label.

        Call this AFTER atlassian_user_prepare_service_request. Pass answers as a dictionary
        where keys are field labels (from atlassian_user_prepare_service_request) and values
        are human-readable answers:
        - Choice fields: pass the option label string (e.g., "UDP Production")
        - Text fields: pass the text string
        - Date fields: pass a date string (e.g., "2024-01-15")

        This tool handles all ID resolution, validation, and payload construction.

        Args:
            service_desk_id: The service desk ID (numeric string, e.g., '1')
            request_type_id: The request type ID (numeric string)
            answers: Dictionary keyed by field label with human-readable values.
                     Example: {"Snowflake Environment": "UDP Production",
                              "Business Justification": "Need access for reporting"}

        Returns:
            Dictionary with created request details or validation errors
        """
        service_desk_id = _validate_param(service_desk_id, r"^\d+$", "service_desk_id")
        request_type_id = _validate_param(request_type_id, r"^\d+$", "request_type_id")

        request_mode, raw_fields, form_id = _build_raw_fields(
            service_desk_id, request_type_id
        )
        _apply_label_disambiguation(raw_fields)

        # Step 1: Resolve answer labels to field IDs
        errors = []
        resolved: dict = {}
        valid_labels = [f.get("label", "") for f in raw_fields]

        for label, value in answers.items():
            field_id, field = _resolve_field_label_to_id(raw_fields, label)
            if field_id is None:
                errors.append(
                    {
                        "field": label,
                        "error": "Unknown field label",
                        "valid_labels": valid_labels,
                    }
                )
                continue

            if field.get("choices"):
                if isinstance(value, list):
                    choice_ids = []
                    field_errors = False
                    for v in value:
                        cid = _resolve_choice_label_to_id(field, str(v))
                        if cid is None:
                            valid_options = [
                                c.get("label", "") for c in field["choices"]
                            ]
                            errors.append(
                                {
                                    "field": label,
                                    "error": f"Unknown choice: {v}",
                                    "valid_options": valid_options,
                                }
                            )
                            field_errors = True
                        else:
                            choice_ids.append(cid)
                    if not field_errors:
                        resolved[field_id] = {"choices": choice_ids}
                else:
                    cid = _resolve_choice_label_to_id(field, str(value))
                    if cid is None:
                        valid_options = [c.get("label", "") for c in field["choices"]]
                        errors.append(
                            {
                                "field": label,
                                "error": f"Unknown choice: {value}",
                                "valid_options": valid_options,
                            }
                        )
                    else:
                        resolved[field_id] = {"choices": [cid]}
            else:
                # Non-choice field — format based on field type
                field_type = field.get("type", "")
                if field_type in ("date", "dd"):
                    resolved[field_id] = {"date": str(value)}
                elif field_type in ("us",):
                    # User select — resolve name/email to accountId
                    account_id = _search_user_account_id(str(value))
                    if account_id:
                        resolved[field_id] = {"users": [account_id]}
                    else:
                        errors.append(
                            {
                                "field": label,
                                "error": f"Could not find Atlassian user matching: {value}",
                            }
                        )
                elif field_type in ("um",):
                    # User multi — resolve each name/email
                    # Value might be a list or comma-separated string
                    names = (
                        value
                        if isinstance(value, list)
                        else [n.strip() for n in str(value).split(",") if n.strip()]
                    )
                    account_ids = []
                    for name in names:
                        aid = _search_user_account_id(name)
                        if aid:
                            account_ids.append(aid)
                        else:
                            errors.append(
                                {
                                    "field": label,
                                    "error": f"Could not find Atlassian user matching: {name}",
                                }
                            )
                    if account_ids and not any(e.get("field") == label for e in errors):
                        resolved[field_id] = {"users": account_ids}
                elif field_type in ("rt",):
                    # Rich text — convert to ADF format
                    resolved[field_id] = {"adf": _text_to_adf(str(value))}
                else:
                    # ts (text short), tl (text long), pg (paragraph), etc.
                    resolved[field_id] = {"text": str(value)}

        if errors:
            return {
                "status": "validation_error",
                "errors": errors,
                "message": "Some answers could not be resolved. Please fix and retry.",
            }

        # Step 2: Compute applicable fields
        applicable = _get_applicable_fields(raw_fields, resolved)

        # Step 3: Filter resolved to only applicable fields
        filtered = {fid: val for fid, val in resolved.items() if fid in applicable}

        # Step 4: Validate required fields
        missing = []
        for f in raw_fields:
            fid = f["field_id"]
            if fid in applicable and f.get("required", False) and fid not in filtered:
                missing.append(f.get("label", fid))

        if missing:
            return {
                "status": "validation_error",
                "errors": [{"error": "Missing required fields", "fields": missing}],
                "message": f"Required fields missing: {', '.join(missing)}",
            }

        # Step 5: Build and submit payload
        if request_mode == "form":
            body: dict = {
                "serviceDeskId": service_desk_id,
                "requestTypeId": request_type_id,
                "requestFieldValues": {},
                "form": {"answers": filtered},
            }
        else:
            request_field_values: dict = {}
            for fid, val in filtered.items():
                if "text" in val:
                    request_field_values[fid] = val["text"]
                elif "choices" in val:
                    if len(val["choices"]) == 1:
                        request_field_values[fid] = {"value": val["choices"][0]}
                    else:
                        request_field_values[fid] = [
                            {"value": c} for c in val["choices"]
                        ]
                elif "date" in val:
                    request_field_values[fid] = val["date"]
                elif "users" in val:
                    if len(val["users"]) == 1:
                        request_field_values[fid] = {"accountId": val["users"][0]}
                    else:
                        request_field_values[fid] = [
                            {"accountId": uid} for uid in val["users"]
                        ]
                elif "adf" in val:
                    request_field_values[fid] = val["adf"]

            body = {
                "serviceDeskId": service_desk_id,
                "requestTypeId": request_type_id,
                "requestFieldValues": request_field_values,
            }

        # Log the payload for debugging
        print(
            f"📋 JSM submit payload: mode={request_mode}, answers={len(filtered)} fields"
        )
        for fid, val in filtered.items():
            flabel = next(
                (f.get("label", fid) for f in raw_fields if f["field_id"] == fid), fid
            )
            val_type = next(iter(val.keys()), "?")
            print(f"  [{fid}] {flabel}: {val_type}")

        try:
            result = _api_request("POST", f"{jsm_base}/request", access_token, body)
        except RuntimeError as e:
            return {
                "status": "api_error",
                "message": str(e),
            }

        issue_key = result.get("issueKey", "")
        issue_id = result.get("issueId", "")
        current_status = result.get("currentStatus", {}).get("status", "")

        # Add "Co-authored by Vera" comment for AI transparency
        if issue_key:
            try:
                _api_request(
                    "POST",
                    f"{jira_base}/issue/{issue_key}/comment",
                    access_token,
                    {
                        "body": {
                            "type": "doc",
                            "version": 1,
                            "content": [VERA_ADF_NOTE],
                        }
                    },
                )
            except Exception as e:
                print(f"🟡 Warning: Failed to add Vera comment to {issue_key}: {e}")

        portal_url = (
            f"https://{site_name}.atlassian.net/servicedesk/customer/portal"
            f"/{service_desk_id}/create/{request_type_id}"
        )
        return {
            "status": "success",
            "issue_key": issue_key,
            "issue_id": issue_id,
            "current_status": current_status,
            "issue_url": f"https://{site_name}.atlassian.net/browse/{issue_key}",
            "portal_url": portal_url,
            "message": f"Created service request {issue_key}",
        }

    return [
        atlassian_user_count_jira_issues,
        atlassian_user_create_jira_issue,
        atlassian_user_add_jira_comment,
        atlassian_user_edit_jira_issue,
        atlassian_user_transition_jira_issue,
        atlassian_user_create_confluence_page,
        atlassian_user_list_service_desks,
        atlassian_user_list_request_types,
        atlassian_user_prepare_service_request,
        atlassian_user_submit_service_request,
    ]

"""Atlassian authorization request tool for Strands Agent"""

import requests
from strands import tool
from typing import Optional


def build_atlassian_auth_tool(
    slack_user_id: str,
    secrets_json: dict,
    user_display_name: Optional[str] = None,
    slack_token: Optional[str] = None,
    channel_id: Optional[str] = None,
    thread_ts: Optional[str] = None,
):
    """
    Build the Atlassian authorization request tool.

    This tool generates and returns a portal link when:
    - User requests a write operation but doesn't have user-level Atlassian auth
    - User says "connect my accounts" or "manage integrations"

    The portal link is sent as an ephemeral message (only visible to the
    requesting user) to prevent others in a shared thread from accidentally
    clicking and linking their Atlassian account to the wrong Slack user.
    """

    @tool
    def request_atlassian_authorization() -> dict:
        """
        Generate an authorization portal link for the user to connect their Atlassian account.

        Call this tool ONLY when:
        - The atlassian_user_* tools are NOT in your available tool list
        - The user explicitly says "connect my accounts" or "manage integrations"

        Do NOT call this tool if atlassian_user_* tools are available — use those instead.

        Returns:
            Dictionary with portal URL and instructions for the user
        """
        try:
            from worker_oauth import generate_portal_url

            signing_secret = secrets_json.get("PORTAL_SIGNING_SECRET", "")
            if not signing_secret:
                return {
                    "status": "error",
                    "content": [
                        {
                            "text": "Portal signing secret not configured. Please contact an administrator."
                        }
                    ],
                }

            portal_url = generate_portal_url(
                slack_user_id, signing_secret, user_display_name=user_display_name
            )
            if not portal_url:
                return {
                    "status": "error",
                    "content": [
                        {
                            "text": "Auth portal URL not configured. Please contact an administrator."
                        }
                    ],
                }

            # Send the portal link as an ephemeral message (only visible to
            # the requesting user) so others in the thread can't click it
            ephemeral_text = (
                f"🔐 *Private Authorization Link*\n\n"
                f"<{portal_url}|Connect Your Atlassian Account>\n\n"
                f"This link is unique to you and expires in 10 minutes. "
                f"After authorizing, send me another message and I'll complete your request."
            )

            link_fallback = {
                "status": "success",
                "content": [
                    {
                        "text": f"<{portal_url}|Connect Your Atlassian Account>\n\n"
                        f"This link expires in 10 minutes. After authorizing, send me another message."
                    }
                ],
            }

            if slack_token and channel_id and slack_user_id:
                try:
                    resp = requests.post(
                        "https://slack.com/api/chat.postEphemeral",
                        headers={"Authorization": f"Bearer {slack_token}"},
                        json={
                            "channel": channel_id,
                            "user": slack_user_id,
                            "text": ephemeral_text,
                            "thread_ts": thread_ts,
                        },
                    )
                    resp_data = resp.json()
                    if resp_data.get("ok"):
                        print(f"🟢 Sent ephemeral auth link to {slack_user_id}")
                    else:
                        print(f"🔴 Ephemeral message failed: {resp_data.get('error')}")
                        return link_fallback
                except Exception as e:
                    print(f"🔴 Failed to send ephemeral message: {e}")
                    return link_fallback
            else:
                # No Slack context available — return link directly
                return link_fallback

            # Ephemeral message sent successfully — tell the agent
            return {
                "status": "success",
                "content": [
                    {
                        "text": "I've sent you a private authorization link (only visible to you). "
                        "Click it to connect your Atlassian account. The link expires in 10 minutes. "
                        "After authorizing, send me another message and I'll complete your request."
                    }
                ],
            }
        except Exception as e:
            return {
                "status": "error",
                "content": [
                    {"text": f"Failed to generate authorization link: {str(e)}"}
                ],
            }

    return request_atlassian_authorization

"""HTML templates for the Vera Auth Portal.

This module provides rendering functions for the OAuth portal interface.
Uses inline CSS for zero external dependencies.
"""

import html
from datetime import datetime, timezone
from typing import List, Dict, Optional


def render_dashboard(
    user_id: str,
    providers: List[Dict],
    just_connected: Optional[str] = None,
    display_name: Optional[str] = None,
    token: Optional[str] = None,
) -> str:
    """Render the main dashboard HTML.

    Args:
        user_id: Slack user ID
        providers: List of dicts with keys:
            - name: Provider identifier (e.g., 'atlassian')
            - display_name: Human-readable name (e.g., 'Atlassian')
            - connected: Boolean connection status
            - authorize_url: URL to initiate OAuth flow
            - revoke_url: URL to revoke authorization
        just_connected: Provider name that was just connected (for success banner)

    Returns:
        HTML string
    """
    provider_cards = []

    for provider in providers:
        status_color = "#10B981" if provider["connected"] else "#6B7280"
        status_text = "Connected" if provider["connected"] else "Not connected"

        if provider["connected"]:
            token_field = (
                f'<input type="hidden" name="token" value="{html.escape(token or "")}">'
                if token
                else ""
            )
            action_button = f"""
                <form method="POST" action="{html.escape(provider['revoke_url'])}" style="margin: 0;">
                    {token_field}
                    <button type="submit" class="btn btn-revoke">Revoke Access</button>
                </form>
            """
        else:
            action_button = f"""
                <a href="{html.escape(provider['authorize_url'])}" class="btn btn-authorize">Authorize</a>
            """

        connected_info = ""
        if provider["connected"] and provider.get("connected_at"):
            connected_dt = datetime.fromtimestamp(
                provider["connected_at"], tz=timezone.utc
            )
            connected_str = connected_dt.strftime("%b %d, %Y at %I:%M %p UTC")

            token_validity = ""
            token_expires_at = provider.get("token_expires_at")
            if token_expires_at:
                now = datetime.now(tz=timezone.utc).timestamp()
                remaining_secs = int(token_expires_at - now)
                if remaining_secs > 0:
                    minutes = remaining_secs // 60
                    token_validity = f"Token valid for {minutes} minutes"
                else:
                    token_validity = "Token expired"
            else:
                token_validity = "Token valid for ~1 hour"

            connected_info = f"""
                <p class="connected-info">Connected on {connected_str}</p>
                <p class="connected-info">{token_validity}</p>
            """

        card_html = f"""
            <div class="provider-card">
                <div class="provider-header">
                    <h3>{html.escape(provider['display_name'])}</h3>
                    <div class="provider-header-actions">
                        <span class="status-badge" style="background-color: {status_color};">
                            {status_text}
                        </span>
                        {action_button}
                    </div>
                </div>
                {connected_info}
            </div>
        """
        provider_cards.append(card_html)

    provider_cards_html = "\n".join(provider_cards)

    # Build success banner if user just connected a provider
    success_banner_html = ""
    if just_connected:
        provider_display = html.escape(just_connected.title())
        for p in providers:
            if p["name"] == just_connected:
                provider_display = html.escape(p["display_name"])
                break
        success_banner_html = f"""
        <div class="success-banner">
            <p>✅ <strong>{provider_display}</strong> has been successfully connected! You can now return to Slack and use write commands.</p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vera Auth Portal</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}

        .container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 600px;
            width: 100%;
            padding: 40px;
        }}

        .header {{
            text-align: center;
            margin-bottom: 40px;
        }}

        .logo {{
            width: 60px;
            height: 60px;
            background-color: #4ECDC4;
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            margin-bottom: 16px;
        }}

        h1 {{
            color: #1F2937;
            font-size: 28px;
            margin-bottom: 8px;
        }}

        .subtitle {{
            color: #6B7280;
            font-size: 14px;
        }}

        .provider-card {{
            background: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 16px;
            transition: all 0.2s ease;
        }}

        .provider-card:hover {{
            border-color: #4ECDC4;
            box-shadow: 0 4px 12px rgba(78, 205, 196, 0.1);
        }}

        .provider-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}

        .provider-header h3 {{
            color: #1F2937;
            font-size: 18px;
            font-weight: 600;
        }}

        .provider-header-actions {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            color: white;
        }}

        .btn {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            text-decoration: none;
            border: none;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .btn-authorize {{
            background-color: #4ECDC4;
            color: white;
        }}

        .btn-authorize:hover {{
            background-color: #3DB9B1;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(78, 205, 196, 0.3);
        }}

        .btn-revoke {{
            background-color: #EF4444;
            color: white;
        }}

        .btn-revoke:hover {{
            background-color: #DC2626;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
        }}

        .note {{
            background: #FEF3C7;
            border-left: 4px solid #F59E0B;
            padding: 16px;
            border-radius: 8px;
            margin-top: 24px;
        }}

        .note p {{
            color: #92400E;
            font-size: 14px;
            line-height: 1.5;
        }}

        .success-banner {{
            background: #D1FAE5;
            border-left: 4px solid #10B981;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 24px;
            animation: fadeIn 0.5s ease;
        }}

        .success-banner p {{
            color: #065F46;
            font-size: 14px;
            line-height: 1.5;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(-10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .connected-info {{
            color: #6B7280;
            font-size: 12px;
            margin-top: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🤖</div>
            <h1>Vera Auth Portal</h1>
            <p class="subtitle">User: {html.escape(display_name or user_id)}</p>
        </div>

        {success_banner_html}

        <div class="providers">
            {provider_cards_html}
        </div>

        <div class="note">
            <p>
                <strong>Note:</strong> After authorizing, return to Slack and retry your command.
                Your connection persists across sessions — you only need to authorize once.
            </p>
        </div>
    </div>
</body>
</html>"""


def render_success(provider_name: str) -> str:
    """Render success page after OAuth callback.

    Args:
        provider_name: Display name of the provider (e.g., 'Atlassian')

    Returns:
        HTML string with success message and auto-close script
    """
    escaped_provider_name = html.escape(str(provider_name))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authorization Successful</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #10B981 0%, #059669 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}

        .container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 500px;
            width: 100%;
            padding: 60px 40px;
            text-align: center;
        }}

        .success-icon {{
            width: 80px;
            height: 80px;
            background-color: #10B981;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            margin-bottom: 24px;
            animation: scaleIn 0.5s ease;
        }}

        @keyframes scaleIn {{
            from {{
                transform: scale(0);
            }}
            to {{
                transform: scale(1);
            }}
        }}

        h1 {{
            color: #1F2937;
            font-size: 32px;
            margin-bottom: 16px;
        }}

        p {{
            color: #6B7280;
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 8px;
        }}

        .countdown {{
            color: #4ECDC4;
            font-weight: 600;
            font-size: 18px;
            margin-top: 24px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon">✓</div>
        <h1>Success!</h1>
        <p>{escaped_provider_name} has been successfully authorized.</p>
        <p>You can now use {escaped_provider_name} commands in Slack.</p>
        <p class="countdown">This window will close in <span id="countdown">5</span> seconds...</p>
    </div>

    <script>
        let seconds = 5;
        const countdownElement = document.getElementById('countdown');

        const timer = setInterval(() => {{
            seconds--;
            countdownElement.textContent = seconds;

            if (seconds <= 0) {{
                clearInterval(timer);
                window.close();
            }}
        }}, 1000);
    </script>
</body>
</html>"""


def render_error(error_message: str) -> str:
    """Render error page.

    Args:
        error_message: Error message to display

    Returns:
        HTML string with error message and back button
    """
    escaped_error_message = html.escape(str(error_message))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authorization Error</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}

        .container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 500px;
            width: 100%;
            padding: 60px 40px;
            text-align: center;
        }}

        .error-icon {{
            width: 80px;
            height: 80px;
            background-color: #EF4444;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            margin-bottom: 24px;
        }}

        h1 {{
            color: #1F2937;
            font-size: 32px;
            margin-bottom: 16px;
        }}

        .error-message {{
            background: #FEE2E2;
            border-left: 4px solid #EF4444;
            padding: 16px;
            border-radius: 8px;
            margin: 24px 0;
            text-align: left;
        }}

        .error-message p {{
            color: #991B1B;
            font-size: 14px;
            font-family: monospace;
            word-break: break-word;
        }}

        .btn {{
            display: inline-block;
            padding: 12px 32px;
            background-color: #4ECDC4;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            margin-top: 16px;
            transition: all 0.2s ease;
        }}

        .btn:hover {{
            background-color: #3DB9B1;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(78, 205, 196, 0.3);
        }}

        p {{
            color: #6B7280;
            font-size: 16px;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="error-icon">✗</div>
        <h1>Authorization Failed</h1>
        <p>We encountered an error while processing your authorization.</p>

        <div class="error-message">
            <p>{escaped_error_message}</p>
        </div>

        <a href="javascript:history.back()" class="btn">Go Back</a>
    </div>
</body>
</html>"""

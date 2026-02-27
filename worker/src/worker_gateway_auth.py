"""
Gateway Authentication Manager

Handles Cognito JWT token caching for AgentCore gateway access.
Tokens are cached in memory and automatically refreshed before expiry.

Gateway configuration is injected via environment variables from Terraform:
- GATEWAY_URL: Gateway MCP endpoint
- GATEWAY_TOKEN_URL: Cognito OAuth token endpoint
- GATEWAY_SCOPE: OAuth scope for gateway access
"""

import time
import base64
import os
import requests

# Token cache with expiry tracking
_token_cache = {"token": None, "expires_at": 0}

# Buffer time before expiry (5 minutes = 300 seconds)
TOKEN_REFRESH_BUFFER = 300


def _fetch_new_token(client_id, client_secret):
    """
    Fetch new JWT token from Cognito.

    Args:
        client_id: Cognito app client ID
        client_secret: Cognito app client secret

    Returns:
        dict: Token response with 'access_token' and 'expires_in'

    Raises:
        requests.HTTPError: If token fetch fails
        ValueError: If environment variables are missing
    """
    print("🟡 Fetching new JWT token from Cognito...")

    # Get token URL and scope from environment
    token_url = os.environ.get("GATEWAY_TOKEN_URL")
    gateway_scope = os.environ.get("GATEWAY_SCOPE")

    if not token_url:
        raise ValueError("Missing GATEWAY_TOKEN_URL environment variable")
    if not gateway_scope:
        raise ValueError("Missing GATEWAY_SCOPE environment variable")

    # Encode credentials for Basic Auth
    auth_string = f"{client_id}:{client_secret}"
    auth_header = base64.b64encode(auth_string.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}",
    }

    data = {"grant_type": "client_credentials", "scope": gateway_scope}

    try:
        response = requests.post(token_url, headers=headers, data=data, timeout=10)
        response.raise_for_status()

        token_data = response.json()
        print(
            f"🟡 JWT token obtained (expires in {token_data.get('expires_in', 'unknown')} seconds)"
        )

        return token_data

    except requests.exceptions.RequestException as e:
        print(f"🔴 Failed to fetch JWT token: {str(e)}")
        raise


def get_gateway_token(secrets_json):
    """
    Get cached JWT token or fetch new one if expired.

    This function implements smart caching:
    - Returns cached token if still valid (with 5-minute buffer)
    - Automatically fetches new token if expired or near expiry
    - Thread-safe for single-process container environment

    Args:
        secrets_json: Dictionary containing gateway credentials

    Returns:
        str: Valid JWT access token

    Raises:
        ValueError: If credentials are missing
        requests.HTTPError: If token fetch fails
    """
    current_time = time.time()

    # Check if token is expired or near expiry
    if current_time >= (_token_cache["expires_at"] - TOKEN_REFRESH_BUFFER):
        print("🟡 Token expired or near expiry, fetching new token...")

        # Get credentials from environment and secrets
        client_id = os.environ.get("GATEWAY_CLIENT_ID")
        client_secret = secrets_json.get("GATEWAY_CLIENT_SECRET")

        if not client_id:
            raise ValueError("Missing GATEWAY_CLIENT_ID environment variable")
        if not client_secret:
            raise ValueError("Missing GATEWAY_CLIENT_SECRET in secrets")

        # Fetch new token
        token_data = _fetch_new_token(client_id, client_secret)

        # Update cache
        _token_cache["token"] = token_data["access_token"]
        _token_cache["expires_at"] = current_time + int(
            token_data.get("expires_in", 3600)
        )

        print(f"🟡 Token cached until {time.ctime(_token_cache['expires_at'])}")
    else:
        time_until_expiry = int(_token_cache["expires_at"] - current_time)
        print(f"🟡 Using cached token (expires in {time_until_expiry} seconds)")

    return _token_cache["token"]


def clear_token_cache():
    """
    Clear the token cache.
    Useful for testing or forcing token refresh.
    """
    print("🟡 Clearing token cache")
    _token_cache["token"] = None
    _token_cache["expires_at"] = 0

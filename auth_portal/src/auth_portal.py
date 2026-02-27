"""Lambda handler for Vera Auth Portal.

Handles OAuth flows for external providers (Atlassian, etc.) with JWT-based
authentication and DynamoDB token storage.

Routes:
    GET /               - Portal dashboard (requires JWT token query param)
    GET /callback/*     - OAuth callback handlers
    POST /revoke/*      - Revocation endpoints
"""

import json
import base64
import binascii
import hmac
import hashlib
import os
import time
import uuid
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
secrets_client = boto3.client("secretsmanager")
dynamodb = boto3.resource("dynamodb")
kms_client = boto3.client("kms")

# Environment variables
SECRET_NAME = os.environ["SECRET_NAME"]
OAUTH_TOKENS_TABLE = os.environ["OAUTH_TABLE_NAME"]
OAUTH_KMS_KEY_ID = os.environ["OAUTH_KMS_KEY_ID"]

# Cache for secrets
_secrets_cache: Optional[Dict[str, str]] = None


def get_secret() -> Dict[str, str]:
    """Fetch secrets from AWS Secrets Manager with caching.

    Returns:
        Dictionary of secret key-value pairs
    """
    global _secrets_cache

    if _secrets_cache is not None:
        return _secrets_cache

    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
        secret_string = response["SecretString"]
        _secrets_cache = json.loads(secret_string)
        return _secrets_cache
    except ClientError as e:
        raise RuntimeError(f"Failed to fetch secrets: {e}")


def create_jwt(payload: Dict[str, Any]) -> str:
    """Create a JWT token with HMAC-SHA256 signature.

    Args:
        payload: Dictionary containing JWT claims (must include 'exp')

    Returns:
        JWT token string (format: header.payload.signature)
    """
    secrets = get_secret()
    signing_secret = secrets["PORTAL_SIGNING_SECRET"]

    # Create header
    header = {"alg": "HS256", "typ": "JWT"}
    header_json = json.dumps(header, separators=(",", ":"))
    header_b64 = base64.urlsafe_b64encode(header_json.encode()).decode().rstrip("=")

    # Create payload
    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")

    # Create signature
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        signing_secret.encode(), message.encode(), hashlib.sha256
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def validate_jwt(token: str) -> Dict[str, Any]:
    """Validate JWT token and return payload.

    Args:
        token: JWT token string (format: header.payload.signature)

    Returns:
        Decoded JWT payload

    Raises:
        ValueError: If token is invalid or expired
    """
    secrets = get_secret()
    signing_secret = secrets["PORTAL_SIGNING_SECRET"]

    try:
        # Split JWT into parts
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        message = f"{header_b64}.{payload_b64}"
        expected_signature = (
            base64.urlsafe_b64encode(
                hmac.new(
                    signing_secret.encode(), message.encode(), hashlib.sha256
                ).digest()
            )
            .decode()
            .rstrip("=")
        )

        # Normalize signature (remove padding)
        provided_signature = signature_b64.rstrip("=")

        if not hmac.compare_digest(expected_signature, provided_signature):
            raise ValueError("Invalid JWT signature")

        # Decode payload
        # Add padding if needed
        payload_b64_padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64_padded)
        payload = json.loads(payload_json)

        # Check expiration
        if "exp" not in payload:
            raise ValueError("JWT missing expiration")

        if time.time() > payload["exp"]:
            raise ValueError("JWT token expired")

        return payload

    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"JWT validation failed: {e}")


def encrypt_value(plaintext: str, kms_key_id: str) -> str:
    """Encrypt a value using KMS.

    Args:
        plaintext: Value to encrypt
        kms_key_id: KMS key ID or ARN

    Returns:
        Base64-encoded ciphertext
    """
    try:
        response = kms_client.encrypt(KeyId=kms_key_id, Plaintext=plaintext.encode())
        ciphertext = response["CiphertextBlob"]
        return base64.b64encode(ciphertext).decode()
    except ClientError as e:
        raise RuntimeError(f"KMS encryption failed: {e}")


def decrypt_value(ciphertext_b64: str, kms_key_id: str) -> str:
    """Decrypt a KMS-encrypted value.

    Args:
        ciphertext_b64: Base64-encoded ciphertext
        kms_key_id: KMS key ID or ARN (not used for decrypt, kept for API consistency)

    Returns:
        Decrypted plaintext
    """
    try:
        ciphertext = base64.b64decode(ciphertext_b64)
        response = kms_client.decrypt(CiphertextBlob=ciphertext)
        return response["Plaintext"].decode()
    except ClientError as e:
        raise RuntimeError(f"KMS decryption failed: {e}")


def get_function_url(event: Dict[str, Any]) -> str:
    """Extract the base function URL from the event.

    Args:
        event: Lambda function URL event

    Returns:
        Base URL (e.g., https://xyz.lambda-url.us-east-1.on.aws)
    """
    request_context = event.get("requestContext", {})
    domain_name = request_context.get("domainName", "")

    if not domain_name:
        raise ValueError("Unable to determine function URL from event")

    return f"https://{domain_name}"


def _verify_atlassian_token(
    item: Dict[str, Any], secrets: Dict[str, str]
) -> Tuple[bool, Optional[int]]:
    """Verify an Atlassian token is still valid by attempting a refresh.

    Returns (is_valid, token_expires_at) tuple. Also stores the rotated
    refresh token back to DynamoDB.
    """
    try:
        encrypted_refresh = item.get("encrypted_refresh_token", "")
        if not encrypted_refresh:
            return False, None

        kms_key_id = os.environ.get("OAUTH_KMS_KEY_ID", "")
        refresh_token = decrypt_value(encrypted_refresh, kms_key_id)

        client_id = secrets.get("ATLASSIAN_OAUTH_CLIENT_ID", "")
        client_secret = secrets.get("ATLASSIAN_OAUTH_CLIENT_SECRET", "")

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

        with urllib.request.urlopen(req, timeout=10) as response:
            token_response = json.loads(response.read().decode())

        # Store rotated refresh token and updated expiry
        new_refresh = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 3600)
        now = int(time.time())
        token_expires_at = now + expires_in

        if new_refresh:
            pk = item.get("pk", "")
            table = dynamodb.Table(OAUTH_TOKENS_TABLE)
            encrypted_new = encrypt_value(new_refresh, kms_key_id)
            table.update_item(
                Key={"pk": pk},
                UpdateExpression="SET encrypted_refresh_token = :t, updated_at = :u, token_expires_at = :e",
                ExpressionAttributeValues={
                    ":t": encrypted_new,
                    ":u": now,
                    ":e": token_expires_at,
                },
            )

        return True, token_expires_at
    except Exception as e:
        print(f"Atlassian token verification failed: {e}")
        return False, None


def handle_dashboard(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GET / - Portal dashboard.

    Args:
        event: Lambda function URL event

    Returns:
        Lambda response dict
    """
    from portal_html import render_dashboard, render_error

    # Extract and validate JWT token
    query_params = event.get("queryStringParameters") or {}
    token = query_params.get("token")
    just_connected = query_params.get("just_connected")

    if not token:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html"},
            "body": render_error("Missing authentication token"),
        }

    try:
        payload = validate_jwt(token)
        slack_user_id = payload.get("slack_user_id")

        if not slack_user_id:
            raise ValueError("JWT missing slack_user_id")

    except ValueError as e:
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(f"Authentication failed: {e}"),
        }

    display_name = payload.get("display_name")

    # Build Atlassian authorize URL
    secrets = get_secret()

    # Check existing connections in DynamoDB
    table = dynamodb.Table(OAUTH_TOKENS_TABLE)
    atlassian_pk = f"user#{slack_user_id}#atlassian"

    atlassian_connected = False
    atlassian_connected_at: Optional[int] = None
    atlassian_token_expires_at: Optional[int] = None
    if just_connected == "atlassian":
        # Token was just stored by callback — skip re-verification
        atlassian_connected = True
        atlassian_connected_at = int(time.time())
        atlassian_token_expires_at = int(time.time()) + 3600  # ~1 hour from Atlassian
    else:
        try:
            response = table.get_item(Key={"pk": atlassian_pk})
            item = response.get("Item")
            if item and item.get("encrypted_refresh_token"):
                atlassian_connected, atlassian_token_expires_at = (
                    _verify_atlassian_token(item, secrets)
                )
                if atlassian_connected:
                    updated_at = item.get("updated_at")
                    if updated_at is not None:
                        atlassian_connected_at = int(updated_at)
        except ClientError as e:
            print(f"Error checking Atlassian connection: {e}")
    client_id = secrets.get("ATLASSIAN_OAUTH_CLIENT_ID", "")

    function_url = get_function_url(event)
    callback_url = f"{function_url}/callback/atlassian"

    # Generate nonce for CSRF protection
    nonce = str(uuid.uuid4())
    state_data = {
        "slack_user_id": slack_user_id,
        "nonce": nonce,
        "display_name": display_name or "",
    }
    state_b64 = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()

    # Store nonce in DynamoDB with 10-minute TTL
    nonce_pk = f"nonce#{nonce}"
    ttl = int(time.time()) + 600  # 10 minutes

    try:
        table.put_item(
            Item={
                "pk": nonce_pk,
                "slack_user_id": slack_user_id,
                "created_at": int(time.time()),
                "ttl": ttl,
            }
        )
    except ClientError as e:
        print(f"Error storing nonce: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(
                "Failed to initialize authorization. Please try again."
            ),
        }

    scopes = (
        "read:jira-work write:jira-work read:jira-user "
        "read:confluence-content.all write:confluence-content "
        "write:page:confluence read:space:confluence "
        "read:servicedesk-request write:servicedesk-request "
        "offline_access"
    )

    authorize_params = {
        "audience": "api.atlassian.com",
        "client_id": client_id,
        "scope": scopes,
        "redirect_uri": callback_url,
        "state": state_b64,
        "response_type": "code",
        "prompt": "consent",
    }

    authorize_url = "https://auth.atlassian.com/authorize?" + urllib.parse.urlencode(
        authorize_params
    )
    revoke_url = f"{function_url}/revoke/atlassian"

    # Build provider list
    providers = [
        {
            "name": "atlassian",
            "display_name": "Atlassian (Jira & Confluence)",
            "connected": atlassian_connected,
            "authorize_url": authorize_url,
            "revoke_url": revoke_url,
            "connected_at": atlassian_connected_at,
            "token_expires_at": atlassian_token_expires_at,
        }
    ]

    html = render_dashboard(
        slack_user_id,
        providers,
        just_connected=just_connected,
        display_name=display_name,
        token=token,
    )

    return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html}


def handle_atlassian_callback(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GET /callback/atlassian - OAuth callback.

    Args:
        event: Lambda function URL event

    Returns:
        Lambda response dict
    """
    from portal_html import render_success, render_error

    query_params = event.get("queryStringParameters") or {}
    code = query_params.get("code")
    state_b64 = query_params.get("state")

    if not code or not state_b64:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html"},
            "body": render_error("Missing OAuth parameters"),
        }

    # Decode and validate state
    try:
        state_json = base64.urlsafe_b64decode(state_b64 + "==").decode()
        state = json.loads(state_json)
        slack_user_id = state["slack_user_id"]
        nonce = state["nonce"]
        display_name = state.get("display_name", "")
    except (ValueError, KeyError, json.JSONDecodeError, binascii.Error) as e:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(f"Invalid state parameter: {e}"),
        }

    # Validate nonce (CSRF protection)
    table = dynamodb.Table(OAUTH_TOKENS_TABLE)
    nonce_pk = f"nonce#{nonce}"

    try:
        response = table.get_item(Key={"pk": nonce_pk})
        if "Item" not in response:
            raise ValueError("Invalid or expired nonce")

        # Verify nonce belongs to the same user (CSRF protection)
        nonce_item = response["Item"]
        if nonce_item.get("slack_user_id") != slack_user_id:
            raise ValueError("Nonce user mismatch")

        # Delete nonce (one-time use)
        table.delete_item(Key={"pk": nonce_pk})

    except (ClientError, ValueError) as e:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(f"CSRF validation failed: {e}"),
        }

    # Exchange code for tokens
    secrets = get_secret()
    client_id = secrets["ATLASSIAN_OAUTH_CLIENT_ID"]
    client_secret = secrets["ATLASSIAN_OAUTH_CLIENT_SECRET"]

    function_url = get_function_url(event)
    redirect_uri = f"{function_url}/callback/atlassian"

    token_data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    try:
        # POST to token endpoint
        token_request = urllib.request.Request(
            "https://auth.atlassian.com/oauth/token",
            data=urllib.parse.urlencode(token_data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(token_request, timeout=10) as response:
            token_response = json.loads(response.read().decode())

        access_token = token_response["access_token"]
        refresh_token = token_response["refresh_token"]
        expires_in = token_response.get("expires_in", 3600)

    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        KeyError,
        json.JSONDecodeError,
    ) as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(f"Failed to exchange OAuth code: {e}"),
        }

    # Get accessible resources (cloud ID)
    try:
        resources_request = urllib.request.Request(
            "https://api.atlassian.com/oauth/token/accessible-resources",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        with urllib.request.urlopen(resources_request, timeout=10) as response:
            resources = json.loads(response.read().decode())

        if not resources or len(resources) == 0:
            raise ValueError("No accessible Atlassian resources found")

        cloud_id = resources[0]["id"]

    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(f"Failed to fetch Atlassian resources: {e}"),
        }

    # Encrypt tokens
    try:
        encrypted_access_token = encrypt_value(access_token, OAUTH_KMS_KEY_ID)
        encrypted_refresh_token = encrypt_value(refresh_token, OAUTH_KMS_KEY_ID)
    except RuntimeError as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(f"Encryption failed: {e}"),
        }

    # Store in DynamoDB
    pk = f"user#{slack_user_id}#atlassian"
    now = int(time.time())
    token_expires_at = now + expires_in

    try:
        table.put_item(
            Item={
                "pk": pk,
                "provider": "atlassian",
                "encrypted_refresh_token": encrypted_refresh_token,
                "encrypted_access_token": encrypted_access_token,
                "token_expires_at": token_expires_at,
                "cloud_id": cloud_id,
                "created_at": now,
                "updated_at": now,
            }
        )
    except ClientError as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(f"Failed to store tokens: {e}"),
        }

    # Mark portal session as completed
    portal_pk = f"portal#{slack_user_id}"
    try:
        table.put_item(
            Item={
                "pk": portal_pk,
                "status": "completed",
                "provider": "atlassian",
                "updated_at": now,
                "ttl": now + 3600,  # Clean up after 1 hour
            }
        )
    except ClientError as e:
        # Non-critical - not a blocker
        print(f"Could not mark portal session as completed: {e}")

    # Redirect to dashboard showing updated connection status
    function_url = get_function_url(event)
    dashboard_jwt = create_jwt(
        {
            "slack_user_id": slack_user_id,
            "display_name": display_name,
            "exp": int(time.time()) + 600,
        }
    )
    dashboard_url = f"{function_url}?token={dashboard_jwt}&just_connected=atlassian"

    return {
        "statusCode": 302,
        "headers": {
            "Location": dashboard_url,
            "Content-Type": "text/html",
        },
        "body": "",
    }


def handle_atlassian_revoke(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle POST /revoke/atlassian - Revoke authorization.

    Args:
        event: Lambda function URL event

    Returns:
        Lambda response dict (redirect to dashboard)
    """
    from portal_html import render_error

    # Extract JWT from query params or POST body (hidden form field)
    query_params = event.get("queryStringParameters") or {}
    token = query_params.get("token")

    if not token:
        # Check POST body (form-encoded hidden field)
        body = event.get("body", "")
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode()
        if body:
            form_data = urllib.parse.parse_qs(body)
            token = form_data.get("token", [None])[0]

    if not token:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html"},
            "body": render_error("Missing authentication token"),
        }

    try:
        payload = validate_jwt(token)
        slack_user_id = payload.get("slack_user_id")

        if not slack_user_id:
            raise ValueError("JWT missing slack_user_id")

    except ValueError as e:
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(f"Authentication failed: {e}"),
        }

    # Delete DynamoDB record
    table = dynamodb.Table(OAUTH_TOKENS_TABLE)
    pk = f"user#{slack_user_id}#atlassian"

    try:
        table.delete_item(Key={"pk": pk})
    except ClientError as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(f"Failed to revoke authorization: {e}"),
        }

    # Create a fresh JWT token for the redirect (10-minute expiry)
    display_name = payload.get("display_name")
    jwt_claims = {"slack_user_id": slack_user_id, "exp": int(time.time()) + 600}
    if display_name:
        jwt_claims["display_name"] = display_name
    fresh_token = create_jwt(jwt_claims)

    # Redirect back to dashboard
    function_url = get_function_url(event)
    dashboard_url = f"{function_url}/?token={fresh_token}"

    return {
        "statusCode": 302,
        "headers": {"Location": dashboard_url, "Content-Type": "text/html"},
        "body": "",
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for auth portal.

    Routes requests based on rawPath:
        GET /                    - Portal dashboard
        GET /callback/atlassian  - OAuth callback
        POST /revoke/atlassian   - Revoke authorization

    Args:
        event: Lambda function URL event
        context: Lambda context object

    Returns:
        Lambda response dict with statusCode, headers, and body
    """
    from portal_html import render_error

    # Redact sensitive data before logging
    safe_event = {**event}
    safe_params = dict(safe_event.get("queryStringParameters") or {})
    for key in ("code", "token"):
        if key in safe_params:
            safe_params[key] = "REDACTED"
    safe_event["queryStringParameters"] = safe_params
    print(f"Event: {json.dumps(safe_event)}")

    raw_path = event.get("rawPath", "/")
    request_method = (
        event.get("requestContext", {}).get("http", {}).get("method", "GET")
    )

    try:
        # Route based on path and method
        if raw_path == "/" and request_method == "GET":
            return handle_dashboard(event)

        elif raw_path == "/callback/atlassian" and request_method == "GET":
            return handle_atlassian_callback(event)

        elif raw_path == "/revoke/atlassian" and request_method == "POST":
            return handle_atlassian_revoke(event)

        else:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "text/html"},
                "body": render_error(f"Route not found: {request_method} {raw_path}"),
            }

    except Exception as e:
        print(f"Unhandled error: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": render_error(f"Internal server error: {e}"),
        }

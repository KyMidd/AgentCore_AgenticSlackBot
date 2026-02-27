"""OAuth token management for per-user Atlassian authorization"""

import os
import json
import time
import hmac
import hashlib
import base64
from typing import Optional
import boto3

# Environment variables
OAUTH_TABLE_NAME = os.environ.get("OAUTH_TABLE_NAME", "")
OAUTH_KMS_KEY_ID = os.environ.get("OAUTH_KMS_KEY_ID", "")
AUTH_PORTAL_URL = os.environ.get("AUTH_PORTAL_URL", "")


def _get_dynamodb_table():
    """Get DynamoDB table resource"""
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(OAUTH_TABLE_NAME)


def _get_kms_client():
    """Get KMS client"""
    return boto3.client("kms")


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token with KMS"""
    kms = _get_kms_client()
    response = kms.encrypt(
        KeyId=OAUTH_KMS_KEY_ID,
        Plaintext=plaintext.encode("utf-8"),
    )
    return base64.b64encode(response["CiphertextBlob"]).decode("utf-8")


def decrypt_token(ciphertext_b64: str) -> str:
    """Decrypt a KMS-encrypted token"""
    kms = _get_kms_client()
    response = kms.decrypt(
        CiphertextBlob=base64.b64decode(ciphertext_b64),
    )
    return response["Plaintext"].decode("utf-8")


def lookup_user_token(slack_user_id: str, provider: str = "atlassian") -> Optional[str]:
    """
    Look up user's OAuth refresh token in DynamoDB.

    Returns decrypted refresh_token string, or None if not found.
    """
    if not OAUTH_TABLE_NAME:
        return None

    try:
        table = _get_dynamodb_table()
        response = table.get_item(Key={"pk": f"user#{slack_user_id}#{provider}"})
        item = response.get("Item")
        if not item:
            return None

        encrypted_refresh = item.get("encrypted_refresh_token")
        if not encrypted_refresh:
            return None

        return decrypt_token(encrypted_refresh)
    except Exception as e:
        print(f"🔴 Error looking up user token: {e}")
        return None


def update_user_refresh_token(
    slack_user_id: str, new_refresh_token: str, provider: str = "atlassian"
) -> bool:
    """
    Update user's stored refresh token after rotation.

    Atlassian rotates refresh tokens on every use — the old token becomes
    invalid. This must be called after each successful token exchange.
    """
    if not OAUTH_TABLE_NAME or not OAUTH_KMS_KEY_ID:
        print(
            "🔴 Cannot update refresh token: OAUTH_TABLE_NAME or OAUTH_KMS_KEY_ID not set"
        )
        return False

    try:
        table = _get_dynamodb_table()
        encrypted_token = encrypt_token(new_refresh_token)
        table.update_item(
            Key={"pk": f"user#{slack_user_id}#{provider}"},
            UpdateExpression="SET encrypted_refresh_token = :t, updated_at = :u",
            ExpressionAttributeValues={
                ":t": encrypted_token,
                ":u": int(time.time()),
            },
        )
        print(f"🟢 Refresh token rotated for {slack_user_id}/{provider}")
        return True
    except Exception as e:
        print(f"🔴 Error updating refresh token: {e}")
        return False


def delete_user_token(slack_user_id: str, provider: str = "atlassian") -> None:
    """Delete a user's stale OAuth token from DynamoDB."""
    if not OAUTH_TABLE_NAME:
        return
    try:
        table = _get_dynamodb_table()
        table.delete_item(Key={"pk": f"user#{slack_user_id}#{provider}"})
    except Exception as e:
        print(f"🔴 Error deleting user token: {e}")


def generate_portal_url(
    slack_user_id: str, signing_secret: str, user_display_name: Optional[str] = None
) -> Optional[str]:
    """
    Generate a signed portal URL for the user.

    Creates a JWT with the user's slack_user_id and 10-minute expiry,
    appended as ?token= query parameter to AUTH_PORTAL_URL.
    """
    if not AUTH_PORTAL_URL:
        return None

    # Create JWT payload
    payload = {
        "slack_user_id": slack_user_id,
        "exp": int(time.time()) + 600,  # 10-minute expiry
    }
    if user_display_name:
        payload["display_name"] = user_display_name

    # Create JWT
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )

    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )

    message = f"{header}.{payload_b64}".encode("utf-8")
    signature = hmac.new(
        signing_secret.encode("utf-8"), message, hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    jwt_token = f"{header}.{payload_b64}.{sig_b64}"

    return f"{AUTH_PORTAL_URL}?token={jwt_token}"


def check_and_cleanup_auth_prompt(slack_user_id: str) -> bool:
    """
    Check if user has completed authorization since last interaction.

    Returns True if user completed auth (so we can log it), False otherwise.
    Deletes the portal session record after reading.
    """
    if not OAUTH_TABLE_NAME:
        return False

    try:
        table = _get_dynamodb_table()
        response = table.get_item(Key={"pk": f"portal#{slack_user_id}"})
        item = response.get("Item")

        if not item or item.get("status") != "completed":
            return False

        # Delete the portal session record
        table.delete_item(Key={"pk": f"portal#{slack_user_id}"})

        return True
    except Exception as e:
        print(f"🔴 Error checking auth prompt cleanup: {e}")
        return False

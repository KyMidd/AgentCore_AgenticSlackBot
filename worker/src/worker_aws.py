# AWS and Bedrock related functions
import os
import boto3
import requests
from worker_inputs import debug_enabled
from worker_mcp_client_github import *
from worker_errors import get_error_message


def get_secret_with_client(secret_name, region_name):
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except requests.exceptions.RequestException as error:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        print(
            f"🔴 Had an error attempting to get secret from AWS Secrets Manager: {error}"
        )
        raise error

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response["SecretString"]

    # Log success
    print(f"🟡 Successfully got secret {secret_name} from AWS Secrets Manager")

    # Return the secret
    return secret


def create_bedrock_client(region_name):
    return boto3.client("bedrock-runtime", region_name=region_name)


def ai_request(
    bedrock_client,
    messages,
    say,
    thread_ts,
    client,
    message_ts,
    channel_id,
    system_prompt,
):
    from worker_inputs import (
        temperature,
        top_k,
        enable_guardrails,
        model_id,
        guardrailIdentifier,
        guardrailVersion,
        guardrailTracing,
    )
    from worker_slack import update_slack_response

    # Format model system prompt for the request
    system = [{"text": system_prompt}]

    # Base inference parameters to use.
    inference_config = {
        "temperature": temperature,
    }

    # Additional inference parameters to use.
    additional_model_fields = {"top_k": top_k}

    # Build converse body. If guardrails is enabled, add those keys to the body
    if enable_guardrails:
        converse_body = {
            "modelId": model_id,
            "guardrailConfig": {
                "guardrailIdentifier": guardrailIdentifier,
                "guardrailVersion": guardrailVersion,
                "trace": guardrailTracing,
            },
            "messages": messages,
            "system": system,
            "inferenceConfig": inference_config,
            "additionalModelRequestFields": additional_model_fields,
        }
    else:
        converse_body = {
            "modelId": model_id,
            "messages": messages,
            "system": system,
            "inferenceConfig": inference_config,
            "additionalModelRequestFields": additional_model_fields,
        }

    # Debug
    import os

    if debug_enabled == "True":
        print(f"🟡 converse_body: {converse_body}")

    # Try to make the request to the AI model
    # Catch any exceptions and return an error message
    try:

        # Request entire body response
        response_raw = bedrock_client.converse(**converse_body)

        # Check for empty response
        if not response_raw.get("output", {}).get("message", {}).get("content", []):
            # If the request fails, print the error
            print(f"🟡 Empty response from Bedrock: {response_raw}")

            # Format response
            response = (
                f"🛑 *Vera didn't generate an answer to this questions.*\n\n"
                f"• *This means Vera had an error.*\n"
                f"*You can try rephrasing your question, or open a ticket with DevOps to investigate*"
            )

            # Return error as response
            return response

        # Extract response
        response = response_raw["output"]["message"]["content"][0]["text"]

        # Return response to caller, don't post to slack
        return response

    # Any errors should return a message to the user
    except Exception as error:
        # If the request fails, print the error
        print(f"🔴 Error making request to Bedrock: {error}")

        error_message = get_error_message(error)

        # Return error as response
        message_ts = update_slack_response(
            say,
            client,
            message_ts,
            channel_id,
            thread_ts,
            error_message,
        )

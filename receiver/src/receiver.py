### Imports
import json
import os
import boto3


### Execute

# Lazy initialize AWS Lambda client
lambda_client = None


def get_lambda_client():
    """Get Lambda client, initializing it lazily on first use"""
    global lambda_client
    if lambda_client is None:
        lambda_client = boto3.client("lambda")
    return lambda_client


# Lambda handler
def lambda_handler(event, context):
    """
    Receives Slack events, performs basic validation, and invokes the AgentCore runtime
    """
    print(f"🟡 Received event: {json.dumps(event)}")

    try:
        # Read environment variables
        INVOKER_FUNCTION_NAME = os.environ.get("INVOKER_FUNCTION_NAME")
        SLACK_BOT_ID = os.environ.get("SLACK_BOT_ID")

        # Parse the event body
        body = json.loads(event["body"])

        # Handle Slack url_verification event (URL verification challenge)
        if body.get("type") == "url_verification":
            challenge = body.get("challenge", "")
            return {"statusCode": 200, "body": json.dumps({"challenge": challenge})}

        # Print body
        print(f"🟡 Parsed body: {json.dumps(body)}")

        # Get the event type
        type = body.get("type", "")
        event_type = body.get("event", {}).get("type", "")
        event_subtype = body.get("event", {}).get("subtype", "")

        # Set canary vars for if we discard the message
        discardMessage = False
        edited = False
        ownMessage = False

        # Check if message is edited
        if "edited" in body.get("event", {}):
            discardMessage = True
            edited = True
            print("🚮 Detected edited message, throwing away")

        # Check if the event is a message from the bot itself
        if "event" in body:
            event_data = body["event"]

            # Check bot_profile.name for "Vera"
            if "bot_profile" in event_data:
                bot_name = event_data["bot_profile"].get("name", "")
                if "Vera" in bot_name:
                    print("🚮 Detected message from our own bot, throwing away")
                    discardMessage = True
                    ownMessage = True

            # Check bot_id against SLACK_BOT_ID environment variable
            elif "bot_id" in event_data and SLACK_BOT_ID:
                if event_data["bot_id"] == SLACK_BOT_ID:
                    print("🚮 Detected message from our own bot, throwing away")
                    discardMessage = True
                    ownMessage = True

        # Detect different types of events to throw away - blocklist
        # List of event subtypes to ignore
        ignored_event_subtypes = [
            "message_changed",  # an edited message, which we see all the time due to the bot streaming responses
            "message_deleted",  # a deleted message, which we don't care about
        ]

        # Check if we want to discard this event
        if event_subtype in ignored_event_subtypes or discardMessage == True:
            if event_subtype in ignored_event_subtypes:
                print(f"🚮 Detected ignored event_subtype: {event_subtype}, discarding")
            if edited == True:
                print("🚮 Detected edited message, discarding")
            if ownMessage == True:
                print("🚮 Detected message from our own bot, discarding")

            # Return 200 OK to Slack to prevent retries and exit
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {"message": "Message changed event subtype discarded"}
                ),
            }

        # Need to build a permit-list here of event types we care about
        # For now, we will process all event types except 'message_changed'
        # Supported event types:
        # - file_share - uploading a file

        # Only process events we care about
        if type == "event_callback":
            print(f"🟢 Processing type: {type}")
            print(f"🟢 Processing event type: {event_type}")
            print(f"🟢 Processing event subtype: {event_subtype}")

            # Invoke the Invoker Lambda asynchronously
            client = get_lambda_client()

            # Build payload for invoker Lambda (which will call AgentCore)
            payload = {
                "slack_event": body,
                "event_type": event_type,
                "event_subtype": event_subtype,
            }

            print(f"🟢 Async invoking Invoker Lambda: {INVOKER_FUNCTION_NAME}")
            client.invoke(
                FunctionName=INVOKER_FUNCTION_NAME,
                InvocationType="Event",  # Async fire-and-forget
                Payload=json.dumps(payload),
            )
            print(f"🟢 Invoker Lambda invoked asynchronously")

        # Always return 200 OK to Slack quickly
        return {"statusCode": 200, "body": json.dumps({"message": "Event received"})}

    except Exception as error:
        print(f"Error processing event: {str(error)}")
        # Still return 200 to Slack to prevent retries
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Error processing event"}),
        }

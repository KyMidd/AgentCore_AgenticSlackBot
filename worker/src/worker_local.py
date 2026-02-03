import json
import os
from worker_slack import register_slack_app
from worker_aws import get_secret_with_client, create_bedrock_client
from worker_conversation import handle_message_event
from worker_inputs import bot_secret_name, kb_region_name
from worker_errors import get_error_message

# Main function, primarily for local development

if __name__ == "__main__":
    # Run in local development mode
    print("🟡 Local server starting")

    # Fetch secret package
    secrets = get_secret_with_client(bot_secret_name, "us-east-1")

    # Disambiguate the secrets with json lookups
    secrets_json = json.loads(secrets)
    token = secrets_json["SLACK_BOT_TOKEN"]
    signing_secret = secrets_json["SLACK_SIGNING_SECRET"]

    # Register the Slack handler
    print("🟡 Registering the Slack handler")
    app, registered_bot_id = register_slack_app(token, signing_secret)

    # Register the AWS Bedrock AI client
    print("🟡 Registering the AWS Bedrock client")
    bedrock_client = create_bedrock_client(kb_region_name)

    # Responds to app mentions
    @app.event("app_mention")
    def handle_app_mention_events(client, body, say, req, payload):
        print("🟡 Local: Handling app mention event")
        try:
            bedrock_client = create_bedrock_client(kb_region_name)
            handle_message_event(
                client,
                body,
                say,
                bedrock_client,
                app,
                token,
                registered_bot_id,
                secrets_json,
            )
        except Exception as error:
            print(f"🔴 Critical error in local handle_app_mention_events: {str(error)}")

            error_message = get_error_message(error)

            try:
                thread_ts = body["event"].get("thread_ts", body["event"]["ts"])
                say(text=error_message, thread_ts=thread_ts)
            except Exception as say_error:
                print(f"🔴 Failed to send error message to user: {str(say_error)}")

    # Respond to message events
    @app.event("message")
    def handle_message_events(client, body, say, req, payload):
        print("🟡 Local: Handling message event")
        try:
            bedrock_client = create_bedrock_client(kb_region_name)
            handle_message_event(
                client,
                body,
                say,
                bedrock_client,
                app,
                token,
                registered_bot_id,
                secrets_json,
            )
        except Exception as error:
            print(f"🔴 Critical error in local handle_message_events: {str(error)}")

            error_message = get_error_message(error)

            try:
                thread_ts = body["event"].get("thread_ts", body["event"]["ts"])
                say(text=error_message, thread_ts=thread_ts)
            except Exception as say_error:
                print(f"🔴 Failed to send error message to user: {str(say_error)}")

    # Start the app in websocket mode for local development
    print("🟡 Starting the slack app listener")
    app.start(
        port=int(os.environ.get("PORT", 3000)),
    )

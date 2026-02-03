import json
import os
import threading
from bedrock_agentcore import BedrockAgentCoreApp
from worker_slack import register_slack_app, say as slack_say
from worker_aws import get_secret_with_client, create_bedrock_client
from worker_conversation import handle_message_event
from worker_inputs import kb_region_name
from worker_errors import get_error_message

# Initialize BedrockAgentCoreApp
app = BedrockAgentCoreApp()
print("🟡 worker_agentcore.py loading - fetching secrets and initializing clients")

# Fetch secrets
secret_name = os.environ.get("SECRET_NAME")
aws_region = os.environ.get("AWS_REGION", "us-east-1")
secrets = get_secret_with_client(secret_name, aws_region)
secrets_json = json.loads(secrets)

# Register Slack app
token = secrets_json["SLACK_BOT_TOKEN"]
slack_app, registered_bot_id = register_slack_app(
    token, secrets_json["SLACK_SIGNING_SECRET"]
)

# Create Bedrock client
bedrock_client = create_bedrock_client(kb_region_name)
print("🟡 worker_agentcore.py loaded - clients initialized, ready for requests")


@app.entrypoint
def handle_slack_message(payload):
    """Process incoming Slack message - delegates to background thread to avoid blocking ping endpoint"""
    print("🟡 Received request")

    # Extract Slack event from payload for validation
    slack_event = payload.get("slack_event", {})

    if not slack_event:
        print("🔴 No slack_event in payload")
        return {"status": "error", "message": "No slack_event in payload"}

    # Extract event details for logging
    event_data = slack_event.get("event", {})
    channel_id = event_data.get("channel", "")
    message_text = event_data.get("text", "")

    print(
        f"🟡 Starting background processing for message in channel {channel_id}: {message_text[:50]}..."
    )

    # Start tracking async task so AgentCore knows we're busy
    task_id = app.add_async_task(
        "slack_message_processing",
        {"channel": channel_id, "message_preview": message_text[:50]},
    )

    # Process the message in a background thread so ping endpoint can respond
    def process_in_background():
        try:
            print(f"🟡 Background thread started for task {task_id}")

            # Extract channel_id
            thread_channel_id = slack_event.get("event", {}).get("channel", "")

            # Create say() function
            def say(text, thread_ts=None):
                """Wrapper for slack_say with channel_id from thread scope"""
                return slack_say(slack_app.client, thread_channel_id, text, thread_ts)

            # Handle the message event
            handle_message_event(
                client=slack_app.client,
                body=slack_event,
                say=say,
                bedrock_client=bedrock_client,
                app=slack_app,
                token=token,
                registered_bot_id=registered_bot_id,
                secrets_json=secrets_json,
            )

            print(f"🟡 Successfully completed message handling for task {task_id}")

        except Exception as error:
            # Log error details
            print(f"🔴 Error processing request in background thread: {str(error)}")

            # Try to post error message to Slack
            try:
                error_message = get_error_message(error)
                thread_ts = slack_event.get("event", {}).get(
                    "thread_ts", slack_event.get("event", {}).get("ts", "")
                )
                channel_id = slack_event.get("event", {}).get("channel", "")

                if channel_id:
                    slack_app.client.chat_postMessage(
                        channel=channel_id, text=error_message, thread_ts=thread_ts
                    )
                    print("🟡 Posted error message to Slack")
            except Exception as slack_error:
                print(f"🔴 Failed to post error to Slack: {str(slack_error)}")

        finally:
            # Always mark the task as complete so AgentCore knows we're done
            app.complete_async_task(task_id)
            print(f"🟡 Completed async task {task_id}")

    # Start the background thread
    thread = threading.Thread(target=process_in_background, daemon=True)
    thread.start()
    print(f"🟡 Background thread launched for task {task_id}, returning immediately")

    # Return immediately so the ping endpoint isn't blocked
    return {"status": "processing", "task_id": task_id}


if __name__ == "__main__":
    # Start the BedrockAgentCoreApp server
    print("🟡 worker_agentcore.py starting - BedrockAgentCoreApp initializing")
    app.run()

# Slack related functions
import os
import requests
from slack_bolt import App
from worker_inputs import debug_enabled


def update_slack_response(say, client, message_ts, channel_id, thread_ts, message_text):
    # If message_ts is None, we're posting a new message
    if message_ts is None:
        slack_response = say(
            text=message_text,
            thread_ts=thread_ts,
        )
        # Set message_ts
        message_ts = slack_response["ts"]
    else:
        # We're updating an existing message
        slack_response = client.chat_update(
            text=message_text,
            channel=channel_id,
            ts=message_ts,
        )

        # Debug
        if debug_enabled == "True":
            print(f"🟡 Slack chat update response: {slack_response}")

    # Check to see if the response was successful
    # Sucessful response: {'ok': True, 'channel': 'D088U5DEXGW', 'ts': '1748898172.661379', 'text': "Hi Kyler! :wa
    if not slack_response.get("ok"):
        error_type = slack_response.get("error")
        print(f"🔴 Error updating Slack message: {error_type}")

        # Message the user that there was an error
        say(
            text=f"🚨 There was an error updating your message: {error_type}\n\nPlease ask your question again",
            thread_ts=thread_ts,
        )

    # Return the message_ts
    return message_ts


def delete_slack_response(client, channel_id, message_ts):
    # Delete the message using the Slack API
    slack_response = client.chat_delete(
        channel=channel_id,
        ts=message_ts,
    )

    # Debug
    if debug_enabled == "True":
        print(f"🟡 Slack chat delete response: {slack_response}")

    # Check to see if the response was successful
    if not slack_response.get("ok"):
        error_type = slack_response.get("error")
        print(f"🔴 Error deleting Slack message: {error_type}")
        return False

    # Return success
    return True


def say(client, channel_id, text, thread_ts=None):
    """Post message to Slack channel/thread"""
    response = client.chat_postMessage(
        channel=channel_id, text=text, thread_ts=thread_ts
    )
    print(f"🟡 Posted message to Slack channel {channel_id}")
    return response


def register_slack_app(token, signing_secret):
    app = App(
        process_before_response=True,  # Required for AWS Lambda
        token=token,
        signing_secret=signing_secret,
    )

    # Find the bot name
    bot_info = requests.get(
        "https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {token}"}
    )

    bot_info_json = bot_info.json()

    if debug_enabled == "True":
        print(f"🟡 Bot info: {bot_info_json}")

    if bot_info_json.get("ok"):
        bot_name = bot_info_json.get("user")
        registered_bot_id = bot_info_json.get("bot_id")
        slack_team = bot_info_json.get("team")
        print(
            f"🟡 Successfully registered as bot, can be tagged with @{bot_name} ({registered_bot_id}) from slack @{slack_team}"
        )
    else:
        print(f"🔴 Failed to retrieve bot name: {bot_info_json.get("error")}")
        # Exit with error
        raise Exception("Failed to retrieve bot name:", bot_info_json.get("error"))

    # Return the app
    return app, registered_bot_id

# Conversation handling functions
import os
import requests
from worker_slack import update_slack_response, delete_slack_response
from worker_agent import execute_agent
from worker_aws import ai_request
from worker_inputs import (
    debug_enabled,
    audit_logging_enabled,
    memory_id,
    memory_type,
    session_ttl_days,
)
from worker_audit import write_audit_log


def generate_session_id(body):
    """
    Generate UNIQUE session ID per message for stateless operation.

    Uses the Slack message timestamp to ensure each inbound message gets its own
    session. This prevents STM (short-term memory) from accumulating and
    replaying corrupted conversation state across messages.

    User preferences still work because they're keyed by actor_id, not session_id.
    The retrieval_config uses /preferences/{actorId} which persists across sessions.

    Format: msg_{ts} (with periods replaced by underscores for AWS regex compliance)

    Args:
        body: Slack event body

    Returns:
        session_id: Unique session identifier per message
    """
    event = body.get("event", {})

    # Use the unique message timestamp from Slack - each message gets its own session
    ts = event.get("ts", "")
    if ts:
        # Replace periods with underscores for AWS regex compliance
        return f"msg_{ts.replace('.', '_')}"

    # Fallback to UUID if no timestamp (shouldn't happen in normal flow)
    import uuid

    return f"msg_{uuid.uuid4()}"


def build_conversation_content(payload, token):
    # Initialize unsupported file type found canary var
    unsupported_file_type_found = False

    # Debug
    if debug_enabled == "True":
        print(f"🟡 Conversation content payload: {payload}")

    # Initialize the content array
    content = []

    # Initialize pronouns as blank
    pronouns = ""

    # Extract bot_id from payload (not from user_info_json)
    bot_id = payload.get("bot_id", "")

    # Safely get user_id - bot messages may not have a user field
    user_id = payload.get("user")
    speaker_name = "Bot" if bot_id else (user_id or "Unknown")
    user_info_json = {}  # Initialize for cases where we can't fetch user info
    profile = {}  # Initialize profile for cases where we can't fetch user info

    # Only fetch user info if we have a valid user_id
    if user_id:
        # Fetch user information from Slack API
        user_info = requests.get(
            f"https://slack.com/api/users.info?user={user_id}",
            headers={"Authorization": "Bearer " + token},
        )
        user_info_json = user_info.json()

        # Debug
        if debug_enabled == "True":
            print(f"🟡 Conversation content user info: {user_info_json}")

        # Identify the speaker's name based on their profile data
        profile = user_info_json.get("user", {}).get("profile", {})
        display_name = profile.get("display_name")
        real_name = user_info_json.get("user", {}).get("real_name", "Unknown User")
        speaker_name = display_name or real_name
    elif bot_id:
        # For bot messages without user field, use username if available
        speaker_name = payload.get("username", "Bot")
        if debug_enabled == "True":
            print(f"🟡 Bot message detected, using username: {speaker_name}")

    # If bot, set pronouns as "Bot"
    if bot_id or "bot_id" in user_info_json:
        pronouns = " (Bot)"
    else:
        # Pronouns
        try:
            # If user has pronouns, set to pronouns with round brackets with a space before, like " (they/them)"
            pronouns = f" ({profile['pronouns']})"
        except:
            # If no pronouns, use the initialized pronouns (blank)
            if debug_enabled == "True":
                print("🟡 User has no pronouns, using blank pronouns")

    # If text is not empty, and text length is greater than 0, append to content array
    if "text" in payload and len(payload["text"]) > 1:
        # If debug variable is set to true, print the text found in the payload
        if debug_enabled == "True":
            print(f"🟡 Text found in payload: {payload["text"]}")

        content.append(
            {
                # Combine the user's name with the text to help the model understand who is speaking
                "text": f"{speaker_name}{pronouns} says: {payload['text']}",
            }
        )

    if "attachments" in payload:
        # Append the attachment text to the content array
        for attachment in payload["attachments"]:

            # If debug variable is set to true, print the text found in the attachments
            if debug_enabled == "True" and "text" in attachment:
                print(f"🟡 Text found in attachment: {attachment["text"]}")

            # Check if the attachment contains text
            if "text" in attachment:
                # Append the attachment text to the content array
                content.append(
                    {
                        # Combine the user's name with the text to help the model understand who is speaking
                        "text": f"{speaker_name}{pronouns} says: "
                        + attachment["text"],
                    }
                )

    # If the payload contains files, iterate through them
    if "files" in payload:

        # Append the payload files to the content array
        for file in payload["files"]:

            # Debug
            if debug_enabled == "True":
                print(f"🟡 File found in payload: {file}")

            # Isolate name of the file and remove characters before the final period
            file_name = file["name"].split(".")[0]

            # File is a supported type
            file_url = file["url_private_download"]

            # Fetch the file and continue
            file_object = requests.get(
                file_url, headers={"Authorization": "Bearer " + token}
            )

            # Decode object into binary file
            file_content = file_object.content

            # Check the mime type of the file is a supported image file type
            if file["mimetype"] in [
                "image/png",  # png
                "image/jpeg",  # jpeg
                "image/gif",  # gif
                "image/webp",  # webp
            ]:

                # Isolate the file type based on the mimetype
                file_type = file["mimetype"].split("/")[1]

                # Append the file to the content array
                content.append(
                    {
                        "image": {
                            "format": file_type,
                            "source": {
                                "bytes": file_content,
                            },
                        }
                    }
                )

            # Check if file is a supported document type
            elif file["mimetype"] in [
                "application/pdf",
                "application/csv",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "text/html",
                "text/markdown",
            ]:

                # Isolate the file type based on the mimetype
                if file["mimetype"] in ["application/pdf"]:
                    file_type = "pdf"
                elif file["mimetype"] in ["application/csv"]:
                    file_type = "csv"
                elif file["mimetype"] in [
                    "application/msword",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ]:
                    file_type = "docx"
                elif file["mimetype"] in [
                    "application/vnd.ms-excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ]:
                    file_type = "xlsx"
                elif file["mimetype"] in ["text/html"]:
                    file_type = "html"
                elif file["mimetype"] in ["text/markdown"]:
                    file_type = "markdown"

                # Append the file to the content array
                content.append(
                    {
                        "document": {
                            "format": file_type,
                            "name": file_name,
                            "source": {
                                "bytes": file_content,
                            },
                        }
                    }
                )

                # Append the required text to the content array
                content.append(
                    {
                        "text": "file",
                    }
                )

            # Support plaintext snippets
            elif file["mimetype"] in ["text/plain"]:
                # File is a supported type
                snippet_file_url = file["url_private_download"]

                # Fetch the file and continue
                snippet_file_object = requests.get(
                    snippet_file_url, headers={"Authorization": "Bearer " + token}
                )

                # Decode the file into plaintext
                snippet_text = snippet_file_object.content.decode("utf-8")

                # Append the file to the content array
                content.append(
                    {
                        "text": f"{speaker_name} {pronouns} attached a snippet of text:\n\n{snippet_text}",
                    }
                )

            # If the mime type is not supported, set unsupported_file_type_found to True
            else:
                print(f"🟡 Unsupported file type found: {file['mimetype']}")
                unsupported_file_type_found = True
                continue

    # Return
    return bot_id, content, unsupported_file_type_found, user_info_json


def build_conversation_context(body, token, registered_bot_id, app):
    """Build conversation context with full thread history"""
    from worker_inputs import bot_name

    conversation = []

    # Check for thread context
    if "thread_ts" in body["event"]:
        # Get thread messages using app client
        thread_ts = body["event"]["thread_ts"]
        messages = app.client.conversations_replies(
            channel=body["event"]["channel"], ts=thread_ts
        )

        # Iterate through every message in the thread
        for message in messages["messages"]:
            # Skip placeholder/status messages - they're not part of the actual conversation
            # We check for unique markers in the placeholder:
            # 1. ":turtle_blob:" - unique emoji shortcode only in placeholder
            # 2. "is connecting to platforms" - unique text pattern
            # Note: We can't use exact match because Slack converts unicode emojis (🚀)
            # to shortcodes (:rocket:) when messages are fetched back via API
            message_text = message.get("text", "")
            is_placeholder = (
                ":turtle_blob:" in message_text
                and f"{bot_name} is connecting to platforms" in message_text
            )
            if is_placeholder:
                if debug_enabled == "True":
                    print("🟡 Skipping placeholder message from conversation history")
                continue

            # Build the content array
            (
                bot_id_from_message,
                thread_conversation_content,
                unsupported_file_type_found,
                user_info_json,
            ) = build_conversation_content(message, token)

            if debug_enabled == "True":
                print(f"🟡 Thread conversation content: {thread_conversation_content}")

            # Check if the thread conversation content is empty
            if thread_conversation_content != []:
                # Check if message came from our bot
                if bot_id_from_message == registered_bot_id:
                    conversation.append(
                        {
                            "role": "assistant",
                            "content": [{"text": message["text"]}],
                        }
                    )
                # If not, the message came from a user
                else:
                    # Pass content array
                    if (
                        isinstance(thread_conversation_content, list)
                        and thread_conversation_content
                    ):
                        user_content = thread_conversation_content
                    else:
                        # Fallback for empty or invalid content
                        user_content = [{"text": "Empty message"}]

                    conversation.append(
                        {
                            "role": "user",
                            "content": user_content,
                        }
                    )

                    if debug_enabled == "True":
                        print(
                            f"🟡 State of conversation after threaded message append: {conversation}"
                        )
    else:
        # Single message conversation
        event = body["event"]
        (
            bot_id_from_message,
            user_conversation_content,
            unsupported_file_type_found,
            user_info_json,
        ) = build_conversation_content(event, token)

        # Pass content array
        if isinstance(user_conversation_content, list) and user_conversation_content:
            user_content = user_conversation_content
        else:
            # Fallback for empty or invalid content
            user_content = [{"text": "Empty message"}]

        conversation.append(
            {
                "role": "user",
                "content": user_content,
            }
        )

    return conversation


def handle_message_event(
    client,
    body,
    say,
    bedrock_client,
    app,
    token,
    registered_bot_id,
    secrets_json,
    context=None,
):
    from worker_inputs import (
        bot_name,
        enable_initial_model_context_step,
        initial_model_user_status_message,
        initial_model_system_prompt,
        initial_message,
    )

    # Initialize message_ts as None
    # This is used to track the slack message timestamp for updating the message
    message_ts = None

    channel_id = body["event"]["channel"]
    event = body["event"]

    # Determine the thread timestamp
    thread_ts = body["event"].get("thread_ts", body["event"]["ts"])

    # Initialize conversation context
    conversation = []

    # Check to see if we're in a thread
    # If yes, read previous messages in the thread, append to conversation context for AI response
    if "thread_ts" in body["event"]:
        # Get the messages in the thread
        thread_ts = body["event"]["thread_ts"]
        messages = app.client.conversations_replies(
            channel=body["event"]["channel"], ts=thread_ts
        )

        # Iterate through every message in the thread
        for message in messages["messages"]:

            # Build the content array
            (
                bot_id_from_message,
                thread_conversation_content,
                unsupported_file_type_found,
                user_info_json,
            ) = build_conversation_content(message, token)

            if debug_enabled == "True":
                print(f"🟡 Thread conversation content: {thread_conversation_content}")

            # Check if the thread conversation content is empty. This happens when a user sends an unsupported doc type only, with no message
            if thread_conversation_content != []:
                # Conversation content is not empty, append to conversation

                # Check if message came from our bot
                # We're assuming our bot only generates text content, which is true of Claude v3.5 Sonnet v2
                if bot_id_from_message == registered_bot_id:
                    conversation.append(
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "text": message["text"],
                                }
                            ],
                        }
                    )
                # If not, the message came from a user
                else:
                    conversation.append(
                        {"role": "user", "content": thread_conversation_content}
                    )

                    if debug_enabled == "True":
                        print(
                            f"🟡 State of conversation after threaded message append: {conversation}"
                        )

    else:
        # We're not in a thread, so we just need to add the user's message to the conversation

        # Build the user's part of the conversation
        (
            bot_id_from_message,
            user_conversation_content,
            unsupported_file_type_found,
            user_info_json,
        ) = build_conversation_content(event, token)

        # Append to the conversation
        conversation.append(
            {
                "role": "user",
                "content": user_conversation_content,
            }
        )

        if debug_enabled == "True":
            print(
                f"🟡 State of conversation after append user's prompt: {conversation}"
            )

    # Check if conversation content is empty, this happens when a user sends an unsupported doc type only, with no message
    # Conversation looks like this: [{'role': 'user', 'text': []}]
    if debug_enabled == "True":
        print(
            f"🟡 State of conversation before check if convo is empty: {conversation}"
        )
    if conversation == []:
        # Conversation is empty, append to error message
        if debug_enabled == "True":
            print("🟡 Conversation is empty, exiting")

        # Announce the error
        say(
            text=f"> `Error`: Unsupported file type found, please ensure you are sending a supported file type. Supported file types are: images (png, jpeg, gif, webp).",
            thread_ts=thread_ts,
        )
        return

    # Before we fetch the knowledge base, do an initial turn with the AI to add context
    if enable_initial_model_context_step:
        message_ts = update_slack_response(
            say,
            client,
            message_ts,
            channel_id,
            thread_ts,
            initial_model_user_status_message,
        )

        # Ask the AI for a response
        ai_response = ai_request(
            bedrock_client,
            conversation,
            say,
            thread_ts,
            client,
            message_ts,
            channel_id,
            initial_model_system_prompt,
        )

        # Append to conversation
        conversation.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "text": f"Initialization information from the model: {ai_response}",
                    }
                ],
            }
        )

        # Debug
        if debug_enabled == "True":
            print(f"🟡 State of conversation after context request: {conversation}")

    # Update Slack with initial message
    message_ts = update_slack_response(
        say,
        client,
        message_ts,
        channel_id,
        thread_ts,
        initial_message,
    )

    # Build conversation in bedrock format
    conversation = build_conversation_context(body, token, registered_bot_id, app)

    # Prepare memory configuration
    session_id = generate_session_id(body)

    # Get user name for actor_id from already-fetched user info
    # I'd like to use the name ahead of the @ in an email address, but slack apps can't fetch user emails
    # So we guess, taking real name normalized, lowercase it, replace spaces with underscores
    # Good enough for now, but it'll have trouble with folks with multiple names. It'll still work, but won't match VeraTeams memories because of name mismatches
    # Example: "Kyler Middleton" becomes "kyler_middleton"

    # Fetch the user's Slack ID (e.g., U12345678) to use as fallback
    actor_id = body["event"]["user"]

    # Extract real_name_normalized
    real_name = (
        user_info_json.get("user", {})
        .get("profile", {})
        .get("real_name_normalized", "")
    )
    if real_name:
        # Convert to lowercase and replace spaces with underscores
        actor_id = real_name.lower().replace(" ", "_")
        print(f"🟡 Using real name as actor_id: {actor_id} (from '{real_name}')")
    else:
        print(
            f"🟡 Could not find real_name_normalized, using Slack user ID as actor_id"
        )

    memory_config = {
        "session_id": session_id,
        "actor_id": actor_id,
        "memory_id": memory_id,
        "memory_type": memory_type,
    }
    print(f"🟡 Memory enabled for session: {session_id}, actor: {actor_id}")

    try:
        # Execute bedrock agent to fetch response
        response = execute_agent(
            secrets_json,
            conversation,
            memory_config,
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"🔴 Error executing agent: {str(e)}")
        response = f"😔 Error processing request: {str(e)}"

    # Delete the initial "researching" message
    delete_slack_response(client, channel_id, message_ts)

    # Update Slack with final response
    message_ts = update_slack_response(
        say, client, None, channel_id, thread_ts, response
    )

    # Write audit log
    if audit_logging_enabled:
        print("🟡 Writing audit log")

        # Extract user_id from user_info_json that was captured earlier
        user_id = user_info_json.get("user", {}).get("name", "unknown_user_id")

        # Extract audit fields
        conversation_id = thread_ts
        user_query = body["event"].get("text", "unknown_user_prompt")

        # Flatten conversation for audit log
        full_conversation = "\n".join(
            [
                content.get("text", "")
                for item in conversation
                for content in item.get("content", [])
                if isinstance(content, dict) and "text" in content
            ]
        )

        # Write to audit logging
        try:
            write_audit_log(
                user_id,
                user_query,
                full_conversation,
                response,
                conversation_id,
            )
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"🔴 Failed to write audit log: {e}")

    print("🟡 Successfully completed response")
    return

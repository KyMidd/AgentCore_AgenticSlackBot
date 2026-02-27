# Error handling utilities for bot
import os


def get_error_message(error):
    """Get appropriate error message based on error type"""
    # Get bot name from environment variable, default to "Vera"
    bot_name = os.environ.get("BOT_NAME", "Vera")

    THROTTLING_KEYWORDS = [
        "throttl",
        "rate limit",
        "too many requests",
        "quota exceeded",
        "service unavailable",
        "timeout",
    ]
    CONTEXT_OVERFLOW_KEYWORDS = [
        "context window",
        "context_window",
        "too many tokens",
        "input too long",
        "maximum context",
        "contextwindowexceeded",
        "token limit",
        "input is too long",
    ]
    error_str = str(error).lower()

    # Check if this is a throttling error
    is_throttling = any(keyword in error_str for keyword in THROTTLING_KEYWORDS)

    # Check if this is a context window overflow error
    is_context_overflow = any(
        keyword in error_str for keyword in CONTEXT_OVERFLOW_KEYWORDS
    )

    # Error messages with dynamic bot name
    THROTTLING_ERROR_MESSAGE = f"🚨 *{bot_name} is currently experiencing high demand and has been throttled by AI services.*\n\n*Please try your request again in a few minutes.* If the issue persists, you can:\n\n• Wait 5-10 minutes and try again\n• Break down complex requests into smaller parts\n• Contact the team in <#C0XXXXXXXXX> if you continue experiencing issues\n\n*{bot_name} is still in beta and we're working to improve stability.* 🤖"

    GENERAL_ERROR_MESSAGE = f"🚨 *{bot_name} encountered an unexpected error and crashed.*\n\n*Please try your request again.* If the issue persists, please contact the team in <#C0XXXXXXXXX> with details about your request.\n\n*{bot_name} is still in beta and we're working to improve stability.* 🤖"

    CONTEXT_OVERFLOW_MESSAGE = f"🚨 *{bot_name}'s request was too large for the AI to process.*\n\nThis usually happens when a request involves too many items (e.g., a very large Jira board or project). Try narrowing your request — for example:\n\n• Limit to a specific sprint or date range\n• Focus on a subset of owners or priorities\n• Ask about fewer tickets at a time\n\n_Contact <#C0XXXXXXXXX> if this continues._ 🤖"

    if is_context_overflow:
        return CONTEXT_OVERFLOW_MESSAGE
    elif is_throttling:
        return THROTTLING_ERROR_MESSAGE
    else:
        return GENERAL_ERROR_MESSAGE

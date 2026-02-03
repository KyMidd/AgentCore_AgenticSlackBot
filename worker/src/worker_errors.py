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
    error_str = str(error).lower()

    # Check if this is a throttling error
    is_throttling = any(keyword in error_str for keyword in THROTTLING_KEYWORDS)

    # Error messages with dynamic bot name
    THROTTLING_ERROR_MESSAGE = f"🚨 *{bot_name} is currently experiencing high demand and has been throttled by AI services.*\n\n*Please try your request again in a few minutes.* If the issue persists, you can:\n\n• Wait 5-10 minutes and try again\n• Break down complex requests into smaller parts\n• Contact the team in <#C06CDN7V3DJ> if you continue experiencing issues\n\n*{bot_name} is still in beta and we're working to improve stability.* 🤖"

    GENERAL_ERROR_MESSAGE = f"🚨 *{bot_name} encountered an unexpected error and crashed.*\n\n*Please try your request again.* If the issue persists, please contact the team in <#C06CDN7V3DJ> with details about your request.\n\n*{bot_name} is still in beta and we're working to improve stability.* 🤖"

    if is_throttling:
        return THROTTLING_ERROR_MESSAGE
    else:
        return GENERAL_ERROR_MESSAGE

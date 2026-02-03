# Audit logging functions
import os
import json
import boto3
from datetime import datetime, timezone
from worker_inputs import audit_log_group_name, model_id, bot_name, bot_platform
from opentelemetry import trace


def write_audit_log(
    user_id,
    user_query,
    full_conversation,
    response,
    conversation_id,
):
    """
    Write audit log to CloudWatch for tracking bot interactions

    For AgentCore environments:
    - Account ID is retrieved from STS
    - Trace and Span IDs are extracted from OpenTelemetry context for correlation
    - Log stream uses span_id for unique identification
    """
    try:
        # Create the logging client
        logs_client = boto3.client("logs", region_name="us-east-1")

        # Get account ID from STS
        sts_client = boto3.client("sts", region_name="us-east-1")
        aws_account_id = sts_client.get_caller_identity()["Account"]

        # Extract OpenTelemetry trace and span IDs if available
        current_span = trace.get_current_span()
        trace_id = None
        span_id = None

        if current_span and current_span.is_recording():
            span_context = current_span.get_span_context()
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")

        # Create log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bot_name": f"{bot_name}{bot_platform}",
            "aws_account_id": aws_account_id,
            "user_id": user_id,
            "user_query": user_query,
            "full_conversation": full_conversation,
            "response": response,
            "model_used": model_id,
            "conversation_id": conversation_id,
            "trace_id": trace_id,
            "span_id": span_id,
        }

        if span_id is not None:
            log_stream_suffix = span_id
        else:
            log_stream_suffix = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        log_stream_name = f"{bot_name}{bot_platform}/{log_stream_suffix}"

        try:
            logs_client.create_log_stream(
                logGroupName=audit_log_group_name, logStreamName=log_stream_name
            )
        except logs_client.exceptions.ResourceAlreadyExistsException:
            print(f"🟡 Log stream already exists: {log_stream_name}")

        # Log event
        logs_client.put_log_events(
            logGroupName=audit_log_group_name,
            logStreamName=log_stream_name,
            logEvents=[
                {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "message": json.dumps(log_entry),
                }
            ],
        )

        print(
            f"🟡 Audit log written for user {user_id}, span {span_id}, trace {trace_id}"
        )

    except Exception as error:
        print(f"🔴 Error writing audit log: {error}")

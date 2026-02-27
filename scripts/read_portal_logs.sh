#!/bin/bash
# Read CloudWatch logs from the Auth Portal Lambda
# Usage: ./scripts/read_portal_logs.sh [minutes_ago] [filter_pattern]
#   minutes_ago: How far back to read (default: 10)
#   filter_pattern: Optional filter (e.g., "error", "JWT", "U06JCNYS5N1")

MINUTES_AGO=${1:-10}
FILTER=${2:-""}
LOG_GROUP="YOUR_PORTAL_LOG_GROUP"
REGION="us-east-1"

START_TIME=$(( $(date +%s) - (MINUTES_AGO * 60) ))000

echo "=== Auth Portal Lambda Logs: last ${MINUTES_AGO} min ==="
echo "=== Log group: ${LOG_GROUP} ==="
if [ -n "$FILTER" ]; then
    echo "=== Filter: ${FILTER} ==="
    aws logs filter-log-events \
        --region "$REGION" \
        --log-group-name "$LOG_GROUP" \
        --start-time "$START_TIME" \
        --filter-pattern "$FILTER" \
        --query 'events[*].message' \
        --output text
else
    aws logs filter-log-events \
        --region "$REGION" \
        --log-group-name "$LOG_GROUP" \
        --start-time "$START_TIME" \
        --query 'events[*].message' \
        --output text
fi

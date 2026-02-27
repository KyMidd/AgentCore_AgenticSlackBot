#!/bin/bash
# Read CloudWatch logs from worker runtime
#
# Usage:
#   ./scripts/read_logs.sh [minutes_ago] [filter_pattern]
#
# Examples:
#   ./scripts/read_logs.sh                    # Last 5 min, no filter
#   ./scripts/read_logs.sh 10                 # Last 10 min, no filter
#   ./scripts/read_logs.sh 5 "Atlassian"      # Last 5 min, filter for "Atlassian"
#   ./scripts/read_logs.sh 3 "403"            # Last 3 min, filter for "403"

MINUTES_AGO="${1:-5}"
FILTER="${2:-}"
LOG_GROUP="YOUR_RUNTIME_LOG_GROUP"
REGION="us-east-1"

# Calculate start time in milliseconds
if [[ "$OSTYPE" == "darwin"* ]]; then
    START_TIME=$(( $(date +%s) * 1000 - MINUTES_AGO * 60 * 1000 ))
else
    START_TIME=$(( $(date +%s%3N) - MINUTES_AGO * 60 * 1000 ))
fi

echo "=== CloudWatch Logs: last ${MINUTES_AGO} min ==="
echo "=== Log group: ${LOG_GROUP} ==="
if [ -n "$FILTER" ]; then
    echo "=== Filter: ${FILTER} ==="
fi
echo ""

if [ -n "$FILTER" ]; then
    aws logs filter-log-events \
        --log-group-name "$LOG_GROUP" \
        --start-time "$START_TIME" \
        --filter-pattern "$FILTER" \
        --region "$REGION" \
        --no-interleaved \
        --query 'events[].message' \
        --output text 2>&1
else
    aws logs filter-log-events \
        --log-group-name "$LOG_GROUP" \
        --start-time "$START_TIME" \
        --region "$REGION" \
        --no-interleaved \
        --query 'events[].message' \
        --output text 2>&1
fi

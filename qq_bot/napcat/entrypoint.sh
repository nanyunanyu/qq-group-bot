#!/bin/bash
set -euo pipefail

if [ -z "${ONEBOT_ACCESS_TOKEN:-}" ]; then
    echo "ONEBOT_ACCESS_TOKEN is required" >&2
    exit 1
fi

export ONEBOT_TEMPLATE_PATH=/app/templates/qq-bot.json
export ONEBOT_RENDERED_TEMPLATE_PATH=/app/templates/qq-bot-rendered.json
while IFS= read -r line || [ -n "$line" ]; do
    printf '%s\n' "${line//__ONEBOT_ACCESS_TOKEN__/$ONEBOT_ACCESS_TOKEN}"
done < "$ONEBOT_TEMPLATE_PATH" > "$ONEBOT_RENDERED_TEMPLATE_PATH"
chmod 600 "$ONEBOT_RENDERED_TEMPLATE_PATH"

export MODE=qq-bot-rendered
exec bash /app/entrypoint.sh
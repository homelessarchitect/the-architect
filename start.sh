#!/bin/bash
set -e

echo "The Factory — starting up"

# Apply production workflows (generates code + creates tables)
WORKFLOWS="${ARCHITECT_WORKFLOWS:-examples/aces/workflow.py examples/asos/workflow.py}"
for wf in $WORKFLOWS; do
  if [ -f "$wf" ]; then
    echo "Applying: $wf"
    uv run architect apply --force "$wf" 2>&1 | grep -E "^(Generating|Creating|Updating|Nothing|Applied)"
  fi
done

echo ""
echo "Starting server..."
exec uv run architect serve --host 0.0.0.0 --port "${PORT:-8000}"

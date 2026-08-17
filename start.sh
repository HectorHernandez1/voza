#!/bin/bash
# Voza — launch script (auto-restarts on crash)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting Voza..."
echo "Press Ctrl+C to stop."
echo

while true; do
    uv run main.py
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "Voza exited normally."
        break
    fi

    # 130 = SIGINT (Ctrl+C before the app's own handler exits 0) — a stop
    # request, not a crash; don't restart.
    if [ $EXIT_CODE -eq 130 ]; then
        echo "Voza interrupted."
        break
    fi

    echo ""
    echo "Voza crashed (exit code $EXIT_CODE). Restarting in 2 seconds..."
    echo "Press Ctrl+C to stop."
    sleep 2
done

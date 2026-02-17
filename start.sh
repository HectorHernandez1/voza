#!/bin/bash
# Voza — launch script (auto-restarts on crash)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate Conda environment
eval "$(conda shell.bash hook)"
conda activate voza

echo "Starting Voza..."
echo "Press Ctrl+C twice to fully stop."
echo

while true; do
    python main.py
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "Voza exited normally."
        break
    fi

    echo ""
    echo "Voza crashed (exit code $EXIT_CODE). Restarting in 2 seconds..."
    echo "Press Ctrl+C to stop."
    sleep 2
done

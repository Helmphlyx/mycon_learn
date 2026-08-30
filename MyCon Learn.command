#!/bin/bash

# MyCon Learn - Vietnamese Practice App
# Double-click this file to start the app

cd "$(dirname "$0")"

echo "========================================"
echo "  MyCon Learn - Vietnamese Practice"
echo "========================================"
echo ""

# Check architecture
echo "Running on: $(uname -m)"

# Check if port 8000 is already in use
if lsof -i :8000 &> /dev/null; then
    echo "Server already running, opening browser..."
    open "http://127.0.0.1:8000"
    exit 0
fi

# Use venv Python directly
VENV_PYTHON=".venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found."
    echo "Run: poetry install"
    read -p "Press Enter to close..."
    exit 1
fi

echo "Starting server..."
echo "Press Ctrl+C to stop"
echo ""

# Open browser after a delay
(sleep 2 && open "http://127.0.0.1:8000") &

# Run the server (this keeps the terminal open)
"$VENV_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

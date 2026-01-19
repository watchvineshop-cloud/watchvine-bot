#!/bin/bash
set -e

# Check if we should skip startup checks (for production SSL issues)
if [ "$SKIP_STARTUP_CHECKS" = "true" ]; then
    echo "⚠️  Skipping startup checks (SKIP_STARTUP_CHECKS=true)"
    echo "Starting main application directly..."
    python main.py
else
    echo "Starting initialization setup..."
    python init_setup.py

    echo "Starting main application..."
    python main.py
fi

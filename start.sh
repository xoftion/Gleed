#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "--- Running start script ---"

# Validate essential environment variables
echo "Validating environment variables..."
: "${API_KEY:?API_KEY not set. Please set this environment variable.}"
: "${API_SECRET:?API_SECRET not set. Please set this environment variable.}"
: "${BEARER_TOKEN:?BEARER_TOKEN not set. Please set this environment variable.}"
: "${ACCESS_TOKEN:?ACCESS_TOKEN not set. Please set this environment variable.}"
: "${ACCESS_TOKEN_SECRET:?ACCESS_TOKEN_SECRET not set. Please set this environment variable.}"
: "${RENDER_URL:?RENDER_URL not set. This is required for the keep-alive ping.}"

# Run the main Python application directly.
# It contains the Flask server, the keep-alive scheduler, and the bookmark poller.
# Running it in the foreground is the standard practice for containers,
# as container orchestrators (like Render) manage the process and collect logs from stdout.
echo "Starting the application..."
python main.py

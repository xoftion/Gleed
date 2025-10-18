#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "--- Running start script ---"

# Run the main Python application directly.
# It contains the Flask server, the keep-alive scheduler, and the bookmark poller.
# Running it in the foreground is the standard practice for containers,
# as container orchestrators (like Render) manage the process and collect logs from stdout.
echo "Starting the application..."
python main.py
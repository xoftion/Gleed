#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "--- Running build script ---"

# Create directories
echo "Creating data directories..."
mkdir -p bookmark_videos

# Validate essential environment variables
echo "Validating environment variables..."
: "${API_KEY:?API_KEY not set. Please set this environment variable.}"
: "${API_SECRET:?API_SECRET not set. Please set this environment variable.}"
: "${BEARER_TOKEN:?BEARER_TOKEN not set. Please set this environment variable.}"
: "${ACCESS_TOKEN:?ACCESS_TOKEN not set. Please set this environment variable.}"
: "${ACCESS_TOKEN_SECRET:?ACCESS_TOKEN_SECRET not set. Please set this environment variable.}"
: "${RENDER_URL:?RENDER_URL not set. This is required for the keep-alive ping.}"

echo "--- Build script finished successfully ---"
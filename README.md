# X Bookmark Video Downloader Bot

This bot automatically detects and downloads all videos from your X account's bookmark section. It's designed for easy deployment on Render and includes features to handle X API rate limits, emulate human-like behavior, and keep itself alive on Render's free tier.

## Features

- **Automatic Video Downloading**: Periodically checks your X bookmarks and downloads any new videos. No content or user filters are applied.
- **Rate Limit Handling**: Adheres to the X API v2 free tier limit (1 request per 15 minutes) using `tenacity` for robust retries.
- **Human-Like Behavior**: Randomizes request intervals and rotates user agents to minimize the risk of bot detection.
- **Keep-Alive Mechanism**: Prevents the Render free tier instance from sleeping by pinging a `/health` endpoint every 5 minutes.
- **Containerized for Production**: Comes with a `Dockerfile`, `build.sh`, and `start.sh` for seamless deployment on Render.
- **Persistent State**: Keeps track of downloaded videos in `processed_tweets.txt` to avoid duplicates.
- **Local Archiving**: Saves downloaded videos into a timestamped folder (`bookmark_videos_YYYY-MM-DD`).
- **Robust Logging**: Provides detailed logs in `app.log` for easy debugging.

## How It Works

The application is built in Python and runs in a multi-threaded environment:
1.  **Flask Web Server**: A lightweight Flask server runs via Gunicorn to expose a `/health` endpoint.
2.  **Keep-Alive Scheduler**: A background thread uses the `schedule` library to send an HTTP GET request to its own `/health` endpoint every 5 minutes. This keeps the Render service active.
3.  **Bookmark Polling Loop**: The main thread authenticates with the X API using `tweepy`, then enters an infinite loop. Every 15-20 minutes, it fetches your bookmarks, checks for new videos, and downloads them using `yt-dlp`.

## Setup and Deployment on Render

Follow these steps to get your bot running.

### 1. X Developer Account & API Keys

1.  **Apply for a X Developer Account**: If you don't have one, go to the [X Developer Portal](https://developer.twitter.com/) and apply.
2.  **Create a Project and App**: Inside the developer portal, create a new Project. Then, create a new App within that project.
3.  **Set App Permissions**: For your App, you must enable **Read** permissions for the **Bookmarks** endpoint. This is crucial for the bot to function.
4.  **Generate Keys & Tokens**: Navigate to your App's "Keys and Tokens" section and generate the following credentials. You will need to store these securely.
    *   API Key (Consumer Key)
    *   API Key Secret (Consumer Secret)
    *   Bearer Token
    *   Access Token
    *   Access Token Secret

### 2. Fork and Deploy on Render

1.  **Fork this Repository**: Click the "Fork" button at the top-right of this page to create a copy of this repository in your own GitHub account.
2.  **Create a New Render Service**:
    *   Go to your [Render Dashboard](https://dashboard.render.com/) and click "New +".
    *   Select "Web Service".
    *   Connect your GitHub account and select the repository you just forked.
3.  **Configure the Service**:
    *   **Name**: Give your service a name (e.g., `x-video-downloader`).
    *   **Runtime**: Select **Docker**. Render will automatically detect the `Dockerfile`.
    *   **Environment Variables**: This is the most important step. Click "Advanced" and add the following environment variables, pasting the values you generated in Step 1.
        *   `API_KEY`: Your API Key
        *   `API_SECRET`: Your API Key Secret
        *   `BEARER_TOKEN`: Your Bearer Token
        *   `ACCESS_TOKEN`: Your Access Token
        *   `ACCESS_TOKEN_SECRET`: Your Access Token Secret
        *   `RENDER_URL`: The public URL Render provides for your service (e.g., `https://x-video-downloader.onrender.com`). You need to create the service first to get this URL, so you might need to add it after the first deployment.
    *   **(Optional) Email Variables**:
        *   `EMAIL_FROM`: Your sender email address.
        *   `EMAIL_TO`: The recipient's email address.
        *   `SMTP_PASS`: Your email account's password or an app-specific password.

4.  **Deploy**: Click "Create Web Service". Render will now build the Docker image and start the service. The first build may take a few minutes.

### 3. Monitoring

You can monitor the bot's activity by checking the **Logs** tab in your Render service dashboard. Look for messages about authentication, checking bookmarks, downloading videos, and keep-alive pings.

## Troubleshooting

*   **Authentication Errors (401/403)**:
    *   Double-check that your API keys and tokens are correctly entered in Render's environment variables.
    *   Ensure your X Developer App has **Read permissions for Bookmarks**.
*   **Rate Limit Errors (429)**: The bot is designed to avoid this, but if it happens, check if another application is using the same API keys. The logs will show when the next check is scheduled.
*   **Download Failures**: Check the `app.log` file for errors from `yt-dlp`. Some videos might be from private accounts, protected, or in a format that is difficult to download.
*   **Render Instance Sleeping**:
    *   Verify the `RENDER_URL` environment variable is set correctly.
    *   Check the logs to ensure the "Keep-alive ping successful" message appears every 5 minutes.
*   **Build Failures**: Ensure you have not made any changes to the `Dockerfile` or `build.sh` script that could cause issues.

## Sample `.env` File

This file is for local development. Do not commit your `.env` file to git.

```
# X (Twitter) API Credentials
API_KEY="your_key"
API_SECRET="your_secret"
BEARER_TOKEN="your_bearer"
ACCESS_TOKEN="your_token"
ACCESS_TOKEN_SECRET="your_secret"

# Render URL for keep-alive pings
RENDER_URL="https://your-app-name.onrender.com"

# Optional: Email configuration for sending ZIP files
EMAIL_FROM="bot@example.com"
EMAIL_TO="you@example.com"
SMTP_PASS="your_smtp_password"
```
import logging
import os
import random
import smtplib
import threading
import time
import zipfile
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import tweepy
from dotenv import load_dotenv
from flask import Flask
from tenacity import retry, stop_after_attempt, wait_fixed

from utils import (download_video, humanize_request, run_keep_alive_scheduler,
                   send_email_with_attachment, setup_logging)

# --- Setup and Configuration ---
load_dotenv()
setup_logging()

# --- Flask App for Health Check ---
app = Flask(__name__)

@app.route('/health')
def health_check():
    return "OK", 200

# --- X API Client ---
def create_api_client():
    """Creates and returns a Tweepy client."""
    try:
        client = tweepy.Client(
            bearer_token=os.getenv("BEARER_TOKEN"),
            consumer_key=os.getenv("API_KEY"),
            consumer_secret=os.getenv("API_SECRET"),
            access_token=os.getenv("ACCESS_TOKEN"),
            access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
            wait_on_rate_limit=True
        )
        # Verify credentials
        me = client.get_me()
        logging.info(f"Successfully authenticated as @{me.data.username}")
        return client
    except Exception as e:
        logging.critical(f"Failed to create X API client: {e}")
        return None

# --- Processed Tweet IDs ---
PROCESSED_TWEETS_FILE = "processed_tweets.txt"
processed_tweet_ids = set()

def load_processed_tweets():
    """Loads processed tweet IDs from a file."""
    if os.path.exists(PROCESSED_TWEETS_FILE):
        with open(PROCESSED_TWEETS_FILE, "r") as f:
            for line in f:
                processed_tweet_ids.add(line.strip())
    logging.info(f"Loaded {len(processed_tweet_ids)} processed tweet IDs.")

def save_processed_tweets():
    """Saves processed tweet IDs to a file."""
    with open(PROCESSED_TWEETS_FILE, "w") as f:
        for tweet_id in processed_tweet_ids:
            f.write(f"{tweet_id}\n")
    logging.info(f"Saved {len(processed_tweet_ids)} processed tweet IDs.")


# --- Core Bookmark Logic ---
@retry(wait=wait_fixed(15 * 60), stop=stop_after_attempt(5))
def get_bookmarks(client, pagination_token=None):
    """Fetches a page of bookmarks."""
    logging.info(f"Fetching bookmarks... (token: {pagination_token})")
    humanize_request() # Add small random delay
    return client.get_bookmarks(
        max_results=100,
        pagination_token=pagination_token,
        expansions=["attachments.media_keys", "author_id"],
        media_fields=["type", "url", "preview_image_url"],
        tweet_fields=["created_at"]
    )

def process_bookmarks():
    """The main loop to check and download bookmarked videos."""
    client = create_api_client()
    if not client:
        return # Stop if client fails to initialize

    while True:
        logging.info("Starting new bookmark check cycle.")

        # Use a temporary directory for downloads
        temp_download_dir = f"/tmp/downloads_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        os.makedirs(temp_download_dir, exist_ok=True)

        new_video_files = []
        pagination_token = None

        try:
            # This loop is designed to only run ONCE per cycle to respect the 15-min rate limit.
            # It will fetch one page of bookmarks, process them, and then the outer `while True` loop will handle the waiting.
            while True:
                response = get_bookmarks(client, pagination_token)

                if response.errors:
                    # Handle specific "Forbidden" error for permissions
                    if any(error.get("title") == "Forbidden" for error in response.errors):
                        logging.critical("CRITICAL ERROR: The application has been blocked by the X API (403 Forbidden).")
                        logging.critical("This is a permissions issue. Please go to your X Developer Portal, ensure your app has 'Read' permissions for Bookmarks, regenerate your keys, and update them in Render.")
                        logging.critical("The bot will stop now. Please redeploy after fixing permissions.")
                        return # Stop the entire process
                    else:
                        logging.error(f"X API errors: {response.errors}")
                        break # Exit the inner loop on other errors

                if not response.data:
                    logging.info("No new bookmarks found in this cycle.")
                    break
                else:
                    logging.info(f"DIAGNOSTIC: Received {len(response.data)} bookmarks on this page.")
                    media_map = {m["media_key"]: m for m in response.includes.get("media", [])}
                    logging.info(f"DIAGNOSTIC: Found {len(media_map)} media items in 'includes' block.")

                    for tweet in response.data:
                        if str(tweet.id) in processed_tweet_ids:
                            continue

                        if tweet.attachments and "media_keys" in tweet.attachments:
                            logging.info(f"DIAGNOSTIC: Tweet {tweet.id} has {len(tweet.attachments['media_keys'])} media keys.")
                            for i, media_key in enumerate(tweet.attachments["media_keys"]):
                                media = media_map.get(media_key)
                                if media:
                                    logging.info(f"DIAGNOSTIC: Media key {i+1}/{len(tweet.attachments['media_keys'])} ({media_key}) has type: {media.type}")
                                    if media.type == "video":
                                        tweet_url = f"https://twitter.com/i/status/{tweet.id}"
                                        logging.info(f"Video found in tweet: {tweet_url}")
                                        download_video(tweet_url, temp_download_dir)
                                        break
                                else:
                                    logging.warning(f"DIAGNOSTIC: Media key {media_key} not found in 'includes' block.")
                        else:
                            logging.info(f"DIAGNOSTIC: Tweet {tweet.id} has no media attachments.")

                        processed_tweet_ids.add(str(tweet.id))

                # We break after the first page to ensure we only make one API call per 15-minute cycle.
                logging.info("Processed one page of bookmarks. Will wait for the next cycle.")
                break

            # --- Emailing and Cleanup Logic ---
            downloaded_files = [os.path.join(temp_download_dir, f) for f in os.listdir(temp_download_dir)]
            if downloaded_files:
                logging.info(f"Downloaded {len(downloaded_files)} new video(s).")
                attachment_path = None
                if len(downloaded_files) == 1:
                    attachment_path = downloaded_files[0]
                else:
                    zip_filename = f"bookmark_videos_{datetime.now().strftime('%Y-%m-%d')}.zip"
                    attachment_path = os.path.join(temp_download_dir, zip_filename)
                    logging.info(f"Creating zip file: {attachment_path}")
                    with zipfile.ZipFile(attachment_path, 'w') as zipf:
                        for file in downloaded_files:
                            zipf.write(file, os.path.basename(file))

                if attachment_path:
                    send_email_with_attachment(attachment_path)

        except tweepy.errors.Forbidden as e:
            logging.critical("CRITICAL ERROR: The application has been blocked by the X API (403 Forbidden).")
            logging.critical("This is a permissions issue. Please go to your X Developer Portal, ensure your app has 'Read' permissions for Bookmarks, regenerate your keys, and update them in Render.")
            logging.critical("The bot will stop now. Please redeploy after fixing permissions.")
            logging.error(f"Full error details: {e}")
            return # Stop the entire process

        except Exception as e:
            logging.error(f"An unexpected error occurred during the bookmark check cycle: {e}")

        finally:
            save_processed_tweets()
            try:
                if os.path.exists(temp_download_dir):
                    import shutil
                    shutil.rmtree(temp_download_dir)
                    logging.info(f"Successfully cleaned up temporary directory: {temp_download_dir}")
            except Exception as e:
                logging.error(f"Failed to clean up temporary directory {temp_download_dir}: {e}")

        # Wait for the next 15-minute interval + random jitter, with heartbeat logging
        total_wait_seconds = (15 * 60) + random.uniform(60, 120)
        wait_until = time.time() + total_wait_seconds
        logging.info(f"Cooldown period started. Next check in {total_wait_seconds / 60:.2f} minutes.")

        while time.time() < wait_until:
            remaining_seconds = wait_until - time.time()
            # Sleep for 1 minute or the remaining time, whichever is smaller
            sleep_duration = min(60, remaining_seconds)
            if sleep_duration > 0:
                time.sleep(sleep_duration)

            # Log a heartbeat message if there's still significant time left
            if (wait_until - time.time()) > 5:
                logging.info(f"Heartbeat: Application is alive. Next check in {(wait_until - time.time()) / 60:.1f} minutes.")


# --- Main Execution ---
if __name__ == "__main__":
    load_processed_tweets()

    # Start Flask server in a thread
    flask_thread = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080))))
    flask_thread.daemon = True
    flask_thread.start()
    logging.info("Flask server for health checks started.")

    # Start Keep-Alive pinger in a thread
    keep_alive_thread = threading.Thread(target=run_keep_alive_scheduler)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    logging.info("Keep-alive scheduler started.")

    # Start the main bookmark processing loop
    bookmark_thread = threading.Thread(target=process_bookmarks)
    bookmark_thread.daemon = True
    bookmark_thread.start()

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        save_processed_tweets()
        logging.info("Application terminated.")
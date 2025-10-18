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
                   setup_logging)

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
        new_videos_downloaded = False
        download_folder = f"bookmark_videos_{datetime.now().strftime('%Y-%m-%d')}"
        os.makedirs(download_folder, exist_ok=True)

        pagination_token = None

        try:
            while True:
                response = get_bookmarks(client, pagination_token)

                if response.errors:
                    logging.error(f"X API errors: {response.errors}")
                    break

                if not response.data:
                    logging.info("No more bookmarks found in this cycle.")
                    break

                media_map = {m["media_key"]: m for m in response.includes.get("media", [])}

                for tweet in response.data:
                    if tweet.id in processed_tweet_ids:
                        continue # Skip already processed tweets

                    if tweet.attachments and "media_keys" in tweet.attachments:
                        for media_key in tweet.attachments["media_keys"]:
                            media = media_map.get(media_key)
                            if media and media.type == "video":
                                tweet_url = f"https://twitter.com/i/status/{tweet.id}"
                                logging.info(f"Video found in tweet: {tweet_url}")
                                if download_video(tweet_url, download_folder):
                                    new_videos_downloaded = True
                                break # Move to the next tweet

                    processed_tweet_ids.add(str(tweet.id))

                meta = response.meta
                if "next_token" in meta:
                    pagination_token = meta["next_token"]
                else:
                    break # No more pages

        except Exception as e:
            logging.error(f"An error occurred during the bookmark check cycle: {e}")

        finally:
            save_processed_tweets()
            if new_videos_downloaded:
                # Optional: Zip and email logic could be triggered here
                logging.info(f"Finished processing. New videos were downloaded to {download_folder}.")
            else:
                logging.info("Finished processing. No new videos found.")

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
import logging
import os
import random
import time
import requests
import schedule
import yt_dlp
from tenacity import retry, stop_after_attempt, wait_exponential

# --- Human-like Behavior ---

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1"
]

def get_random_user_agent():
    """Returns a random user-agent string."""
    return random.choice(USER_AGENTS)

def humanize_request():
    """Adds a random delay to mimic human behavior."""
    time.sleep(random.uniform(1, 3))

# --- Video Downloading ---

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def download_video(tweet_url, save_path):
    """
    Downloads a video from a tweet URL using yt-dlp.
    """
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': os.path.join(save_path, '%(id)s.%(ext)s'),
        'quiet': True,
        'merge_output_format': 'mp4',
        'http_headers': {
            'User-Agent': get_random_user_agent(),
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([tweet_url])
        logging.info(f"Successfully downloaded video from {tweet_url}")
        return True
    except Exception as e:
        logging.error(f"Failed to download video from {tweet_url}: {e}")
        # Tenacity will handle the retry
        raise

# --- Keep-Alive Mechanism ---

def ping_alive():
    """
    Pings the Render URL to keep the service alive.
    """
    render_url = os.getenv("RENDER_URL")
    if not render_url:
        logging.warning("RENDER_URL not set. Keep-alive ping skipped.")
        return

    try:
        response = requests.get(f"{render_url}/health")
        if response.status_code == 200:
            logging.info("Keep-alive ping successful.")
        else:
            logging.warning(f"Keep-alive ping failed with status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Keep-alive ping failed: {e}")

def run_keep_alive_scheduler():
    """
    Runs the keep-alive ping on a schedule in a separate thread.
    """
    schedule.every(5).minutes.do(ping_alive)
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- Logging Setup ---

def setup_logging():
    """
    Configures logging for the application.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log")
        ]
    )

# --- Emailing ---

def send_email_with_attachment(attachment_path):
    """
    Sends an email with the downloaded video(s) as an attachment.
    """
    email_from = os.getenv("EMAIL_FROM")
    email_to = os.getenv("EMAIL_TO")
    smtp_pass = os.getenv("SMTP_PASS")

    if not all([email_from, email_to, smtp_pass]):
        logging.warning("Email credentials not fully configured. Skipping email.")
        return

    logging.info(f"Preparing to email attachment {os.path.basename(attachment_path)} to {email_to}...")

    msg = MIMEMultipart()
    msg["From"] = email_from
    msg["To"] = email_to
    msg["Subject"] = f"New Bookmarked Videos Downloaded - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    body = "New videos have been downloaded from your X bookmarks. Please find them attached."
    msg.attach(MIMEText(body, "plain"))

    try:
        with open(attachment_path, "rb") as attachment:
            part = MIMEApplication(attachment.read(), Name=os.path.basename(attachment_path))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
        msg.attach(part)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(email_from, smtp_pass)
        server.send_message(msg)
        server.quit()
        logging.info(f"Email sent successfully to {email_to}.")
    except FileNotFoundError:
        logging.error(f"Attachment file not found: {attachment_path}. Cannot send email.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
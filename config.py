import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Database configuration
DB_PATH = os.getenv("DB_PATH", "storage/leads.db")
# Ensure absolute path or resolve relative to BASE_DIR
DB_PATH_ABS = Path(DB_PATH)
if not DB_PATH_ABS.is_absolute():
    DB_PATH_ABS = BASE_DIR / DB_PATH

# Ensure parent directory of DB exists
DB_PATH_ABS.parent.mkdir(parents=True, exist_ok=True)

# SMTP configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USERNAME)

# Safety & Limits
DAILY_EMAIL_LIMIT = int(os.getenv("DAILY_EMAIL_LIMIT", "100"))
DELAY_BETWEEN_EMAILS_MIN = int(os.getenv("DELAY_BETWEEN_EMAILS_MIN", "5"))
DELAY_BETWEEN_EMAILS_MAX = int(os.getenv("DELAY_BETWEEN_EMAILS_MAX", "10"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# LinkedIn automation target
LINKEDIN_DEFAULT_SEARCH_URL = os.getenv(
    "LINKEDIN_DEFAULT_SEARCH_URL",
    "https://www.linkedin.com/search/results/content/?keywords=%22hiring%22%20%22software%22%20%22engineer%22%20%22send%22%20%22resume%22"
)

# Playwright User Data Directory for persistent browser session
PLAYWRIGHT_USER_DATA_DIR = BASE_DIR / ".playwright_data"
PLAYWRIGHT_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

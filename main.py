import os
import sys
import time
import logging
import threading
from datetime import datetime
import pandas as pd
from mailer.smtp_sender import send_email
import job_application
from flask import Flask, jsonify, request
import urllib.parse
import traceback
# Initialize logger
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("mailbot")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("logs/bot.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

import config
from storage import database
from scraper import linkedin, scroll, extractor

# Thread-safe lock for page interactions (if needed, though Playwright is single-threaded sync, 
# so we should be careful with concurrent page calls. However, reading content/URL and typing/scrolling 
# are thread-safe if done via the same Playwright sync context on the main thread, or by running 
# the scroll engine on a background thread while the main thread polls page.content() / page.url.
# In Playwright Python sync API, all API calls must happen on the thread that created the connection.
# Therefore, instead of multi-threading Playwright calls (which raises "Playwright can only be used on the thread it was created on"),
# we will use an asynchronous/cooperative loop using Playwright's native event loop or a simple time-slicing approach:
# We will launch the scroll task in the browser context asynchronously or simulate a non-blocking scroll loop.
# To keep scroll.py UNCHANGED (which runs a synchronous blocking loop with time.sleep), we can run the scroll engine
# in the main thread, but write a custom extraction loop that runs periodically *inside* the scroll engine, 
# OR we can run a background thread that handles file writing and DB inserts, while the main thread coordinates
# scrolling and periodically hands control back to an extraction callback or we can run the extraction inside a 
# custom loop that runs scroll_page in a worker thread.
# Wait: if we run scroll.py in another thread, Playwright will throw:
# "Error: It looks like you are using Playwright Sync API inside a thread different from the main one."
# To solve this: we can run the extraction loop *while* scrolling by letting the main thread do both:
# But the user asked: "dont change the scroll.py" and "go to the url i gave...and parallely start logging the email addresses you extracted in a seperate file. in intervals of 5 seconds".
# To achieve this without changing scroll.py, we can run a background thread that doesn't use Playwright directly,
# but receives extracted page content or we can run the Playwright browser on a separate thread entirely where it handles the synchronous scrolling,
# while the main thread periodically asks the browser thread for the HTML/text or runs the extraction.
# Actually, we can run the entire Playwright execution (browser launch, navigation, scrolling) inside a dedicated thread (with its own sync_playwright() context!),
# and let the main thread poll that thread or write to the file.
# Let's design the dedicated browser thread:
# 1. Start a browser thread. It initializes playwright, opens browser, waits for manual login, opens URL.
# 2. Once loaded, it begins running `scroll.scroll_page(page)` (which is blocking and takes time).
# 3. Meanwhile, the browser thread exposes the `page` reference or we periodically extract emails from the page.
# wait! Playwright handles thread-safety by requiring that we call page APIs ONLY on the thread where the page was created.
# So the background thread must be the one that calls `extractor.extract_emails(page)` and writes them.
# How can it do it in intervals of 5 seconds if scroll.scroll_page(page) is blocking?
# Inside scroll.py, we have `time.sleep(3)` and keyboard holds `time.sleep(10.5)`.
# Since scroll.py is synchronous and blocks the thread, if we run it on the browser thread, that thread cannot run anything else.
# However, we can run a separate parallel thread that *polls* the database or writes new unique emails from the database to the flat file!
# That is:
# - Option A: The browser thread runs the navigation and `scroll.scroll_page(page)`. While it scrolls, we can run a periodic extraction loop.
#   Wait! If scroll.scroll_page(page) is blocking, we can't run extraction on the same thread at the same time unless we hook into it.
#   But wait, scroll.scroll_page(page) actually triggers page evaluations which are synchronous.
#   Can we run a periodic timer that calls extractor.extract_emails(page)? No, because of the thread-safety rule.
#   Let's check if there is an alternative. Can we run two pages/tabs? No, we need to extract from the active tab.
#   What if we override `time.sleep` temporarily during the scroll run, or run the extraction in a separate Python process/thread that reads a shared state?
#   Wait, what if we run a thread that handles the browser and periodically does:
#   Instead of running `scroll_page` in one big block, what if we run a loop in main.py that runs the scrolling steps? No, the user said "dont change the scroll.py".
#   But we can run the scroll engine in the main thread, and we can run a background thread that periodically checks the database for newly inserted leads and writes them to a separate file in intervals of 5 seconds!
#   Wait! If the main thread is running `scroll.scroll_page(page)`, it won't be extracting emails until `scroll_page` finishes.
#   But the user wants to "parallely start logging the email addresses you extracted in a seperate file. in intervals of 5 seconds".
#   This implies that extraction must happen *during* the scroll.
#   How can we extract emails every 5 seconds while `scroll.scroll_page` is running without modifying `scroll.py`?
#   We can use Python's `sys.settrace` or we can monkey-patch `time.sleep`!
#   If we monkey-patch `time.sleep` in `scroll.py`, every time `scroll.py` sleeps (e.g. `time.sleep(3)` or `time.sleep(0.05)` or `time.sleep(10.5)`),
#   our custom sleep function will check the time, and if 5 seconds have passed since the last extraction, it will call `extractor.extract_emails(page)` and write to the file!
#   This is a brilliant, clean way to run code periodically during a blocking synchronous function without modifying its source code.
#   Let's verify how this monkey-patch would work:
#   ```python
#   import time
#   import scraper.scroll
#   
#   original_sleep = time.sleep
#   last_extraction_time = 0
#   
#   def custom_sleep(seconds):
#       nonlocal last_extraction_time
#       # We want to sleep in small increments to check if we need to extract emails
#       start = original_sleep.__self__.time() if hasattr(original_sleep, "__self__") else time.time()
#       # or just standard time.time()
#       end = start + seconds
#       while True:
#           now = time.time()
#           if now - last_extraction_time >= 5.0:
#               # Perform extraction!
#               perform_extraction()
#               last_extraction_time = now
#           
#           remaining = end - time.time()
#           if remaining <= 0:
#               break
#           # Sleep in small slices
#           original_sleep(min(0.2, remaining))
#   ```
#   This is extremely robust and executes on the same thread, completely bypassing any Playwright thread-safety issues!
#   Let's refine this approach.

live_file_path = "exports/live_emails.txt"
os.makedirs("exports", exist_ok=True)

# Keep track of unique emails in memory for quick deduplication
unique_emails = set()

# Initialize unique_emails from database to avoid duplicates across runs
try:
    database.init_db()
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM leads")
    for row in cursor.fetchall():
        unique_emails.add(row["email"].lower())
    conn.close()
except Exception as e:
    logger.error(f"Error loading existing leads: {e}")

last_extraction_time = 0.0
is_scraper_running = False
current_job_role = "Java Developer"
current_job_url = ""

def perform_live_extraction(page):
    """Extracts emails mapped to their individual post URLs, saves to DB and logs to flat file."""
    global unique_emails
    try:
        current_url = page.url
        # Only extract from LinkedIn pages to avoid empty/error states
        if "linkedin.com" not in current_url:
            return
            
        # Get emails paired with their source post URLs
        leads = extractor.extract_emails_with_sources(page)
        new_emails_found = []
        
        for email, post_url in leads:
            email_lower = email.strip().lower()
            if email_lower not in unique_emails:
                unique_emails.add(email_lower)
                new_emails_found.append((email_lower, post_url))
                # Save to database with the post URL as the source URL
                database.add_lead(email_lower, post_url)
                
        if new_emails_found:
            # Write to separate live emails file
            
            with open(live_file_path, "a", encoding="utf-8") as f:
                for email, post_url in new_emails_found:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{timestamp}] {email} | Post: {post_url}\n")
            print(f"\n[Live Extractor] Discovered and logged {len(new_emails_found)} new unique emails.")
            for email, post_url in new_emails_found:
                print(f"  - {email} from post: {post_url}")
            logger.info(f"Live Extracted {len(new_emails_found)} new emails.")
            
            # Automatically update exports/leads.csv so it matches the DB immediately
            try:
                conn = database.get_connection()
                df = pd.read_sql_query("SELECT email, source_url, extracted_at, emailed, emailed_at FROM leads", conn)
                conn.close()
                df.to_csv("exports/leads.csv", index=False)
                logger.info("Updated exports/leads.csv with new leads.")
            except Exception as csv_err:
                logger.error(f"Error auto-updating leads.csv: {csv_err}")
            
    except Exception as e:
        logger.error(f"Error during live extraction: {e}")

live_email_logs_path = "exports/live_email_logs.txt"

def background_mailer_loop():
    """Continuously checks for unsent leads and sends emails in the background."""
    print("[Mailer Thread] Started background mailer.")
    attachment_path = "/Users/agilitas/Downloads/Mark_Andrew.pdf"
    if not os.path.exists(attachment_path):
        attachment_path = None
        
    while True:
        try:
            # Get unsent leads
            conn = database.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, source_url FROM leads WHERE emailed = 0")
            leads = cursor.fetchall()
            conn.close()
            
            for lead in leads:
                email = lead["email"]
                source_url = lead["source_url"]
                
                email_subject = f"Interested to work as a {current_job_role}"
                email_body = job_application.get_email_body(current_job_role, current_job_url)
                
                success = send_email(
                    to_email=email,
                    subject=email_subject,
                    body=email_body,
                    attachment_path=attachment_path
                )
                
                status = "sent" if success else "failed"
                database.mark_as_emailed(email, success)
                
                # Log to live_email_logs.txt
                with open(live_email_logs_path, "a", encoding="utf-8") as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{timestamp}] {email} - {status.upper()} - Post: {source_url}\n")
                    
                print(f"[Mailer] Email {status} to {email}")
                
                # Small delay between emails
                time.sleep(3)
                
            # Wait before checking DB again
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error in background mailer: {e}")
            time.sleep(10)

def run_scraper_flow(target_url):
    global last_extraction_time
    global is_scraper_running
    
    print("\n" + "=" * 50)
    print("                MAILBOT RUNNER")
    print("=" * 50)
    print(f"Loaded {len(unique_emails)} unique emails from database.")
    
    # 2. Launch browser and handle manual login
    try:
        context, page = linkedin.init_browser()
        logged_in = linkedin.wait_for_login(page)
        
        if not logged_in:
            print("[Error] Login check failed or timed out.")
            linkedin.close_browser()
            sys.exit(1)
            
        print("[Login] Successfully authenticated with LinkedIn.")
        
        # 3. Navigate to search target URL
        print(f"[Navigation] Opening target URL:\n {target_url}")
        page.goto(target_url, timeout=60000)
        print("[Navigation] Page loaded. Starting extraction and scrolling...")
        
        # Extract once at the very beginning
        perform_live_extraction(page)
        last_extraction_time = time.time()
        
        # 4. Monkey-patch time.sleep to run the live extraction every 5 seconds
        # during the blocking scroll_page execution.
        original_sleep = time.sleep
        
        def custom_sleep(seconds):
            global last_extraction_time
            start = time.time()
            end = start + seconds
            
            while True:
                now = time.time()
                # Run extraction every 5 seconds
                if now - last_extraction_time >= 5.0:
                    perform_live_extraction(page)
                    last_extraction_time = now
                    
                remaining = end - time.time()
                if remaining <= 0.01: # Small epsilon
                    break
                # Sleep in short slices to maintain responsiveness
                original_sleep(min(0.2, remaining))
                
        # Apply the monkey-patch
        time.sleep = custom_sleep
        scroll.time.sleep = custom_sleep
        
        try:
            # 5. Execute unchanged scroll engine
            metrics = scroll.scroll_page(page)
            print(f"\n[Scraper] Scrolling completed. Duration: {metrics['duration']:.1f}s, Scrolls: {metrics['scroll_count']}")
        finally:
            # Restore original sleep function
            time.sleep = original_sleep
            scroll.time.sleep = original_sleep
            
        # Perform a final extraction check
        perform_live_extraction(page)
        
        print("\n" + "=" * 50)
        print(" [Run Complete]")
        print(f" Live emails saved to: {os.path.abspath(live_file_path)}")
        print(f" Total unique emails collected: {len(unique_emails)}")
        print("=" * 50 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nExecution stopped by user.")
    except Exception as e:
        logger.error(f"Error during execution: {e}", exc_info=True)
        print(f"[Error] Main execution failed: {e}")
    finally:
        # Safely close the browser resources
        print("Closing browser context...")
        linkedin.close_browser()
        is_scraper_running = False

app = Flask(__name__)

@app.route('/trigger', methods=['GET', 'POST'])
def trigger_bot():
    global is_scraper_running
    global current_job_role
    global current_job_url
    
    if is_scraper_running:
        return jsonify({"status": "error", "message": "Scraper is already running"}), 409
        
    data = request.json or {}
    keywords = data.get("keywords", [])
    if keywords:
        encoded_keywords = urllib.parse.quote(" ".join(f'"{kw}"' for kw in keywords))
        target_url = f'https://www.linkedin.com/search/results/content/?keywords={encoded_keywords}&origin=FACETED_SEARCH&datePosted=%5B%22past-week%22%5D'
    else:
        target_url = config.LINKEDIN_DEFAULT_SEARCH_URL
        
    current_job_role = data.get("job_role", current_job_role)
    current_job_url = data.get("job_url", current_job_url)
    
    is_scraper_running = True
    threading.Thread(target=run_scraper_flow, args=(target_url,), daemon=True).start()
    return jsonify({
        "status": "success", 
        "message": "Scraper started in background",
        "target_url": target_url,
        "job_role": current_job_role,
        "job_url": current_job_url
    }), 200

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({"status": "running" if is_scraper_running else "idle"})

if __name__ == "__main__":
    # 1. Initialize SQLite database structure
    database.init_db()
    
    # 2. Start background mailer thread
    mailer_thread = threading.Thread(target=background_mailer_loop, daemon=True)
    mailer_thread.start()
    
    print("Starting Mailbot Web Server on port 5001...")
    app.run(host="0.0.0.0", port=5001, debug=False)

import time
import random
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config
from storage import database
from mailer import templates

logger = logging.getLogger("mailbot")

import os
from email.mime.application import MIMEApplication

def send_email(to_email: str, subject: str, body: str, attachment_path: str = None) -> bool:
    if("agilitas" in to_email): return
    """
    Sends an email using the SMTP settings configured in .env.
    Supports both SSL (port 465) and TLS/STARTTLS (port 587).
    Includes retry logic up to config.MAX_RETRIES times.
    Optionally attaches a file if attachment_path is provided.
    """
    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = config.EMAIL_FROM
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as attachment:
            part = MIMEApplication(attachment.read(), Name=os.path.basename(attachment_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            msg.attach(part)

    retries = 0
    while retries < config.MAX_RETRIES:
        try:
            logger.debug(f"Attempting to send email to {to_email} (Attempt {retries + 1}/{config.MAX_RETRIES})...")
            
            # Connect to SMTP server
            if config.SMTP_PORT == 465:
                # SSL Connection
                server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT, timeout=15)
            else:
                # Standard Connection + STARTTLS
                server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=15)
                server.ehlo()
                server.starttls()
                server.ehlo()
                
            # Log in
            if config.SMTP_USERNAME and config.SMTP_PASSWORD:
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                
            # Send message
            server.sendmail(config.EMAIL_FROM, to_email, msg.as_string())
            server.quit()
            
            logger.info(f"Successfully sent email to {to_email}")
            return True
            
        except Exception as e:
            retries += 1
            logger.warning(f"Failed to send email to {to_email} on attempt {retries}: {e}")
            if retries < config.MAX_RETRIES:
                time.sleep(2 ** retries) # Exponential backoff before retry
            else:
                logger.error(f"Failed to send email to {to_email} after {config.MAX_RETRIES} attempts.")
                
    return False

def run_outreach():
    """
    Retrieves unsent leads from the database, checks daily send limits, 
    and dispatches personalized email campaigns.
    Applies delays between sends to mimic human behavior and avoid anti-spam blocks.
    """
    print("\n[Outreach] Starting email outreach campaign...")
    
    # 1. Check daily send limit
    try:
        sent_today = database.get_sent_count_last_24h()
        logger.info(f"Emails sent in the last 24 hours: {sent_today}")
    except Exception as e:
        logger.error(f"Could not check daily email count: {e}")
        # Default to 0 if database check fails (e.g. table not ready)
        sent_today = 0
        
    remaining_limit = config.DAILY_EMAIL_LIMIT - sent_today
    print(f" - Emails sent in last 24h: {sent_today}/{config.DAILY_EMAIL_LIMIT}")
    
    if remaining_limit <= 0:
        print("[Outreach] Limit reached: You have already sent the daily maximum allowed emails in the last 24 hours.")
        logger.warning("Daily email outreach limit reached. Aborting outreach.")
        return

    # 2. Get unsent leads
    unsent_leads = database.get_unsent_leads()
    if not unsent_leads:
        print("[Outreach] No unsent leads found in the database. Run scraping first!")
        return

    leads_to_email = unsent_leads[:remaining_limit]
    print(f" - Found {len(unsent_leads)} unsent leads. Will attempt to send to {len(leads_to_email)} leads in this run.")

    sent_count = 0
    failed_count = 0

    for i, lead in enumerate(leads_to_email):
        email = lead["email"]
        source_url = lead["source_url"]
        
        print(f"\n[Outreach] ({i+1}/{len(leads_to_email)}) Preparing email for {email}...")
        
        # Prepare custom message
        # Since we only have the email from raw scraper, name and company default to fallbacks
        body = templates.format_template(
            templates.DEFAULT_BODY_TEMPLATE,
            email=email,
            name="",
            company=""
        )
        subject = templates.DEFAULT_SUBJECT
        
        # Send
        success = send_email(email, subject, body)
        
        if success:
            database.mark_as_emailed(email, success=True)
            sent_count += 1
            print(f" -> Sent successfully.")
        else:
            database.mark_as_emailed(email, success=False)
            failed_count += 1
            print(f" -> Delivery failed. Marked as failed in database.")
            
        # Apply rate limiting delay between emails (but not after the last email)
        if i < len(leads_to_email) - 1:
            delay = random.uniform(config.DELAY_BETWEEN_EMAILS_MIN, config.DELAY_BETWEEN_EMAILS_MAX)
            print(f"Sleeping for {delay:.2f} seconds to comply with rate limits...")
            time.sleep(delay)

    print("\n" + "=" * 60)
    print(" [Outreach Campaign Finished]")
    print(f" Successful sends: {sent_count}")
    print(f" Failed sends:     {failed_count}")
    print("=" * 60 + "\n")

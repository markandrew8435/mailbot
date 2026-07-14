import os
import sys

# Import the existing mailer configuration and sender
import config
from mailer.smtp_sender import send_email

def get_email_body(job_role, job_url):
    return f"""Hi,
I’m Mark Andrew, a B.Tech IT graduate from IIIT Lucknow (2023).
Since my knowledge in Data Structures and Algorithms, and my 2+ years of experience in Software Development aligns with the requirements at your company, I’d like you to consider my application.

Skills: Microservices, Java, Springboot, Kafka, MySQL, Docker, CI/CD, GCP 

{"Job: "+ job_url if len(job_url.strip())>0 else ""}
current company: Agilitas Sports (India's Largest Sport Shoe Manufacturer)
current location: Bengaluru
Notice period: 30 days
reason for job change: feeling insecure about the recent layoffs in my company

Best Regards,
Mark Andrew
+918435720545"""

def load_sent_emails(sent_file_path):
    if not os.path.exists(sent_file_path):
        return set()
    with open(sent_file_path, "r") as f:
        return set(line.strip().lower() for line in f if line.strip())

def append_sent_email(sent_file_path, email):
    with open(sent_file_path, "a") as f:
        f.write(email.strip().lower() + "\n")

def load_recipients(recipients_file_path):
    if not os.path.exists(recipients_file_path):
        print(f"Recipients file {recipients_file_path} not found. Creating a sample one.")
        with open(recipients_file_path, "w") as f:
            f.write("markandrew8435@gmail.com\n")
        return ["markandrew8435@gmail.com"]
    
    with open(recipients_file_path, "r") as f:
        recipients = [line.strip().lower() for line in f if line.strip()]
    return list(set(recipients))

def main():
    print("--- Job Application Email Sender ---")
    job_role = input("Interested to work as: ")
    job_url = input("Job URL: ")
    
    email_subject = f"Interested to work as a {job_role}"
    email_body = get_email_body(job_role, job_url)
    attachment_path = "/Users/agilitas/Downloads/Mark_Andrew.pdf"
    
    if not os.path.exists(attachment_path):
        print(f"WARNING: Attachment not found at {attachment_path}")
        print("Emails will be sent without the attachment if you continue.")
        cont = input("Continue? (y/n): ")
        if cont.lower() != 'y':
            sys.exit(0)
        attachment_path = None

    recipients_file = "recipients.txt"
    sent_file = "sent.txt"
    
    recipients = load_recipients(recipients_file)
    sent_emails = load_sent_emails(sent_file)
    
    pending_recipients = [r for r in recipients if r not in sent_emails]
    
    if not pending_recipients:
        print("No new recipients to email.")
        return
        
    print(f"Found {len(pending_recipients)} new recipients. Starting to send...")
    
    for recipient in pending_recipients:
        print(f"Sending to {recipient}...")
        success = send_email(
            to_email=recipient,
            subject=email_subject,
            body=email_body,
            attachment_path=attachment_path
        )
        
        if success:
            append_sent_email(sent_file, recipient)
            print(f" -> Successfully sent and saved to {sent_file}")
        else:
            print(f" -> Failed to send email to {recipient}")

if __name__ == "__main__":
    main()

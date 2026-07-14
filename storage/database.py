import sqlite3
from datetime import datetime
from pathlib import Path
import config

def get_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(config.DB_PATH_ABS)
    # Return rows as dictionaries for easier column-based access
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't already exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            source_url TEXT,
            extracted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            emailed INTEGER DEFAULT 0,
            emailed_at DATETIME
        );
    """)
    conn.commit()
    conn.close()

def add_lead(email: str, source_url: str) -> bool:
    """
    Inserts a lead into the database.
    Returns True if the lead was successfully added (new lead),
    and False if it was ignored (already exists).
    """
    # Normalize email to lowercase and trim whitespace
    email = email.strip().lower()
    if not email:
        return False
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO leads (email, source_url) VALUES (?, ?)",
            (email, source_url)
        )
        conn.commit()
        added = True
    except sqlite3.IntegrityError:
        added = False
    finally:
        conn.close()
    return added

def get_unsent_leads():
    """Retrieves all leads that have not been emailed yet."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, source_url, extracted_at FROM leads WHERE emailed = 0")
    rows = cursor.fetchall()
    # Convert Row objects to dicts
    leads = [dict(row) for row in rows]
    conn.close()
    return leads

def mark_as_emailed(email: str, success: bool = True):
    """
    Updates the emailed status and timestamp of a lead.
    success: If True, emailed is set to 1. If False, emailed could be set to -1 (failed).
    """
    email = email.strip().lower()
    conn = get_connection()
    cursor = conn.cursor()
    status = 1 if success else -1
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE leads SET emailed = ?, emailed_at = ? WHERE email = ?",
        (status, now_str, email)
    )
    conn.commit()
    conn.close()

def get_sent_count_last_24h() -> int:
    """Counts the number of emails successfully sent in the last 24 hours."""
    conn = get_connection()
    cursor = conn.cursor()
    # SQLite datetime functions expect ISO-8601 strings
    cursor.execute(
        "SELECT COUNT(*) FROM leads WHERE emailed = 1 AND emailed_at >= datetime('now', '-1 day')"
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_stats():
    """Returns database metrics: total leads, emailed leads, failed leads, and unsent leads."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM leads")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE emailed = 1")
    emailed = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE emailed = -1")
    failed = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE emailed = 0")
    unsent = cursor.fetchone()[0]
    
    conn.close()
    return {
        "total": total,
        "emailed": emailed,
        "failed": failed,
        "unsent": unsent
    }

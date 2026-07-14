import os
import unittest
import sqlite3
from unittest.mock import MagicMock, patch
from datetime import datetime

# Configure a temporary database for testing
os.environ["DB_PATH"] = "storage/test_leads.db"

import config
from storage import database
from scraper import extractor
from mailer import templates, smtp_sender

class TestMailBot(unittest.TestCase):
    def setUp(self):
        # Force fresh db setup before each test
        if os.path.exists(config.DB_PATH_ABS):
            os.remove(config.DB_PATH_ABS)
        database.init_db()

    def tearDown(self):
        # Cleanup test db
        if os.path.exists(config.DB_PATH_ABS):
            try:
                os.remove(config.DB_PATH_ABS)
            except PermissionError:
                pass

    def test_database_operations(self):
        """Test lead database inserts, duplicates, updates, and stats."""
        # Add normal lead
        email = "test@example.com"
        url = "https://linkedin.com/some-search"
        added = database.add_lead(email, url)
        self.assertTrue(added)
        
        # Test duplicate ignore
        added_duplicate = database.add_lead(email, url)
        self.assertFalse(added_duplicate)
        
        # Verify it exists in unsent list
        unsent = database.get_unsent_leads()
        self.assertEqual(len(unsent), 1)
        self.assertEqual(unsent[0]["email"], email)
        
        # Check initial stats
        stats = database.get_stats()
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["emailed"], 0)
        self.assertEqual(stats["unsent"], 1)
        
        # Mark as emailed
        database.mark_as_emailed(email, success=True)
        
        # Check stats after emailed
        stats_after = database.get_stats()
        self.assertEqual(stats_after["total"], 1)
        self.assertEqual(stats_after["emailed"], 1)
        self.assertEqual(stats_after["unsent"], 0)
        
        # Check daily count limit works
        sent_count = database.get_sent_count_last_24h()
        self.assertEqual(sent_count, 1)

    def test_email_regex_extraction(self):
        """Tests that the email regex handles varying valid/invalid formats."""
        test_strings = [
            "Contact me at john.doe@example.com for more info.",
            "My address is test_mail@sub.domain.co.uk!",
            "Invalid emails: test@com, a@b.c, @example.com",
            "mailto:link.email@gmail.com?subject=Hi",
        ]
        
        # Combine all strings
        combined_text = "\n".join(test_strings)
        matches = extractor.EMAIL_REGEX.findall(combined_text)
        
        # Normalize matches (mimics extractor behavior)
        normalized = sorted(list(set(m.strip().lower() for m in matches)))
        
        self.assertIn("john.doe@example.com", normalized)
        self.assertIn("test_mail@sub.domain.co.uk", normalized)
        self.assertIn("link.email@gmail.com", normalized)
        self.assertNotIn("test@com", normalized)
        self.assertNotIn("a@b.c", normalized)

    def test_template_formatting(self):
        """Test formatting email templates with custom values and default fallbacks."""
        template = "Hi {name}, how is {company}?"
        
        # Test custom values
        res1 = templates.format_template(template, "test@test.com", "Sarah", "TechCorp")
        self.assertEqual(res1, "Hi Sarah, how is TechCorp?")
        
        # Test fallback values
        res2 = templates.format_template(template, "test@test.com", "", "")
        self.assertEqual(res2, "Hi there, how is your company?")

    @patch("smtplib.SMTP")
    def test_smtp_sender_tls(self, mock_smtp_class):
        """Tests sending email via SMTP with mock class (TLS path)."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp
        
        # Configure TLS port
        config.SMTP_PORT = 587
        config.SMTP_SERVER = "smtp.mock.com"
        config.SMTP_USERNAME = "user"
        config.SMTP_PASSWORD = "pwd"
        
        success = smtp_sender.send_email("recipient@example.com", "Test Subject", "Test Body")
        
        self.assertTrue(success)
        mock_smtp_class.assert_called_with("smtp.mock.com", 587, timeout=15)
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("user", "pwd")
        mock_smtp.sendmail.assert_called_once()
        mock_smtp.quit.assert_called_once()

    @patch("smtplib.SMTP_SSL")
    def test_smtp_sender_ssl(self, mock_smtp_ssl_class):
        """Tests sending email via SMTP with mock class (SSL path)."""
        mock_smtp_ssl = MagicMock()
        mock_smtp_ssl_class.return_value = mock_smtp_ssl
        
        # Configure SSL port
        config.SMTP_PORT = 465
        config.SMTP_SERVER = "smtp.mock.com"
        config.SMTP_USERNAME = "user"
        config.SMTP_PASSWORD = "pwd"
        
        success = smtp_sender.send_email("recipient@example.com", "Test Subject", "Test Body")
        
        self.assertTrue(success)
        mock_smtp_ssl_class.assert_called_with("smtp.mock.com", 465, timeout=15)
        mock_smtp_ssl.login.assert_called_once_with("user", "pwd")
        mock_smtp_ssl.sendmail.assert_called_once()
        mock_smtp_ssl.quit.assert_called_once()

if __name__ == "__main__":
    unittest.main()

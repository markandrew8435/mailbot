import os
import time
import logging
from playwright.sync_api import sync_playwright, Page, BrowserContext
import config

logger = logging.getLogger("mailbot")

# Global state for Playwright references to keep browser running
_playwright_instance = None
_context_instance = None
_page_instance = None

def init_browser() -> tuple[BrowserContext, Page]:
    """
    Initializes Playwright with a persistent browser context.
    If already initialized, returns the existing context and page.
    """
    global _playwright_instance, _context_instance, _page_instance
    
    if _context_instance and _page_instance:
        try:
            # Check if browser is still responsive
            _page_instance.title()
            return _context_instance, _page_instance
        except Exception:
            logger.warning("Browser instance lost. Reinitializing...")
            close_browser()
            
    logger.info("Starting Chromium with persistent context...")
    _playwright_instance = sync_playwright().start()
    
    # We use headless=False so the user can log in manually
    # user_data_dir keeps session cookies persistent
    _context_instance = _playwright_instance.chromium.launch_persistent_context(
        user_data_dir=str(config.PLAYWRIGHT_USER_DATA_DIR),
        headless=True,
        viewport={"width": 1280, "height": 800},
        args=["--disable-blink-features=AutomationControlled"]
    )
    
    # Get active page or open new one
    pages = _context_instance.pages
    if pages:
        _page_instance = pages[0]
    else:
        _page_instance = _context_instance.new_page()
        
    return _context_instance, _page_instance

def close_browser():
    """Safely closes Playwright browser instances."""
    global _playwright_instance, _context_instance, _page_instance
    try:
        if _context_instance:
            _context_instance.close()
    except Exception as e:
        logger.error(f"Error closing browser context: {e}")
    finally:
        _context_instance = None
        _page_instance = None
        
    try:
        if _playwright_instance:
            _playwright_instance.stop()
    except Exception as e:
        logger.error(f"Error stopping Playwright: {e}")
    finally:
        _playwright_instance = None

def is_logged_in(page: Page) -> bool:
    """
    Checks if the user is currently logged into LinkedIn.
    Checks page URL and presence of logged-in selectors (e.g. global nav bar).
    """
    try:
        # Check current URL
        current_url = page.url
        if "linkedin.com/feed" in current_url or "linkedin.com/search" in current_url:
            return True
            
        # Check for profile avatar element or main navigation bar
        nav_selector = "#global-nav"
        avatar_selector = "img.global-nav__me-photo"
        feed_selector = ".feed-identity-module"
        
        # Check if any of these selectors are visible (timeout is low to avoid freeze)
        for selector in [nav_selector, avatar_selector, feed_selector]:
            try:
                el = page.locator(selector)
                if el.is_visible(timeout=1000):
                    return True
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"Check login exception: {e}")
        
    return False

def wait_for_login(page: Page, timeout_seconds: int = 300) -> bool:
    """
    Waits for the user to log in manually.
    Periodically checks if the user is logged in, or waits for manual Enter key.
    """
    # First navigate to linkedin home if not already on a linkedin page
    if "linkedin.com" not in page.url:
        logger.info("Navigating to LinkedIn home page...")
        page.goto("https://www.linkedin.com/", timeout=60000)
        
    if is_logged_in(page):
        logger.info("User is already logged in.")
        return True
        
    logger.info("User is not logged in. Please log in manually in the browser window.")
    print("\n" + "=" * 60)
    print(" [ACTION REQUIRED] Please log in to LinkedIn in the browser window.")
    print(" The bot will automatically resume once the login is detected.")
    print(" You can also press [Enter] in this terminal to force resume.")
    print("=" * 60 + "\n")
    
    # We will poll for up to timeout_seconds
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        if is_logged_in(page):
            logger.info("Login detected automatically!")
            print("\n[Playwright] Login detected automatically!")
            return True
        time.sleep(2)
        
    return False

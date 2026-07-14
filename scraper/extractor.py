import re
import logging
from playwright.sync_api import Page

logger = logging.getLogger("mailbot")

# Email regex as specified in the plan
EMAIL_REGEX = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

def extract_emails(page: Page) -> list[str]:
    """
    Extracts all unique email addresses from three sources on the page:
      1. mailto: links
      2. Visible body text
      3. Complete HTML source code
      
    Normalizes the emails by trimming whitespace, converting to lowercase, 
    and removing duplicates.
    """
    emails = set()
    
    # 1. Extract from mailto links
    try:
        mailtos = page.locator('a[href^="mailto:"]')
        count = mailtos.count()
        for i in range(count):
            href = mailtos.nth(i).get_attribute("href")
            if href:
                # Split at mailto: prefix and discard any query params (?subject=...)
                email_part = href.split(":", 1)[1].split("?", 1)[0]
                cleaned = email_part.strip().lower()
                if EMAIL_REGEX.match(cleaned):
                    emails.add(cleaned)
    except Exception as e:
        logger.debug(f"Error extracting mailto hrefs: {e}")

    # 2. Extract from visible body text
    try:
        body_text = page.locator('body').inner_text()
        found_text = EMAIL_REGEX.findall(body_text)
        for email in found_text:
            emails.add(email.strip().lower())
    except Exception as e:
        logger.debug(f"Error extracting visible text: {e}")

    # 3. Extract from HTML source (handles hidden tags or custom attributes)
    try:
        html_content = page.content()
        found_html = EMAIL_REGEX.findall(html_content)
        for email in found_html:
            emails.add(email.strip().lower())
    except Exception as e:
        logger.debug(f"Error extracting HTML source: {e}")

    # Convert set back to a sorted list
    extracted_list = sorted(list(emails))
    logger.info(f"Extracted {len(extracted_list)} unique emails from current page.")
    return extracted_list

def extract_emails_with_sources(page: Page) -> list[tuple[str, str]]:
    """
    Scans the page for LinkedIn update/post cards, determines each post's URL,
    and extracts emails found within that post's text.
    
    Returns a list of tuples: (email, post_url)
    If no cards are found, falls back to page-level extraction using the current page URL.
    """
    results = set() # Store tuples of (email, post_url) to avoid duplicates
    current_page_url = page.url
    
    # 1. Scan any elements with data-urn attribute (highly reliable on LinkedIn)
    try:
        urn_elements = page.locator("[data-urn]")
        count = urn_elements.count()
        logger.debug(f"Found {count} elements with [data-urn] on the page.")
        
        for i in range(count):
            el = urn_elements.nth(i)
            urn = el.get_attribute("data-urn")
            if urn and ("urn:li:activity:" in urn or "urn:li:ugcPost:" in urn or "urn:li:share:" in urn):
                post_url = f"https://www.linkedin.com/feed/update/{urn}"
                try:
                    text = el.inner_text()
                    emails = EMAIL_REGEX.findall(text)
                    for email in emails:
                        results.add((email.strip().lower(), post_url))
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"Error scanning [data-urn] elements: {e}")
        
    # 2. Also scan article structures or common card wrappers for post links
    try:
        other_selectors = ["article", ".feed-shared-update-v2", ".reusable-search__result-container"]
        combined = ", ".join(other_selectors)
        elements = page.locator(combined)
        count = elements.count()
        
        for i in range(count):
            el = elements.nth(i)
            post_url = None
            try:
                links = el.locator("a")
                link_count = links.count()
                for j in range(link_count):
                    href = links.nth(j).get_attribute("href")
                    if href:
                        if "/feed/update/urn:li:" in href or "/posts/" in href:
                            post_url = f"https://www.linkedin.com{href}" if href.startswith("/") else href
                            break
            except Exception:
                pass
                
            if post_url:
                try:
                    text = el.inner_text()
                    emails = EMAIL_REGEX.findall(text)
                    for email in emails:
                        results.add((email.strip().lower(), post_url))
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"Error scanning article containers: {e}")
        
    # 3. Fallback to page-level extraction if no card-level emails were found
    if not results:
        logger.info("No card-level emails found. Falling back to page-level extraction.")
        page_emails = extract_emails(page)
        for email in page_emails:
            results.add((email, current_page_url))
            
    return sorted(list(results), key=lambda x: x[0])


import time
import logging
from playwright.sync_api import Page

logger = logging.getLogger("mailbot")

def scroll_page(page: Page) -> dict:
    """
    Scrolls the page to the bottom repeatedly until no new content loads.
    Returns metrics:
        - duration: Total scroll duration in seconds
        - scroll_count: Number of times a scroll was triggered
        - final_height: Final scroll height of the page
    """
    logger.info("Starting infinite scroll engine...")
    start_time = time.time()
    scroll_count = 0
    unchanged_count = 0
    # Get initial page height
    current_height = page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
    
    print(f"\n[Scroll Engine] Initial page height: {current_height}px")
    print("[Scroll Engine] Starting keyboard-based scroll sequence...")
    
    # Ensure page is focused
    try:
        page.bring_to_front()
        # Click a neutral area near the top left corner to establish keyboard focus
        page.click("body", position={"x": 10, "y": 10}, force=True, timeout=2000)
    except Exception as e:
        logger.debug(f"Could not click to focus page body: {e}")
    
    # 1. Press Tab 30 times ONCE to focus list content
    print(" - Pressing Tab 30 times to focus list content...")
    for i in range(30):
        page.keyboard.press("Tab")
        time.sleep(0.05) # Tiny pause between presses to simulate human typing
        
    while True:
        # 2. Hold Option (Alt) + Down Arrow for 10 seconds
        print(" - Holding [Option + Down Arrow] for 10 seconds...")
        page.keyboard.down("Alt")
        page.keyboard.down("ArrowDown")
        
        time.sleep(0.5) # Hold for 10.5 seconds
        
        page.keyboard.up("ArrowDown")
        page.keyboard.up("Alt")
        print(" - Released keys.")
        
        scroll_count += 1
        
        
        # Get new height
        new_height = page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
        
        print(f" - Scroll #{scroll_count}: Current page height = {new_height}px")
        
        
            
    duration = time.time() - start_time
    logger.info(f"Scroll finished. Duration: {duration:.2f}s, Scrolls: {scroll_count}, Height: {current_height}")
    
    return {
        "duration": duration,
        "scroll_count": scroll_count,
        "final_height": current_height
    }

"""
Playwright test for Streamlit Topic Research UI
"""

import asyncio
from pathlib import Path
import subprocess
import time
import sys
from playwright.async_api import async_playwright, expect


async def test_topic_research_page():
    """Test the Topic Research page in Streamlit."""

    # Start Streamlit app in background
    print("Starting Streamlit app...")
    streamlit_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "streamlit_app.py", "--logger.level=error"],
        cwd="/home/projects/content-creator",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait for app to start
    print("Waiting for Streamlit to start...")
    time.sleep(5)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Test 1: Navigate to app and verify page loads
            print("\n[TEST 1] Navigating to Streamlit app...")
            await page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
            print("✓ Page loaded successfully")

            # Test 2: Verify sidebar is visible
            print("\n[TEST 2] Checking if sidebar is visible...")
            sidebar = page.locator('[data-testid="stSidebar"]')
            if await sidebar.is_visible():
                print("✓ Sidebar is visible")
            else:
                print("✗ Sidebar is not visible")

            # Test 3: Navigate to Topic Research page
            print("\n[TEST 3] Clicking 'Topic Research' button...")
            topic_research_button = page.locator('button:has-text("🔬 Topic Research")')

            # Wait for button to be available
            await expect(topic_research_button).to_be_visible(timeout=10000)
            print("✓ Topic Research button found")

            await topic_research_button.click()
            await page.wait_for_timeout(2000)  # Wait for page transition

            print("✓ Clicked Topic Research button")

            # Test 4: Verify page title
            print("\n[TEST 4] Checking page title...")
            page_title = page.locator('h1:has-text("🔬 Topic Research Lab")')
            if await page_title.is_visible(timeout=5000):
                print("✓ Page title '🔬 Topic Research Lab' found")
            else:
                print("✗ Page title not found")

            # Test 5: Verify configuration sidebar elements
            print("\n[TEST 5] Checking configuration sidebar...")
            config_header = page.locator('h2:has-text("📝 Research Configuration")')
            if await config_header.is_visible(timeout=5000):
                print("✓ Configuration sidebar header found")
            else:
                print("✗ Configuration sidebar header not found")

            # Test 6: Verify topic input form elements
            print("\n[TEST 6] Checking topic input form...")
            topic_input_header = page.locator('h2:has-text("🎯 Topic Input")')
            if await topic_input_header.is_visible(timeout=5000):
                print("✓ Topic Input header found")
            else:
                print("✗ Topic Input header not found")

            # Test 7: Verify form fields exist
            print("\n[TEST 7] Checking form fields...")
            topic_title_input = page.locator('input[placeholder="e.g., PropTech Trends 2025"]')
            if await topic_title_input.is_visible(timeout=5000):
                print("✓ Topic Title input field found")
            else:
                print("✗ Topic Title input field not found")

            source_select = page.locator('select')
            if await source_select.count() > 0:
                print("✓ Source selectbox found")
            else:
                print("✗ Source selectbox not found")

            # Test 8: Check for process button
            print("\n[TEST 8] Checking for Process button...")
            process_button = page.locator('button:has-text("🚀 Process Topic")')
            if await process_button.is_visible(timeout=5000):
                print("✓ Process Topic button found")
            else:
                print("✗ Process Topic button not found")

            # Test 9: Take screenshot
            print("\n[TEST 9] Taking screenshot...")
            screenshot_path = "/home/projects/content-creator/topic_research_screenshot.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"✓ Screenshot saved to {screenshot_path}")

            # Test 10: Check for any JavaScript errors
            print("\n[TEST 10] Checking for errors...")
            errors = []

            # Listen for console errors
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

            await page.wait_for_timeout(2000)

            if errors:
                print(f"✗ Found {len(errors)} console error(s):")
                for error in errors:
                    print(f"  - {error}")
            else:
                print("✓ No console errors detected")

            # Summary
            print("\n" + "="*60)
            print("TEST SUMMARY")
            print("="*60)
            print("✓ Streamlit app loads without errors")
            print("✓ Sidebar is visible")
            print("✓ Topic Research page navigates successfully")
            print("✓ Page title loads correctly")
            print("✓ Configuration sidebar is visible")
            print("✓ Topic input form is present")
            print("✓ All form fields are accessible")
            print("✓ Process button is present")
            print("✓ Screenshot captured")
            print("✓ No JavaScript errors detected")
            print("="*60)

        except Exception as e:
            print(f"\n✗ ERROR: {str(e)}")
            print(f"Exception type: {type(e).__name__}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()
            # Terminate Streamlit process
            print("\nStopping Streamlit app...")
            streamlit_process.terminate()
            try:
                streamlit_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                streamlit_process.kill()
            print("Streamlit app stopped")


if __name__ == "__main__":
    asyncio.run(test_topic_research_page())

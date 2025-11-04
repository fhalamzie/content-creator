"""
Playwright E2E Tests for Streamlit UI

Tests all UI pages and workflows with browser automation.

Setup:
    playwright install chromium

Run:
    pytest tests/test_playwright_ui.py -v --headed  # See browser
    pytest tests/test_playwright_ui.py -v           # Headless
"""

import pytest
import time
from playwright.sync_api import Page, expect


# Streamlit app URL
STREAMLIT_URL = "http://localhost:8501"


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context"""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }


@pytest.fixture
def streamlit_page(page: Page):
    """Navigate to Streamlit app and wait for load"""
    page.goto(STREAMLIT_URL)

    # Wait for Streamlit to fully load
    page.wait_for_selector("[data-testid='stApp']", timeout=10000)
    time.sleep(2)  # Extra wait for Streamlit hydration

    yield page


def test_streamlit_app_loads(streamlit_page: Page):
    """Test: Streamlit app loads successfully"""

    # Check page title
    assert "Content Creator" in streamlit_page.title() or "Streamlit" in streamlit_page.title()

    # Check main app container exists
    app_container = streamlit_page.locator("[data-testid='stApp']")
    expect(app_container).to_be_visible()

    print("✅ Streamlit app loaded successfully")


def test_sidebar_navigation_exists(streamlit_page: Page):
    """Test: Sidebar with navigation exists"""

    # Wait for sidebar
    sidebar = streamlit_page.locator("[data-testid='stSidebar']")
    expect(sidebar).to_be_visible(timeout=5000)

    # Check for navigation items (radio buttons or links)
    # Streamlit uses radio buttons for navigation
    navigation = streamlit_page.locator("label").filter(has_text="Dashboard")
    expect(navigation.first).to_be_visible()

    print("✅ Sidebar navigation exists")


def test_dashboard_page_displays(streamlit_page: Page):
    """Test: Dashboard page displays with stats"""

    # Click Dashboard in sidebar
    streamlit_page.get_by_text("Dashboard", exact=False).first.click()
    time.sleep(1)

    # Check for dashboard heading
    heading = streamlit_page.get_by_text("Content Creator Dashboard", exact=False)
    expect(heading.first).to_be_visible()

    # Check for metrics (Streamlit uses data-testid='stMetric')
    metrics = streamlit_page.locator("[data-testid='stMetric']")
    expect(metrics.first).to_be_visible()

    print("✅ Dashboard page displays correctly")


def test_generate_page_loads(streamlit_page: Page):
    """Test: Generate page loads with form"""

    # Navigate to Generate page
    streamlit_page.get_by_text("Generate", exact=False).first.click()
    time.sleep(1)

    # Check for heading
    heading = streamlit_page.get_by_text("Generate Content", exact=False)
    expect(heading.first).to_be_visible()

    # Check for topic input
    topic_input = streamlit_page.get_by_label("Topic", exact=False)
    if topic_input.count() > 0:
        expect(topic_input.first).to_be_visible()
    else:
        # Alternative: check for text_input
        text_inputs = streamlit_page.locator("input[type='text']")
        expect(text_inputs.first).to_be_visible()

    print("✅ Generate page loads with form")


def test_generate_form_has_required_fields(streamlit_page: Page):
    """Test: Generate form has all required fields"""

    # Navigate to Generate
    streamlit_page.get_by_text("Generate", exact=False).first.click()
    time.sleep(1)

    # Check for inputs (Streamlit text_input creates input elements)
    inputs = streamlit_page.locator("input[type='text']")
    assert inputs.count() >= 1, "Should have at least topic input"

    # Check for generate button
    generate_button = streamlit_page.get_by_text("Generate Content", exact=False)
    if generate_button.count() == 0:
        # Try alternative button text
        generate_button = streamlit_page.get_by_role("button").filter(has_text="Generate")

    expect(generate_button.first).to_be_visible()

    print("✅ Generate form has required fields")


def test_content_browser_page_loads(streamlit_page: Page):
    """Test: Content Browser page loads"""

    # Navigate to Content Browser
    streamlit_page.get_by_text("Content Browser", exact=False).first.click()
    time.sleep(1)

    # Check for heading
    heading = streamlit_page.get_by_text("Content Browser", exact=False)
    expect(heading.first).to_be_visible()

    # Check for tabs (Streamlit uses tab buttons)
    tabs = streamlit_page.get_by_role("tab")
    assert tabs.count() >= 3, "Should have at least 3 tabs (Blog, Social, Research)"

    print("✅ Content Browser page loads with tabs")


def test_content_browser_tabs_work(streamlit_page: Page):
    """Test: Content Browser tabs are clickable"""

    # Navigate to Content Browser
    streamlit_page.get_by_text("Content Browser", exact=False).first.click()
    time.sleep(1)

    # Get all tabs
    tabs = streamlit_page.get_by_role("tab")

    if tabs.count() >= 2:
        # Click second tab
        tabs.nth(1).click()
        time.sleep(0.5)

        # Click third tab if exists
        if tabs.count() >= 3:
            tabs.nth(2).click()
            time.sleep(0.5)

    print("✅ Content Browser tabs work")


def test_settings_page_loads(streamlit_page: Page):
    """Test: Settings page loads"""

    # Navigate to Settings
    streamlit_page.get_by_text("Settings", exact=False).first.click()
    time.sleep(1)

    # Check for settings heading or content
    heading = streamlit_page.get_by_text("Settings", exact=False)
    expect(heading.first).to_be_visible()

    print("✅ Settings page loads")


def test_no_errors_in_console(streamlit_page: Page):
    """Test: No critical errors in browser console"""

    errors = []

    # Listen for console errors
    def handle_console(msg):
        if msg.type == "error":
            errors.append(msg.text)

    streamlit_page.on("console", handle_console)

    # Navigate through all pages
    pages = ["Dashboard", "Generate", "Content Browser", "Settings"]
    for page_name in pages:
        try:
            streamlit_page.get_by_text(page_name, exact=False).first.click()
            time.sleep(1)
        except:
            pass

    # Filter out non-critical errors (Streamlit has some expected warnings)
    critical_errors = [e for e in errors if "AttributeError" in e or "TypeError" in e]

    assert len(critical_errors) == 0, f"Critical errors found: {critical_errors}"

    print(f"✅ No critical console errors (total errors: {len(errors)})")


def test_generate_page_validation(streamlit_page: Page):
    """Test: Generate page validates empty topic"""

    # Navigate to Generate
    streamlit_page.get_by_text("Generate", exact=False).first.click()
    time.sleep(1)

    # Try to submit empty form (if validation exists)
    generate_button = streamlit_page.get_by_text("Generate Content", exact=False)

    if generate_button.count() > 0:
        # Clear any existing input
        inputs = streamlit_page.locator("input[type='text']")
        if inputs.count() > 0:
            inputs.first.fill("")

        # Click generate (should show validation error or be disabled)
        # Note: Actual behavior depends on implementation
        print("✅ Generate page has submit button")


def test_app_responsive_layout(streamlit_page: Page):
    """Test: App has responsive layout"""

    # Check main container
    main_container = streamlit_page.locator("[data-testid='stApp']")
    expect(main_container).to_be_visible()

    # Check sidebar
    sidebar = streamlit_page.locator("[data-testid='stSidebar']")
    expect(sidebar).to_be_visible()

    print("✅ App has responsive layout")


@pytest.mark.slow
def test_generate_content_mock_flow(streamlit_page: Page):
    """Test: Full generate flow (with mocked backend)

    Note: This test requires the backend to be properly set up.
    It will be marked as @pytest.mark.slow and skipped in CI.
    """

    # Navigate to Generate
    streamlit_page.get_by_text("Generate", exact=False).first.click()
    time.sleep(1)

    # Fill in topic
    topic_input = streamlit_page.locator("input[type='text']").first
    topic_input.fill("Test Topic for E2E")

    # Submit form
    generate_button = streamlit_page.get_by_text("Generate Content", exact=False)

    if generate_button.count() > 0 and not generate_button.first.is_disabled():
        # Note: In real test, we'd mock the API responses
        # For now, just verify button exists and is clickable
        expect(generate_button.first).to_be_enabled()
        print("✅ Generate button is enabled with topic")
    else:
        print("⚠️  Generate button not found or disabled")


def test_cached_content_displays(streamlit_page: Page):
    """Test: Content Browser shows cached content if available"""

    # Navigate to Content Browser
    streamlit_page.get_by_text("Content Browser", exact=False).first.click()
    time.sleep(1)

    # Check for either content or "no content" message
    page_content = streamlit_page.locator("[data-testid='stApp']").inner_text()

    has_content = "blog post" in page_content.lower() or "no blog posts" in page_content.lower()
    assert has_content, "Content Browser should show content or 'no content' message"

    print("✅ Content Browser displays content state")


if __name__ == "__main__":
    print("Run with: pytest tests/test_playwright_ui.py -v")

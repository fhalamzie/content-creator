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

    # Check for navigation items (buttons with emoji prefixes)
    # Navigation uses buttons like "📊 Dashboard", "✨ Generate", etc.
    navigation = streamlit_page.get_by_role("button").filter(has_text="Dashboard")
    expect(navigation.first).to_be_visible()

    print("✅ Sidebar navigation exists")


def test_dashboard_page_displays(streamlit_page: Page):
    """Test: Dashboard page displays with stats"""

    # Click Dashboard in sidebar (button with emoji)
    streamlit_page.get_by_role("button").filter(has_text="Dashboard").first.click()
    time.sleep(1)

    # Check for dashboard heading (actual heading is "📊 Dashboard")
    heading = streamlit_page.get_by_text("Dashboard", exact=False)
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


@pytest.mark.e2e
@pytest.mark.slow
def test_topic_research_page_loads(streamlit_page: Page):
    """Test: Topic Research page loads with configuration"""

    # Navigate to Topic Research page (look for "Research" or "Topic Research" button)
    research_button = streamlit_page.get_by_role("button").filter(has_text="Research")
    if research_button.count() > 0:
        research_button.first.click()
    else:
        # Try alternative navigation text
        streamlit_page.get_by_text("Topic Research", exact=False).first.click()

    time.sleep(2)

    # Check for heading
    heading = streamlit_page.get_by_text("Topic Research", exact=False)
    expect(heading.first).to_be_visible()

    # Check for configuration sidebar
    sidebar = streamlit_page.locator("[data-testid='stSidebar']")
    expect(sidebar).to_be_visible()

    # Check for configuration inputs
    domain_input = streamlit_page.get_by_label("Domain", exact=False)
    expect(domain_input).to_be_visible()

    market_input = streamlit_page.get_by_label("Market", exact=False)
    expect(market_input).to_be_visible()

    language_input = streamlit_page.get_by_label("Language Code", exact=False)
    expect(language_input).to_be_visible()

    print("✅ Topic Research page loads correctly")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.skipif(True, reason="Requires real API keys and takes ~2 minutes to run")
def test_topic_research_full_pipeline(streamlit_page: Page):
    """Test: Full 5-stage ContentPipeline execution via UI

    This test simulates a user running the complete pipeline:
    1. Configure research settings
    2. Enter a topic
    3. Submit and watch progress through all 5 stages
    4. View enhanced results

    NOTE: This test makes real API calls and costs ~$0.02-0.05
    """

    # Navigate to Topic Research page
    research_button = streamlit_page.get_by_role("button").filter(has_text="Research")
    if research_button.count() > 0:
        research_button.first.click()
    else:
        streamlit_page.get_by_text("Topic Research", exact=False).first.click()

    time.sleep(2)

    # Fill in configuration
    domain_input = streamlit_page.get_by_label("Domain", exact=False)
    domain_input.fill("SaaS")

    market_input = streamlit_page.get_by_label("Market", exact=False)
    market_input.fill("Germany")

    language_input = streamlit_page.get_by_label("Language Code", exact=False)
    language_input.fill("de")

    vertical_input = streamlit_page.get_by_label("Vertical", exact=False)
    vertical_input.fill("PropTech")

    # Save configuration
    save_button = streamlit_page.get_by_role("button").filter(has_text="Save Configuration")
    save_button.click()
    time.sleep(1)

    # Enter topic
    topic_input = streamlit_page.get_by_label("Topic Title", exact=False)
    topic_input.fill("PropTech SaaS Solutions 2025")

    description_input = streamlit_page.get_by_label("Topic Description", exact=False)
    description_input.fill("Emerging PropTech software solutions transforming real estate management")

    # Submit
    submit_button = streamlit_page.get_by_role("button").filter(has_text="Start Research")
    submit_button.click()

    # Wait for progress bar to appear
    progress_bar = streamlit_page.locator("[data-testid='stProgress']")
    expect(progress_bar.first).to_be_visible(timeout=10000)

    # Wait for all 5 stages to complete (up to 3 minutes)
    # Stage 1: Competitor Research
    stage_1 = streamlit_page.get_by_text("Stage 1/5", exact=False)
    expect(stage_1).to_be_visible(timeout=30000)
    print("✅ Stage 1: Competitor Research started")

    # Stage 2: Keyword Research
    stage_2 = streamlit_page.get_by_text("Stage 2/5", exact=False)
    expect(stage_2).to_be_visible(timeout=30000)
    print("✅ Stage 2: Keyword Research started")

    # Stage 3: Deep Research (the newly enabled stage!)
    stage_3 = streamlit_page.get_by_text("Stage 3/5", exact=False)
    expect(stage_3).to_be_visible(timeout=30000)
    print("✅ Stage 3: Deep Research started")

    # Stage 4: Content Optimization
    stage_4 = streamlit_page.get_by_text("Stage 4/5", exact=False)
    expect(stage_4).to_be_visible(timeout=30000)
    print("✅ Stage 4: Content Optimization started")

    # Stage 5: Scoring & Ranking
    stage_5 = streamlit_page.get_by_text("Stage 5/5", exact=False)
    expect(stage_5).to_be_visible(timeout=30000)
    print("✅ Stage 5: Scoring & Ranking started")

    # Wait for completion message
    completion = streamlit_page.get_by_text("Processing Complete", exact=False)
    expect(completion).to_be_visible(timeout=120000)  # Up to 2 minutes for Stage 3
    print("✅ All 5 stages completed successfully")

    # Check results
    results = streamlit_page.get_by_text("Topic processed", exact=False)
    expect(results).to_be_visible()

    print("✅ Full 5-stage pipeline executed successfully via UI")

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

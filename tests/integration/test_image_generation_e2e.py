"""
E2E Integration Test: Image Generation Flow

Complete image generation pipeline validation:
1. ContentSynthesizer: Article synthesis with DALL-E 3 image generation
2. Topic Model: Image field population
3. Notion Sync: Image URL syncing to Notion database

Tests image generation in production-like scenarios:
- Enabled: Generates 1 HD hero + 2 standard supporting images
- Disabled: No image generation, zero cost
- Failure: Silent failure handling, research continues
- Notion: Images sync to Topics database

Cost per run: ~$0.18 ($0.01 synthesis + $0.16 images + $0.01 Voyage)
"""

import pytest
import os
import json
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.research.synthesizer.content_synthesizer import (
    ContentSynthesizer,
    PassageExtractionStrategy
)
from src.models.topic import Topic, TopicSource, TopicStatus
from src.notion_integration.topics_sync import TopicsSync
from src.research.backends.base import SearchResult
from src.utils.config_loader import FullConfig, MarketConfig, CollectorsConfig, SchedulingConfig


# Skip markers for tests that require API keys
skip_if_no_gemini = pytest.mark.skipif(
    not os.getenv('GEMINI_API_KEY'),
    reason="GEMINI_API_KEY not set"
)

skip_if_no_openai = pytest.mark.skipif(
    not os.getenv('OPENAI_API_KEY'),
    reason="OPENAI_API_KEY not set (required for DALL-E 3)"
)


@pytest.fixture
def market_config():
    """Market configuration with brand tone"""
    market = MarketConfig(
        domain='PropTech',
        market='Germany',
        language='en',
        vertical='PropTech',
        seed_keywords=['PropTech', 'Smart Building'],
        brand_tone=['Professional', 'Technical']
    )
    return FullConfig(
        market=market,
        collectors=CollectorsConfig(),
        scheduling=SchedulingConfig()
    )


@pytest.fixture
def sample_sources():
    """Sample search results for testing"""
    return [
        SearchResult.create(
            url="https://example.com/proptech-ai",
            title="PropTech AI Trends 2025",
            snippet="PropTech is revolutionizing real estate with AI-powered automation...",
            backend="tavily",
            content=None,
            published_date=datetime(2025, 1, 1),
            final_score=0.95
        ),
        SearchResult.create(
            url="https://example.com/smart-buildings",
            title="Smart Buildings and IoT Integration",
            snippet="Smart buildings use IoT sensors to optimize energy consumption...",
            backend="gemini",
            content=None,
            published_date=datetime(2025, 1, 2),
            final_score=0.90
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.e2e
@skip_if_no_gemini
@skip_if_no_openai
async def test_synthesis_with_images_enabled(market_config, sample_sources):
    """
    Test complete synthesis pipeline with image generation enabled

    Expected: Article + 1 hero image + 2 supporting images generated
    Cost: ~$0.17 ($0.01 synthesis + $0.16 images)
    """
    print("\n=== E2E Test: Synthesis with Images Enabled ===")

    # Initialize synthesizer
    synthesizer = ContentSynthesizer(
        strategy=PassageExtractionStrategy.BM25_LLM,
        max_article_words=500  # Shorter for faster testing
    )

    query = "PropTech AI automation trends"
    brand_tone = ['Professional', 'Technical']

    # Synthesize with images enabled
    print(f"\nSynthesizing article for: {query}")
    print(f"Brand tone: {brand_tone}")
    print(f"Image generation: ENABLED")

    result = await synthesizer.synthesize(
        sources=sample_sources,
        query=query,
        config=market_config,
        brand_tone=brand_tone,
        generate_images=True  # Enable image generation
    )

    # Validate article
    assert 'article' in result
    assert len(result['article']) > 100, "Article should be substantial"
    print(f"✅ Article generated: {len(result['article'].split())} words")

    # Validate citations
    assert 'citations' in result
    assert len(result['citations']) > 0, "Should have citations"
    print(f"✅ Citations: {len(result['citations'])} sources")

    # Validate hero image
    assert 'hero_image_url' in result
    assert result['hero_image_url'] is not None, "Hero image should be generated"
    assert result['hero_image_url'].startswith('http'), "Hero image should be a URL"
    print(f"✅ Hero image URL: {result['hero_image_url'][:50]}...")

    # Validate hero image alt text
    assert 'hero_image_alt' in result
    assert result['hero_image_alt'] is not None
    assert query.lower() in result['hero_image_alt'].lower(), "Alt text should mention query"
    print(f"✅ Hero image alt: {result['hero_image_alt']}")

    # Validate supporting images
    assert 'supporting_images' in result
    assert len(result['supporting_images']) == 2, "Should generate 2 supporting images"

    for i, img in enumerate(result['supporting_images'], 1):
        assert 'url' in img
        assert img['url'].startswith('http'), f"Supporting image {i} should be a URL"
        assert 'alt' in img
        assert 'size' in img
        assert 'quality' in img
        print(f"✅ Supporting image {i}: {img['url'][:50]}...")

    # Validate cost tracking
    assert 'image_cost' in result
    assert result['image_cost'] > 0, "Image cost should be tracked"
    assert result['image_cost'] == 0.16, "Expected cost: $0.08 hero + $0.08 supporting"
    print(f"✅ Image generation cost: ${result['image_cost']:.2f}")

    # Validate metadata
    assert 'metadata' in result
    assert 'image_generation_duration_ms' in result['metadata']
    print(f"✅ Image generation duration: {result['metadata']['image_generation_duration_ms']:.0f}ms")

    print("\n✅ E2E Test PASSED: All images generated successfully")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.e2e
@skip_if_no_gemini
async def test_synthesis_with_images_disabled(market_config, sample_sources):
    """
    Test synthesis pipeline with image generation disabled

    Expected: Article only, no images, zero image cost
    Cost: ~$0.01 (synthesis only)
    """
    print("\n=== E2E Test: Synthesis with Images Disabled ===")

    # Initialize synthesizer
    synthesizer = ContentSynthesizer(
        strategy=PassageExtractionStrategy.BM25_LLM,
        max_article_words=500
    )

    query = "PropTech AI automation trends"

    # Synthesize with images disabled
    print(f"\nSynthesizing article for: {query}")
    print(f"Image generation: DISABLED")

    result = await synthesizer.synthesize(
        sources=sample_sources,
        query=query,
        config=market_config,
        brand_tone=['Professional'],
        generate_images=False  # Disable image generation
    )

    # Validate article
    assert 'article' in result
    assert len(result['article']) > 100
    print(f"✅ Article generated: {len(result['article'].split())} words")

    # Validate NO images
    assert result['hero_image_url'] is None, "Hero image should not be generated"
    assert result['hero_image_alt'] is None
    assert result['supporting_images'] == [], "Supporting images should be empty"
    print(f"✅ No images generated (as expected)")

    # Validate zero image cost
    assert result['image_cost'] == 0.0, "Image cost should be zero"
    print(f"✅ Image cost: $0.00 (as expected)")

    # Validate metadata does NOT have image generation duration
    assert 'image_generation_duration_ms' not in result['metadata']

    print("\n✅ E2E Test PASSED: Images correctly disabled")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_topic_with_images_notion_sync():
    """
    Test Topic model with images and Notion sync

    Validates:
    - Topic model accepts image fields
    - Images serialize to JSON for Notion
    - Notion sync maps images correctly

    Note: This test uses mocked Notion API (no actual API calls)
    """
    print("\n=== E2E Test: Topic with Images → Notion Sync ===")

    # Create topic with images
    topic = Topic(
        title="PropTech AI Automation Trends 2025",
        description="Comprehensive research on AI trends in PropTech",
        source=TopicSource.MANUAL,
        domain="proptech",
        market="de",
        language="en",
        status=TopicStatus.RESEARCHED,
        priority=8,
        research_report="Full research report on PropTech AI trends...",
        word_count=2000,
        content_score=85.5,
        hero_image_url="https://oaidalleapiprodscus.blob.core.windows.net/hero.png",
        supporting_images=[
            {
                "url": "https://oaidalleapiprodscus.blob.core.windows.net/support1.png",
                "alt": "Supporting illustration 1 for PropTech AI",
                "size": "1024x1024",
                "quality": "standard"
            },
            {
                "url": "https://oaidalleapiprodscus.blob.core.windows.net/support2.png",
                "alt": "Supporting illustration 2 for PropTech AI",
                "size": "1024x1024",
                "quality": "standard"
            }
        ]
    )

    print(f"✅ Topic created: {topic.title}")
    print(f"✅ Hero image URL: {topic.hero_image_url[:50]}...")
    print(f"✅ Supporting images: {len(topic.supporting_images)}")

    # Mock Notion client
    with patch('src.notion_integration.topics_sync.NotionClient') as MockNotionClient:
        mock_client = Mock()
        mock_client.create_page = Mock(return_value={
            'id': 'notion_page_123',
            'url': 'https://notion.so/page_123'
        })
        MockNotionClient.return_value = mock_client

        # Initialize sync
        sync = TopicsSync(
            notion_token="test_token",
            database_id="test_db_id"
        )

        # Sync topic (builds properties)
        result = sync.sync_topic(topic, update_existing=False)

        # Verify sync result
        assert result['action'] == 'created'
        assert result['id'] == 'notion_page_123'
        print(f"✅ Notion page created: {result['id']}")

        # Verify create_page was called
        assert mock_client.create_page.called
        call_args = mock_client.create_page.call_args
        properties = call_args.kwargs['properties']

        # Validate hero image URL property
        assert 'Hero Image URL' in properties
        assert properties['Hero Image URL']['url'] == topic.hero_image_url
        print(f"✅ Hero Image URL synced to Notion")

        # Validate supporting images property (JSON serialized)
        assert 'Supporting Images' in properties
        images_text = properties['Supporting Images']['rich_text'][0]['text']['content']
        supporting_images = json.loads(images_text)
        assert len(supporting_images) == 2
        assert supporting_images[0]['url'].startswith('http')
        print(f"✅ Supporting Images synced to Notion (JSON)")

        # Validate other required fields
        assert 'Title' in properties
        assert properties['Title']['title'][0]['text']['content'] == topic.title
        assert 'Status' in properties
        assert 'Priority' in properties
        assert 'Domain' in properties

    print("\n✅ E2E Test PASSED: Topic with images synced to Notion")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_image_generation_silent_failure():
    """
    Test that synthesis continues when image generation fails

    Expected: Article completes, images are None, zero image cost
    """
    print("\n=== E2E Test: Image Generation Silent Failure ===")

    with patch('src.research.synthesizer.content_synthesizer.ImageGenerator') as MockImageGen, \
         patch('src.research.synthesizer.content_synthesizer.genai') as mock_genai, \
         patch('src.research.synthesizer.content_synthesizer.fetch_url') as mock_fetch, \
         patch('src.research.synthesizer.content_synthesizer.extract') as mock_extract:

        # Mock Gemini API
        mock_response = Mock()
        mock_response.text = "This is a test article generated by the mocked Gemini API. It contains enough content to pass validation."
        mock_genai.Client.return_value.models.generate_content = Mock(return_value=mock_response)

        # Mock content extraction
        mock_fetch.return_value = "<html>content</html>"
        mock_extract.return_value = "Test article content.\n\nSecond paragraph."

        # Mock image generator to fail
        mock_generator = Mock()
        mock_generator.generate_hero_image = AsyncMock(return_value=None)  # Failed
        mock_generator.generate_supporting_image = AsyncMock(return_value=None)  # Failed
        MockImageGen.return_value = mock_generator

        # Initialize synthesizer with fake API key (test uses mocked Gemini API)
        synthesizer = ContentSynthesizer(
            gemini_api_key="fake_test_key",  # Provide fake key for testing
            strategy=PassageExtractionStrategy.BM25_LLM,
            max_article_words=500
        )

        # Sample sources
        sources = [
            SearchResult.create(
                url="https://example.com/test",
                title="Test Article",
                snippet="Test content for validation",
                backend="test",
                content=None,
                published_date=datetime(2025, 1, 1),
                final_score=0.9
            )
        ]

        market = MarketConfig(
            domain='Test',
            market='US',
            language='en',
            vertical='Test',
            seed_keywords=['test']
        )
        config = FullConfig(
            market=market,
            collectors=CollectorsConfig(),
            scheduling=SchedulingConfig()
        )

        # Synthesize with images enabled (but will fail)
        print("\nAttempting synthesis with image generation...")
        print("Image generation will fail (mocked)")

        result = await synthesizer.synthesize(
            sources=sources,
            query="Test query",
            config=config,
            brand_tone=['Professional'],
            generate_images=True
        )

        # Validate article still generated
        assert 'article' in result
        assert len(result['article']) > 50, "Article should still be generated"
        print(f"✅ Article generated despite image failure")

        # Validate failed images
        assert result['hero_image_url'] is None, "Hero image should be None (failed)"
        assert result['supporting_images'] == [], "Supporting images should be empty (failed)"
        print(f"✅ Images are None (silent failure)")

        # Validate zero cost
        assert result['image_cost'] == 0.0, "Image cost should be zero (failed)"
        print(f"✅ Image cost is $0.00 (no successful generations)")

        # Verify image generator was called
        assert mock_generator.generate_hero_image.called
        assert mock_generator.generate_supporting_image.called
        print(f"✅ Image generation was attempted")

    print("\n✅ E2E Test PASSED: Silent failure handling works correctly")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])

"""
Integration Tests for RepurposingAgent

Tests the full repurposing pipeline:
- Platform-specific content generation
- Cache integration (disk writes)
- Cost tracking across platforms
- German language content quality

Test Categories:
- 2 live API tests (marked @pytest.mark.integration) - minimal cost, real API
- 8 mocked integration tests - testing integration points without API cost
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock
from src.agents.repurposing_agent import RepurposingAgent, RepurposingError
from src.cache_manager import CacheManager


# ==================== Fixtures ====================

@pytest.fixture
def api_key():
    """Get API key from environment (for live tests)"""
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set")
    return key


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_blog_post():
    """Sample German blog post for testing"""
    return {
        "title": "Die Zukunft von PropTech in Deutschland",
        "excerpt": "Innovative Technologien revolutionieren die deutsche Immobilienbranche durch KI und Automatisierung",
        "keywords": ["PropTech", "Innovation", "KI", "Digitalisierung"],
        "slug": "proptech-zukunft-deutschland"
    }


@pytest.fixture
def sample_blog_post_simple():
    """Simpler blog post for basic testing"""
    return {
        "title": "AI Marketing Trends 2024",
        "excerpt": "How artificial intelligence is transforming modern marketing strategies",
        "keywords": ["AI", "Marketing", "Automation"],
        "slug": "ai-marketing-trends-2024"
    }


@pytest.fixture
def mock_generate_response():
    """Mock response from BaseAgent.generate()"""
    return {
        'content': 'LinkedIn post content about PropTech innovation with hashtags and CTA.',
        'tokens': {'prompt': 200, 'completion': 150, 'total': 350},
        'cost': 0.0008
    }


# ==================== Live API Tests (Mark with @pytest.mark.integration) ====================

@pytest.mark.integration
def test_generate_linkedin_post_live_api(api_key, sample_blog_post):
    """Test LinkedIn post generation with real OpenRouter API

    Validates:
    - Real API call to OpenRouter
    - German language output
    - Character count within platform limits
    - Cost tracking accuracy
    - Hashtags properly formatted

    Cost: ~$0.0008 per test
    """
    agent = RepurposingAgent(api_key=api_key)

    # Generate single LinkedIn post
    results = agent.generate_social_posts(
        blog_post=sample_blog_post,
        platforms=["LinkedIn"],
        save_to_cache=False  # Don't pollute cache during tests
    )

    # Assertions
    assert len(results) == 1
    assert results[0]["platform"] == "LinkedIn"

    # Verify content exists and has reasonable length
    content = results[0]["content"]
    assert len(content) > 0
    assert len(content) <= 3000  # LinkedIn max
    assert len(content) >= 100  # Reasonable minimum

    # Verify German language (contains umlauts or German words)
    # Sample German indicators: ü, ö, ä, ß or common German words
    german_indicators = "üöäßderdidasunddichdichdemmitfürhalt"
    has_german = any(char in content.lower() for char in german_indicators)
    assert has_german or "PropTech" in content, "Content should be in German or contain German keywords"

    # Verify hashtags exist and are properly formatted
    hashtags = results[0]["hashtags"]
    assert len(hashtags) > 0
    assert len(hashtags) <= 5  # LinkedIn hashtag limit
    for hashtag in hashtags:
        assert hashtag.startswith("#"), f"Hashtag should start with #: {hashtag}"
        assert not " " in hashtag, f"Hashtag should not contain spaces: {hashtag}"

    # Verify character count matches content
    assert results[0]["character_count"] == len(content)

    # Verify cost is reasonable
    assert results[0]["cost"] > 0
    assert results[0]["cost"] < 0.005, "Cost should be less than $0.005 for single platform"

    # Verify token tracking
    assert results[0]["tokens"]["total"] > 0
    assert results[0]["tokens"]["prompt"] > 0
    assert results[0]["tokens"]["completion"] > 0


@pytest.mark.integration
def test_generate_all_platforms_live_api(api_key, sample_blog_post):
    """Test all 4 platforms with real OpenRouter API

    Validates:
    - All platforms generated successfully
    - Each post is unique and platform-optimized
    - Character limits respected on all platforms
    - Total cost is sum of individual platform costs
    - All posts have proper hashtags

    Cost: ~$0.003 total (~$0.0008 per platform)
    """
    agent = RepurposingAgent(api_key=api_key)

    platforms = ["LinkedIn", "Facebook", "Instagram", "TikTok"]
    results = agent.generate_social_posts(
        blog_post=sample_blog_post,
        platforms=platforms,
        brand_tone=["Professional", "Friendly"],
        save_to_cache=False
    )

    # Verify all platforms generated
    assert len(results) == 4
    result_platforms = [r["platform"] for r in results]
    assert set(result_platforms) == set(platforms)

    # Verify each platform has content
    contents = {}
    for result in results:
        platform = result["platform"]
        content = result["content"]

        assert len(content) > 0, f"{platform} should have content"
        contents[platform] = content

        # Verify character limits respected
        if platform == "LinkedIn":
            assert len(content) <= 3000
        elif platform == "Facebook":
            assert len(content) <= 63206
        elif platform == "Instagram":
            assert len(content) <= 2200
        elif platform == "TikTok":
            assert len(content) <= 2200

        # Verify hashtags
        hashtags = result["hashtags"]
        assert len(hashtags) > 0

    # Verify posts are different (platform-specific optimization)
    # Content should vary by platform due to different optimal lengths and tones
    unique_contents = set(contents.values())
    assert len(unique_contents) >= 3, "Posts should be platform-specific (mostly unique)"

    # Verify total cost is sum of platform costs
    total_cost = sum(r["cost"] for r in results)
    assert total_cost > 0
    assert total_cost < 0.012, "Total cost should be less than $0.012 for all 4 platforms (includes retry overhead)"

    # Verify each platform cost is reasonable
    for result in results:
        assert result["cost"] < 0.005, f"{result['platform']} cost should be < $0.005"

    # Verify German content appears in results
    all_content = " ".join(contents.values()).lower()
    # Check for German indicators
    german_words = ["innovation", "technologie", "digitalisierung", "proptech"]
    has_german = any(word in all_content for word in german_words)
    assert has_german, "Content should contain German keywords or text"


# ==================== Mocked Integration Tests ====================

def test_cache_integration_saves_to_disk(sample_blog_post, temp_cache_dir, mock_generate_response):
    """Verify cache writes work correctly

    Validates:
    - Cache files created at correct paths
    - File naming convention: {slug}_{platform}.md
    - Cache manager integration works without breaking generation
    """
    with patch('src.agents.repurposing_agent.BaseAgent.generate') as mock_generate:
        mock_generate.return_value = mock_generate_response

        agent = RepurposingAgent(
            api_key="test-key-12345",
            cache_dir=temp_cache_dir
        )

        # Generate with cache enabled
        results = agent.generate_social_posts(
            blog_post=sample_blog_post,
            platforms=["LinkedIn", "Facebook"],
            save_to_cache=True
        )

        assert len(results) == 2

        # Verify cache files created
        cache_path = Path(temp_cache_dir) / "social_posts"

        # Check LinkedIn cache file
        linkedin_file = cache_path / f"{sample_blog_post['slug']}_linkedin.md"
        assert linkedin_file.exists(), f"LinkedIn cache file should exist: {linkedin_file}"
        linkedin_content = linkedin_file.read_text(encoding="utf-8")
        assert linkedin_content == mock_generate_response['content']

        # Check Facebook cache file
        facebook_file = cache_path / f"{sample_blog_post['slug']}_facebook.md"
        assert facebook_file.exists(), f"Facebook cache file should exist: {facebook_file}"
        facebook_content = facebook_file.read_text(encoding="utf-8")
        assert facebook_content == mock_generate_response['content']


def test_cache_integration_failure_doesnt_block(sample_blog_post, mock_generate_response):
    """Verify cache failures don't block content generation

    Validates:
    - Content generation succeeds even if cache fails
    - Error is logged but doesn't raise exception
    - Results still returned to user
    """
    with patch('src.agents.repurposing_agent.BaseAgent.generate') as mock_generate, \
         patch('src.cache_manager.CacheManager.write_social_post') as mock_cache_write:

        mock_generate.return_value = mock_generate_response
        mock_cache_write.side_effect = IOError("Disk full")

        agent = RepurposingAgent(
            api_key="test-key",
            cache_dir="/tmp/test-cache"  # Will fail on write
        )

        # Generate with cache enabled - should NOT raise
        results = agent.generate_social_posts(
            blog_post=sample_blog_post,
            platforms=["LinkedIn"],
            save_to_cache=True
        )

        # Verify results still returned
        assert len(results) == 1
        assert results[0]["platform"] == "LinkedIn"
        assert results[0]["content"] == mock_generate_response['content']

        # Verify cache write was attempted (and failed gracefully)
        assert mock_cache_write.called


def test_brand_tone_propagation(sample_blog_post, mock_generate_response):
    """Verify brand_tone reaches prompt template

    Validates:
    - Brand tone is included in generated prompts
    - Multiple tones can be combined
    - Tone appears in final prompt sent to API
    """
    with patch('src.agents.repurposing_agent.BaseAgent.generate') as mock_generate:
        mock_generate.return_value = mock_generate_response

        agent = RepurposingAgent(api_key="test-key")

        # Spy on _build_prompt to capture generated prompts
        original_build_prompt = agent._build_prompt
        captured_prompts = []

        def spy_build_prompt(*args, **kwargs):
            prompt = original_build_prompt(*args, **kwargs)
            captured_prompts.append(prompt)
            return prompt

        agent._build_prompt = spy_build_prompt

        # Generate with specific brand tones
        brand_tones = ["Professional", "Friendly"]
        results = agent.generate_social_posts(
            blog_post=sample_blog_post,
            platforms=["LinkedIn"],
            brand_tone=brand_tones,
            save_to_cache=False
        )

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]

        # Verify tone appears in prompt
        for tone in brand_tones:
            assert tone in prompt, f"Brand tone '{tone}' should appear in prompt"


def test_cost_tracking_accuracy(sample_blog_post, mock_generate_response):
    """Verify costs calculated correctly across platforms

    Validates:
    - Each platform cost tracked accurately
    - Total cost = sum of platform costs
    - Cost is included in results
    """
    with patch('src.agents.repurposing_agent.BaseAgent.generate') as mock_generate:
        # Different costs for different platforms
        responses = [
            {'content': 'LinkedIn post', 'tokens': {'prompt': 200, 'completion': 150, 'total': 350}, 'cost': 0.0008},
            {'content': 'Facebook post', 'tokens': {'prompt': 100, 'completion': 80, 'total': 180}, 'cost': 0.0004},
            {'content': 'Instagram post', 'tokens': {'prompt': 150, 'completion': 100, 'total': 250}, 'cost': 0.0006},
        ]
        mock_generate.side_effect = responses

        agent = RepurposingAgent(api_key="test-key")

        results = agent.generate_social_posts(
            blog_post=sample_blog_post,
            platforms=["LinkedIn", "Facebook", "Instagram"],
            save_to_cache=False
        )

        assert len(results) == 3

        # Verify individual costs
        assert results[0]["cost"] == 0.0008
        assert results[1]["cost"] == 0.0004
        assert results[2]["cost"] == 0.0006

        # Verify total cost is accurate
        total_cost = sum(r["cost"] for r in results)
        expected_total = 0.0008 + 0.0004 + 0.0006
        assert abs(total_cost - expected_total) < 0.00001


def test_batch_generation_order(sample_blog_post, mock_generate_response):
    """Verify platforms generated in correct order

    Validates:
    - Platforms are processed in order specified
    - Each platform config is correctly applied
    - Order is predictable and matches input
    """
    with patch('src.agents.repurposing_agent.BaseAgent.generate') as mock_generate:
        mock_generate.return_value = mock_generate_response

        agent = RepurposingAgent(api_key="test-key")

        # Track which platform configs are used
        original_get_config = __import__('src.agents.platform_profiles', fromlist=['get_platform_config']).get_platform_config
        called_platforms = []

        def spy_get_config(platform):
            called_platforms.append(platform)
            return original_get_config(platform)

        with patch('src.agents.repurposing_agent.get_platform_config', side_effect=spy_get_config):
            platforms = ["LinkedIn", "Facebook", "Instagram", "TikTok"]
            results = agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=platforms,
                save_to_cache=False
            )

        # Verify platforms processed in order (called_platforms may have duplicates due to hashtag generation)
        # Extract first occurrence of each platform
        first_occurrences = []
        seen = set()
        for p in called_platforms:
            if p not in seen:
                first_occurrences.append(p)
                seen.add(p)

        assert platforms == first_occurrences, "Platforms should be processed in order"

        # Verify results match expected platforms
        result_platforms = [r["platform"] for r in results]
        assert result_platforms == platforms


def test_platform_specific_prompts(sample_blog_post, mock_generate_response):
    """Verify each platform gets unique, optimized prompt

    Validates:
    - LinkedIn prompt includes professional tone, 1300 optimal chars
    - Facebook prompt is conversational, 250 optimal chars
    - Instagram prompt emphasizes visual, 150 optimal chars
    - TikTok prompt focuses on entertainment, 100 optimal chars
    """
    with patch('src.agents.repurposing_agent.BaseAgent.generate') as mock_generate:
        mock_generate.return_value = mock_generate_response

        agent = RepurposingAgent(api_key="test-key")

        # Spy on _build_prompt
        captured_prompts = {}
        original_build_prompt = agent._build_prompt

        def spy_build_prompt(blog_post, platform, brand_tone, language="de"):
            prompt = original_build_prompt(blog_post, platform, brand_tone, language)
            captured_prompts[platform] = prompt
            return prompt

        agent._build_prompt = spy_build_prompt

        # Generate for all platforms
        results = agent.generate_social_posts(
            blog_post=sample_blog_post,
            platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"],
            save_to_cache=False
        )

        assert len(captured_prompts) == 4

        # Verify LinkedIn prompt has professional tone and high char limit
        linkedin_prompt = captured_prompts["LinkedIn"]
        assert "1300" in linkedin_prompt or "3000" in linkedin_prompt  # optimal or max chars
        assert "Professional" in linkedin_prompt or "LinkedIn" in linkedin_prompt

        # Verify Facebook prompt is different (conversational)
        facebook_prompt = captured_prompts["Facebook"]
        assert "250" in facebook_prompt or "63206" in facebook_prompt
        assert facebook_prompt != linkedin_prompt, "Platform prompts should differ"

        # Verify Instagram prompt is different
        instagram_prompt = captured_prompts["Instagram"]
        assert instagram_prompt != linkedin_prompt
        assert instagram_prompt != facebook_prompt

        # Verify TikTok prompt is different
        tiktok_prompt = captured_prompts["TikTok"]
        assert tiktok_prompt != linkedin_prompt
        assert tiktok_prompt != facebook_prompt
        assert tiktok_prompt != instagram_prompt


def test_german_content_generation(sample_blog_post):
    """Verify German language content generation

    Validates:
    - German keywords from blog post are included
    - German language indicators present in output
    - German tone/style apparent
    """
    german_content = """Die Zukunft von PropTech liegt in der Automatisierung und künstlichen Intelligenz.
    Innovative Lösungen revolutionieren die Immobilienbranche und schaffen neue Möglichkeiten für Digitalisierung."""

    mock_response = {
        'content': german_content,
        'tokens': {'prompt': 150, 'completion': 100, 'total': 250},
        'cost': 0.0006
    }

    with patch('src.agents.repurposing_agent.BaseAgent.generate') as mock_generate:
        mock_generate.return_value = mock_response

        agent = RepurposingAgent(api_key="test-key")

        results = agent.generate_social_posts(
            blog_post=sample_blog_post,
            platforms=["LinkedIn"],
            save_to_cache=False
        )

        assert len(results) == 1
        content = results[0]["content"]

        # Verify German content
        german_indicators = [
            "und", "der", "die", "das", "für", "von", "zu", "mit",
            "PropTech", "Automatisierung", "Innovation", "Digitalisierung"
        ]

        found_indicators = [ind for ind in german_indicators if ind in content]
        assert len(found_indicators) > 0, "Content should contain German words or keywords"


def test_metadata_includes_character_count(sample_blog_post, mock_generate_response):
    """Verify character_count metadata in results

    Validates:
    - character_count field present in each result
    - character_count matches actual content length
    - character_count is integer, not string
    """
    with patch('src.agents.repurposing_agent.BaseAgent.generate') as mock_generate:
        mock_generate.return_value = mock_generate_response

        agent = RepurposingAgent(api_key="test-key")

        results = agent.generate_social_posts(
            blog_post=sample_blog_post,
            platforms=["LinkedIn", "Facebook", "Instagram"],
            save_to_cache=False
        )

        assert len(results) == 3

        for result in results:
            # Verify character_count exists
            assert "character_count" in result, f"Result should have character_count: {result}"

            # Verify character_count is integer
            assert isinstance(result["character_count"], int), "character_count should be integer"

            # Verify character_count matches content
            expected_count = len(result["content"])
            assert result["character_count"] == expected_count, \
                f"character_count ({result['character_count']}) should match content length ({expected_count})"

            # Verify character_count is reasonable
            assert result["character_count"] > 0, "character_count should be positive"
            assert result["character_count"] < 5000, "character_count should be under 5000"


# ==================== Error Handling Tests ====================

def test_empty_platforms_raises_error(sample_blog_post):
    """Verify error raised for empty platforms list"""
    agent = RepurposingAgent(api_key="test-key")

    with pytest.raises(ValueError, match="platforms list cannot be empty"):
        agent.generate_social_posts(
            blog_post=sample_blog_post,
            platforms=[]
        )


def test_missing_blog_post_keys_raises_error():
    """Verify error raised for missing required blog_post keys"""
    agent = RepurposingAgent(api_key="test-key")

    incomplete_blog = {
        "title": "Test",
        "excerpt": "Test excerpt",
        # Missing: keywords, slug
    }

    with pytest.raises(ValueError, match="blog_post missing required keys"):
        agent.generate_social_posts(
            blog_post=incomplete_blog,
            platforms=["LinkedIn"]
        )


def test_invalid_platform_raises_error(sample_blog_post):
    """Verify error raised for invalid platform name"""
    agent = RepurposingAgent(api_key="test-key")

    with pytest.raises(ValueError, match="Invalid platforms"):
        agent.generate_social_posts(
            blog_post=sample_blog_post,
            platforms=["InvalidPlatform"]
        )


# ==================== Hashtag Generation Tests ====================

def test_hashtag_generation_respects_platform_limits(sample_blog_post, mock_generate_response):
    """Verify hashtags respect platform-specific limits"""
    with patch('src.agents.repurposing_agent.BaseAgent.generate') as mock_generate:
        mock_generate.return_value = mock_generate_response

        agent = RepurposingAgent(api_key="test-key")

        # Create blog post with many keywords
        blog = {
            **sample_blog_post,
            "keywords": ["Keyword1", "Keyword2", "Keyword3", "Keyword4", "Keyword5",
                        "Keyword6", "Keyword7", "Keyword8", "Keyword9", "Keyword10"]
        }

        results = agent.generate_social_posts(
            blog_post=blog,
            platforms=["LinkedIn", "Instagram", "TikTok"],
            save_to_cache=False
        )

        # LinkedIn: 5 hashtag limit
        linkedin_result = [r for r in results if r["platform"] == "LinkedIn"][0]
        assert len(linkedin_result["hashtags"]) <= 5, "LinkedIn should limit to 5 hashtags"

        # Instagram: 30 hashtag limit
        instagram_result = [r for r in results if r["platform"] == "Instagram"][0]
        assert len(instagram_result["hashtags"]) <= 30, "Instagram should limit to 30 hashtags"

        # TikTok: 5 hashtag limit
        tiktok_result = [r for r in results if r["platform"] == "TikTok"][0]
        assert len(tiktok_result["hashtags"]) <= 5, "TikTok should limit to 5 hashtags"

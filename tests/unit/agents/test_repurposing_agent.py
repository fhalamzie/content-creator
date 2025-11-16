"""
Unit tests for RepurposingAgent

Tests platform-optimized social media content generation from blog posts.
Uses extensive mocking to avoid live API calls and cost.

Test coverage includes:
- Initialization with and without cache
- Platform-specific content generation
- Hashtag generation with platform limits
- Batch generation across multiple platforms
- Error handling and retry logic
- Character limit enforcement
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from pathlib import Path

from src.agents.repurposing_agent import (
    RepurposingAgent,
    RepurposingError
)
from src.agents.base_agent import AgentError
from src.agents.platform_profiles import VALID_PLATFORMS


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def api_key():
    """Valid OpenRouter API key for testing"""
    return "test-api-key-123"


@pytest.fixture
def sample_blog_post():
    """Sample blog post data for testing"""
    return {
        "title": "Die Zukunft von PropTech",
        "excerpt": "Innovative Technologien revolutionieren die Immobilienbranche",
        "keywords": ["PropTech", "Innovation", "Digitalisierung"],
        "slug": "proptech-zukunft"
    }


@pytest.fixture
def base_agent_response():
    """Standard BaseAgent.generate() response"""
    return {
        'content': 'Test content for platform optimization',
        'tokens': {
            'prompt': 100,
            'completion': 50,
            'total': 150
        },
        'cost': 0.0002
    }


@pytest.fixture
def repurposing_agent(api_key):
    """RepurposingAgent instance with mocked template loading"""
    with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template'):
        agent = RepurposingAgent(api_key=api_key)
        # Mock the prompt template
        agent.prompt_template = (
            "Generate a {platform} post about {topic}. "
            "Excerpt: {excerpt}. Keywords: {keywords}. "
            "Tone: {tone}. Optimal: {optimal_chars} chars, Max: {max_chars}. "
            "Hashtags: max {hashtag_limit}. "
            "Format: {format}. Emojis: {emoji_usage}. CTA: {cta_style}"
        )
        return agent


@pytest.fixture
def repurposing_agent_with_cache(api_key, tmp_path):
    """RepurposingAgent instance with cache enabled"""
    with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template'):
        agent = RepurposingAgent(
            api_key=api_key,
            cache_dir=str(tmp_path / "cache")
        )
        agent.prompt_template = (
            "Generate a {platform} post about {topic}. "
            "Excerpt: {excerpt}. Keywords: {keywords}. "
            "Tone: {tone}. Optimal: {optimal_chars} chars, Max: {max_chars}. "
            "Hashtags: max {hashtag_limit}. "
            "Format: {format}. Emojis: {emoji_usage}. CTA: {cta_style}"
        )
        return agent


# ============================================================================
# TestRepurposingAgentInit: Initialization Tests
# ============================================================================


class TestRepurposingAgentInit:
    """Test RepurposingAgent initialization"""

    def test_init_with_api_key_succeeds(self, api_key):
        """Test initialization with valid API key"""
        with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template'):
            agent = RepurposingAgent(api_key=api_key)
            assert agent is not None
            assert agent.api_key == api_key
            assert agent.agent_type == "repurposing"

    def test_init_without_api_key_raises_error(self):
        """Test initialization fails without API key"""
        with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template'):
            with pytest.raises(AgentError) as exc_info:
                RepurposingAgent(api_key="")
            assert "API key is required" in str(exc_info.value)

    def test_init_with_cache_dir_creates_cache_manager(self, api_key, tmp_path):
        """Test initialization with cache_dir creates CacheManager"""
        cache_dir = str(tmp_path / "cache")
        with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template'):
            with patch('src.agents.repurposing_agent.CacheManager') as mock_cache_class:
                mock_cache = Mock()
                mock_cache_class.return_value = mock_cache

                agent = RepurposingAgent(api_key=api_key, cache_dir=cache_dir)

                assert agent.cache_manager is not None
                mock_cache_class.assert_called_once_with(cache_dir=cache_dir)

    def test_init_without_cache_dir_no_cache_manager(self, api_key):
        """Test initialization without cache_dir leaves cache_manager as None"""
        with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template'):
            agent = RepurposingAgent(api_key=api_key)
            assert agent.cache_manager is None

    def test_init_loads_prompt_template(self, api_key):
        """Test initialization loads prompt template"""
        with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template') as mock_load:
            mock_load.return_value = "Test template"

            agent = RepurposingAgent(api_key=api_key)

            assert agent.prompt_template == "Test template"
            mock_load.assert_called_once()

    def test_init_raises_error_if_template_load_fails(self, api_key):
        """Test initialization fails if prompt template cannot be loaded"""
        with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template') as mock_load:
            mock_load.side_effect = Exception("Template file not found")

            with pytest.raises(RepurposingError) as exc_info:
                RepurposingAgent(api_key=api_key)
            assert "Failed to load prompt template" in str(exc_info.value)


# ============================================================================
# TestGeneratePlatformContent: Platform Content Generation Tests
# ============================================================================


class TestGeneratePlatformContent:
    """Test _generate_platform_content method"""

    def test_generate_linkedin_content(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test LinkedIn content generation"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            result = repurposing_agent._generate_platform_content(
                blog_post=sample_blog_post,
                platform="LinkedIn",
                brand_tone=["Professional"]
            )

            assert 'content' in result
            assert 'tokens' in result
            assert 'cost' in result
            assert result['cost'] == 0.0002
            assert result['tokens']['total'] == 150

    def test_generate_facebook_content(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test Facebook content generation"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            result = repurposing_agent._generate_platform_content(
                blog_post=sample_blog_post,
                platform="Facebook",
                brand_tone=["Friendly"]
            )

            assert 'content' in result
            assert result['cost'] > 0

    def test_generate_instagram_content(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test Instagram content generation"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            result = repurposing_agent._generate_platform_content(
                blog_post=sample_blog_post,
                platform="Instagram",
                brand_tone=["Authentic"]
            )

            assert result['content'] == "Test content for platform optimization"

    def test_generate_tiktok_content(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test TikTok content generation"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            result = repurposing_agent._generate_platform_content(
                blog_post=sample_blog_post,
                platform="TikTok",
                brand_tone=["Casual"]
            )

            assert 'content' in result
            assert isinstance(result['cost'], float)

    def test_content_truncated_if_exceeds_character_limit(self, repurposing_agent, sample_blog_post):
        """Test content is truncated if it exceeds max_chars"""
        # LinkedIn has max 3000 chars - generate 4000 char content
        long_content = "x" * 4000
        response = {
            'content': long_content,
            'tokens': {'prompt': 100, 'completion': 50, 'total': 150},
            'cost': 0.0002
        }

        with patch.object(repurposing_agent, 'generate', return_value=response):
            result = repurposing_agent._generate_platform_content(
                blog_post=sample_blog_post,
                platform="LinkedIn",
                brand_tone=["Professional"]
            )

            # Content should be truncated to 3000 chars with "..." appended
            assert len(result['content']) <= 3000
            assert result['content'].endswith("...")

    def test_base_agent_generate_failure_raises_repurposing_error(self, repurposing_agent, sample_blog_post):
        """Test RepurposingError raised when BaseAgent.generate() fails"""
        with patch.object(repurposing_agent, 'generate', side_effect=AgentError("API error")):
            with pytest.raises(RepurposingError) as exc_info:
                repurposing_agent._generate_platform_content(
                    blog_post=sample_blog_post,
                    platform="LinkedIn",
                    brand_tone=["Professional"]
                )
            assert "Failed to generate LinkedIn content" in str(exc_info.value)

    def test_unexpected_error_wrapped_in_repurposing_error(self, repurposing_agent, sample_blog_post):
        """Test unexpected exceptions are wrapped in RepurposingError"""
        with patch.object(repurposing_agent, 'generate', side_effect=Exception("Unexpected error")):
            with pytest.raises(RepurposingError) as exc_info:
                repurposing_agent._generate_platform_content(
                    blog_post=sample_blog_post,
                    platform="LinkedIn",
                    brand_tone=["Professional"]
                )
            assert "Unexpected error generating" in str(exc_info.value)


# ============================================================================
# TestGenerateHashtags: Hashtag Generation Tests
# ============================================================================


class TestGenerateHashtags:
    """Test _generate_hashtags method"""

    def test_generate_hashtags_from_keywords(self, repurposing_agent):
        """Test hashtag generation from keywords with CamelCase formatting"""
        hashtags = repurposing_agent._generate_hashtags(
            keywords=["PropTech", "Innovation", "Digitalisierung"],
            platform="LinkedIn"
        )

        assert len(hashtags) > 0
        assert all(tag.startswith("#") for tag in hashtags)
        # Check CamelCase formatting
        assert "#Proptech" in hashtags or "#PropTech" in hashtags

    def test_linkedin_hashtag_limit_5(self, repurposing_agent):
        """Test LinkedIn limits to 5 hashtags"""
        keywords = ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6"]
        hashtags = repurposing_agent._generate_hashtags(
            keywords=keywords,
            platform="LinkedIn"
        )

        assert len(hashtags) == 5

    def test_facebook_hashtag_limit_3(self, repurposing_agent):
        """Test Facebook limits to 3 hashtags"""
        keywords = ["keyword1", "keyword2", "keyword3", "keyword4"]
        hashtags = repurposing_agent._generate_hashtags(
            keywords=keywords,
            platform="Facebook"
        )

        assert len(hashtags) == 3

    def test_instagram_hashtag_limit_30(self, repurposing_agent):
        """Test Instagram limits to 30 hashtags"""
        keywords = [f"keyword{i}" for i in range(35)]
        hashtags = repurposing_agent._generate_hashtags(
            keywords=keywords,
            platform="Instagram"
        )

        assert len(hashtags) == 30

    def test_tiktok_hashtag_limit_5(self, repurposing_agent):
        """Test TikTok limits to 5 hashtags"""
        keywords = ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6"]
        hashtags = repurposing_agent._generate_hashtags(
            keywords=keywords,
            platform="TikTok"
        )

        assert len(hashtags) == 5

    def test_empty_keywords_returns_empty_hashtags(self, repurposing_agent):
        """Test empty keywords list returns empty hashtags"""
        hashtags = repurposing_agent._generate_hashtags(
            keywords=[],
            platform="LinkedIn"
        )

        assert hashtags == []

    def test_hashtags_have_hash_prefix(self, repurposing_agent):
        """Test all generated hashtags have # prefix"""
        hashtags = repurposing_agent._generate_hashtags(
            keywords=["Test", "Example"],
            platform="LinkedIn"
        )

        for hashtag in hashtags:
            assert hashtag.startswith("#")

    def test_multi_word_keyword_becomes_camelcase(self, repurposing_agent):
        """Test multi-word keywords are converted to CamelCase without spaces"""
        hashtags = repurposing_agent._generate_hashtags(
            keywords=["machine learning", "artificial intelligence"],
            platform="LinkedIn"
        )

        # Should have # prefix and CamelCase
        assert any(tag.startswith("#") for tag in hashtags)
        # Check that spaces are removed (should be CamelCase)
        for tag in hashtags:
            assert " " not in tag


# ============================================================================
# TestGenerateSocialPosts: Batch Generation Tests
# ============================================================================


class TestGenerateSocialPosts:
    """Test generate_social_posts method"""

    def test_generate_all_platforms(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test generation for all 4 platforms"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"],
                brand_tone=["Professional"]
            )

            assert len(results) == 4
            platforms = [r['platform'] for r in results]
            assert set(platforms) == {"LinkedIn", "Facebook", "Instagram", "TikTok"}

    def test_generate_single_platform(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test generation for single platform"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"],
                brand_tone=["Professional"]
            )

            assert len(results) == 1
            assert results[0]['platform'] == "LinkedIn"

    def test_result_structure_contains_required_keys(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test result has all required keys"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            result = results[0]
            required_keys = ['platform', 'content', 'hashtags', 'character_count', 'cost', 'tokens']
            for key in required_keys:
                assert key in result, f"Missing key: {key}"

    def test_character_count_calculation(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test character count is calculated correctly"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            result = results[0]
            expected_count = len("Test content for platform optimization")
            assert result['character_count'] == expected_count

    def test_invalid_platform_raises_value_error(self, repurposing_agent, sample_blog_post):
        """Test invalid platform raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["InvalidPlatform"]
            )
        assert "Invalid platforms" in str(exc_info.value)
        assert "InvalidPlatform" in str(exc_info.value)

    def test_empty_platforms_list_raises_value_error(self, repurposing_agent, sample_blog_post):
        """Test empty platforms list raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=[]
            )
        assert "platforms list cannot be empty" in str(exc_info.value)

    def test_missing_blog_post_keys_raises_value_error(self, repurposing_agent):
        """Test missing required blog_post keys raises ValueError"""
        incomplete_post = {
            "title": "Test",
            "excerpt": "Test excerpt"
            # Missing: keywords, slug
        }

        with pytest.raises(ValueError) as exc_info:
            repurposing_agent.generate_social_posts(
                blog_post=incomplete_post,
                platforms=["LinkedIn"]
            )
        assert "missing required keys" in str(exc_info.value)
        assert "keywords" in str(exc_info.value) or "slug" in str(exc_info.value)

    def test_cost_calculation_across_platforms(self, repurposing_agent, sample_blog_post):
        """Test cost is calculated correctly across platforms"""
        response_with_cost = {
            'content': 'Test content',
            'tokens': {'prompt': 100, 'completion': 50, 'total': 150},
            'cost': 0.0005
        }

        with patch.object(repurposing_agent, 'generate', return_value=response_with_cost):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn", "Facebook"]
            )

            total_cost = sum(r['cost'] for r in results)
            assert total_cost == pytest.approx(0.001, rel=1e-5)

    def test_cache_integration_called_when_save_to_cache_true(self, repurposing_agent_with_cache, sample_blog_post, base_agent_response):
        """Test cache.write_social_post is called when save_to_cache=True"""
        with patch.object(repurposing_agent_with_cache, 'generate', return_value=base_agent_response):
            with patch.object(repurposing_agent_with_cache.cache_manager, 'write_social_post') as mock_write:
                results = repurposing_agent_with_cache.generate_social_posts(
                    blog_post=sample_blog_post,
                    platforms=["LinkedIn"],
                    save_to_cache=True
                )

                mock_write.assert_called()
                # Verify it was called with correct arguments
                call_args = mock_write.call_args
                assert call_args[1]['slug'] == "proptech-zukunft"
                assert call_args[1]['platform'] == "linkedin"

    def test_cache_not_called_when_save_to_cache_false(self, repurposing_agent_with_cache, sample_blog_post, base_agent_response):
        """Test cache is not called when save_to_cache=False"""
        with patch.object(repurposing_agent_with_cache, 'generate', return_value=base_agent_response):
            with patch.object(repurposing_agent_with_cache.cache_manager, 'write_social_post') as mock_write:
                results = repurposing_agent_with_cache.generate_social_posts(
                    blog_post=sample_blog_post,
                    platforms=["LinkedIn"],
                    save_to_cache=False
                )

                mock_write.assert_not_called()

    def test_cache_failure_doesnt_fail_generation(self, repurposing_agent_with_cache, sample_blog_post, base_agent_response):
        """Test cache errors don't cause generation to fail"""
        with patch.object(repurposing_agent_with_cache, 'generate', return_value=base_agent_response):
            with patch.object(repurposing_agent_with_cache.cache_manager, 'write_social_post', side_effect=Exception("Cache error")):
                # Should not raise, cache failure is silent
                results = repurposing_agent_with_cache.generate_social_posts(
                    blog_post=sample_blog_post,
                    platforms=["LinkedIn"],
                    save_to_cache=True
                )

                assert len(results) == 1
                assert results[0]['platform'] == "LinkedIn"

    def test_all_platforms_failed_raises_repurposing_error(self, repurposing_agent, sample_blog_post):
        """Test RepurposingError raised when all platforms fail"""
        with patch.object(repurposing_agent, 'generate', side_effect=AgentError("API error")):
            with pytest.raises(RepurposingError) as exc_info:
                repurposing_agent.generate_social_posts(
                    blog_post=sample_blog_post,
                    platforms=["LinkedIn", "Facebook"]
                )
            assert "Failed to generate content for all platforms" in str(exc_info.value)

    def test_partial_platform_failure_returns_successful_results(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test partial failures return successful platform results"""
        # Mock generate to fail for Facebook, succeed for others
        def generate_side_effect(prompt):
            if "Facebook" in prompt:
                raise AgentError("Facebook API error")
            return base_agent_response

        with patch.object(repurposing_agent, 'generate', side_effect=generate_side_effect):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn", "Facebook", "Instagram"]
            )

            # Should return results for LinkedIn and Instagram
            assert len(results) == 2
            platforms = [r['platform'] for r in results]
            assert "LinkedIn" in platforms
            assert "Instagram" in platforms
            assert "Facebook" not in platforms

    def test_hashtags_included_in_results(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test hashtags are included in results"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            result = results[0]
            assert 'hashtags' in result
            assert isinstance(result['hashtags'], list)
            # Should have hashtags from the sample keywords
            assert len(result['hashtags']) > 0


# ============================================================================
# TestBuildPrompt: Prompt Template Building Tests
# ============================================================================


class TestBuildPrompt:
    """Test _build_prompt method"""

    def test_prompt_contains_platform_name(self, repurposing_agent, sample_blog_post):
        """Test prompt includes platform name"""
        prompt = repurposing_agent._build_prompt(
            blog_post=sample_blog_post,
            platform="LinkedIn",
            brand_tone=["Professional"]
        )

        assert "LinkedIn" in prompt

    def test_prompt_contains_blog_title(self, repurposing_agent, sample_blog_post):
        """Test prompt includes blog post title"""
        prompt = repurposing_agent._build_prompt(
            blog_post=sample_blog_post,
            platform="LinkedIn",
            brand_tone=["Professional"]
        )

        assert sample_blog_post['title'] in prompt

    def test_prompt_contains_excerpt(self, repurposing_agent, sample_blog_post):
        """Test prompt includes blog excerpt"""
        prompt = repurposing_agent._build_prompt(
            blog_post=sample_blog_post,
            platform="LinkedIn",
            brand_tone=["Professional"]
        )

        assert sample_blog_post['excerpt'] in prompt

    def test_prompt_contains_keywords(self, repurposing_agent, sample_blog_post):
        """Test prompt includes keywords as comma-separated string"""
        prompt = repurposing_agent._build_prompt(
            blog_post=sample_blog_post,
            platform="LinkedIn",
            brand_tone=["Professional"]
        )

        # Check keywords are included
        for keyword in sample_blog_post['keywords']:
            assert keyword in prompt

    def test_prompt_contains_platform_config_values(self, repurposing_agent, sample_blog_post):
        """Test prompt includes platform-specific configuration values"""
        prompt = repurposing_agent._build_prompt(
            blog_post=sample_blog_post,
            platform="LinkedIn",
            brand_tone=["Professional"]
        )

        # LinkedIn specific values
        assert "3000" in prompt  # max_chars
        assert "1300" in prompt  # optimal_chars

    def test_prompt_contains_multiple_brand_tones(self, repurposing_agent, sample_blog_post):
        """Test prompt with multiple brand tones joins them correctly"""
        prompt = repurposing_agent._build_prompt(
            blog_post=sample_blog_post,
            platform="LinkedIn",
            brand_tone=["Professional", "Friendly", "Inspirational"]
        )

        # All tones should be in the prompt, separated by commas
        assert "Professional" in prompt
        assert "Friendly" in prompt
        assert "Inspirational" in prompt


# ============================================================================
# TestLoadPromptTemplate: Template Loading Tests
# ============================================================================


class TestLoadPromptTemplate:
    """Test _load_prompt_template method"""

    def test_load_template_file_exists(self):
        """Test loading template when file exists"""
        template_content = "Test template content {platform} {topic}"

        with patch('builtins.open', mock_open(read_data=template_content)):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template', return_value=template_content):
                    with patch('src.agents.repurposing_agent.RepurposingAgent.__init__', lambda self, *args, **kwargs: None):
                        agent = RepurposingAgent.__new__(RepurposingAgent)
                        result = agent._load_prompt_template()
                        # Result would be the mock return value

    def test_load_template_file_not_found_raises_error(self):
        """Test loading template when file doesn't exist raises RepurposingError"""
        with patch('pathlib.Path.exists', return_value=False):
            with patch('src.agents.repurposing_agent.RepurposingAgent.__init__', lambda self, *args, **kwargs: None):
                agent = RepurposingAgent.__new__(RepurposingAgent)
                with pytest.raises(RepurposingError) as exc_info:
                    agent._load_prompt_template()
                assert "Prompt template not found" in str(exc_info.value)

    def test_load_template_read_error_raises_error(self):
        """Test loading template when file read fails raises RepurposingError"""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', side_effect=IOError("Permission denied")):
                with patch('src.agents.repurposing_agent.RepurposingAgent.__init__', lambda self, *args, **kwargs: None):
                    agent = RepurposingAgent.__new__(RepurposingAgent)
                    with pytest.raises(RepurposingError) as exc_info:
                        agent._load_prompt_template()
                    assert "Failed to read prompt template" in str(exc_info.value)


# ============================================================================
# TestErrorHandling: Comprehensive Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_agent_error_on_base_generate_wrapped(self, repurposing_agent, sample_blog_post):
        """Test AgentError from BaseAgent is wrapped in RepurposingError"""
        with patch.object(repurposing_agent, 'generate', side_effect=AgentError("Rate limited")):
            with pytest.raises(RepurposingError) as exc_info:
                repurposing_agent._generate_platform_content(
                    blog_post=sample_blog_post,
                    platform="LinkedIn",
                    brand_tone=["Professional"]
                )
            assert "Failed to generate" in str(exc_info.value)

    def test_multiple_platform_errors_listed_in_message(self, repurposing_agent, sample_blog_post):
        """Test RepurposingError lists all platform errors"""
        with patch.object(repurposing_agent, 'generate', side_effect=AgentError("API error")):
            with pytest.raises(RepurposingError) as exc_info:
                repurposing_agent.generate_social_posts(
                    blog_post=sample_blog_post,
                    platforms=["LinkedIn", "Facebook"]
                )
            error_msg = str(exc_info.value)
            assert "Failed to generate" in error_msg

    def test_invalid_blog_post_keys_detailed_error(self, repurposing_agent):
        """Test error message lists all missing blog_post keys"""
        incomplete = {"title": "Test"}  # Missing excerpt, keywords, slug

        with pytest.raises(ValueError) as exc_info:
            repurposing_agent.generate_social_posts(
                blog_post=incomplete,
                platforms=["LinkedIn"]
            )
        error_msg = str(exc_info.value)
        assert "missing required keys" in error_msg

    def test_invalid_platforms_error_lists_valid_options(self, repurposing_agent, sample_blog_post):
        """Test error message includes list of valid platforms"""
        with pytest.raises(ValueError) as exc_info:
            repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["Twitter", "Snapchat"]
            )
        error_msg = str(exc_info.value)
        assert "Valid platforms are" in error_msg
        # Should list at least one valid platform
        assert any(p in error_msg for p in VALID_PLATFORMS)

    def test_none_api_key_raises_error(self):
        """Test None API key raises AgentError"""
        with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template'):
            with pytest.raises(AgentError) as exc_info:
                RepurposingAgent(api_key=None)
            assert "API key is required" in str(exc_info.value)


# ============================================================================
# TestDataTypes: Data Type Validation Tests
# ============================================================================


class TestDataTypes:
    """Test data type correctness in responses"""

    def test_result_cost_is_float(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test cost field is a float"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            assert isinstance(results[0]['cost'], float)

    def test_result_character_count_is_int(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test character_count field is an integer"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            assert isinstance(results[0]['character_count'], int)

    def test_result_hashtags_is_list(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test hashtags field is a list"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            assert isinstance(results[0]['hashtags'], list)

    def test_result_tokens_is_dict(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test tokens field is a dictionary"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            assert isinstance(results[0]['tokens'], dict)

    def test_tokens_has_total_key(self, repurposing_agent, sample_blog_post, base_agent_response):
        """Test tokens dict has 'total' key"""
        with patch.object(repurposing_agent, 'generate', return_value=base_agent_response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            assert 'total' in results[0]['tokens']


# ============================================================================
# TestEdgeCases: Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_single_character_content(self, repurposing_agent, sample_blog_post):
        """Test handling of very short content"""
        response = {
            'content': 'x',
            'tokens': {'prompt': 10, 'completion': 5, 'total': 15},
            'cost': 0.0001
        }

        with patch.object(repurposing_agent, 'generate', return_value=response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            assert len(results) == 1
            assert results[0]['character_count'] == 1

    def test_zero_cost_response(self, repurposing_agent, sample_blog_post):
        """Test handling of zero cost"""
        response = {
            'content': 'Test content',
            'tokens': {'prompt': 0, 'completion': 0, 'total': 0},
            'cost': 0.0
        }

        with patch.object(repurposing_agent, 'generate', return_value=response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            assert results[0]['cost'] == 0.0

    def test_whitespace_in_content(self, repurposing_agent, sample_blog_post):
        """Test content with leading/trailing whitespace is stripped"""
        response = {
            'content': '  Test content with spaces  ',
            'tokens': {'prompt': 100, 'completion': 50, 'total': 150},
            'cost': 0.0002
        }

        with patch.object(repurposing_agent, 'generate', return_value=response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            # Content should be stripped in _generate_platform_content
            content = results[0]['content']
            assert content == content.strip()

    def test_special_characters_in_keywords(self, repurposing_agent):
        """Test hashtags with special characters in keywords"""
        hashtags = repurposing_agent._generate_hashtags(
            keywords=["C++", "C#", "Node.js"],
            platform="LinkedIn"
        )

        # Should handle special characters gracefully
        assert len(hashtags) > 0
        assert all(tag.startswith("#") for tag in hashtags)

    def test_unicode_content_character_count(self, repurposing_agent, sample_blog_post):
        """Test character count with Unicode content"""
        unicode_content = "Öl überrascht Präsidenten" * 10  # German umlauts
        response = {
            'content': unicode_content,
            'tokens': {'prompt': 100, 'completion': 50, 'total': 150},
            'cost': 0.0002
        }

        with patch.object(repurposing_agent, 'generate', return_value=response):
            results = repurposing_agent.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"]
            )

            # Character count should include Unicode characters
            assert results[0]['character_count'] == len(unicode_content)

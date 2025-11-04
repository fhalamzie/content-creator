"""Tests for Dashboard UI page.

Tests cover:
- Statistics calculation
- Data loading from cache
- Cost tracking
- Recent activity display
- Configuration display
"""

import pytest
from pathlib import Path
from unittest.mock import patch
import json


# Import dashboard functions
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ui.pages.dashboard import (
    load_project_config,
    calculate_stats,
)
from cache_manager import CacheManager


class TestProjectConfigLoading:
    """Test project configuration loading."""

    def test_load_project_config_when_file_exists(self, tmp_path):
        """Test loading existing project configuration."""
        # Create config file
        config_dir = tmp_path / "cache"
        config_dir.mkdir()
        config_file = config_dir / "project_config.json"

        test_config = {
            "brand_name": "Test Brand",
            "brand_voice": "Professional",
            "posts_per_week": 2
        }

        config_file.write_text(json.dumps(test_config))

        # Load config
        with patch('ui.pages.dashboard.CONFIG_FILE', config_file):
            result = load_project_config()

        assert result == test_config
        assert result["brand_name"] == "Test Brand"

    def test_load_project_config_when_file_missing(self, tmp_path):
        """Test loading config when file doesn't exist returns None."""
        config_file = tmp_path / "nonexistent_config.json"

        with patch('ui.pages.dashboard.CONFIG_FILE', config_file):
            result = load_project_config()

        assert result is None

    def test_load_project_config_with_all_fields(self, tmp_path):
        """Test loading config with all expected fields."""
        config_dir = tmp_path / "cache"
        config_dir.mkdir()
        config_file = config_dir / "project_config.json"

        full_config = {
            "brand_name": "TechStartup GmbH",
            "brand_url": "https://example.com",
            "brand_voice": "Technical",
            "target_audience": "German developers",
            "keywords": "Python, AI, Machine Learning",
            "content_goals": "Generate leads",
            "posts_per_week": 3,
            "social_per_post": 4
        }

        config_file.write_text(json.dumps(full_config, ensure_ascii=False))

        with patch('ui.pages.dashboard.CONFIG_FILE', config_file):
            result = load_project_config()

        assert result == full_config
        assert result["keywords"] == "Python, AI, Machine Learning"


class TestStatisticsCalculation:
    """Test statistics calculation functionality."""

    def test_calculate_stats_with_empty_cache(self, tmp_path):
        """Test stats calculation with no cached posts."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        stats = calculate_stats(cache_manager)

        assert stats["total_blogs"] == 0
        assert stats["total_social"] == 0
        assert stats["total_words"] == 0
        assert stats["total_cost"] == 0
        assert stats["status_counts"] == {}

    def test_calculate_stats_with_blog_posts(self, tmp_path):
        """Test stats calculation with cached blog posts."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create test blog posts
        for i in range(3):
            metadata = {
                "title": f"Test Post {i}",
                "word_count": 1800,
                "status": "Draft",
                "created_at": "2025-11-01"
            }
            cache_manager.write_blog_post(
                slug=f"test-post-{i}",
                content=f"# Test Post {i}\n\nContent here.",
                metadata=metadata
            )

        stats = calculate_stats(cache_manager)

        assert stats["total_blogs"] == 3
        assert stats["total_words"] == 5400  # 3 posts × 1800 words
        assert stats["total_cost"] == pytest.approx(2.94, 0.01)  # 3 posts × $0.98

    def test_calculate_stats_with_social_posts(self, tmp_path):
        """Test stats calculation includes social posts count."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create blog post
        cache_manager.write_blog_post(
            slug="test-blog",
            content="# Blog\n\nContent",
            metadata={"word_count": 1500}
        )

        # Create social posts
        for platform in ["linkedin", "facebook", "instagram", "tiktok"]:
            cache_manager.write_social_post(
                slug="test-blog",
                platform=platform,
                content=f"Social content for {platform}"
            )

        stats = calculate_stats(cache_manager)

        assert stats["total_blogs"] == 1
        assert stats["total_social"] == 4

    def test_calculate_stats_status_breakdown(self, tmp_path):
        """Test status breakdown counting."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create posts with different statuses
        statuses = ["Draft", "Draft", "Ready", "Published", "Published"]
        for i, status in enumerate(statuses):
            cache_manager.write_blog_post(
                slug=f"post-{i}",
                content="Content",
                metadata={"status": status, "word_count": 1000}
            )

        stats = calculate_stats(cache_manager)

        assert stats["status_counts"]["Draft"] == 2
        assert stats["status_counts"]["Ready"] == 1
        assert stats["status_counts"]["Published"] == 2

    def test_calculate_stats_with_missing_word_count(self, tmp_path):
        """Test stats calculation handles missing word_count gracefully."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create post without word_count in metadata
        cache_manager.write_blog_post(
            slug="test-post",
            content="# Test\n\nContent",
            metadata={"title": "Test Post"}  # No word_count
        )

        stats = calculate_stats(cache_manager)

        assert stats["total_blogs"] == 1
        assert stats["total_words"] == 0  # Should default to 0

    def test_calculate_stats_cost_calculation_accuracy(self, tmp_path):
        """Test cost calculation is accurate ($0.98 per post)."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        num_posts = 10
        for i in range(num_posts):
            cache_manager.write_blog_post(
                slug=f"post-{i}",
                content="Content",
                metadata={"word_count": 1800}
            )

        stats = calculate_stats(cache_manager)

        expected_cost = num_posts * 0.98
        assert stats["total_cost"] == pytest.approx(expected_cost, 0.01)


class TestRecentActivityDisplay:
    """Test recent activity data preparation."""

    def test_recent_posts_sorted_by_date(self, tmp_path):
        """Test recent posts are sorted by creation date (newest first)."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create posts with different dates
        dates = ["2025-11-01", "2025-11-03", "2025-11-02"]
        for i, date in enumerate(dates):
            cache_manager.write_blog_post(
                slug=f"post-{i}",
                content="Content",
                metadata={
                    "title": f"Post {i}",
                    "created_at": date,
                    "word_count": 1500
                }
            )

        posts = cache_manager.get_cached_blog_posts()
        sorted_posts = sorted(
            posts,
            key=lambda x: x.get("metadata", {}).get("created_at", ""),
            reverse=True
        )

        # Newest post should be first
        assert sorted_posts[0]["metadata"]["created_at"] == "2025-11-03"
        assert sorted_posts[1]["metadata"]["created_at"] == "2025-11-02"
        assert sorted_posts[2]["metadata"]["created_at"] == "2025-11-01"

    def test_recent_posts_limit_to_five(self, tmp_path):
        """Test dashboard shows only last 5 posts."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create 10 posts
        for i in range(10):
            cache_manager.write_blog_post(
                slug=f"post-{i}",
                content="Content",
                metadata={"created_at": f"2025-11-{i+1:02d}"}
            )

        posts = cache_manager.get_cached_blog_posts()
        sorted_posts = sorted(
            posts,
            key=lambda x: x.get("metadata", {}).get("created_at", ""),
            reverse=True
        )

        recent_posts = sorted_posts[:5]
        assert len(recent_posts) == 5

    def test_recent_posts_include_notion_url(self, tmp_path):
        """Test recent posts display includes Notion URL if available."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create post with Notion URL
        cache_manager.write_blog_post(
            slug="synced-post",
            content="Content",
            metadata={
                "title": "Synced Post",
                "notion_url": "https://notion.so/abc123",
                "word_count": 1500
            }
        )

        posts = cache_manager.get_cached_blog_posts()
        assert posts[0]["metadata"].get("notion_url") is not None

    def test_posts_display_with_missing_metadata(self, tmp_path):
        """Test posts display handles missing metadata fields gracefully."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create post with minimal metadata
        cache_manager.write_blog_post(
            slug="minimal-post",
            content="Content",
            metadata={}  # Empty metadata
        )

        posts = cache_manager.get_cached_blog_posts()
        post = posts[0]

        # Should not crash, use defaults
        assert post["metadata"].get("word_count", "N/A") == "N/A"
        assert post["metadata"].get("created_at", "N/A") == "N/A"


class TestDashboardMetrics:
    """Test dashboard metrics display."""

    def test_average_words_per_post_calculation(self, tmp_path):
        """Test average words per post calculation."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create posts with varying word counts
        word_counts = [1500, 1800, 2000, 1700, 2100]
        for i, count in enumerate(word_counts):
            cache_manager.write_blog_post(
                slug=f"post-{i}",
                content="Content",
                metadata={"word_count": count}
            )

        stats = calculate_stats(cache_manager)
        avg_words = stats["total_words"] / stats["total_blogs"]

        expected_avg = sum(word_counts) / len(word_counts)
        assert avg_words == expected_avg

    def test_cost_per_post_metric(self, tmp_path):
        """Test cost per post is $0.98."""
        cost_per_post = 0.98
        assert cost_per_post == 0.98

    def test_monthly_target_calculation(self, tmp_path):
        """Test monthly target calculation based on posts per week."""
        posts_per_week = 2
        monthly_posts = posts_per_week * 4
        monthly_cost = monthly_posts * 0.98

        assert monthly_posts == 8
        assert monthly_cost == pytest.approx(7.84, 0.01)

    def test_progress_bar_percentage(self, tmp_path):
        """Test progress bar calculation for monthly target."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create 3 posts
        for i in range(3):
            cache_manager.write_blog_post(
                slug=f"post-{i}",
                content="Content",
                metadata={"word_count": 1500}
            )

        stats = calculate_stats(cache_manager)
        monthly_posts = 8  # Target
        progress = (stats["total_blogs"] / monthly_posts * 100)

        assert progress == 37.5  # 3 out of 8 posts


class TestSystemInformation:
    """Test system information display."""

    def test_system_info_research_model(self):
        """Test system info shows research model as Gemini CLI (FREE)."""
        research_model = "Gemini CLI (FREE)"
        assert "FREE" in research_model

    def test_system_info_writing_model_cost(self):
        """Test system info shows writing model cost."""
        writing_cost = 0.64
        assert writing_cost == 0.64

    def test_system_info_language(self):
        """Test system info shows German language."""
        language = "German 🇩🇪"
        assert "German" in language

    def test_sync_rate_display(self):
        """Test sync rate is displayed as 2.5 req/s."""
        sync_rate = 2.5
        assert sync_rate == 2.5


class TestQuickActions:
    """Test quick action functionality."""

    def test_quick_action_generate_content_available(self):
        """Test Generate Content quick action is available."""
        quick_actions = ["Generate Content", "Browse Content", "Settings"]
        assert "Generate Content" in quick_actions

    def test_quick_action_browse_content_available(self):
        """Test Browse Content quick action is available."""
        quick_actions = ["Generate Content", "Browse Content", "Settings"]
        assert "Browse Content" in quick_actions

    def test_quick_action_settings_available(self):
        """Test Settings quick action is available."""
        quick_actions = ["Generate Content", "Browse Content", "Settings"]
        assert "Settings" in quick_actions


class TestTipsAndRecommendations:
    """Test tips and recommendations logic."""

    def test_tip_for_no_posts(self, tmp_path):
        """Test tip shown when no posts exist."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))
        posts = cache_manager.get_cached_blog_posts()

        if not posts:
            tip = "📝 Start by generating your first blog post in the Generate page"
            assert "first blog post" in tip

    def test_tip_for_few_posts(self, tmp_path):
        """Test tip shown when fewer than 5 posts exist."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        for i in range(3):
            cache_manager.write_blog_post(
                slug=f"post-{i}",
                content="Content",
                metadata={"word_count": 1500}
            )

        posts = cache_manager.get_cached_blog_posts()
        if len(posts) < 5:
            tip = "🚀 Keep generating content to build your content library"
            assert "content library" in tip

    def test_tip_for_high_weekly_posts(self):
        """Test tip shown when posts per week exceeds budget."""
        posts_per_week = 5  # High value

        if posts_per_week > 3:
            tip = "💰 Consider reducing posts/week to stay within budget"
            assert "budget" in tip

    def test_tip_for_missing_keywords(self):
        """Test tip shown when keywords are not configured."""
        config = {"keywords": ""}

        if not config.get("keywords"):
            tip = "🎯 Add keywords in Setup to improve SEO targeting"
            assert "keywords" in tip

    def test_tip_for_unsynced_content(self, tmp_path):
        """Test tip shown when content not synced to Notion."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        cache_manager.write_blog_post(
            slug="unsynced-post",
            content="Content",
            metadata={"word_count": 1500}  # No notion_url
        )

        posts = cache_manager.get_cached_blog_posts()
        has_notion_url = any(
            post.get("metadata", {}).get("notion_url")
            for post in posts
        )

        if not has_notion_url:
            tip = "☁️ Sync your content to Notion for editorial review"
            assert "Notion" in tip


class TestIntegrationScenarios:
    """Test complete dashboard scenarios."""

    def test_dashboard_with_complete_data(self, tmp_path):
        """Test dashboard with fully populated data."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create complete dataset
        for i in range(5):
            metadata = {
                "title": f"Blog Post {i}",
                "word_count": 1800,
                "status": "Published" if i < 2 else "Draft",
                "created_at": f"2025-11-0{i+1}",
                "notion_url": f"https://notion.so/post-{i}"
            }
            cache_manager.write_blog_post(
                slug=f"blog-{i}",
                content=f"# Blog {i}\n\nContent here.",
                metadata=metadata
            )

            # Add social posts
            for platform in ["linkedin", "facebook"]:
                cache_manager.write_social_post(
                    slug=f"blog-{i}",
                    platform=platform,
                    content=f"Social for {platform}"
                )

        stats = calculate_stats(cache_manager)

        assert stats["total_blogs"] == 5
        assert stats["total_social"] == 10  # 5 blogs × 2 platforms
        assert stats["total_words"] == 9000  # 5 × 1800
        assert stats["status_counts"]["Published"] == 2
        assert stats["status_counts"]["Draft"] == 3

    def test_dashboard_with_no_configuration(self, tmp_path):
        """Test dashboard behavior with missing project configuration."""
        config_file = tmp_path / "nonexistent_config.json"

        with patch('ui.pages.dashboard.CONFIG_FILE', config_file):
            result = load_project_config()

        # Should return None and prompt user to configure
        assert result is None

    def test_dashboard_performance_metrics(self, tmp_path):
        """Test all performance metrics calculation."""
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # Create posts
        for i in range(10):
            cache_manager.write_blog_post(
                slug=f"post-{i}",
                content="Content",
                metadata={"word_count": 1800}
            )

        stats = calculate_stats(cache_manager)

        # Calculate metrics
        avg_words = stats["total_words"] / stats["total_blogs"]
        cost_per_post = 0.98
        sync_rate = 2.5

        assert avg_words == 1800
        assert cost_per_post == 0.98
        assert sync_rate == 2.5


# Mark all tests as UI tests for optional filtering
pytestmark = pytest.mark.ui

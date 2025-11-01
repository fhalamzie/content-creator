"""
Tests for cache_manager.py

TDD approach: Write tests first, then implement.
Coverage target: 100% (critical path component)
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from src.cache_manager import CacheManager


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory for testing"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def cache_manager(temp_cache_dir):
    """Create CacheManager instance with temp directory"""
    return CacheManager(cache_dir=str(temp_cache_dir))


class TestCacheManagerInitialization:
    """Test cache manager initialization and directory creation"""

    def test_creates_cache_directory_if_not_exists(self, tmp_path):
        cache_dir = tmp_path / "new_cache"
        manager = CacheManager(cache_dir=str(cache_dir))
        assert cache_dir.exists()

    def test_creates_subdirectories_on_init(self, cache_manager, temp_cache_dir):
        expected_dirs = [
            "blog_posts",
            "social_posts",
            "research",
            "sync_logs"
        ]
        for subdir in expected_dirs:
            assert (temp_cache_dir / subdir).exists()


class TestBlogPostOperations:
    """Test blog post caching (markdown + metadata)"""

    def test_write_blog_post_creates_markdown_file(self, cache_manager, temp_cache_dir):
        slug = "test-post"
        content = "# Test Blog Post\n\nThis is content."
        metadata = {
            "title": "Test Post",
            "author": "Test Author",
            "created_at": datetime.now().isoformat()
        }

        cache_manager.write_blog_post(slug, content, metadata)

        md_file = temp_cache_dir / "blog_posts" / f"{slug}.md"
        assert md_file.exists()
        assert md_file.read_text() == content

    def test_write_blog_post_creates_metadata_file(self, cache_manager, temp_cache_dir):
        slug = "test-post"
        content = "# Test Blog Post"
        metadata = {
            "title": "Test Post",
            "word_count": 500,
            "keywords": ["test", "blog"]
        }

        cache_manager.write_blog_post(slug, content, metadata)

        meta_file = temp_cache_dir / "blog_posts" / f"{slug}_metadata.json"
        assert meta_file.exists()

        saved_metadata = json.loads(meta_file.read_text())
        assert saved_metadata["title"] == "Test Post"
        assert saved_metadata["word_count"] == 500
        assert saved_metadata["keywords"] == ["test", "blog"]

    def test_read_blog_post_returns_content_and_metadata(self, cache_manager):
        slug = "test-post"
        content = "# Test Blog Post\n\nContent here."
        metadata = {"title": "Test Post", "status": "draft"}

        cache_manager.write_blog_post(slug, content, metadata)
        result = cache_manager.read_blog_post(slug)

        assert result["content"] == content
        assert result["metadata"]["title"] == "Test Post"
        assert result["metadata"]["status"] == "draft"

    def test_read_blog_post_raises_error_if_not_exists(self, cache_manager):
        with pytest.raises(FileNotFoundError):
            cache_manager.read_blog_post("nonexistent-post")

    def test_list_blog_posts_returns_all_slugs(self, cache_manager):
        cache_manager.write_blog_post("post-1", "Content 1", {"title": "Post 1"})
        cache_manager.write_blog_post("post-2", "Content 2", {"title": "Post 2"})
        cache_manager.write_blog_post("post-3", "Content 3", {"title": "Post 3"})

        posts = cache_manager.list_blog_posts()
        assert len(posts) == 3
        assert "post-1" in posts
        assert "post-2" in posts
        assert "post-3" in posts

    def test_list_blog_posts_returns_empty_list_if_none(self, cache_manager):
        posts = cache_manager.list_blog_posts()
        assert posts == []


class TestSocialPostOperations:
    """Test social media post caching"""

    def test_write_social_post_creates_markdown_file(self, cache_manager, temp_cache_dir):
        slug = "test-post"
        platform = "linkedin"
        content = "This is a LinkedIn post.\n\n#AI #ContentCreation"

        cache_manager.write_social_post(slug, platform, content)

        social_file = temp_cache_dir / "social_posts" / f"{slug}_{platform}.md"
        assert social_file.exists()
        assert social_file.read_text() == content

    def test_write_social_post_for_multiple_platforms(self, cache_manager):
        slug = "test-post"
        platforms = ["linkedin", "facebook", "instagram", "tiktok"]

        for platform in platforms:
            content = f"Content for {platform}"
            cache_manager.write_social_post(slug, platform, content)

        for platform in platforms:
            result = cache_manager.read_social_post(slug, platform)
            assert result == f"Content for {platform}"

    def test_read_social_post_raises_error_if_not_exists(self, cache_manager):
        with pytest.raises(FileNotFoundError):
            cache_manager.read_social_post("nonexistent", "linkedin")

    def test_list_social_posts_for_slug(self, cache_manager):
        slug = "test-post"
        cache_manager.write_social_post(slug, "linkedin", "LinkedIn content")
        cache_manager.write_social_post(slug, "facebook", "Facebook content")

        platforms = cache_manager.list_social_posts(slug)
        assert len(platforms) == 2
        assert "linkedin" in platforms
        assert "facebook" in platforms


class TestResearchDataOperations:
    """Test research data caching (JSON)"""

    def test_write_research_data_creates_json_file(self, cache_manager, temp_cache_dir):
        slug = "test-topic"
        research_data = {
            "topic": "AI Content Generation",
            "keywords": ["AI", "content", "automation"],
            "sources": [
                {"title": "Source 1", "url": "https://example.com/1"},
                {"title": "Source 2", "url": "https://example.com/2"}
            ],
            "competitor_gaps": ["Gap 1", "Gap 2"],
            "search_volume": 1500
        }

        cache_manager.write_research_data(slug, research_data)

        research_file = temp_cache_dir / "research" / f"{slug}_research.json"
        assert research_file.exists()

        saved_data = json.loads(research_file.read_text())
        assert saved_data["topic"] == "AI Content Generation"
        assert len(saved_data["sources"]) == 2
        assert saved_data["search_volume"] == 1500

    def test_read_research_data_returns_dict(self, cache_manager):
        slug = "test-topic"
        research_data = {
            "keywords": ["test", "keywords"],
            "sources": []
        }

        cache_manager.write_research_data(slug, research_data)
        result = cache_manager.read_research_data(slug)

        assert result["keywords"] == ["test", "keywords"]
        assert result["sources"] == []

    def test_read_research_data_raises_error_if_not_exists(self, cache_manager):
        with pytest.raises(FileNotFoundError):
            cache_manager.read_research_data("nonexistent-topic")


class TestSyncLogOperations:
    """Test sync log operations"""

    def test_write_sync_log_creates_json_file(self, cache_manager, temp_cache_dir):
        log_data = {
            "last_sync": datetime.now().isoformat(),
            "synced_posts": ["post-1", "post-2"],
            "failed_posts": [],
            "total_requests": 10,
            "duration_seconds": 4.5
        }

        cache_manager.write_sync_log(log_data)

        log_file = temp_cache_dir / "sync_logs" / "sync_status.json"
        assert log_file.exists()

        saved_log = json.loads(log_file.read_text())
        assert len(saved_log["synced_posts"]) == 2
        assert saved_log["total_requests"] == 10

    def test_read_sync_log_returns_dict(self, cache_manager):
        log_data = {
            "last_sync": "2025-11-01T12:00:00",
            "synced_posts": ["post-1"]
        }

        cache_manager.write_sync_log(log_data)
        result = cache_manager.read_sync_log()

        assert result["last_sync"] == "2025-11-01T12:00:00"
        assert result["synced_posts"] == ["post-1"]

    def test_read_sync_log_returns_empty_dict_if_not_exists(self, cache_manager):
        result = cache_manager.read_sync_log()
        assert result == {}


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_write_blog_post_with_empty_content(self, cache_manager):
        """Empty content should be allowed (draft posts)"""
        cache_manager.write_blog_post("empty-post", "", {"title": "Empty"})
        result = cache_manager.read_blog_post("empty-post")
        assert result["content"] == ""

    def test_write_blog_post_with_special_characters_in_slug(self, cache_manager):
        """Slugs should be sanitized"""
        slug = "test post with spaces!"
        cache_manager.write_blog_post(slug, "Content", {"title": "Test"})
        result = cache_manager.read_blog_post(slug)
        assert result["content"] == "Content"

    def test_write_social_post_with_invalid_platform(self, cache_manager):
        """Invalid platform names should raise ValueError"""
        with pytest.raises(ValueError):
            cache_manager.write_social_post("post", "invalid_platform", "Content")

    def test_handles_corrupted_json_gracefully(self, cache_manager, temp_cache_dir):
        """Corrupted JSON files should raise helpful errors"""
        # Create markdown file first
        md_file = temp_cache_dir / "blog_posts" / "corrupted.md"
        md_file.write_text("# Corrupted Post")

        # Create corrupted metadata JSON
        meta_file = temp_cache_dir / "blog_posts" / "corrupted_metadata.json"
        meta_file.write_text("{ invalid json }")

        with pytest.raises(json.JSONDecodeError):
            cache_manager.read_blog_post("corrupted")


class TestCacheClearance:
    """Test cache clearing operations"""

    def test_clear_blog_post_removes_files(self, cache_manager, temp_cache_dir):
        slug = "test-post"
        cache_manager.write_blog_post(slug, "Content", {"title": "Test"})

        cache_manager.clear_blog_post(slug)

        md_file = temp_cache_dir / "blog_posts" / f"{slug}.md"
        meta_file = temp_cache_dir / "blog_posts" / f"{slug}_metadata.json"
        assert not md_file.exists()
        assert not meta_file.exists()

    def test_clear_all_cache_removes_all_files(self, cache_manager):
        cache_manager.write_blog_post("post-1", "Content 1", {"title": "Post 1"})
        cache_manager.write_blog_post("post-2", "Content 2", {"title": "Post 2"})
        cache_manager.write_social_post("post-1", "linkedin", "LinkedIn content")
        cache_manager.write_research_data("topic-1", {"keywords": ["test"]})

        cache_manager.clear_all_cache()

        assert cache_manager.list_blog_posts() == []
        with pytest.raises(FileNotFoundError):
            cache_manager.read_social_post("post-1", "linkedin")

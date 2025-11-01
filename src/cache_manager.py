"""
Cache Manager

Handles disk-based caching for blog posts, social media content, research data,
and sync logs. Implements write-through cache pattern with human-readable formats.

Design Principles:
- Write to disk BEFORE syncing to Notion
- Human-readable formats (*.md for content, JSON for metadata)
- Fail-safe: cache persists on API failures
- Version control friendly: plain text files
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

VALID_PLATFORMS = ["linkedin", "facebook", "instagram", "tiktok"]


class CacheManager:
    """
    Manages disk cache for all content types.

    Directory structure:
        cache/
        ├── blog_posts/{slug}.md + {slug}_metadata.json
        ├── social_posts/{slug}_{platform}.md
        ├── research/{slug}_research.json
        └── sync_logs/sync_status.json
    """

    def __init__(self, cache_dir: str = "cache"):
        """
        Initialize cache manager and create directories.

        Args:
            cache_dir: Root cache directory path
        """
        self.cache_dir = Path(cache_dir)
        self._create_directories()
        logger.info(f"CacheManager initialized with cache_dir={cache_dir}")

    def _create_directories(self) -> None:
        """Create cache directory structure if not exists"""
        subdirs = ["blog_posts", "social_posts", "research", "sync_logs"]
        self.cache_dir.mkdir(exist_ok=True, parents=True)

        for subdir in subdirs:
            (self.cache_dir / subdir).mkdir(exist_ok=True, parents=True)

    # ==================== Blog Post Operations ====================

    def write_blog_post(self, slug: str, content: str, metadata: Dict[str, Any]) -> None:
        """
        Write blog post content and metadata to disk.

        Args:
            slug: Post slug (filename)
            content: Markdown content
            metadata: Post metadata (title, author, keywords, etc.)

        Raises:
            IOError: If file write fails
        """
        blog_dir = self.cache_dir / "blog_posts"

        # Write markdown content
        md_file = blog_dir / f"{slug}.md"
        md_file.write_text(content, encoding="utf-8")

        # Write metadata JSON
        meta_file = blog_dir / f"{slug}_metadata.json"
        meta_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"Wrote blog post: {slug} ({len(content)} chars)")

    def read_blog_post(self, slug: str) -> Dict[str, Any]:
        """
        Read blog post content and metadata from disk.

        Args:
            slug: Post slug

        Returns:
            Dict with 'content' and 'metadata' keys

        Raises:
            FileNotFoundError: If post doesn't exist
            json.JSONDecodeError: If metadata JSON is corrupted
        """
        blog_dir = self.cache_dir / "blog_posts"
        md_file = blog_dir / f"{slug}.md"
        meta_file = blog_dir / f"{slug}_metadata.json"

        if not md_file.exists():
            raise FileNotFoundError(f"Blog post not found: {slug}")

        content = md_file.read_text(encoding="utf-8")
        metadata = json.loads(meta_file.read_text(encoding="utf-8"))

        return {"content": content, "metadata": metadata}

    def list_blog_posts(self) -> List[str]:
        """
        List all cached blog post slugs.

        Returns:
            List of slugs
        """
        blog_dir = self.cache_dir / "blog_posts"
        md_files = blog_dir.glob("*.md")

        # Extract slugs from filenames
        slugs = [f.stem for f in md_files]
        return sorted(slugs)

    def clear_blog_post(self, slug: str) -> None:
        """
        Remove blog post and metadata from cache.

        Args:
            slug: Post slug to remove
        """
        blog_dir = self.cache_dir / "blog_posts"
        md_file = blog_dir / f"{slug}.md"
        meta_file = blog_dir / f"{slug}_metadata.json"

        md_file.unlink(missing_ok=True)
        meta_file.unlink(missing_ok=True)

        logger.info(f"Cleared blog post: {slug}")

    # ==================== Social Post Operations ====================

    def write_social_post(self, slug: str, platform: str, content: str) -> None:
        """
        Write social media post to disk.

        Args:
            slug: Blog post slug (parent post)
            platform: Social platform (linkedin, facebook, instagram, tiktok)
            content: Platform-specific content

        Raises:
            ValueError: If platform is invalid
            IOError: If file write fails
        """
        if platform not in VALID_PLATFORMS:
            raise ValueError(
                f"Invalid platform: {platform}. "
                f"Must be one of {VALID_PLATFORMS}"
            )

        social_dir = self.cache_dir / "social_posts"
        social_file = social_dir / f"{slug}_{platform}.md"

        social_file.write_text(content, encoding="utf-8")
        logger.info(f"Wrote social post: {slug}_{platform} ({len(content)} chars)")

    def read_social_post(self, slug: str, platform: str) -> str:
        """
        Read social media post from disk.

        Args:
            slug: Blog post slug
            platform: Social platform

        Returns:
            Post content

        Raises:
            FileNotFoundError: If post doesn't exist
        """
        social_dir = self.cache_dir / "social_posts"
        social_file = social_dir / f"{slug}_{platform}.md"

        if not social_file.exists():
            raise FileNotFoundError(
                f"Social post not found: {slug}_{platform}"
            )

        return social_file.read_text(encoding="utf-8")

    def list_social_posts(self, slug: str) -> List[str]:
        """
        List all social platforms for a blog post.

        Args:
            slug: Blog post slug

        Returns:
            List of platforms
        """
        social_dir = self.cache_dir / "social_posts"
        pattern = f"{slug}_*.md"
        social_files = social_dir.glob(pattern)

        # Extract platform names from filenames
        platforms = [f.stem.replace(f"{slug}_", "") for f in social_files]
        return sorted(platforms)

    # ==================== Research Data Operations ====================

    def write_research_data(self, slug: str, research_data: Dict[str, Any]) -> None:
        """
        Write research data to disk.

        Args:
            slug: Topic slug
            research_data: Research results (keywords, sources, gaps, etc.)

        Raises:
            IOError: If file write fails
        """
        research_dir = self.cache_dir / "research"
        research_file = research_dir / f"{slug}_research.json"

        research_file.write_text(
            json.dumps(research_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        logger.info(f"Wrote research data: {slug}")

    def read_research_data(self, slug: str) -> Dict[str, Any]:
        """
        Read research data from disk.

        Args:
            slug: Topic slug

        Returns:
            Research data dict

        Raises:
            FileNotFoundError: If research data doesn't exist
            json.JSONDecodeError: If JSON is corrupted
        """
        research_dir = self.cache_dir / "research"
        research_file = research_dir / f"{slug}_research.json"

        if not research_file.exists():
            raise FileNotFoundError(f"Research data not found: {slug}")

        return json.loads(research_file.read_text(encoding="utf-8"))

    # ==================== Sync Log Operations ====================

    def write_sync_log(self, log_data: Dict[str, Any]) -> None:
        """
        Write sync status log.

        Args:
            log_data: Sync status (last_sync, synced_posts, failed_posts, etc.)

        Raises:
            IOError: If file write fails
        """
        log_dir = self.cache_dir / "sync_logs"
        log_file = log_dir / "sync_status.json"

        log_file.write_text(
            json.dumps(log_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        logger.info("Wrote sync log")

    def read_sync_log(self) -> Dict[str, Any]:
        """
        Read sync status log.

        Returns:
            Sync log data, or empty dict if not exists
        """
        log_dir = self.cache_dir / "sync_logs"
        log_file = log_dir / "sync_status.json"

        if not log_file.exists():
            return {}

        return json.loads(log_file.read_text(encoding="utf-8"))

    # ==================== Cache Clearance ====================

    def get_cached_blog_posts(self) -> List[Dict[str, Any]]:
        """
        Get all cached blog posts.

        Returns:
            List of dicts with 'slug', 'content', 'metadata'
        """
        slugs = self.list_blog_posts()
        posts = []

        for slug in slugs:
            try:
                post_data = self.read_blog_post(slug)
                posts.append({
                    'slug': slug,
                    'content': post_data['content'],
                    'metadata': post_data['metadata']
                })
            except Exception as e:
                logger.warning(f"Failed to read cached blog post {slug}: {e}")

        logger.info(f"Retrieved {len(posts)} cached blog posts")
        return posts

    def get_cached_social_posts(self) -> List[Dict[str, Any]]:
        """
        Get all cached social posts.

        Returns:
            List of dicts with 'platform', 'content', 'blog_slug'
        """
        # Get all blog slugs first
        blog_slugs = self.list_blog_posts()
        social_posts = []

        for slug in blog_slugs:
            platforms = self.list_social_posts(slug)
            for platform in platforms:
                try:
                    content = self.read_social_post(slug, platform)
                    social_posts.append({
                        'platform': platform,
                        'content': content,
                        'blog_slug': slug
                    })
                except Exception as e:
                    logger.warning(f"Failed to read social post {slug}/{platform}: {e}")

        logger.info(f"Retrieved {len(social_posts)} cached social posts")
        return social_posts

    def save_blog_post(
        self,
        content: str,
        metadata: Dict[str, Any],
        topic: str
    ) -> str:
        """
        Save blog post to cache (convenience wrapper for write_blog_post).

        Args:
            content: Blog post markdown content
            metadata: Blog post metadata
            topic: Topic (used to generate slug)

        Returns:
            Cache file path
        """
        # Generate slug from topic
        slug = topic.lower().replace(' ', '-').replace('/', '-')[:50]

        # Write to cache
        self.write_blog_post(slug=slug, content=content, metadata=metadata)

        # Return cache path
        cache_path = self.cache_dir / "blog_posts" / f"{slug}.md"
        return str(cache_path)

    def clear_all_cache(self) -> None:
        """
        Remove all cached content (DESTRUCTIVE).

        WARNING: This deletes all cached data. Use with caution.
        """
        import shutil

        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self._create_directories()

        logger.warning("Cleared all cache")

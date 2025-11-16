"""
Content Cache Utilities

Helper functions to save blog posts and social posts to SQLite database.
Ensures all content is persisted BEFORE Notion sync (single source of truth).

Design Goals:
- Simple API: save_blog_post(), save_social_posts()
- SQLite first, Notion second
- Graceful error handling (log but don't crash)
- WAL mode enabled for concurrent access
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.database.sqlite_manager import SQLiteManager
from src.utils.research_cache import slugify

logger = logging.getLogger(__name__)


def save_blog_post_to_db(
    title: str,
    content: str,
    metadata: Dict[str, Any],
    hero_image_url: Optional[str] = None,
    supporting_images: Optional[List[Dict]] = None,
    research_topic_id: Optional[str] = None,
    db_path: str = "data/topics.db"
) -> str:
    """
    Save blog post to SQLite database (single source of truth).

    Args:
        title: Blog post title
        content: Full blog post content (markdown)
        metadata: Dict with word_count, brand_voice, target_audience, language, etc.
        hero_image_url: Optional hero image URL
        supporting_images: Optional list of supporting images
        research_topic_id: Optional reference to research topic (slug)
        db_path: Path to SQLite database

    Returns:
        Blog post ID (slug)

    Example:
        >>> blog_id = save_blog_post_to_db(
        ...     title="PropTech Trends 2025",
        ...     content="# PropTech Trends...",
        ...     metadata={"word_count": 1500, "language": "de"},
        ...     hero_image_url="https://s3.../hero.jpg"
        ... )
        'proptech-trends-2025'
    """
    # Generate slug
    slug = slugify(title)

    logger.info(f"saving_blog_post_to_db: title={title}, slug={slug}, words={metadata.get('word_count', 0)}")

    # Extract metadata
    excerpt = content[:200] if content else ""
    word_count = metadata.get("word_count", len(content.split()))
    language = metadata.get("language", "de")
    brand_voice = metadata.get("brand_voice", "Professional")
    target_audience = metadata.get("target_audience", "")

    # SEO fields
    keywords = metadata.get("keywords", [])
    primary_keyword = metadata.get("primary_keyword", title)
    meta_description = metadata.get("meta_description", excerpt)

    # Open database connection
    db_manager = SQLiteManager(db_path=db_path)

    try:
        with db_manager._get_connection() as conn:
            # Check if blog post already exists
            cursor = conn.execute("SELECT id FROM blog_posts WHERE slug = ?", (slug,))
            existing = cursor.fetchone()

            if existing:
                # Update existing blog post
                logger.info(f"updating_existing_blog_post: slug={slug}")

                conn.execute("""
                    UPDATE blog_posts SET
                        title = ?,
                        content = ?,
                        excerpt = ?,
                        meta_description = ?,
                        keywords = ?,
                        primary_keyword = ?,
                        word_count = ?,
                        language = ?,
                        brand_voice = ?,
                        target_audience = ?,
                        hero_image_url = ?,
                        hero_image_alt = ?,
                        supporting_images = ?,
                        research_topic_id = ?,
                        updated_at = ?
                    WHERE slug = ?
                """, (
                    title,
                    content,
                    excerpt,
                    meta_description,
                    json.dumps(keywords) if keywords else None,
                    primary_keyword,
                    word_count,
                    language,
                    brand_voice,
                    target_audience,
                    hero_image_url,
                    metadata.get("hero_image_alt"),
                    json.dumps(supporting_images) if supporting_images else None,
                    research_topic_id,
                    datetime.utcnow().isoformat(),
                    slug
                ))
            else:
                # Insert new blog post
                logger.info(f"inserting_new_blog_post: slug={slug}")

                conn.execute("""
                    INSERT INTO blog_posts (
                        id, slug, title, content, excerpt,
                        meta_description, keywords, primary_keyword,
                        word_count, language, brand_voice, target_audience,
                        hero_image_url, hero_image_alt, supporting_images,
                        research_topic_id,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    slug, slug, title, content, excerpt,
                    meta_description, json.dumps(keywords) if keywords else None, primary_keyword,
                    word_count, language, brand_voice, target_audience,
                    hero_image_url, metadata.get("hero_image_alt"), json.dumps(supporting_images) if supporting_images else None,
                    research_topic_id,
                    'draft', datetime.utcnow().isoformat(), datetime.utcnow().isoformat()
                ))

            conn.commit()

        logger.info(f"blog_post_saved_to_db: slug={slug}, words={word_count}")
        return slug

    except Exception as e:
        logger.error(f"failed_to_save_blog_post: title={title}, error={str(e)}")
        # Don't crash - log and return slug anyway (markdown cache still exists)
        return slug


def save_social_posts_to_db(
    blog_post_id: str,
    social_posts: List[Dict[str, Any]],
    db_path: str = "data/topics.db"
) -> int:
    """
    Save social media posts to SQLite database.

    Args:
        blog_post_id: Blog post slug (references blog_posts table)
        social_posts: List of social post dicts (platform, content, hashtags, image, etc.)
        db_path: Path to SQLite database

    Returns:
        Number of social posts saved

    Example:
        >>> social_posts = [
        ...     {
        ...         "platform": "LinkedIn",
        ...         "content": "Exciting PropTech trends...",
        ...         "hashtags": ["#PropTech", "#RealEstate"],
        ...         "character_count": 150,
        ...         "image": {"url": "https://...", "provider": "og"}
        ...     }
        ... ]
        >>> saved_count = save_social_posts_to_db("proptech-trends-2025", social_posts)
        4
    """
    if not social_posts:
        logger.info(f"no_social_posts_to_save: blog_post_id={blog_post_id}")
        return 0

    logger.info(f"saving_social_posts_to_db: blog_post_id={blog_post_id}, count={len(social_posts)}")

    db_manager = SQLiteManager(db_path=db_path)
    saved_count = 0

    try:
        with db_manager._get_connection() as conn:
            for post in social_posts:
                platform = post.get("platform", "Unknown")
                content = post.get("content", "")
                hashtags = post.get("hashtags", [])
                character_count = post.get("character_count", len(content))
                language = post.get("language", "de")

                # Image info
                image = post.get("image", {})
                image_url = image.get("url") if image else None
                image_provider = image.get("provider") if image else None

                # Generate unique ID
                social_post_id = f"{blog_post_id}_{platform.lower()}"

                # Check if social post already exists
                cursor = conn.execute("SELECT id FROM social_posts WHERE id = ?", (social_post_id,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing social post
                    logger.info(f"updating_social_post: id={social_post_id}")

                    conn.execute("""
                        UPDATE social_posts SET
                            content = ?,
                            hashtags = ?,
                            character_count = ?,
                            language = ?,
                            image_url = ?,
                            image_provider = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        content,
                        json.dumps(hashtags) if hashtags else None,
                        character_count,
                        language,
                        image_url,
                        image_provider,
                        datetime.utcnow().isoformat(),
                        social_post_id
                    ))
                else:
                    # Insert new social post
                    logger.info(f"inserting_social_post: id={social_post_id}")

                    conn.execute("""
                        INSERT INTO social_posts (
                            id, blog_post_id, platform, content,
                            hashtags, character_count, language,
                            image_url, image_provider,
                            status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        social_post_id, blog_post_id, platform, content,
                        json.dumps(hashtags) if hashtags else None, character_count, language,
                        image_url, image_provider,
                        'draft', datetime.utcnow().isoformat(), datetime.utcnow().isoformat()
                    ))

                saved_count += 1

            conn.commit()

        logger.info(f"social_posts_saved_to_db: blog_post_id={blog_post_id}, saved={saved_count}")
        return saved_count

    except Exception as e:
        logger.error(f"failed_to_save_social_posts: blog_post_id={blog_post_id}, error={str(e)}")
        # Don't crash - return count of posts attempted
        return saved_count

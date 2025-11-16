"""
Research Cache Utilities

Helper functions to save and load deep research reports from SQLite database.
Enables research reuse across Quick Create and Hybrid Orchestrator.

Design Goals:
- Simple API: save_research(), load_research()
- Slug-based lookup: Convert topics to URL-safe slugs
- Fallback support: Return None if not found (for graceful fallback)
- Database integration: Uses SQLiteManager for persistence
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from src.database.sqlite_manager import SQLiteManager
from src.models.topic import Topic, TopicSource, TopicStatus

logger = logging.getLogger(__name__)


def slugify(text: str, max_length: int = 100) -> str:
    """
    Convert text to URL-safe slug.

    German umlaut support:
    - ä → ae, ö → oe, ü → ue, ß → ss

    Args:
        text: Text to slugify
        max_length: Maximum slug length (default: 100)

    Returns:
        URL-safe slug (lowercase, hyphens, no special chars)

    Examples:
        >>> slugify("PropTech Trends 2025")
        'proptech-trends-2025'
        >>> slugify("KI-Einsatz in Hausverwaltung")
        'ki-einsatz-in-hausverwaltung'
        >>> slugify("Schädlingsbekämpfung für Wohnungen")
        'schaedlingsbekaempfung-fuer-wohnungen'
    """
    # Normalize German umlauts
    umlaut_map = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'ß': 'ss'
    }

    for umlaut, replacement in umlaut_map.items():
        text = text.replace(umlaut, replacement)

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)

    # Trim hyphens from ends
    text = text.strip('-')

    # Limit length
    if len(text) > max_length:
        text = text[:max_length].rsplit('-', 1)[0]

    return text


def save_research_to_cache(
    topic: str,
    research_article: str,
    sources: list,
    config: Optional[Dict[str, Any]] = None,
    db_path: str = "data/topics.db"
) -> str:
    """
    Save deep research report to SQLite database for reuse.

    Args:
        topic: Topic title
        research_article: Generated research article (2000+ words with citations)
        sources: List of source dicts (url, title, snippet)
        config: Optional market configuration (market, vertical, language, domain)
        db_path: Path to SQLite database (default: data/topics.db)

    Returns:
        Topic ID (slug)

    Example:
        >>> save_research_to_cache(
        ...     topic="PropTech Trends 2025",
        ...     research_article="# PropTech Trends 2025...",
        ...     sources=[{"url": "...", "title": "..."}],
        ...     config={"market": "Germany", "vertical": "PropTech", "language": "de"}
        ... )
        'proptech-trends-2025'
    """
    # Generate slug
    topic_id = slugify(topic)

    logger.info(f"saving_research_to_cache: topic={topic}, topic_id={topic_id}, article_length={len(research_article)}, sources={len(sources)}")

    # Extract config values
    config = config or {}
    market = config.get("market", "")
    vertical = config.get("vertical", "")
    language = config.get("language", "en")
    domain = config.get("domain", "")

    # Create Topic model
    topic_obj = Topic(
        id=topic_id,
        title=topic,
        description=research_article[:200],  # First 200 chars as description
        source=TopicSource.MANUAL,  # Manual/Hybrid Orchestrator research
        source_url=None,
        discovered_at=datetime.utcnow(),
        domain=domain,
        market=market,
        language=language,
        intent=None,
        engagement_score=0,
        trending_score=0.0,
        priority=5,
        content_score=None,
        research_report=research_article,  # Full article
        citations=[s.get("url", "") for s in sources],  # Extract URLs
        word_count=len(research_article.split()),
        minhash_signature=None,
        status=TopicStatus.RESEARCHED,
        notion_id=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        published_at=None
    )

    # Save to database
    db_manager = SQLiteManager(db_path=db_path)

    try:
        # Check if topic already exists
        existing = db_manager.get_topic(topic_id)

        if existing:
            # Update existing topic
            logger.info("updating_existing_topic", topic_id=topic_id)
            db_manager.update_topic(topic_obj)
        else:
            # Insert new topic
            logger.info("inserting_new_topic", topic_id=topic_id)
            db_manager.insert_topic(topic_obj)

        logger.info(f"research_saved_to_cache: topic_id={topic_id}, words={topic_obj.word_count}, sources={len(sources)}")

        return topic_id

    except Exception as e:
        logger.error(f"failed_to_save_research: topic={topic}, error={str(e)}")
        raise


def load_research_from_cache(
    topic: str,
    db_path: str = "data/topics.db"
) -> Optional[Dict[str, Any]]:
    """
    Load cached research report from SQLite database.

    Args:
        topic: Topic title (will be slugified for lookup)
        db_path: Path to SQLite database (default: data/topics.db)

    Returns:
        Dict with:
            - topic: str - Original topic title
            - research_article: str - Full research article
            - sources: List[str] - Source URLs
            - word_count: int - Article word count
            - language: str - Content language
            - cached_at: str - ISO timestamp when cached

        Returns None if not found in cache.

    Example:
        >>> cached = load_research_from_cache("PropTech Trends 2025")
        >>> if cached:
        ...     print(f"Found cached research: {cached['word_count']} words")
        ...     print(cached['research_article'][:100])
        ... else:
        ...     print("Not in cache, need to research")
    """
    # Generate slug for lookup
    topic_id = slugify(topic)

    logger.info(f"looking_up_cached_research: topic={topic}, topic_id={topic_id}")

    # Query database
    db_manager = SQLiteManager(db_path=db_path)

    try:
        topic_obj = db_manager.get_topic(topic_id)

        if not topic_obj:
            logger.info(f"research_not_in_cache: topic_id={topic_id}")
            return None

        # Check if research report exists
        if not topic_obj.research_report:
            logger.info(f"topic_found_but_no_research: topic_id={topic_id}")
            return None

        logger.info(f"research_found_in_cache: topic_id={topic_id}, words={topic_obj.word_count}, status={topic_obj.status.value}")

        # Return structured data
        cached_at = topic_obj.updated_at if hasattr(topic_obj, 'updated_at') and topic_obj.updated_at else datetime.utcnow()

        return {
            "topic": topic_obj.title,
            "research_article": topic_obj.research_report,
            "sources": topic_obj.citations or [],
            "word_count": topic_obj.word_count,
            "language": topic_obj.language or "en",
            "cached_at": cached_at.isoformat() if hasattr(cached_at, 'isoformat') else str(cached_at),
            "summary": topic_obj.description or "",
            "keywords": []  # TODO: Extract from article if needed
        }

    except Exception as e:
        logger.error(f"failed_to_load_cached_research: topic={topic}, error={str(e)}")
        # Return None on error (graceful fallback)
        return None


def clear_research_cache(
    topic: Optional[str] = None,
    db_path: str = "data/topics.db"
) -> int:
    """
    Clear cached research from database.

    Args:
        topic: Optional topic to delete (if None, clears all)
        db_path: Path to SQLite database

    Returns:
        Number of topics deleted

    Example:
        >>> clear_research_cache("PropTech Trends 2025")  # Delete one
        1
        >>> clear_research_cache()  # Clear all
        42
    """
    db_manager = SQLiteManager(db_path=db_path)

    if topic:
        # Delete single topic
        topic_id = slugify(topic)
        logger.info(f"deleting_cached_research: topic_id={topic_id}")

        try:
            db_manager.delete_topic(topic_id)
            return 1
        except Exception as e:
            logger.error(f"failed_to_delete_topic: topic_id={topic_id}, error={str(e)}")
            return 0
    else:
        # Clear all topics
        logger.warning("clearing_all_cached_research")

        try:
            # Get all topics
            # TODO: Add get_all_topics() method to SQLiteManager
            # For now, return 0 (feature not implemented)
            logger.warning("clear_all_not_implemented")
            return 0
        except Exception as e:
            logger.error(f"failed_to_clear_cache: error={str(e)}")
            return 0

"""
RSS Feed Database Manager

Manages a curated database of RSS feeds organized by domain and vertical.

Structure:
{
  "domains": {
    "medicine": {
      "cardiology": [
        {
          "url": "https://example.com/feed",
          "title": "Cardiology News",
          "quality_score": 0.85,
          "last_validated": "2025-11-16T10:00:00",
          ...
        }
      ],
      "oncology": [...]
    },
    "technology": {
      "saas": [...],
      "ai": [...]
    }
  },
  "metadata": {
    "version": "1.0",
    "last_updated": "2025-11-16T10:00:00",
    "total_feeds": 1250,
    "total_domains": 15,
    "total_verticals": 120
  }
}
"""

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.collectors.rss_feed_discoverer import RSSFeed
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RSSFeedDatabase:
    """
    Manages RSS feed database with CRUD operations.

    Usage:
        db = RSSFeedDatabase()

        # Add feed
        feed = RSSFeed(url="https://example.com/feed", ...)
        db.add_feed(domain="technology", vertical="saas", feed=feed)

        # Query feeds
        feeds = db.get_feeds(domain="technology", vertical="saas")

        # Get all verticals in a domain
        verticals = db.get_verticals("technology")
    """

    def __init__(self, database_path: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            database_path: Path to database JSON file
        """
        self.database_path = database_path or os.path.join(
            os.path.dirname(__file__),
            "..",
            "config",
            "rss_feeds_database.json"
        )

        # Ensure config directory exists
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)

        # Load or initialize database
        self.db = self._load_database()

        logger.info(
            "rss_database_initialized",
            path=self.database_path,
            domains=len(self.db.get("domains", {})),
            total_feeds=self.db.get("metadata", {}).get("total_feeds", 0)
        )

    def _load_database(self) -> Dict:
        """
        Load database from JSON file or create new.

        Returns:
            Database dictionary
        """
        if os.path.exists(self.database_path):
            try:
                with open(self.database_path, 'r', encoding='utf-8') as f:
                    db = json.load(f)

                logger.info(
                    "database_loaded",
                    path=self.database_path,
                    domains=len(db.get("domains", {}))
                )

                return db

            except Exception as e:
                logger.error(
                    "database_load_failed",
                    path=self.database_path,
                    error=str(e)
                )

        # Create new database
        logger.info("creating_new_database", path=self.database_path)
        return self._create_empty_database()

    def _create_empty_database(self) -> Dict:
        """
        Create empty database structure.

        Returns:
            Empty database dictionary
        """
        return {
            "domains": {},
            "metadata": {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_feeds": 0,
                "total_domains": 0,
                "total_verticals": 0
            }
        }

    def save(self) -> bool:
        """
        Save database to JSON file.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update metadata
            self._update_metadata()

            # Write to file
            with open(self.database_path, 'w', encoding='utf-8') as f:
                json.dump(self.db, f, indent=2, ensure_ascii=False)

            logger.info(
                "database_saved",
                path=self.database_path,
                total_feeds=self.db["metadata"]["total_feeds"]
            )

            return True

        except Exception as e:
            logger.error(
                "database_save_failed",
                path=self.database_path,
                error=str(e)
            )
            return False

    def _update_metadata(self):
        """Update metadata counters."""
        total_feeds = 0
        total_verticals = 0

        for domain, verticals in self.db["domains"].items():
            total_verticals += len(verticals)
            for vertical, feeds in verticals.items():
                total_feeds += len(feeds)

        self.db["metadata"]["last_updated"] = datetime.now().isoformat()
        self.db["metadata"]["total_feeds"] = total_feeds
        self.db["metadata"]["total_domains"] = len(self.db["domains"])
        self.db["metadata"]["total_verticals"] = total_verticals

    def add_feed(
        self,
        domain: str,
        vertical: str,
        feed: RSSFeed,
        allow_duplicates: bool = False
    ) -> bool:
        """
        Add a feed to the database.

        Args:
            domain: Domain category (e.g., "technology", "medicine")
            vertical: Vertical within domain (e.g., "saas", "cardiology")
            feed: RSS feed to add
            allow_duplicates: Allow duplicate URLs (default: False)

        Returns:
            True if added, False if duplicate and allow_duplicates=False
        """
        # Ensure domain exists
        if domain not in self.db["domains"]:
            self.db["domains"][domain] = {}

        # Ensure vertical exists
        if vertical not in self.db["domains"][domain]:
            self.db["domains"][domain][vertical] = []

        # Check for duplicates
        if not allow_duplicates:
            existing_urls = {f["url"] for f in self.db["domains"][domain][vertical]}
            if feed.url in existing_urls:
                logger.debug(
                    "feed_already_exists",
                    domain=domain,
                    vertical=vertical,
                    url=feed.url
                )
                return False

        # Convert feed to dict
        feed_dict = {
            "url": feed.url,
            "source_url": feed.source_url,
            "title": feed.title,
            "description": feed.description,
            "discovery_method": feed.discovery_method,
            "quality_score": feed.quality_score,
            "last_updated": feed.last_updated.isoformat() if feed.last_updated else None,
            "article_count": feed.article_count,
            "is_valid": feed.is_valid,
            "discovered_at": feed.discovered_at.isoformat() if hasattr(feed, 'discovered_at') else datetime.now().isoformat(),
            "last_validated": datetime.now().isoformat()
        }

        # Add to database
        self.db["domains"][domain][vertical].append(feed_dict)

        logger.info(
            "feed_added",
            domain=domain,
            vertical=vertical,
            url=feed.url,
            quality_score=feed.quality_score
        )

        return True

    def get_feeds(
        self,
        domain: Optional[str] = None,
        vertical: Optional[str] = None,
        min_quality_score: float = 0.0,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Query feeds from database.

        Args:
            domain: Filter by domain (None = all domains)
            vertical: Filter by vertical (None = all verticals)
            min_quality_score: Minimum quality score threshold
            limit: Maximum number of feeds to return

        Returns:
            List of feed dictionaries, sorted by quality score (descending)
        """
        feeds = []

        # Determine domains to search
        if domain:
            domains = [domain] if domain in self.db["domains"] else []
        else:
            domains = list(self.db["domains"].keys())

        # Collect feeds
        for dom in domains:
            # Determine verticals to search
            if vertical:
                verticals = [vertical] if vertical in self.db["domains"][dom] else []
            else:
                verticals = list(self.db["domains"][dom].keys())

            for vert in verticals:
                domain_feeds = self.db["domains"][dom][vert]

                # Filter by quality score
                filtered = [
                    {**f, "domain": dom, "vertical": vert}
                    for f in domain_feeds
                    if f.get("quality_score", 0.0) >= min_quality_score
                ]

                feeds.extend(filtered)

        # Sort by quality score (descending)
        feeds.sort(key=lambda f: -f.get("quality_score", 0.0))

        # Apply limit
        if limit:
            feeds = feeds[:limit]

        logger.debug(
            "feeds_queried",
            domain=domain,
            vertical=vertical,
            min_quality_score=min_quality_score,
            results=len(feeds)
        )

        return feeds

    def get_domains(self) -> List[str]:
        """
        Get all domain names.

        Returns:
            List of domain names
        """
        return sorted(self.db["domains"].keys())

    def get_verticals(self, domain: str) -> List[str]:
        """
        Get all verticals in a domain.

        Args:
            domain: Domain name

        Returns:
            List of vertical names
        """
        if domain not in self.db["domains"]:
            return []

        return sorted(self.db["domains"][domain].keys())

    def get_statistics(self) -> Dict:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_feeds": self.db["metadata"]["total_feeds"],
            "total_domains": self.db["metadata"]["total_domains"],
            "total_verticals": self.db["metadata"]["total_verticals"],
            "last_updated": self.db["metadata"]["last_updated"],
            "domains": {}
        }

        # Per-domain statistics
        for domain, verticals in self.db["domains"].items():
            domain_stats = {
                "verticals": len(verticals),
                "feeds": sum(len(feeds) for feeds in verticals.values()),
                "avg_quality": 0.0
            }

            # Calculate average quality
            all_feeds = [f for feeds in verticals.values() for f in feeds]
            if all_feeds:
                domain_stats["avg_quality"] = sum(
                    f.get("quality_score", 0.0) for f in all_feeds
                ) / len(all_feeds)

            stats["domains"][domain] = domain_stats

        return stats

    def remove_low_quality_feeds(self, min_quality_score: float = 0.3) -> int:
        """
        Remove feeds below quality threshold.

        Args:
            min_quality_score: Minimum quality score to keep

        Returns:
            Number of feeds removed
        """
        removed_count = 0

        for domain in self.db["domains"]:
            for vertical in self.db["domains"][domain]:
                original_count = len(self.db["domains"][domain][vertical])

                # Filter feeds
                self.db["domains"][domain][vertical] = [
                    f for f in self.db["domains"][domain][vertical]
                    if f.get("quality_score", 0.0) >= min_quality_score
                ]

                removed_count += original_count - len(self.db["domains"][domain][vertical])

        if removed_count > 0:
            logger.info(
                "low_quality_feeds_removed",
                count=removed_count,
                min_quality_score=min_quality_score
            )

        return removed_count

    def export_feeds_list(
        self,
        domain: Optional[str] = None,
        vertical: Optional[str] = None,
        output_format: str = "urls"
    ) -> List[str]:
        """
        Export feeds as list of URLs or titles.

        Args:
            domain: Filter by domain (None = all)
            vertical: Filter by vertical (None = all)
            output_format: "urls" or "titles"

        Returns:
            List of URLs or titles
        """
        feeds = self.get_feeds(domain=domain, vertical=vertical)

        if output_format == "urls":
            return [f["url"] for f in feeds]
        elif output_format == "titles":
            return [f.get("title", f["url"]) for f in feeds]
        else:
            raise ValueError(f"Invalid output_format: {output_format}")

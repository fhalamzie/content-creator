#!/usr/bin/env python3
"""
Import RSS-Link-Database-2024

Imports curated RSS feeds from the RSS-Link-Database-2024 GitHub repository.

Source: https://github.com/rumca-js/RSS-Link-Database-2024

Usage:
    python scripts/import_rss_link_database.py
"""

import json
import os
import sys
from typing import Dict

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.collectors.rss_feed_database import RSSFeedDatabase
from src.collectors.rss_feed_discoverer import RSSFeed
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Category mapping: JSON category -> (domain, vertical)
CATEGORY_MAPPING = {
    # News domain
    ("News", "News"): ("news", "general"),
    ("News", "Politics"): ("news", "politics"),
    ("News", "World"): ("news", "world"),

    # Technology domain
    ("Tech", "Tech"): ("technology", "general"),
    ("Tech", "Programming"): ("technology", "programming"),
    ("Tech", "Linux"): ("technology", "linux"),
    ("Tech", "Android"): ("technology", "android"),
    ("Tech", "Apple"): ("technology", "apple"),
    ("Tech", "Security"): ("technology", "security"),
    ("Tech", "AI"): ("technology", "ai"),

    # Hobby domain -> lifestyle
    ("Hobby", "3D Printing"): ("lifestyle", "3d-printing"),
    ("Hobby", "Board Games"): ("entertainment", "board-games"),
    ("Hobby", "Books"): ("entertainment", "books"),
    ("Hobby", "Tabletop"): ("entertainment", "tabletop"),

    # Entertainment domain
    ("Entertainment", "Movies"): ("entertainment", "movies"),
    ("Entertainment", "Gaming"): ("entertainment", "gaming"),
    ("Entertainment", "Music"): ("entertainment", "music"),
    ("Entertainment", "Comedy"): ("entertainment", "comedy"),

    # Science domain
    ("Science", "Science"): ("science", "general"),
    ("Science", "Space"): ("science", "space"),
    ("Science", "Physics"): ("science", "physics"),

    # Cars domain -> sports
    ("Cars", "Cars"): ("sports", "cars"),

    # VR domain -> technology
    ("VR", "VR"): ("technology", "vr"),

    # Art domain -> lifestyle
    ("Art", "Art"): ("lifestyle", "art"),

    # Travel domain -> lifestyle
    ("Travel", "Travel"): ("lifestyle", "travel"),

    # Religion domain -> education
    ("Religion", "Religion"): ("education", "religion"),
}


def normalize_category(category: str, subcategory: str) -> tuple:
    """
    Normalize category and subcategory to domain and vertical.

    Args:
        category: Category name
        subcategory: Subcategory name

    Returns:
        Tuple of (domain, vertical)
    """
    # Try exact match
    key = (category, subcategory)
    if key in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[key]

    # Try category-only match
    for (cat, subcat), (domain, vertical) in CATEGORY_MAPPING.items():
        if cat == category:
            return (domain, subcategory.lower().replace(" ", "-"))

    # Default: use category as domain, subcategory as vertical
    return (
        category.lower().replace(" ", "-"),
        subcategory.lower().replace(" ", "-")
    )


def import_rss_link_database(json_path: str = "temp/rss-link-database-2024.json"):
    """
    Import RSS feeds from JSON database.

    Args:
        json_path: Path to JSON file
    """
    print(f"\n{'=' * 60}")
    print(f"🚀 RSS-Link-Database-2024 Importer")
    print(f"{'=' * 60}\n")

    # Load JSON
    print(f"📂 Loading: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        feeds_data = json.load(f)

    print(f"   Found {len(feeds_data)} feeds\n")

    # Initialize database
    database = RSSFeedDatabase()

    # Statistics
    stats = {
        "total": len(feeds_data),
        "imported": 0,
        "duplicates": 0,
        "disabled": 0,
        "errors": 0
    }

    # Import feeds
    for feed_data in feeds_data:
        try:
            # Skip disabled feeds
            if not feed_data.get("enabled", True):
                stats["disabled"] += 1
                continue

            # Get domain and vertical
            category = feed_data.get("category_name", "uncategorized")
            subcategory = feed_data.get("subcategory_name", "general")
            domain, vertical = normalize_category(category, subcategory)

            # Create RSSFeed object
            rss_feed = RSSFeed(
                url=feed_data["url"],
                source_url=feed_data.get("proxy_location", feed_data["url"]),
                title=feed_data.get("title", "Untitled"),
                description=None,
                discovery_method="rss-link-database",
                quality_score=0.5,  # Default score (not validated yet)
                is_valid=True
            )

            # Import to database
            added = database.add_feed(
                domain=domain,
                vertical=vertical,
                feed=rss_feed,
                allow_duplicates=False
            )

            if added:
                stats["imported"] += 1
            else:
                stats["duplicates"] += 1

        except Exception as e:
            logger.error("feed_import_error", error=str(e), feed=feed_data.get("title"))
            stats["errors"] += 1

    # Save database
    print(f"\n💾 Saving database...")
    database.save()

    # Print statistics
    print(f"\n" + "=" * 60)
    print(f"📊 Import Statistics")
    print(f"=" * 60)
    print(f"Total feeds:         {stats['total']}")
    print(f"Imported:            {stats['imported']}")
    print(f"Duplicates skipped:  {stats['duplicates']}")
    print(f"Disabled skipped:    {stats['disabled']}")
    print(f"Errors:              {stats['errors']}")
    print(f"=" * 60)

    # Database statistics
    db_stats = database.get_statistics()
    print(f"\n📚 Database Statistics")
    print(f"=" * 60)
    print(f"Total feeds:         {db_stats['total_feeds']}")
    print(f"Total domains:       {db_stats['total_domains']}")
    print(f"Total verticals:     {db_stats['total_verticals']}")
    print(f"=" * 60)

    # Per-domain statistics
    print(f"\n🗂️  Feeds by Domain")
    print(f"=" * 60)
    for domain, domain_stats in sorted(db_stats['domains'].items(), key=lambda x: -x[1]['feeds']):
        print(f"{domain:20} {domain_stats['feeds']:4} feeds across {domain_stats['verticals']:2} verticals")
    print(f"=" * 60)

    logger.info(
        "import_complete",
        stats=stats,
        db_stats=db_stats
    )

    print(f"\n✅ Import complete!")
    print(f"\n📄 Database saved to: {database.database_path}")
    print(f"\n🎉 You now have {db_stats['total_feeds']} RSS feeds!\n")


if __name__ == "__main__":
    import_rss_link_database()

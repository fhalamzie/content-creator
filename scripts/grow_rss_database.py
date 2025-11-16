#!/usr/bin/env python3
"""
Grow RSS Database

Automatically discovers and adds RSS feeds to the database.

Usage:
    # Discover feeds for a specific vertical
    python scripts/grow_rss_database.py --domain technology --vertical proptech --max-feeds 20

    # Grow all verticals to target size
    python scripts/grow_rss_database.py --grow-all --target 30

    # Run daily growth (add 100-200 feeds)
    python scripts/grow_rss_database.py --daily
"""

import argparse
import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.collectors.automated_feed_discovery import AutomatedFeedDiscovery
from src.collectors.rss_feed_database import RSSFeedDatabase
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def discover_for_vertical(
    domain: str,
    vertical: str,
    max_feeds: int = 20,
    language: str = "en",
    region: str = "US"
):
    """Discover feeds for a specific vertical."""
    print(f"\n🔍 Discovering feeds for {domain}/{vertical}...")
    print(f"Target: {max_feeds} feeds\n")

    discovery = AutomatedFeedDiscovery(
        min_quality_score=0.6,
        auto_add_to_database=True
    )

    feeds = await discovery.discover_for_vertical(
        domain=domain,
        vertical=vertical,
        max_feeds=max_feeds,
        language=language,
        region=region
    )

    stats = discovery.get_statistics()

    print(f"\n✅ Discovery Complete!")
    print(f"=" * 60)
    print(f"Seed URLs generated:  {stats['seed_urls_generated']}")
    print(f"Websites crawled:     {stats['websites_crawled']}")
    print(f"Feeds discovered:     {stats['feeds_discovered']}")
    print(f"Feeds added:          {stats['feeds_added']}")
    print(f"Feeds rejected:       {stats['feeds_rejected']}")
    print(f"=" * 60)


async def grow_all_verticals(
    target_per_vertical: int = 30,
    language: str = "en",
    region: str = "US"
):
    """Grow all verticals to target size."""
    print(f"\n🌱 Growing database to {target_per_vertical} feeds per vertical...")

    discovery = AutomatedFeedDiscovery(
        min_quality_score=0.6,
        auto_add_to_database=True
    )

    stats = await discovery.grow_database(
        feeds_per_vertical=target_per_vertical,
        language=language,
        region=region
    )

    print(f"\n✅ Database Growth Complete!")
    print(f"=" * 60)
    print(f"Domains processed:    {stats['domains_processed']}")
    print(f"Verticals processed:  {stats['verticals_processed']}")
    print(f"Feeds added:          {stats['feeds_added']}")
    print(f"=" * 60)

    # Show final database stats
    database = RSSFeedDatabase()
    db_stats = database.get_statistics()

    print(f"\n📊 Final Database Statistics")
    print(f"=" * 60)
    print(f"Total feeds:          {db_stats['total_feeds']}")
    print(f"Total domains:        {db_stats['total_domains']}")
    print(f"Total verticals:      {db_stats['total_verticals']}")
    print(f"=" * 60)


async def daily_growth(
    target_new_feeds: int = 150,
    language: str = "en",
    region: str = "US"
):
    """
    Run daily growth: discover 100-200 new feeds.

    Strategy:
    1. Get verticals with <30 feeds
    2. Discover 10-15 feeds for each
    3. Stop when target reached
    """
    print(f"\n📅 Running daily growth (target: {target_new_feeds} new feeds)...")

    database = RSSFeedDatabase()
    discovery = AutomatedFeedDiscovery(
        min_quality_score=0.6,
        auto_add_to_database=True
    )

    # Get all verticals with <30 feeds
    verticals_to_grow = []
    for domain in database.get_domains():
        for vertical in database.get_verticals(domain):
            current_feeds = database.get_feeds(domain=domain, vertical=vertical)
            if len(current_feeds) < 30:
                verticals_to_grow.append((domain, vertical, len(current_feeds)))

    # Sort by feed count (grow smallest first)
    verticals_to_grow.sort(key=lambda x: x[2])

    print(f"Found {len(verticals_to_grow)} verticals with <30 feeds\n")

    total_added = 0

    for domain, vertical, current_count in verticals_to_grow:
        if total_added >= target_new_feeds:
            break

        needed = min(15, 30 - current_count)  # Add 10-15 feeds per vertical

        print(f"\n🔍 {domain}/{vertical} (current: {current_count}, adding: {needed})")

        feeds = await discovery.discover_for_vertical(
            domain=domain,
            vertical=vertical,
            max_feeds=needed,
            language=language,
            region=region
        )

        total_added += len(feeds)
        print(f"   ✅ Added {len(feeds)} feeds (total: {total_added}/{target_new_feeds})")

    stats = discovery.get_statistics()

    print(f"\n✅ Daily Growth Complete!")
    print(f"=" * 60)
    print(f"Verticals processed:  {stats.get('verticals_processed', len(verticals_to_grow))}")
    print(f"Websites crawled:     {stats['websites_crawled']}")
    print(f"Feeds discovered:     {stats['feeds_discovered']}")
    print(f"Feeds added:          {stats['feeds_added']}")
    print(f"=" * 60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Grow RSS feed database")

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--vertical",
        action="store_true",
        help="Discover feeds for a specific vertical"
    )
    mode_group.add_argument(
        "--grow-all",
        action="store_true",
        help="Grow all verticals to target size"
    )
    mode_group.add_argument(
        "--daily",
        action="store_true",
        help="Run daily growth (100-200 feeds)"
    )

    # Vertical mode options
    parser.add_argument(
        "--domain",
        help="Domain name (required for --vertical mode)"
    )
    parser.add_argument(
        "--vertical-name",
        dest="vertical_name",
        help="Vertical name (required for --vertical mode)"
    )
    parser.add_argument(
        "--max-feeds",
        type=int,
        default=20,
        help="Maximum feeds to discover (default: 20)"
    )

    # Grow all mode options
    parser.add_argument(
        "--target",
        type=int,
        default=30,
        help="Target feeds per vertical (default: 30)"
    )

    # Daily mode options
    parser.add_argument(
        "--target-new-feeds",
        type=int,
        default=150,
        help="Target new feeds for daily run (default: 150)"
    )

    # Common options
    parser.add_argument(
        "--language",
        default="en",
        help="Language code (default: en)"
    )
    parser.add_argument(
        "--region",
        default="US",
        help="Region code (default: US)"
    )

    args = parser.parse_args()

    # Validate vertical mode requirements
    if args.vertical and (not args.domain or not args.vertical_name):
        parser.error("--vertical mode requires --domain and --vertical-name")

    # Run selected mode
    if args.vertical:
        await discover_for_vertical(
            domain=args.domain,
            vertical=args.vertical_name,
            max_feeds=args.max_feeds,
            language=args.language,
            region=args.region
        )

    elif args.grow_all:
        await grow_all_verticals(
            target_per_vertical=args.target,
            language=args.language,
            region=args.region
        )

    elif args.daily:
        await daily_growth(
            target_new_feeds=args.target_new_feeds,
            language=args.language,
            region=args.region
        )


if __name__ == "__main__":
    asyncio.run(main())

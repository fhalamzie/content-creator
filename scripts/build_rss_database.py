#!/usr/bin/env python3
"""
RSS Feed Database Builder

Automated crawler that discovers RSS feeds across domains and verticals.

Usage:
    # Crawl specific domain and vertical
    python scripts/build_rss_database.py --domain technology --vertical saas --limit 20

    # Crawl from predefined config
    python scripts/build_rss_database.py --config scripts/rss_crawler_config.json

    # Crawl all configured domains
    python scripts/build_rss_database.py --all

Example Config (rss_crawler_config.json):
    {
      "domains": {
        "technology": ["saas", "ai", "cybersecurity", "cloud"],
        "medicine": ["cardiology", "oncology", "neurology"],
        "business": ["entrepreneurship", "marketing", "finance"]
      },
      "search_queries_per_vertical": 10,
      "sites_per_query": 5,
      "min_quality_score": 0.5
    }
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.collectors.rss_feed_discoverer import RSSFeedDiscoverer
from src.collectors.rss_feed_database import RSSFeedDatabase
from src.agents.gemini_agent import GeminiAgent
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RSSFeedCrawler:
    """
    Automated RSS feed crawler using web search + feed discovery.
    """

    def __init__(
        self,
        database_path: Optional[str] = None,
        search_queries_per_vertical: int = 10,
        sites_per_query: int = 5,
        min_quality_score: float = 0.5
    ):
        """
        Initialize crawler.

        Args:
            database_path: Path to RSS feed database
            search_queries_per_vertical: Number of search queries per vertical
            sites_per_query: Number of websites to check per search query
            min_quality_score: Minimum quality score to save feed
        """
        self.discoverer = RSSFeedDiscoverer()
        self.database = RSSFeedDatabase(database_path)
        self.gemini_agent = GeminiAgent()
        self.search_queries_per_vertical = search_queries_per_vertical
        self.sites_per_query = sites_per_query
        self.min_quality_score = min_quality_score

        # Statistics
        self.stats = {
            "domains_processed": 0,
            "verticals_processed": 0,
            "websites_crawled": 0,
            "feeds_discovered": 0,
            "feeds_saved": 0,
            "errors": 0
        }

    async def generate_search_queries(
        self,
        domain: str,
        vertical: str,
        count: int = 10
    ) -> List[str]:
        """
        Generate search queries for a domain/vertical using LLM.

        Args:
            domain: Domain category (e.g., "technology")
            vertical: Vertical within domain (e.g., "saas")
            count: Number of queries to generate

        Returns:
            List of search queries optimized for finding blogs/news sites
        """
        prompt = f"""Generate {count} Google search queries to find high-quality blogs, news sites, and publications in this niche:

Domain: {domain}
Vertical: {vertical}

Requirements:
- Focus on finding sites that likely have RSS feeds (blogs, news sites, publications)
- Include variations like "top blogs", "news sites", "industry publications"
- Target authoritative sources, not random forums
- Make queries specific and actionable

Return ONLY a JSON array of search query strings:
["query 1", "query 2", ...]"""

        try:
            response_schema = {
                "type": "array",
                "items": {"type": "string"}
            }

            response = await self.gemini_agent.generate_async(
                prompt=prompt,
                response_schema=response_schema,
                temperature=0.7
            )

            queries = json.loads(response['content'])
            logger.info(
                "search_queries_generated",
                domain=domain,
                vertical=vertical,
                count=len(queries)
            )

            return queries[:count]

        except Exception as e:
            logger.error(
                "search_query_generation_failed",
                domain=domain,
                vertical=vertical,
                error=str(e)
            )

            # Fallback to simple queries
            return [
                f"top {vertical} blogs {domain}",
                f"best {vertical} news sites",
                f"{vertical} industry publications"
            ]

    async def search_websites(
        self,
        query: str,
        limit: int = 5
    ) -> List[str]:
        """
        Search for websites using Gemini grounding.

        Args:
            query: Search query
            limit: Maximum number of URLs to return

        Returns:
            List of website URLs
        """
        prompt = f"""Find the top {limit} websites for this search query: "{query}"

Return ONLY a JSON array of URLs (homepage URLs, not article pages):
["https://example1.com", "https://example2.com", ...]"""

        try:
            response_schema = {
                "type": "array",
                "items": {"type": "string", "format": "uri"}
            }

            response = await self.gemini_agent.generate_async(
                prompt=prompt,
                response_schema=response_schema,
                temperature=0.3,
                use_grounding=True  # Enable Google Search grounding
            )

            urls = json.loads(response['content'])

            # Normalize URLs (remove paths, keep domain)
            from urllib.parse import urlparse
            normalized_urls = []
            for url in urls:
                parsed = urlparse(url)
                normalized = f"{parsed.scheme}://{parsed.netloc}"
                if normalized not in normalized_urls:
                    normalized_urls.append(normalized)

            logger.info(
                "websites_found",
                query=query,
                count=len(normalized_urls)
            )

            return normalized_urls[:limit]

        except Exception as e:
            logger.error(
                "website_search_failed",
                query=query,
                error=str(e)
            )
            return []

    async def crawl_vertical(
        self,
        domain: str,
        vertical: str,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """
        Crawl a single vertical: generate queries → search websites → discover feeds.

        Args:
            domain: Domain category
            vertical: Vertical within domain
            progress_callback: Optional callback(message, progress_pct)

        Returns:
            Statistics dictionary
        """
        logger.info(
            "vertical_crawl_started",
            domain=domain,
            vertical=vertical
        )

        vertical_stats = {
            "queries_generated": 0,
            "websites_found": 0,
            "websites_crawled": 0,
            "feeds_discovered": 0,
            "feeds_saved": 0
        }

        # Step 1: Generate search queries
        if progress_callback:
            progress_callback(f"Generating search queries for {vertical}...", 10)

        queries = await self.generate_search_queries(
            domain=domain,
            vertical=vertical,
            count=self.search_queries_per_vertical
        )
        vertical_stats["queries_generated"] = len(queries)

        # Step 2: Search for websites
        all_websites = set()

        for i, query in enumerate(queries, 1):
            if progress_callback:
                progress_pct = 10 + (40 * i / len(queries))
                progress_callback(f"Searching: {query[:50]}...", progress_pct)

            websites = await self.search_websites(query, limit=self.sites_per_query)
            all_websites.update(websites)

            # Rate limiting
            await asyncio.sleep(1)

        vertical_stats["websites_found"] = len(all_websites)
        logger.info(
            "websites_collected",
            domain=domain,
            vertical=vertical,
            count=len(all_websites)
        )

        # Step 3: Discover RSS feeds
        for i, website in enumerate(all_websites, 1):
            if progress_callback:
                progress_pct = 50 + (50 * i / len(all_websites))
                progress_callback(f"Discovering feeds: {website[:40]}...", progress_pct)

            try:
                feeds = await self.discoverer.discover_feeds(website)
                vertical_stats["websites_crawled"] += 1

                # Filter by quality score
                quality_feeds = [
                    f for f in feeds
                    if f.is_valid and f.quality_score >= self.min_quality_score
                ]

                vertical_stats["feeds_discovered"] += len(quality_feeds)

                # Save to database
                for feed in quality_feeds:
                    added = self.database.add_feed(
                        domain=domain,
                        vertical=vertical,
                        feed=feed,
                        allow_duplicates=False
                    )

                    if added:
                        vertical_stats["feeds_saved"] += 1

                logger.info(
                    "website_crawled",
                    website=website,
                    feeds_found=len(quality_feeds)
                )

            except Exception as e:
                logger.error(
                    "website_crawl_failed",
                    website=website,
                    error=str(e)
                )
                self.stats["errors"] += 1

            # Rate limiting
            await asyncio.sleep(0.5)

        # Save database after vertical
        self.database.save()

        logger.info(
            "vertical_crawl_complete",
            domain=domain,
            vertical=vertical,
            stats=vertical_stats
        )

        # Update global stats
        self.stats["verticals_processed"] += 1
        self.stats["websites_crawled"] += vertical_stats["websites_crawled"]
        self.stats["feeds_discovered"] += vertical_stats["feeds_discovered"]
        self.stats["feeds_saved"] += vertical_stats["feeds_saved"]

        return vertical_stats

    async def crawl_domain(
        self,
        domain: str,
        verticals: List[str],
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """
        Crawl all verticals in a domain.

        Args:
            domain: Domain category
            verticals: List of verticals to crawl
            progress_callback: Optional callback(message, progress_pct)

        Returns:
            Statistics dictionary
        """
        logger.info(
            "domain_crawl_started",
            domain=domain,
            verticals=len(verticals)
        )

        domain_stats = {
            "verticals": {},
            "total_feeds_saved": 0
        }

        for i, vertical in enumerate(verticals, 1):
            if progress_callback:
                progress_callback(
                    f"Crawling {domain}/{vertical} ({i}/{len(verticals)})...",
                    (i - 1) / len(verticals) * 100
                )

            vertical_stats = await self.crawl_vertical(
                domain=domain,
                vertical=vertical,
                progress_callback=None  # Use domain-level callback
            )

            domain_stats["verticals"][vertical] = vertical_stats
            domain_stats["total_feeds_saved"] += vertical_stats["feeds_saved"]

        self.stats["domains_processed"] += 1

        logger.info(
            "domain_crawl_complete",
            domain=domain,
            total_feeds=domain_stats["total_feeds_saved"]
        )

        return domain_stats

    async def crawl_from_config(
        self,
        config: Dict,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """
        Crawl from configuration dictionary.

        Args:
            config: Configuration with domains and verticals
            progress_callback: Optional callback(message, progress_pct)

        Returns:
            Complete crawl statistics
        """
        domains = config.get("domains", {})

        logger.info(
            "crawl_started",
            domains=len(domains),
            total_verticals=sum(len(v) for v in domains.values())
        )

        all_stats = {
            "started_at": datetime.now().isoformat(),
            "domains": {}
        }

        for domain, verticals in domains.items():
            domain_stats = await self.crawl_domain(
                domain=domain,
                verticals=verticals,
                progress_callback=progress_callback
            )

            all_stats["domains"][domain] = domain_stats

        all_stats["completed_at"] = datetime.now().isoformat()
        all_stats["summary"] = self.stats

        logger.info(
            "crawl_complete",
            stats=self.stats
        )

        return all_stats


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build RSS feed database")

    parser.add_argument(
        "--domain",
        help="Domain to crawl (e.g., technology, medicine)"
    )
    parser.add_argument(
        "--vertical",
        help="Vertical to crawl (e.g., saas, cardiology)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of search queries per vertical (default: 10)"
    )
    parser.add_argument(
        "--config",
        help="Path to crawler config JSON file"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Crawl all configured domains from config"
    )
    parser.add_argument(
        "--min-quality",
        type=float,
        default=0.5,
        help="Minimum quality score to save feed (default: 0.5)"
    )
    parser.add_argument(
        "--database",
        help="Path to RSS feed database JSON file"
    )

    args = parser.parse_args()

    # Initialize crawler
    crawler = RSSFeedCrawler(
        database_path=args.database,
        search_queries_per_vertical=args.limit,
        sites_per_query=5,
        min_quality_score=args.min_quality
    )

    def progress_callback(message: str, progress: float):
        """Print progress updates."""
        print(f"[{progress:3.0f}%] {message}")

    # Mode 1: Single domain/vertical
    if args.domain and args.vertical:
        print(f"\n🔍 Crawling {args.domain}/{args.vertical}...\n")

        stats = await crawler.crawl_vertical(
            domain=args.domain,
            vertical=args.vertical,
            progress_callback=progress_callback
        )

        print(f"\n✅ Crawl complete!")
        print(f"   Websites crawled: {stats['websites_crawled']}")
        print(f"   Feeds discovered: {stats['feeds_discovered']}")
        print(f"   Feeds saved: {stats['feeds_saved']}")

    # Mode 2: From config file
    elif args.config or args.all:
        config_path = args.config or "scripts/rss_crawler_config.json"

        if not os.path.exists(config_path):
            print(f"❌ Config file not found: {config_path}")
            sys.exit(1)

        with open(config_path, 'r') as f:
            config = json.load(f)

        print(f"\n🔍 Crawling from config: {config_path}\n")

        stats = await crawler.crawl_from_config(
            config=config,
            progress_callback=progress_callback
        )

        print(f"\n✅ Crawl complete!")
        print(f"   Domains processed: {crawler.stats['domains_processed']}")
        print(f"   Verticals processed: {crawler.stats['verticals_processed']}")
        print(f"   Websites crawled: {crawler.stats['websites_crawled']}")
        print(f"   Feeds discovered: {crawler.stats['feeds_discovered']}")
        print(f"   Feeds saved: {crawler.stats['feeds_saved']}")

        # Show database statistics
        print(f"\n📊 Database Statistics:")
        db_stats = crawler.database.get_statistics()
        print(f"   Total feeds: {db_stats['total_feeds']}")
        print(f"   Total domains: {db_stats['total_domains']}")
        print(f"   Total verticals: {db_stats['total_verticals']}")

    else:
        parser.print_help()
        print("\n❌ Please specify either:")
        print("   1. --domain and --vertical")
        print("   2. --config <path>")
        print("   3. --all")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

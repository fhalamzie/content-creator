"""
Automated Feed Discovery System

Continuously grows the RSS feed database by:
1. Generating seed URLs for each domain/vertical
2. Discovering feeds from those URLs
3. Validating and scoring feeds
4. Auto-categorizing and adding to database

Can run:
- Manually (on-demand)
- Scheduled (daily/weekly via Huey)
- Triggered (after competitor analysis)
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.agents.gemini_agent import GeminiAgent
from src.collectors.rss_feed_discoverer import RSSFeedDiscoverer, RSSFeed
from src.collectors.rss_feed_database import RSSFeedDatabase
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AutomatedFeedDiscovery:
    """
    Automatically discover and curate RSS feeds.

    Usage:
        discovery = AutomatedFeedDiscovery()

        # Discover feeds for a vertical
        feeds = await discovery.discover_for_vertical(
            domain="technology",
            vertical="saas",
            max_feeds=50
        )

        # Grow database for all verticals
        stats = await discovery.grow_database(
            domains=["technology", "business"],
            feeds_per_vertical=20
        )
    """

    def __init__(
        self,
        min_quality_score: float = 0.6,
        auto_add_to_database: bool = True
    ):
        """
        Initialize automated feed discovery.

        Args:
            min_quality_score: Minimum quality score to add feed to database
            auto_add_to_database: Automatically add discovered feeds to database
        """
        self.gemini_agent = GeminiAgent()
        self.discoverer = RSSFeedDiscoverer()
        self.database = RSSFeedDatabase()
        self.min_quality_score = min_quality_score
        self.auto_add_to_database = auto_add_to_database

        # Statistics
        self.stats = {
            "seed_urls_generated": 0,
            "websites_crawled": 0,
            "feeds_discovered": 0,
            "feeds_added": 0,
            "feeds_rejected": 0
        }

    async def generate_seed_urls(
        self,
        domain: str,
        vertical: str,
        count: int = 20,
        language: str = "en",
        region: str = "US"
    ) -> List[str]:
        """
        Generate seed URLs for a domain/vertical using LLM + web search.

        Args:
            domain: Domain category (e.g., "technology", "business")
            vertical: Vertical within domain (e.g., "saas", "proptech")
            count: Number of URLs to generate
            language: Language for search
            region: Region for search

        Returns:
            List of website URLs to crawl for feeds

        Example:
            >>> discovery = AutomatedFeedDiscovery()
            >>> urls = await discovery.generate_seed_urls(
            ...     domain="technology",
            ...     vertical="proptech",
            ...     count=20
            ... )
            >>> # Returns: ["https://example1.com", "https://example2.com", ...]
        """
        logger.info(
            "generating_seed_urls",
            domain=domain,
            vertical=vertical,
            count=count
        )

        # Build search query
        search_query = f"top {vertical} blogs news websites {region}"

        # Use Gemini with Google Search grounding to find websites
        prompt = f"""Find {count} high-quality blogs, news sites, and industry publications for this niche:

Domain: {domain}
Vertical: {vertical}
Language: {language}
Region: {region}

Focus on:
- Industry-specific blogs and publications
- News sites covering this vertical
- Company blogs in this space
- Trade publications and magazines

Return ONLY a JSON array of website homepage URLs (not article pages):
["https://example1.com", "https://example2.com", ...]"""

        try:
            response_schema = {
                "type": "array",
                "items": {"type": "string", "format": "uri"}
            }

            response = await self.gemini_agent.generate_async(
                prompt=prompt,
                response_schema=response_schema,
                temperature=0.7,
                use_grounding=True  # Enable Google Search
            )

            urls = json.loads(response['content'])

            # Normalize URLs (remove paths, keep domain only)
            from urllib.parse import urlparse
            normalized_urls = []
            for url in urls:
                parsed = urlparse(url)
                normalized = f"{parsed.scheme}://{parsed.netloc}"
                if normalized not in normalized_urls:
                    normalized_urls.append(normalized)

            self.stats["seed_urls_generated"] += len(normalized_urls)

            logger.info(
                "seed_urls_generated",
                domain=domain,
                vertical=vertical,
                count=len(normalized_urls)
            )

            return normalized_urls[:count]

        except Exception as e:
            logger.error(
                "seed_url_generation_failed",
                domain=domain,
                vertical=vertical,
                error=str(e)
            )
            return []

    async def auto_categorize_feed(
        self,
        feed: RSSFeed,
        hint_domain: Optional[str] = None,
        hint_vertical: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Auto-categorize a feed into domain and vertical using LLM.

        Args:
            feed: RSS feed to categorize
            hint_domain: Optional hint for domain
            hint_vertical: Optional hint for vertical

        Returns:
            Tuple of (domain, vertical)

        Example:
            >>> feed = RSSFeed(url="...", title="PropTech News", ...)
            >>> domain, vertical = await discovery.auto_categorize_feed(feed)
            >>> # Returns: ("technology", "proptech")
        """
        # If hints provided, use them
        if hint_domain and hint_vertical:
            return (hint_domain, hint_vertical)

        prompt = f"""Categorize this RSS feed into a domain and vertical:

Feed Title: {feed.title}
Feed URL: {feed.url}
Description: {feed.description or "N/A"}

Available domains: technology, business, lifestyle, entertainment, sports, science, news, education
Examples of verticals: saas, proptech, ai, web-development, marketing, finance, travel, gaming

Return ONLY a JSON object:
{{"domain": "domain_name", "vertical": "vertical_name"}}"""

        try:
            response_schema = {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "vertical": {"type": "string"}
                },
                "required": ["domain", "vertical"]
            }

            response = await self.gemini_agent.generate_async(
                prompt=prompt,
                response_schema=response_schema,
                temperature=0.3
            )

            result = json.loads(response['content'])
            domain = result["domain"].lower().replace(" ", "-")
            vertical = result["vertical"].lower().replace(" ", "-")

            logger.debug(
                "feed_auto_categorized",
                feed_title=feed.title,
                domain=domain,
                vertical=vertical
            )

            return (domain, vertical)

        except Exception as e:
            logger.error(
                "auto_categorization_failed",
                feed_title=feed.title,
                error=str(e)
            )
            # Fallback to hints or default
            return (hint_domain or "uncategorized", hint_vertical or "general")

    async def discover_for_vertical(
        self,
        domain: str,
        vertical: str,
        max_feeds: int = 50,
        language: str = "en",
        region: str = "US"
    ) -> List[RSSFeed]:
        """
        Discover feeds for a specific domain/vertical.

        Args:
            domain: Domain category
            vertical: Vertical within domain
            max_feeds: Maximum number of feeds to discover
            language: Language for search
            region: Region for search

        Returns:
            List of discovered and validated RSS feeds
        """
        logger.info(
            "vertical_discovery_started",
            domain=domain,
            vertical=vertical,
            max_feeds=max_feeds
        )

        discovered_feeds = []

        # Step 1: Generate seed URLs
        seed_urls = await self.generate_seed_urls(
            domain=domain,
            vertical=vertical,
            count=max(20, max_feeds // 2),  # Generate enough URLs to find max_feeds
            language=language,
            region=region
        )

        if not seed_urls:
            logger.warning("no_seed_urls_generated", domain=domain, vertical=vertical)
            return []

        # Step 2: Discover feeds from each URL
        for i, url in enumerate(seed_urls, 1):
            if len(discovered_feeds) >= max_feeds:
                break

            try:
                logger.info(
                    "crawling_website",
                    url=url,
                    progress=f"{i}/{len(seed_urls)}"
                )

                # Discover feeds from URL
                feeds = await self.discoverer.discover_feeds(url)
                self.stats["websites_crawled"] += 1

                # Filter by quality
                quality_feeds = [
                    f for f in feeds
                    if f.is_valid and f.quality_score >= self.min_quality_score
                ]

                self.stats["feeds_discovered"] += len(quality_feeds)

                # Add to results
                for feed in quality_feeds:
                    if len(discovered_feeds) >= max_feeds:
                        break

                    # Auto-add to database if enabled
                    if self.auto_add_to_database:
                        added = self.database.add_feed(
                            domain=domain,
                            vertical=vertical,
                            feed=feed,
                            allow_duplicates=False
                        )

                        if added:
                            self.stats["feeds_added"] += 1
                            discovered_feeds.append(feed)
                        else:
                            self.stats["feeds_rejected"] += 1
                    else:
                        discovered_feeds.append(feed)

                logger.info(
                    "website_crawled",
                    url=url,
                    feeds_found=len(quality_feeds),
                    total_discovered=len(discovered_feeds)
                )

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(
                    "website_crawl_failed",
                    url=url,
                    error=str(e)
                )

        # Save database
        if self.auto_add_to_database:
            self.database.save()

        logger.info(
            "vertical_discovery_complete",
            domain=domain,
            vertical=vertical,
            feeds_discovered=len(discovered_feeds)
        )

        return discovered_feeds

    async def discover_from_competitor_urls(
        self,
        competitor_urls: List[str],
        hint_domain: Optional[str] = None,
        hint_vertical: Optional[str] = None
    ) -> List[RSSFeed]:
        """
        Discover feeds from competitor URLs.

        Args:
            competitor_urls: List of competitor website URLs
            hint_domain: Optional hint for domain categorization
            hint_vertical: Optional hint for vertical categorization

        Returns:
            List of discovered RSS feeds
        """
        logger.info(
            "competitor_feed_discovery_started",
            count=len(competitor_urls)
        )

        discovered_feeds = []

        for url in competitor_urls:
            try:
                # Discover feeds from competitor
                feeds = await self.discoverer.discover_feeds(url)
                self.stats["websites_crawled"] += 1

                # Filter by quality
                quality_feeds = [
                    f for f in feeds
                    if f.is_valid and f.quality_score >= self.min_quality_score
                ]

                self.stats["feeds_discovered"] += len(quality_feeds)

                # Add to database
                for feed in quality_feeds:
                    # Auto-categorize or use hints
                    domain, vertical = await self.auto_categorize_feed(
                        feed,
                        hint_domain=hint_domain,
                        hint_vertical=hint_vertical
                    )

                    # Add to database
                    if self.auto_add_to_database:
                        added = self.database.add_feed(
                            domain=domain,
                            vertical=vertical,
                            feed=feed,
                            allow_duplicates=False
                        )

                        if added:
                            self.stats["feeds_added"] += 1
                            discovered_feeds.append(feed)
                        else:
                            self.stats["feeds_rejected"] += 1
                    else:
                        discovered_feeds.append(feed)

                logger.info(
                    "competitor_feeds_discovered",
                    url=url,
                    feeds_found=len(quality_feeds)
                )

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(
                    "competitor_crawl_failed",
                    url=url,
                    error=str(e)
                )

        # Save database
        if self.auto_add_to_database:
            self.database.save()

        logger.info(
            "competitor_feed_discovery_complete",
            feeds_discovered=len(discovered_feeds)
        )

        return discovered_feeds

    async def grow_database(
        self,
        domains: Optional[List[str]] = None,
        feeds_per_vertical: int = 20,
        language: str = "en",
        region: str = "US"
    ) -> Dict:
        """
        Grow database for multiple domains.

        Args:
            domains: List of domains to grow (None = all existing domains)
            feeds_per_vertical: Target number of feeds per vertical
            language: Language for search
            region: Region for search

        Returns:
            Statistics dictionary
        """
        logger.info("database_growth_started", domains=domains)

        # Get existing domains if not specified
        if not domains:
            domains = self.database.get_domains()

        growth_stats = {
            "started_at": datetime.now().isoformat(),
            "domains_processed": 0,
            "verticals_processed": 0,
            "feeds_added": 0
        }

        for domain in domains:
            # Get verticals in this domain
            verticals = self.database.get_verticals(domain)

            for vertical in verticals:
                # Check current feed count
                current_feeds = self.database.get_feeds(
                    domain=domain,
                    vertical=vertical
                )

                # Skip if already have enough feeds
                if len(current_feeds) >= feeds_per_vertical:
                    logger.debug(
                        "vertical_has_enough_feeds",
                        domain=domain,
                        vertical=vertical,
                        count=len(current_feeds)
                    )
                    continue

                # Discover more feeds
                needed = feeds_per_vertical - len(current_feeds)
                feeds = await self.discover_for_vertical(
                    domain=domain,
                    vertical=vertical,
                    max_feeds=needed,
                    language=language,
                    region=region
                )

                growth_stats["verticals_processed"] += 1
                growth_stats["feeds_added"] += len(feeds)

            growth_stats["domains_processed"] += 1

        growth_stats["completed_at"] = datetime.now().isoformat()
        growth_stats["summary"] = self.stats

        logger.info("database_growth_complete", stats=growth_stats)

        return growth_stats

    def get_statistics(self) -> Dict:
        """Get discovery statistics."""
        return self.stats

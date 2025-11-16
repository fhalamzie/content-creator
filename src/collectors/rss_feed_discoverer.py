"""
RSS Feed Discoverer

Automated RSS feed discovery using:
1. Pattern-based discovery (try /feed/, /rss/, /atom.xml)
2. HTML scraping for autodiscovery tags
3. Feed validation and quality scoring

Used to build a database of RSS feeds across domains and verticals.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
import feedparser
import time

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RSSFeed:
    """
    Discovered RSS feed with metadata.
    """
    url: str
    source_url: str  # The website where it was found
    title: Optional[str] = None
    description: Optional[str] = None
    discovery_method: str = "unknown"  # "pattern", "html", "sitemap"
    quality_score: float = 0.0
    last_updated: Optional[datetime] = None
    article_count: int = 0
    is_valid: bool = False
    error: Optional[str] = None
    discovered_at: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        status = "✓" if self.is_valid else "✗"
        return f"RSSFeed({status} {self.url[:50]}... score={self.quality_score:.2f})"


class RSSFeedDiscoverer:
    """
    Discovers RSS feeds from websites using multiple strategies.

    Usage:
        discoverer = RSSFeedDiscoverer()
        feeds = await discoverer.discover_feeds("https://techcrunch.com")

        for feed in feeds:
            print(f"{feed.title}: {feed.url} (score: {feed.quality_score:.2f})")
    """

    # Common RSS URL patterns to try
    RSS_PATTERNS = [
        "/feed/",
        "/rss/",
        "/rss.xml",
        "/feed.xml",
        "/atom.xml",
        "/feeds/posts/default",  # Blogger
        "/rss/index.xml",
        "/index.xml",
        "/blog/feed/",
        "/blog/rss/",
        "/news/feed/",
        "/news/rss/",
    ]

    def __init__(
        self,
        timeout: int = 10,
        max_concurrent_requests: int = 5,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ):
        """
        Initialize RSS feed discoverer.

        Args:
            timeout: HTTP request timeout in seconds
            max_concurrent_requests: Maximum concurrent HTTP requests
            user_agent: User agent string for HTTP requests
        """
        self.timeout = timeout
        self.max_concurrent_requests = max_concurrent_requests
        self.user_agent = user_agent
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def discover_feeds(
        self,
        url: str,
        methods: Optional[List[str]] = None
    ) -> List[RSSFeed]:
        """
        Discover RSS feeds from a URL using multiple methods.

        Args:
            url: Website URL to discover feeds from
            methods: Discovery methods to use (default: ["pattern", "html"])

        Returns:
            List of discovered RSS feeds, sorted by quality score
        """
        methods = methods or ["pattern", "html"]

        logger.info(
            "feed_discovery_started",
            url=url,
            methods=methods
        )

        discovered_feeds: Dict[str, RSSFeed] = {}

        # Pattern-based discovery
        if "pattern" in methods:
            pattern_feeds = await self._discover_by_pattern(url)
            for feed in pattern_feeds:
                discovered_feeds[feed.url] = feed

        # HTML scraping for autodiscovery tags
        if "html" in methods:
            html_feeds = await self._discover_by_html(url)
            for feed in html_feeds:
                # Prefer HTML-discovered feeds (more reliable)
                if feed.url not in discovered_feeds:
                    discovered_feeds[feed.url] = feed

        # Validate and score all discovered feeds
        feeds_list = list(discovered_feeds.values())
        validated_feeds = await self._validate_feeds(feeds_list)

        # Sort by quality score (descending)
        validated_feeds.sort(key=lambda f: -f.quality_score)

        logger.info(
            "feed_discovery_complete",
            url=url,
            total_discovered=len(validated_feeds),
            valid_feeds=sum(1 for f in validated_feeds if f.is_valid)
        )

        return validated_feeds

    async def _discover_by_pattern(self, base_url: str) -> List[RSSFeed]:
        """
        Try common RSS URL patterns.

        Args:
            base_url: Website URL

        Returns:
            List of potentially valid RSS feeds
        """
        logger.debug("pattern_discovery_started", url=base_url)

        feeds = []

        # Try each pattern
        for pattern in self.RSS_PATTERNS:
            feed_url = urljoin(base_url, pattern)

            # Check if URL is accessible (HEAD request)
            is_accessible = await self._check_url_accessible(feed_url)

            if is_accessible:
                feeds.append(RSSFeed(
                    url=feed_url,
                    source_url=base_url,
                    discovery_method="pattern"
                ))

        logger.debug(
            "pattern_discovery_complete",
            url=base_url,
            feeds_found=len(feeds)
        )

        return feeds

    async def _discover_by_html(self, url: str) -> List[RSSFeed]:
        """
        Parse HTML for RSS autodiscovery tags.

        Looks for: <link rel="alternate" type="application/rss+xml" href="...">

        Args:
            url: Website URL

        Returns:
            List of discovered RSS feeds
        """
        logger.debug("html_discovery_started", url=url)

        feeds = []

        try:
            # Fetch HTML
            async with self._semaphore:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        headers={"User-Agent": self.user_agent}
                    ) as response:
                        if response.status != 200:
                            logger.warning(
                                "html_fetch_failed",
                                url=url,
                                status=response.status
                            )
                            return feeds

                        html = await response.text()

            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser')

            # Find all RSS/Atom autodiscovery links
            rss_links = soup.find_all(
                'link',
                attrs={
                    'rel': 'alternate',
                    'type': lambda t: t and ('rss' in t.lower() or 'atom' in t.lower())
                }
            )

            for link in rss_links:
                feed_url = link.get('href')
                if not feed_url:
                    continue

                # Make absolute URL
                feed_url = urljoin(url, feed_url)

                # Extract title if available
                title = link.get('title')

                feeds.append(RSSFeed(
                    url=feed_url,
                    source_url=url,
                    title=title,
                    discovery_method="html"
                ))

            logger.debug(
                "html_discovery_complete",
                url=url,
                feeds_found=len(feeds)
            )

        except Exception as e:
            logger.error(
                "html_discovery_failed",
                url=url,
                error=str(e)
            )

        return feeds

    async def _check_url_accessible(self, url: str) -> bool:
        """
        Check if a URL is accessible with HEAD request.

        Args:
            url: URL to check

        Returns:
            True if accessible (status 200), False otherwise
        """
        try:
            async with self._semaphore:
                async with aiohttp.ClientSession() as session:
                    async with session.head(
                        url,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        headers={"User-Agent": self.user_agent},
                        allow_redirects=True
                    ) as response:
                        return response.status == 200

        except Exception:
            return False

    async def _validate_feeds(self, feeds: List[RSSFeed]) -> List[RSSFeed]:
        """
        Validate RSS feeds and calculate quality scores.

        Args:
            feeds: List of RSS feeds to validate

        Returns:
            List of validated feeds with quality scores
        """
        if not feeds:
            return []

        logger.debug("feed_validation_started", count=len(feeds))

        # Validate concurrently
        tasks = [self._validate_feed(feed) for feed in feeds]
        validated_feeds = await asyncio.gather(*tasks)

        valid_count = sum(1 for f in validated_feeds if f.is_valid)
        logger.debug(
            "feed_validation_complete",
            total=len(validated_feeds),
            valid=valid_count
        )

        return validated_feeds

    async def _validate_feed(self, feed: RSSFeed) -> RSSFeed:
        """
        Validate a single RSS feed and calculate quality score.

        Quality score based on:
        - Feed is parseable (40%)
        - Number of articles (30%)
        - Recency of last update (20%)
        - Has title/description (10%)

        Args:
            feed: RSS feed to validate

        Returns:
            Updated RSSFeed with validation results
        """
        try:
            async with self._semaphore:
                # Fetch feed
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        feed.url,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        headers={"User-Agent": self.user_agent}
                    ) as response:
                        if response.status != 200:
                            feed.is_valid = False
                            feed.error = f"HTTP {response.status}"
                            return feed

                        feed_content = await response.read()

            # Parse feed
            parsed = feedparser.parse(feed_content)

            # Check if valid
            if parsed.bozo:
                feed.is_valid = False
                feed.error = "Parse error"
                return feed

            # Extract metadata
            feed.is_valid = True
            feed.title = parsed.feed.get('title', feed.title)
            feed.description = parsed.feed.get('description', feed.description)
            feed.article_count = len(parsed.entries)

            # Get last updated date
            if parsed.entries:
                entry = parsed.entries[0]
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    feed.last_updated = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    feed.last_updated = datetime(*entry.updated_parsed[:6])

            # Calculate quality score
            feed.quality_score = self._calculate_quality_score(feed)

        except Exception as e:
            feed.is_valid = False
            feed.error = str(e)
            logger.debug(
                "feed_validation_failed",
                url=feed.url,
                error=str(e)
            )

        return feed

    def _calculate_quality_score(self, feed: RSSFeed) -> float:
        """
        Calculate quality score for a feed (0.0 - 1.0).

        Scoring:
        - Feed is parseable: 0.4
        - Number of articles: 0.3 (max at 50 articles)
        - Recency: 0.2 (max if updated in last 7 days)
        - Has title/description: 0.1

        Args:
            feed: Validated RSS feed

        Returns:
            Quality score (0.0 - 1.0)
        """
        score = 0.0

        # 1. Is parseable (40%)
        if feed.is_valid:
            score += 0.4

        # 2. Number of articles (30%)
        if feed.article_count > 0:
            article_score = min(feed.article_count / 50, 1.0)
            score += 0.3 * article_score

        # 3. Recency (20%)
        if feed.last_updated:
            days_old = (datetime.now() - feed.last_updated).days
            recency_score = max(0, 1.0 - (days_old / 30))  # 0 at 30 days
            score += 0.2 * recency_score

        # 4. Has metadata (10%)
        if feed.title and feed.description:
            score += 0.1
        elif feed.title or feed.description:
            score += 0.05

        return min(score, 1.0)

    async def batch_discover(
        self,
        urls: List[str],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, List[RSSFeed]]:
        """
        Discover feeds from multiple URLs concurrently.

        Args:
            urls: List of website URLs
            progress_callback: Optional callback(current, total, url)

        Returns:
            Dict mapping URL -> List of discovered feeds
        """
        logger.info("batch_discovery_started", count=len(urls))

        results = {}

        for i, url in enumerate(urls, 1):
            try:
                feeds = await self.discover_feeds(url)
                results[url] = feeds

                if progress_callback:
                    progress_callback(i, len(urls), url)

            except Exception as e:
                logger.error(
                    "batch_discovery_failed",
                    url=url,
                    error=str(e)
                )
                results[url] = []

            # Rate limiting
            await asyncio.sleep(0.5)

        logger.info(
            "batch_discovery_complete",
            urls_processed=len(results),
            total_feeds=sum(len(feeds) for feeds in results.values())
        )

        return results

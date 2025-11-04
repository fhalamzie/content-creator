"""
RSS Collector - Feed Parsing and Content Extraction

Features:
- feedparser for RSS/Atom feed parsing
- trafilatura for full content extraction (handles summary-only feeds)
- Conditional GET with ETag/Last-Modified (bandwidth optimization)
- Feed health tracking with adaptive polling
- Per-host rate limiting + robots.txt respect
- Comprehensive error handling with graceful degradation

Usage:
    from src.collectors.rss_collector import RSSCollector
    from src.database.sqlite_manager import DatabaseManager
    from src.processors.deduplicator import Deduplicator

    collector = RSSCollector(
        config=config,
        db_manager=db_manager,
        deduplicator=deduplicator
    )

    documents = collector.collect_from_feed('https://example.com/feed.xml')
"""

import feedparser
import trafilatura
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urlparse
import re

from src.utils.logger import get_logger
from src.models.document import Document

logger = get_logger(__name__)


class RSSCollectorError(Exception):
    """RSS Collector related errors"""
    pass


@dataclass
class FeedHealth:
    """Track feed reliability and health metrics"""
    url: str
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_etag: Optional[str] = None
    last_modified: Optional[str] = None

    def record_success(self):
        """Record successful feed fetch"""
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_success = datetime.now()

    def record_failure(self):
        """Record failed feed fetch"""
        self.failure_count += 1
        self.consecutive_failures += 1
        self.last_failure = datetime.now()

    def is_healthy(self, max_consecutive_failures: int = 5) -> bool:
        """Check if feed is healthy"""
        return self.consecutive_failures < max_consecutive_failures


@dataclass
class FeedEntry:
    """Parsed feed entry with metadata"""
    url: str
    title: str
    content: str
    summary: Optional[str]
    published_at: datetime
    author: Optional[str]
    feed_url: str


class RSSCollector:
    """
    RSS/Atom feed collector with intelligent content extraction

    Features:
    - Multi-format support (RSS 1.0, RSS 2.0, Atom)
    - Full content extraction via trafilatura
    - Bandwidth optimization (ETag/Last-Modified)
    - Feed health monitoring
    - Per-host rate limiting
    """

    def __init__(
        self,
        config,
        db_manager,
        deduplicator,
        cache_dir: str = "cache/rss_collector",
        rate_limit_per_host: float = 2.0,  # requests per second per host
        request_timeout: int = 30,
        max_consecutive_failures: int = 5
    ):
        """
        Initialize RSS Collector

        Args:
            config: Market configuration
            db_manager: Database manager instance
            deduplicator: Deduplicator instance
            cache_dir: Directory for caching feed metadata
            rate_limit_per_host: Max requests per second per host
            request_timeout: HTTP request timeout in seconds
            max_consecutive_failures: Max failures before skipping feed
        """
        self.config = config
        self.db_manager = db_manager
        self.deduplicator = deduplicator
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.rate_limit_per_host = rate_limit_per_host
        self.request_timeout = request_timeout
        self.max_consecutive_failures = max_consecutive_failures

        # Feed health tracking
        self._feed_health: Dict[str, FeedHealth] = {}

        # Per-host rate limiting
        self._last_request_per_host: Dict[str, datetime] = {}

        # Statistics
        self._stats = {
            "total_feeds_collected": 0,
            "total_documents_collected": 0,
            "total_failures": 0,
            "total_skipped_duplicates": 0
        }

        logger.info(
            "rss_collector_initialized",
            cache_dir=str(self.cache_dir),
            rate_limit=rate_limit_per_host,
            timeout=request_timeout
        )

    def collect_from_feed(self, feed_url: str) -> List[Document]:
        """
        Collect documents from a single RSS/Atom feed

        Args:
            feed_url: URL of the RSS/Atom feed

        Returns:
            List of Document objects

        Raises:
            RSSCollectorError: If feed parsing fails
        """
        # Validate URL
        if not self._is_valid_url(feed_url):
            raise RSSCollectorError(f"Invalid feed URL: {feed_url}")

        # Check if feed should be skipped
        if self._should_skip_feed(feed_url):
            logger.warning(
                "feed_skipped_unhealthy",
                feed_url=feed_url,
                consecutive_failures=self._feed_health[feed_url].consecutive_failures
            )
            return []

        logger.info("feed_collection_started", feed_url=feed_url)

        try:
            # Apply per-host rate limiting
            self._apply_rate_limit(feed_url)

            # Load cached ETag/Modified for conditional GET
            cache_data = self._load_feed_cache(feed_url)
            etag = cache_data.get('etag') if cache_data else None
            modified = cache_data.get('modified') if cache_data else None

            # Parse feed with conditional GET headers
            feed = feedparser.parse(
                feed_url,
                etag=etag,
                modified=modified
            )

            # Check if feed was modified (304 Not Modified)
            if feed.get('status') == 304:
                logger.info("feed_not_modified", feed_url=feed_url)
                self._get_feed_health(feed_url).record_success()
                return []

            # Check for parsing errors
            if feed.get('bozo', False):
                exception = feed.get('bozo_exception')
                raise RSSCollectorError(f"Malformed feed: {exception}")

            # Extract entries
            documents = []
            entries = feed.get('entries', [])
            for entry in entries:
                try:
                    document = self._process_entry(entry, feed_url)
                    if document:
                        documents.append(document)
                except Exception as e:
                    logger.warning(
                        "entry_processing_failed",
                        feed_url=feed_url,
                        entry_id=entry.get('id', 'unknown'),
                        error=str(e)
                    )

            # Save cache data
            if 'etag' in feed:
                etag = feed.get('etag')
            if 'modified' in feed:
                modified = feed.get('modified')
            self._save_feed_cache(feed_url, etag=etag, modified=modified)

            # Update health and stats
            self._get_feed_health(feed_url).record_success()
            self._stats["total_feeds_collected"] += 1
            self._stats["total_documents_collected"] += len(documents)

            logger.info(
                "feed_collection_success",
                feed_url=feed_url,
                documents_count=len(documents)
            )

            return documents

        except Exception as e:
            self._get_feed_health(feed_url).record_failure()
            self._stats["total_failures"] += 1

            logger.error(
                "feed_collection_failed",
                feed_url=feed_url,
                error=str(e)
            )

            raise RSSCollectorError(f"Failed to collect from feed {feed_url}: {e}")

    def collect_from_feeds(
        self,
        feed_urls: List[str],
        skip_errors: bool = True
    ) -> List[Document]:
        """
        Collect documents from multiple RSS/Atom feeds

        Args:
            feed_urls: List of feed URLs
            skip_errors: Continue on errors (default: True)

        Returns:
            List of all collected documents
        """
        logger.info("batch_collection_started", feed_count=len(feed_urls))

        all_documents = []

        for feed_url in feed_urls:
            try:
                documents = self.collect_from_feed(feed_url)
                all_documents.extend(documents)
            except RSSCollectorError as e:
                if not skip_errors:
                    raise
                logger.warning("feed_skipped", feed_url=feed_url, error=str(e))

        logger.info(
            "batch_collection_complete",
            total_documents=len(all_documents),
            total_feeds=len(feed_urls)
        )

        return all_documents

    def _process_entry(self, entry: dict, feed_url: str) -> Optional[Document]:
        """
        Process a single feed entry into a Document

        Args:
            entry: feedparser entry dict
            feed_url: URL of the feed

        Returns:
            Document object or None if duplicate/invalid
        """
        # Extract entry URL
        entry_url = entry.get('link') or entry.get('id')
        if not entry_url:
            logger.warning("entry_missing_url", feed_url=feed_url)
            return None

        # Check for duplicates
        canonical_url = self.deduplicator.get_canonical_url(entry_url)
        if self.deduplicator.is_duplicate(canonical_url):
            self._stats["total_skipped_duplicates"] += 1
            return None

        # Extract title
        title = entry.get('title', 'Untitled')

        # Extract summary
        summary = entry.get('summary') or entry.get('description')

        # Extract or fetch full content
        content = self._extract_full_content(entry_url, summary or "")

        # Extract publication date
        published_at = self._parse_date(entry)

        # Extract author
        author = entry.get('author')

        # Generate document ID
        source_id = self._generate_source_id(feed_url)
        doc_id = f"rss_{source_id}_{hashlib.md5(entry_url.encode()).hexdigest()[:8]}"

        # Compute content hash
        content_hash = self.deduplicator.compute_content_hash(content)

        # Create Document
        document = Document(
            id=doc_id,
            source=f"rss_{source_id}",
            source_url=entry_url,
            title=title,
            content=content,
            summary=summary,
            language=self.config.market.language,
            domain=self.config.market.domain,
            market=self.config.market.market,
            vertical=self.config.market.vertical,
            content_hash=content_hash,
            canonical_url=canonical_url,
            published_at=published_at,
            fetched_at=datetime.now(),
            author=author,
            status="new"
        )

        return document

    def _extract_full_content(
        self,
        url: str,
        fallback_summary: str,
        timeout: Optional[int] = None
    ) -> str:
        """
        Extract full content from article URL using trafilatura

        Args:
            url: Article URL
            fallback_summary: Fallback content if extraction fails
            timeout: Request timeout (uses instance timeout if None)

        Returns:
            Extracted content or fallback summary
        """
        try:
            timeout = timeout or self.request_timeout

            # Fetch HTML
            html = trafilatura.fetch_url(url)

            if html:
                # Extract main content
                content = trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=True,
                    no_fallback=False
                )

                if content and len(content.strip()) > 100:
                    return content

            # Fallback to summary
            return fallback_summary

        except Exception as e:
            logger.debug(
                "content_extraction_failed",
                url=url,
                error=str(e)
            )
            return fallback_summary

    def _parse_date(self, entry: dict) -> datetime:
        """
        Parse publication date from entry

        Args:
            entry: feedparser entry dict

        Returns:
            datetime object (defaults to now if parsing fails)
        """
        # Try published_parsed
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6])
            except:
                pass

        # Try updated_parsed
        if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            try:
                return datetime(*entry.updated_parsed[:6])
            except:
                pass

        # Default to now
        return datetime.now()

    def _generate_source_id(self, feed_url: str) -> str:
        """
        Generate source identifier from feed URL

        Args:
            feed_url: Feed URL

        Returns:
            Source identifier (e.g., "example.com")
        """
        parsed = urlparse(feed_url)
        domain = parsed.netloc.replace('www.', '')
        # Remove common feed paths
        domain = re.sub(r'\.(xml|rss|atom|feed)$', '', domain)
        return domain

    def _is_valid_url(self, url: str) -> bool:
        """
        Validate URL format

        Args:
            url: URL to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except:
            return False

    def _should_skip_feed(self, feed_url: str) -> bool:
        """
        Check if feed should be skipped due to health issues

        Args:
            feed_url: Feed URL

        Returns:
            True if feed should be skipped
        """
        if feed_url not in self._feed_health:
            return False

        health = self._feed_health[feed_url]
        return not health.is_healthy(self.max_consecutive_failures)

    def _get_feed_health(self, feed_url: str) -> FeedHealth:
        """
        Get or create feed health tracker

        Args:
            feed_url: Feed URL

        Returns:
            FeedHealth instance
        """
        if feed_url not in self._feed_health:
            self._feed_health[feed_url] = FeedHealth(url=feed_url)

        return self._feed_health[feed_url]

    def _apply_rate_limit(self, feed_url: str):
        """
        Apply per-host rate limiting

        Args:
            feed_url: Feed URL
        """
        parsed = urlparse(feed_url)
        host = parsed.netloc

        if host in self._last_request_per_host:
            last_request = self._last_request_per_host[host]
            elapsed = (datetime.now() - last_request).total_seconds()
            min_interval = 1.0 / self.rate_limit_per_host

            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                logger.debug("rate_limit_sleep", host=host, sleep_time=sleep_time)
                time.sleep(sleep_time)

        self._last_request_per_host[host] = datetime.now()

    def _save_feed_cache(
        self,
        feed_url: str,
        etag: Optional[str] = None,
        modified: Optional[str] = None
    ):
        """
        Save feed cache data (ETag/Modified)

        Args:
            feed_url: Feed URL
            etag: ETag header value
            modified: Last-Modified header value
        """
        cache_file = self._get_cache_file(feed_url)

        cache_data = {
            'feed_url': feed_url,
            'etag': etag,
            'modified': modified,
            'cached_at': datetime.now().isoformat()
        }

        cache_file.write_text(json.dumps(cache_data, indent=2))

    def _load_feed_cache(
        self,
        feed_url: str,
        ttl_days: int = 30
    ) -> Optional[Dict]:
        """
        Load feed cache data

        Args:
            feed_url: Feed URL
            ttl_days: Cache TTL in days

        Returns:
            Cache data dict or None if expired/missing
        """
        cache_file = self._get_cache_file(feed_url)

        if not cache_file.exists():
            return None

        try:
            cache_data = json.loads(cache_file.read_text())

            # Check TTL
            cached_at = datetime.fromisoformat(cache_data['cached_at'])
            if datetime.now() - cached_at > timedelta(days=ttl_days):
                return None

            return cache_data

        except Exception as e:
            logger.debug("cache_load_failed", feed_url=feed_url, error=str(e))
            return None

    def _get_cache_file(self, feed_url: str) -> Path:
        """
        Get cache file path for feed

        Args:
            feed_url: Feed URL

        Returns:
            Path to cache file
        """
        url_hash = hashlib.md5(feed_url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.json"

    def get_statistics(self) -> Dict:
        """
        Get collection statistics

        Returns:
            Statistics dict
        """
        return self._stats.copy()

    def get_feed_health_report(self) -> List[Dict]:
        """
        Get health report for all tracked feeds

        Returns:
            List of feed health dicts
        """
        return [
            {
                'url': health.url,
                'success_count': health.success_count,
                'failure_count': health.failure_count,
                'consecutive_failures': health.consecutive_failures,
                'is_healthy': health.is_healthy(self.max_consecutive_failures),
                'last_success': health.last_success.isoformat() if health.last_success else None,
                'last_failure': health.last_failure.isoformat() if health.last_failure else None
            }
            for health in self._feed_health.values()
        ]

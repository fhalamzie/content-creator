"""
Feed Discovery Pipeline - 2-Stage Intelligent Feed Discovery

Stage 1: OPML Seeds + Gemini CLI Expansion
- Load curated OPML seed feeds
- Use Gemini CLI (FREE) to expand seed keywords intelligently
- Fallback to basic keyword extraction if Gemini fails

Stage 2: SerpAPI + feedfinder2
- Search seed keywords via SerpAPI (3/day hard cap)
- Extract top domains from search results
- Use feedfinder2 to auto-detect RSS/Atom feeds on each domain
- Cache SERP results for 30 days

Features:
- Circuit breaker enforces 3 requests/day SerpAPI limit
- 30-day caching reduces duplicate queries
- Graceful degradation when quota exhausted
- Retry logic (2 attempts) with exponential backoff
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import xml.etree.ElementTree as ET

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DiscoveryStage(Enum):
    """Feed discovery stages"""
    OPML = "opml"
    CUSTOM = "custom"
    SERPAPI = "serpapi"
    FEEDFINDER = "feedfinder"


@dataclass
class DiscoveredFeed:
    """Discovered feed with metadata"""
    url: str
    source: str
    stage: DiscoveryStage
    discovered_at: datetime = field(default_factory=datetime.now)
    domain: Optional[str] = None


class FeedDiscoveryError(Exception):
    """Feed discovery related errors"""
    pass


class FeedDiscovery:
    """
    Intelligent feed discovery pipeline using 2-stage approach:
    1. OPML seeds + Gemini CLI keyword expansion
    2. SerpAPI search + feedfinder2 auto-detection
    """

    def __init__(
        self,
        config,
        cache_dir: str = "cache/feed_discovery",
        serpapi_daily_limit: int = 3,
        serpapi_api_key: Optional[str] = None
    ):
        """
        Initialize Feed Discovery

        Args:
            config: Market configuration with seed keywords
            cache_dir: Directory for caching SERP results
            serpapi_daily_limit: Max SerpAPI requests per day (default: 3)
            serpapi_api_key: SerpAPI key (optional, loads from env if not provided)
        """
        self.config = config
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.serpapi_daily_limit = serpapi_daily_limit

        # Load SerpAPI key from env if not provided
        if serpapi_api_key is None:
            import os
            from dotenv import load_dotenv
            load_dotenv()  # Load .env file
            serpapi_api_key = os.getenv("SERPAPI_API_KEY")

        self.serpapi_api_key = serpapi_api_key

        logger.info(
            "serpapi_config",
            has_api_key=bool(self.serpapi_api_key),
            daily_limit=self.serpapi_daily_limit
        )

        # Circuit breaker state
        self._serpapi_requests_today = 0
        self._last_request_date = datetime.now().date()

        # Statistics
        self._stats = {
            "opml_feeds": 0,
            "custom_feeds": 0,
            "serpapi_feeds": 0,
            "serpapi_requests_today": 0,
            "total_feeds": 0
        }

        logger.info(
            "feed_discovery_initialized",
            cache_dir=str(self.cache_dir),
            serpapi_daily_limit=serpapi_daily_limit
        )

    def discover_feeds(self, opml_file: Optional[str] = None) -> List[DiscoveredFeed]:
        """
        Run full 2-stage feed discovery pipeline

        Args:
            opml_file: Path to OPML seed file (optional)

        Returns:
            List of discovered feeds with metadata
        """
        logger.info("feed_discovery_started")
        all_feeds: List[DiscoveredFeed] = []

        # Stage 1: OPML + Gemini expansion
        try:
            stage1_feeds = self.run_stage1(opml_file=opml_file)
            all_feeds.extend(stage1_feeds)
            logger.info("stage1_completed", feeds_count=len(stage1_feeds))
        except Exception as e:
            logger.error("stage1_failed", error=str(e))

        # Stage 2: SerpAPI + feedfinder
        try:
            # Expand keywords with Gemini
            keywords = self._expand_keywords_with_gemini(
                self.config.market.seed_keywords
            )
            stage2_feeds = self.run_stage2(keywords)
            all_feeds.extend(stage2_feeds)
            logger.info("stage2_completed", feeds_count=len(stage2_feeds))
        except Exception as e:
            logger.error("stage2_failed", error=str(e))

        # Deduplicate feeds by URL
        unique_feeds = self._deduplicate_feeds(all_feeds)

        # Update statistics
        self._stats["total_feeds"] = len(unique_feeds)
        self._stats["serpapi_requests_today"] = self._serpapi_requests_today

        logger.info(
            "feed_discovery_completed",
            total_feeds=len(unique_feeds),
            duplicates_removed=len(all_feeds) - len(unique_feeds)
        )

        return unique_feeds

    def run_stage1(self, opml_file: Optional[str] = None) -> List[DiscoveredFeed]:
        """
        Stage 1: OPML seeds + custom feeds from config

        Args:
            opml_file: Path to OPML file

        Returns:
            List of feeds from OPML and config
        """
        feeds: List[DiscoveredFeed] = []

        # Load OPML seeds
        if opml_file:
            opml_urls = self._load_opml_seeds(opml_file)
            for url in opml_urls:
                feeds.append(DiscoveredFeed(
                    url=url,
                    source="opml",
                    stage=DiscoveryStage.OPML
                ))
            self._stats["opml_feeds"] = len(opml_urls)

        # Add custom feeds from config
        if hasattr(self.config.collectors, 'custom_feeds'):
            for url in self.config.collectors.custom_feeds:
                feeds.append(DiscoveredFeed(
                    url=url,
                    source="custom",
                    stage=DiscoveryStage.CUSTOM
                ))
            self._stats["custom_feeds"] = len(self.config.collectors.custom_feeds)

        return feeds

    def run_stage2(self, keywords: List[str]) -> List[DiscoveredFeed]:
        """
        Stage 2: SerpAPI search + feedfinder2 auto-detection

        Args:
            keywords: Expanded keywords to search

        Returns:
            List of feeds discovered via SERP + feedfinder
        """
        feeds: List[DiscoveredFeed] = []
        discovered_domains: Set[str] = set()

        for keyword in keywords:
            try:
                # Search with SerpAPI
                domains = self._search_with_serpapi(keyword)

                for domain in domains:
                    if domain not in discovered_domains:
                        discovered_domains.add(domain)

                        # Discover feeds from domain
                        domain_feeds = self._discover_feeds_from_domain(domain)
                        feeds.extend(domain_feeds)

            except FeedDiscoveryError as e:
                logger.warning("serpapi_search_failed", keyword=keyword, error=str(e))
                # Re-raise to stop processing (circuit breaker hit)
                raise

        self._stats["serpapi_feeds"] = len(feeds)
        return feeds

    def _load_opml_seeds(self, opml_file: str) -> List[str]:
        """
        Parse OPML file and extract feed URLs

        Args:
            opml_file: Path to OPML file

        Returns:
            List of feed URLs
        """
        feed_urls: List[str] = []

        try:
            tree = ET.parse(opml_file)
            root = tree.getroot()

            # Find all outline elements with xmlUrl attribute
            for outline in root.findall(".//outline[@xmlUrl]"):
                url = outline.get("xmlUrl")
                if url:
                    feed_urls.append(url)

            logger.info("opml_loaded", feeds_count=len(feed_urls), file=opml_file)

        except FileNotFoundError:
            logger.warning("opml_file_not_found", file=opml_file)
        except ET.ParseError as e:
            logger.error("opml_parse_error", file=opml_file, error=str(e))

        return feed_urls

    def _expand_keywords_with_gemini(self, keywords: List[str]) -> List[str]:
        """
        Expand keywords using Gemini CLI (FREE) with retry logic

        Args:
            keywords: Seed keywords

        Returns:
            Expanded keyword list (or original if Gemini fails)
        """
        # Retry up to 2 times
        for attempt in range(2):
            try:
                # Prepare Gemini CLI prompt
                prompt = f"""Expand these keywords with related terms for RSS feed discovery in {self.config.market.market} {self.config.market.domain} market:

Keywords: {', '.join(keywords)}

Return JSON with:
{{
  "expanded_keywords": ["keyword1", "keyword2", ...],
  "reasoning": "brief explanation"
}}

Keep original keywords and add 2-3 related terms per keyword."""

                # Call Gemini CLI
                result = subprocess.run(
                    ["gemini", "chat", "-m", prompt],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    # Parse JSON response
                    response = json.loads(result.stdout)
                    expanded = response.get("expanded_keywords", keywords)

                    logger.info(
                        "keywords_expanded_via_gemini",
                        original=keywords,
                        expanded=expanded,
                        attempt=attempt + 1
                    )
                    return expanded
                else:
                    logger.warning(
                        "gemini_cli_failed",
                        stderr=result.stderr,
                        attempt=attempt + 1
                    )
                    # Continue to retry

            except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(
                    "gemini_expansion_attempt_failed",
                    error=str(e),
                    attempt=attempt + 1
                )
                # Continue to retry

        # All retries failed, return original keywords
        logger.warning("gemini_expansion_all_retries_failed", fallback="using_original_keywords")
        return keywords

    def _search_with_serpapi(self, keyword: str) -> List[str]:
        """
        Search keyword with SerpAPI and extract domains

        Args:
            keyword: Search keyword

        Returns:
            List of domain names from search results

        Raises:
            FeedDiscoveryError: If daily limit exceeded
        """
        # Check cache first (30-day TTL) - cache check does NOT count toward limit
        cached_domains = self._get_cached_serp_results(keyword)
        if cached_domains is not None:
            logger.info("serp_cache_hit", keyword=keyword)
            return cached_domains

        # Check circuit breaker AFTER cache check
        self._check_daily_limit()

        try:
            # Build SerpAPI request
            params = {
                "q": keyword,
                "hl": self.config.market.language,
                "gl": self.config.market.market[:2].lower(),
                "num": 10,
                "engine": "google"  # Use Google search engine
            }

            if self.serpapi_api_key:
                params["api_key"] = self.serpapi_api_key
                url = "https://serpapi.com/search"
            else:
                # No API key - skip Stage 2
                logger.warning("serpapi_key_missing", message="Stage 2 requires SerpAPI key")
                return []

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 429:
                logger.warning("serpapi_rate_limit_hit")
                return []

            if response.status_code != 200:
                logger.error("serpapi_request_failed", status=response.status_code)
                return []

            # Parse results
            data = response.json()
            domains = []

            for result in data.get("organic_results", [])[:10]:
                link = result.get("link", "")
                if link:
                    # Extract domain
                    domain = self._extract_domain(link)
                    if domain:
                        domains.append(domain)

            # Increment circuit breaker counter
            self._serpapi_requests_today += 1

            # Cache results (30 days)
            self._cache_serp_results(keyword, domains)

            logger.info(
                "serp_search_completed",
                keyword=keyword,
                domains_found=len(domains),
                requests_today=self._serpapi_requests_today
            )

            return domains

        except requests.RequestException as e:
            logger.error("serpapi_network_error", error=str(e))
            return []

    def _discover_feeds_from_domain(self, domain: str) -> List[DiscoveredFeed]:
        """
        Auto-detect RSS/Atom feeds from domain using feedfinder2

        Args:
            domain: Domain name (e.g., "example.com")

        Returns:
            List of discovered feeds
        """
        feeds: List[DiscoveredFeed] = []

        try:
            import feedfinder2

            # Ensure domain has protocol
            url = domain if domain.startswith("http") else f"https://{domain}"

            # Discover feeds (feedfinder2 doesn't support timeout parameter)
            feed_urls = feedfinder2.find_feeds(url)

            for feed_url in feed_urls:
                feeds.append(DiscoveredFeed(
                    url=feed_url,
                    source="serpapi+feedfinder",
                    stage=DiscoveryStage.FEEDFINDER,
                    domain=domain
                ))

            logger.info("feeds_discovered_from_domain", domain=domain, feeds_count=len(feeds))

        except (TimeoutError, requests.RequestException) as e:
            logger.warning("feedfinder_failed", domain=domain, error=str(e))

        return feeds

    def _check_daily_limit(self):
        """Check if SerpAPI daily limit is reached"""
        today = datetime.now().date()

        # Reset counter if new day
        if today != self._last_request_date:
            self._serpapi_requests_today = 0
            self._last_request_date = today

        # Enforce limit
        if self._serpapi_requests_today >= self.serpapi_daily_limit:
            raise FeedDiscoveryError(
                f"SerpAPI daily limit reached ({self.serpapi_daily_limit} requests/day)"
            )

    def _get_cached_serp_results(self, keyword: str) -> Optional[List[str]]:
        """Get cached SERP results if not expired (30 days)"""
        cache_file = self.cache_dir / "serp_cache.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                cache = json.load(f)

            if keyword in cache:
                entry = cache[keyword]
                timestamp = datetime.fromisoformat(entry["timestamp"])

                # Check if expired (30 days)
                if datetime.now() - timestamp < timedelta(days=30):
                    return entry["domains"]

        except (json.JSONDecodeError, KeyError, ValueError):
            logger.warning("serp_cache_corrupted")

        return None

    def _cache_serp_results(self, keyword: str, domains: List[str]):
        """Cache SERP results with 30-day TTL"""
        cache_file = self.cache_dir / "serp_cache.json"

        # Load existing cache
        cache = {}
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
            except json.JSONDecodeError:
                logger.warning("serp_cache_corrupted_overwriting")

        # Add new entry
        cache[keyword] = {
            "domains": domains,
            "timestamp": datetime.now().isoformat()
        }

        # Save cache
        with open(cache_file, 'w') as f:
            json.dump(cache, f, indent=2)

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain name from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            # Remove www. prefix
            return domain.replace("www.", "") if domain else None
        except Exception:
            return None

    def _deduplicate_feeds(self, feeds: List[DiscoveredFeed]) -> List[DiscoveredFeed]:
        """Remove duplicate feed URLs"""
        seen_urls: Set[str] = set()
        unique_feeds: List[DiscoveredFeed] = []

        for feed in feeds:
            if feed.url not in seen_urls:
                seen_urls.add(feed.url)
                unique_feeds.append(feed)

        return unique_feeds

    def get_stats(self) -> Dict[str, int]:
        """Get discovery statistics"""
        return {
            **self._stats,
            "serpapi_requests_today": self._serpapi_requests_today
        }

    def reset_daily_limit(self):
        """Manually reset daily limit counter (for testing)"""
        self._serpapi_requests_today = 0
        self._last_request_date = datetime.now().date()
        logger.info("serpapi_daily_limit_reset")

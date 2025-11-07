"""
Autocomplete Collector - Google Autocomplete Suggestions

Features:
- Google autocomplete API for keyword expansion
- Alphabet expansion (a-z patterns)
- Question prefix expansion (what, how, why, when, where, who)
- Preposition expansion (for, with, without, near, vs, versus)
- Smart caching (30-day TTL for suggestions)
- Rate limiting (10 req/sec - Google autocomplete is lenient)
- Language support (de, en, fr, etc.)
- Deduplication across expansion types

Usage:
    from src.collectors.autocomplete_collector import AutocompleteCollector, ExpansionType
    from src.database.sqlite_manager import DatabaseManager
    from src.processors.deduplicator import Deduplicator

    collector = AutocompleteCollector(
        config=config,
        db_manager=db_manager,
        deduplicator=deduplicator,
        language='de'  # German
    )

    # Collect with alphabet + question expansion
    docs = collector.collect_suggestions(
        seed_keywords=['PropTech', 'Smart Building'],
        expansion_types=[ExpansionType.ALPHABET, ExpansionType.QUESTIONS]
    )
"""

import json
import hashlib
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from enum import Enum
import httpx

from src.utils.logger import get_logger
from src.models.document import Document

logger = get_logger(__name__)


class AutocompleteCollectorError(Exception):
    """Autocomplete Collector related errors"""
    pass


class ExpansionType(str, Enum):
    """Types of keyword expansion"""
    ALPHABET = "alphabet"  # a-z expansion
    QUESTIONS = "questions"  # what, how, why, when, where, who
    PREPOSITIONS = "prepositions"  # for, with, without, near, vs, versus


class AutocompleteCollector:
    """
    Google Autocomplete collector for keyword expansion

    Features:
    - Alphabet expansion (keyword + a-z)
    - Question prefix expansion (what/how/why keyword)
    - Preposition expansion (keyword for/with/without)
    - Smart caching (30-day TTL)
    - Rate limiting (10 req/sec)
    - Language support
    """

    # Google autocomplete API endpoint
    AUTOCOMPLETE_URL = "https://suggestqueries.google.com/complete/search"

    # Expansion patterns
    ALPHABET = list('abcdefghijklmnopqrstuvwxyz')
    QUESTION_PREFIXES = ['what', 'how', 'why', 'when', 'where', 'who']
    PREPOSITION_PATTERNS = ['for', 'with', 'without', 'near', 'vs', 'versus']

    def __init__(
        self,
        config,
        db_manager,
        deduplicator,
        cache_dir: str = "cache/autocomplete",
        language: str = "en",
        rate_limit: float = 10.0,  # Requests per second (default: 10 req/sec)
        request_timeout: int = 10,
        cache_ttl_days: int = 30
    ):
        """
        Initialize Autocomplete Collector

        Args:
            config: Market configuration
            db_manager: Database manager for persistence
            deduplicator: Deduplicator for duplicate detection
            cache_dir: Directory for cache storage
            language: Language code (de, en, fr, etc.)
            rate_limit: Requests per second (default 10.0)
            request_timeout: Request timeout in seconds
            cache_ttl_days: Cache TTL in days (default 30)
        """
        self.config = config
        self.db_manager = db_manager
        self.deduplicator = deduplicator
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.language = language
        self.rate_limit = rate_limit
        self.request_timeout = request_timeout
        self.cache_ttl_days = cache_ttl_days

        # Internal state
        self._cache: Dict = {}  # In-memory cache
        self.last_request_time: Optional[float] = None

        # Statistics
        self._stats = {
            'total_requests': 0,
            'total_suggestions': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'failed_requests': 0,
        }

        # Load cache from disk
        self.load_cache()

        logger.info(
            "AutocompleteCollector initialized",
            language=language,
            rate_limit=rate_limit,
            cache_dir=str(self.cache_dir)
        )

    def collect_suggestions(
        self,
        seed_keywords: List[str],
        expansion_types: List[ExpansionType] = None,
        max_per_keyword: Optional[int] = None
    ) -> List[Document]:
        """
        Collect autocomplete suggestions for seed keywords

        Args:
            seed_keywords: List of seed keywords to expand
            expansion_types: Types of expansion to use (default: all)
            max_per_keyword: Max expansions per keyword (useful for limiting alphabet)

        Returns:
            List of Document objects with autocomplete suggestions

        Raises:
            AutocompleteCollectorError: If collection fails
        """
        if expansion_types is None:
            expansion_types = [ExpansionType.ALPHABET, ExpansionType.QUESTIONS, ExpansionType.PREPOSITIONS]

        all_documents = []
        seen_suggestions = set()  # Dedup across all expansions

        for seed_keyword in seed_keywords:
            keyword_lower = seed_keyword.lower()

            for expansion_type in expansion_types:
                # Check cache first
                cache_key = f"autocomplete_{keyword_lower}_{expansion_type.value}"
                cached_suggestions = self._get_from_cache(cache_key)

                if cached_suggestions:
                    logger.info(
                        "Autocomplete suggestions retrieved from cache",
                        keyword=seed_keyword,
                        expansion_type=expansion_type.value
                    )
                    self._stats['cache_hits'] += 1
                    suggestions = cached_suggestions
                else:
                    # Collect new suggestions
                    try:
                        suggestions = self._collect_for_expansion(
                            seed_keyword,
                            expansion_type,
                            max_per_keyword
                        )

                        # Cache results
                        self._save_to_cache(cache_key, suggestions)

                    except AutocompleteCollectorError as e:
                        logger.error(
                            "Failed to collect suggestions",
                            keyword=seed_keyword,
                            expansion_type=expansion_type.value,
                            error=str(e)
                        )
                        self._stats['failed_requests'] += 1

                        # If this is a single keyword + single expansion, re-raise
                        if len(seed_keywords) == 1 and len(expansion_types) == 1:
                            raise

                        # Otherwise continue with other expansions
                        continue

                # Create documents from suggestions
                for suggestion in suggestions:
                    # Skip if already seen (dedup across expansions)
                    if suggestion in seen_suggestions:
                        continue

                    seen_suggestions.add(suggestion)

                    # Create document
                    doc = self._create_document(
                        suggestion=suggestion,
                        seed_keyword=seed_keyword,
                        expansion_type=expansion_type
                    )

                    # Check for duplicates (pass Document object, not string)
                    if self.deduplicator.is_duplicate(doc):
                        logger.debug("Skipping duplicate suggestion", suggestion=suggestion)
                        continue

                    all_documents.append(doc)

        self._stats['total_suggestions'] += len(all_documents)

        logger.info(
            "Autocomplete suggestions collected",
            keywords=seed_keywords,
            total_suggestions=len(all_documents)
        )

        return all_documents

    def _collect_for_expansion(
        self,
        seed_keyword: str,
        expansion_type: ExpansionType,
        max_per_keyword: Optional[int] = None
    ) -> List[str]:
        """Collect suggestions for a specific expansion type"""
        suggestions = []

        if expansion_type == ExpansionType.ALPHABET:
            patterns = self.ALPHABET[:max_per_keyword] if max_per_keyword else self.ALPHABET
            queries = [f"{seed_keyword} {letter}" for letter in patterns]

        elif expansion_type == ExpansionType.QUESTIONS:
            queries = [f"{prefix} {seed_keyword}" for prefix in self.QUESTION_PREFIXES]

        elif expansion_type == ExpansionType.PREPOSITIONS:
            queries = [f"{seed_keyword} {prep}" for prep in self.PREPOSITION_PATTERNS]

        else:
            raise AutocompleteCollectorError(f"Unknown expansion type: {expansion_type}")

        # Fetch suggestions for each query
        all_failed = True
        last_error = None

        for query in queries:
            try:
                query_suggestions = self._fetch_autocomplete(query)
                suggestions.extend(query_suggestions)
                self._stats['cache_misses'] += 1  # Track each API request
                all_failed = False  # At least one succeeded
            except Exception as e:
                logger.warning(
                    "Failed to fetch autocomplete",
                    query=query,
                    error=str(e)
                )
                self._stats['cache_misses'] += 1  # Count as cache miss even if failed
                last_error = e
                continue

        # If ALL queries failed, raise the last error
        if all_failed and last_error:
            raise AutocompleteCollectorError(f"Failed to collect suggestions: {last_error}")

        # Deduplicate suggestions
        return list(set(suggestions))

    def _fetch_autocomplete(self, query: str) -> List[str]:
        """
        Fetch autocomplete suggestions from Google

        Args:
            query: Search query

        Returns:
            List of autocomplete suggestions

        Raises:
            AutocompleteCollectorError: If request fails
        """
        # Enforce rate limiting
        self._enforce_rate_limit()

        # Build request URL
        params = {
            'q': query,
            'client': 'firefox',  # Use Firefox client for consistent results
            'hl': self.language
        }

        url = f"{self.AUTOCOMPLETE_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        try:
            logger.debug("Fetching autocomplete", query=query)
            response = httpx.get(url, timeout=self.request_timeout)

            # Check HTTP status
            if response.status_code != 200:
                raise AutocompleteCollectorError(
                    f"HTTP error {response.status_code}: {response.text}"
                )

            # Parse JSON response
            # Format: [query, [suggestions], [], {}]
            data = response.json()

            if not isinstance(data, list) or len(data) < 2:
                logger.warning("Unexpected autocomplete response format", data=data)
                return []

            suggestions = data[1]
            self._stats['total_requests'] += 1

            logger.debug(
                "Autocomplete fetched",
                query=query,
                count=len(suggestions)
            )

            return suggestions

        except httpx.ConnectError as e:
            raise AutocompleteCollectorError(f"Network error: {e}")
        except ValueError as e:
            raise AutocompleteCollectorError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise AutocompleteCollectorError(f"Failed to collect suggestions: {e}")

    def _create_document(
        self,
        suggestion: str,
        seed_keyword: str,
        expansion_type: ExpansionType
    ) -> Document:
        """Create Document from autocomplete suggestion"""
        doc_id = self._generate_document_id("autocomplete_suggestions", suggestion)

        # Create synthetic URL for autocomplete suggestion
        source_url = f"{self.AUTOCOMPLETE_URL}?q={suggestion.replace(' ', '+')}&client=firefox&hl={self.language}"
        canonical_url = self.deduplicator.get_canonical_url(source_url)

        # Create content with metadata
        content = f"Autocomplete suggestion: {suggestion}\nSeed keyword: {seed_keyword}\nExpansion type: {expansion_type.value}"

        return Document(
            id=doc_id,
            source="autocomplete_suggestions",
            source_url=source_url,
            canonical_url=canonical_url,
            title=suggestion,
            content=content,
            language=self.config.market.language,
            domain=self.config.market.domain,
            market=self.config.market.market,
            vertical=self.config.market.vertical,
            published_at=datetime.now(),  # Autocomplete is real-time
            fetched_at=datetime.now(),
            content_hash=self.deduplicator.compute_content_hash(content)
        )

    def _generate_document_id(self, source: str, title: str) -> str:
        """Generate unique document ID"""
        unique_string = f"{source}:{title}"
        return hashlib.md5(unique_string.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[List[str]]:
        """Get suggestions from cache if not expired"""
        if cache_key not in self._cache:
            return None

        cached = self._cache[cache_key]
        cache_time = cached.get('timestamp')

        if not cache_time:
            return None

        # Check if expired (30 days default)
        if datetime.now() - cache_time > timedelta(days=self.cache_ttl_days):
            del self._cache[cache_key]
            return None

        return cached.get('suggestions')

    def _save_to_cache(self, cache_key: str, suggestions: List[str]):
        """Save suggestions to cache"""
        self._cache[cache_key] = {
            'timestamp': datetime.now(),
            'suggestions': suggestions
        }

    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests"""
        if self.last_request_time is None:
            self.last_request_time = time.time()
            return

        elapsed = time.time() - self.last_request_time
        required_delay = 1.0 / self.rate_limit

        if elapsed < required_delay:
            sleep_time = required_delay - elapsed
            logger.debug("Rate limiting", sleep_time=sleep_time)
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def get_statistics(self) -> Dict:
        """Get collection statistics"""
        return self._stats.copy()

    def save_cache(self):
        """Save cache to disk"""
        cache_file = self.cache_dir / "autocomplete_cache.json"

        # Prepare cache for serialization
        serializable_cache = {}
        for key, value in self._cache.items():
            serializable_cache[key] = {
                'timestamp': value['timestamp'].isoformat(),
                'suggestions': value['suggestions']
            }

        try:
            with open(cache_file, 'w') as f:
                json.dump(serializable_cache, f, indent=2)
            logger.info("Cache saved", file=str(cache_file))
        except Exception as e:
            logger.error("Failed to save cache", error=str(e))

    def load_cache(self):
        """Load cache from disk"""
        cache_file = self.cache_dir / "autocomplete_cache.json"

        if not cache_file.exists():
            return

        try:
            with open(cache_file, 'r') as f:
                serialized_cache = json.load(f)

            # Deserialize cache
            for key, value in serialized_cache.items():
                self._cache[key] = {
                    'timestamp': datetime.fromisoformat(value['timestamp']),
                    'suggestions': value['suggestions']
                }

            logger.info("Cache loaded", entries=len(self._cache))
        except Exception as e:
            logger.error("Failed to load cache", error=str(e))

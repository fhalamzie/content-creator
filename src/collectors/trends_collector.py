"""
Trends Collector - Google Trends via Gemini API

**BREAKING CHANGE (Nov 2025)**: Replaced pytrends with Gemini API
- pytrends is DEAD (archived April 2025, no maintenance)
- Google 404/429 errors make pytrends unreliable
- Gemini API provides FREE, RELIABLE trend data with 60s timeout

Features:
- Gemini API for trend data (FREE, 1,500 grounded queries/day)
- Real-time trending topics via Google Search grounding
- Related queries and interest trends via web search
- Intelligent caching (1h for trending, 24h for interest)
- Built-in 60s timeout (no hanging)
- Query health tracking with adaptive retry
- Regional targeting (DE, US, FR, etc.)

Usage:
    from src.collectors.trends_collector import TrendsCollector
    from src.database.sqlite_manager import DatabaseManager
    from src.processors.deduplicator import Deduplicator
    from src.agents.gemini_agent import GeminiAgent

    gemini_agent = GeminiAgent(enable_grounding=True)
    collector = TrendsCollector(
        config=config,
        db_manager=db_manager,
        deduplicator=deduplicator,
        gemini_agent=gemini_agent,
        region='DE'  # Germany
    )

    # Collect trending searches
    docs = collector.collect_trending_searches(pn='germany')

    # Collect related queries
    docs = collector.collect_related_queries(keywords=['PropTech'], query_type='top')

    # Collect interest over time
    docs = collector.collect_interest_over_time(keywords=['PropTech'])
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Literal
from dataclasses import dataclass
from enum import Enum

from src.utils.logger import get_logger
from src.models.document import Document
from src.agents.gemini_agent import GeminiAgent, GeminiAgentError

logger = get_logger(__name__)


class TrendsCollectorError(Exception):
    """Trends Collector related errors"""
    pass


class TrendType(str, Enum):
    """Types of trend queries"""
    TRENDING_SEARCHES = "trending_searches"
    RELATED_QUERIES = "related_queries"
    INTEREST_OVER_TIME = "interest_over_time"


@dataclass
class QueryHealth:
    """Track query reliability and health metrics"""
    query_id: str
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None

    def record_success(self):
        """Record successful query"""
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_success = datetime.now()

    def record_failure(self):
        """Record failed query"""
        self.failure_count += 1
        self.consecutive_failures += 1
        self.last_failure = datetime.now()

    def is_healthy(self, max_consecutive_failures: int = 5) -> bool:
        """Check if query is healthy"""
        return self.consecutive_failures < max_consecutive_failures


class TrendsCollector:
    """
    Google Trends collector using Gemini API (FREE, reliable, 60s timeout)

    Features:
    - Real-time trending topics via Google Search grounding
    - Related queries via web search
    - Interest trends via web research
    - Built-in 60s timeout (no hanging)
    - Smart caching (1h trending, 24h interest)
    - Query health tracking
    - Free tier: 1,500 grounded queries/day
    """

    def __init__(
        self,
        config,
        db_manager,
        deduplicator,
        gemini_agent: Optional[GeminiAgent] = None,
        cache_dir: str = "cache/trends",
        region: str = "US",
        max_consecutive_failures: int = 5
    ):
        """
        Initialize Trends Collector (Gemini API version)

        Args:
            config: Market configuration
            db_manager: Database manager for persistence
            deduplicator: Deduplicator for duplicate detection
            gemini_agent: GeminiAgent instance (creates default if None)
            cache_dir: Directory for cache storage
            region: Default region for trends (ISO code: US, DE, FR, etc.)
            max_consecutive_failures: Max failures before marking query unhealthy
        """
        self.config = config
        self.db_manager = db_manager
        self.deduplicator = deduplicator
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize or use provided GeminiAgent
        if gemini_agent is None:
            self.gemini_agent = GeminiAgent(
                model="gemini-2.5-flash",
                enable_grounding=True,
                temperature=0.3
            )
        else:
            self.gemini_agent = gemini_agent

        self.region = region
        self.max_consecutive_failures = max_consecutive_failures

        # Internal state
        self._cache: Dict = {}  # In-memory cache
        self.query_health: Dict[str, QueryHealth] = {}

        # Statistics
        self._stats = {
            'total_queries': 0,
            'total_documents': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'failed_queries': 0,
        }

        # Load cache from disk
        self.load_cache()

        logger.info(
            "TrendsCollector initialized (Gemini API)",
            region=region,
            cache_dir=str(self.cache_dir),
            backend="gemini_api"
        )

    def collect_trending_searches(
        self,
        pn: str = 'united_states'
    ) -> List[Document]:
        """
        Collect trending searches for a region using Gemini API

        Args:
            pn: Region name (e.g., 'germany', 'united_states', 'france')

        Returns:
            List of Document objects for trending searches

        Raises:
            TrendsCollectorError: If collection fails
        """
        query_id = f"trending_searches_{pn}"

        # Check if query is healthy
        if self._should_skip_query(query_id):
            logger.warning("Skipping unhealthy query", query_id=query_id)
            return []

        # Check cache (1 hour TTL for trending searches)
        cache_key = f"trending_searches_{pn}"
        cached = self._get_from_cache(cache_key, ttl_hours=1)
        if cached:
            logger.info("Trending searches retrieved from cache", pn=pn)
            self._stats['cache_hits'] += 1
            return self._create_documents_from_cache(cached, f"trends_trending_searches_{pn}")

        self._stats['cache_misses'] += 1

        try:
            # Map region codes to full names
            region_map = {
                'germany': 'Germany',
                'united_states': 'United States',
                'france': 'France',
                'uk': 'United Kingdom',
                'spain': 'Spain',
                'italy': 'Italy'
            }
            region_name = region_map.get(pn.lower(), pn.title())

            # Build Gemini prompt for trending topics
            prompt = f"""What are the top 20 trending topics in {region_name} today?

Include topics from: news, technology, business, entertainment, sports.

Search the web for current trending topics and return them as a structured list."""

            # Define response schema
            response_schema = {
                "type": "object",
                "properties": {
                    "topics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic": {"type": "string"},
                                "category": {"type": "string"},
                                "description": {"type": "string"}
                            },
                            "required": ["topic", "category", "description"]
                        }
                    }
                },
                "required": ["topics"]
            }

            logger.info("Fetching trending searches via Gemini API", pn=pn)

            # Call Gemini API
            result = self._call_gemini_api(prompt, response_schema)

            # Extract topics array
            trends_data = result if isinstance(result, list) else result.get('topics', [])

            if not trends_data:
                logger.warning("No trending searches found", pn=pn)
                self._record_query_success(query_id)
                return []

            # Cache results
            self._save_to_cache(cache_key, trends_data)

            # Create documents
            documents = []
            for trend in trends_data:
                doc = self._create_document(
                    source=f"trends_trending_searches_{pn}",
                    title=trend.get('topic', 'Unknown'),
                    content=f"Trending topic: {trend.get('topic', 'Unknown')}\nCategory: {trend.get('category', 'N/A')}\nDescription: {trend.get('description', 'N/A')}",
                    metadata={
                        'category': trend.get('category', 'N/A'),
                        'description': trend.get('description', ''),
                        'region': pn
                    }
                )

                # Check for duplicates
                if self.deduplicator.is_duplicate(doc.content):
                    logger.debug("Skipping duplicate trend", title=doc.title)
                    continue

                documents.append(doc)

            self._stats['total_queries'] += 1
            self._stats['total_documents'] += len(documents)
            self._record_query_success(query_id)

            logger.info(
                "Trending searches collected",
                pn=pn,
                count=len(documents)
            )

            return documents

        except Exception as e:
            self._stats['failed_queries'] += 1
            self._record_query_failure(query_id)
            logger.error(
                "Failed to collect trending searches",
                pn=pn,
                error=str(e)
            )
            raise TrendsCollectorError(f"Failed to collect trending searches: {e}")

    def collect_related_queries(
        self,
        keywords: List[str],
        query_type: Literal['top', 'rising'] = 'top',
        timeframe: str = 'today 3-m'
    ) -> List[Document]:
        """
        Collect related queries for keywords using Gemini API

        Args:
            keywords: List of keywords to analyze
            query_type: 'top' or 'rising' queries
            timeframe: Time range (for context only)

        Returns:
            List of Document objects for related queries

        Raises:
            TrendsCollectorError: If collection fails
        """
        f"related_queries_{'_'.join(keywords)}"

        # Check cache (24 hour TTL)
        cache_key = f"related_queries_{query_type}_{'_'.join(keywords)}_{timeframe}"
        cached = self._get_from_cache(cache_key, ttl_hours=24)
        if cached:
            logger.info("Related queries retrieved from cache", keywords=keywords)
            self._stats['cache_hits'] += 1
            # Add query_type to cached data
            for item in cached:
                item['query_type'] = query_type
            return self._create_documents_from_cache(cached, "trends_related_queries")

        self._stats['cache_misses'] += 1

        try:
            # Build Gemini prompt for related queries
            keywords_str = ', '.join(keywords)
            query_context = "most popular" if query_type == 'top' else "fastest rising"

            prompt = f"""What are the {query_context} related search queries for these keywords: {keywords_str}?

Find 15-20 related queries that people are searching for.

Search the web for current trending related queries."""

            # Define response schema
            response_schema = {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "keyword": {"type": "string"},
                                "query": {"type": "string"},
                                "relevance": {"type": "number"}
                            },
                            "required": ["keyword", "query", "relevance"]
                        }
                    }
                },
                "required": ["queries"]
            }

            logger.info(
                "Fetching related queries via Gemini API",
                keywords=keywords,
                query_type=query_type
            )

            # Call Gemini API
            result = self._call_gemini_api(prompt, response_schema)

            # Extract queries array
            queries_data = result if isinstance(result, list) else result.get('queries', [])

            if not queries_data:
                logger.warning("No related queries found", keywords=keywords)
                return []

            # Cache results
            self._save_to_cache(cache_key, queries_data)

            # Create documents
            documents = []
            for query_data in queries_data:
                title_prefix = "Related query" if query_type == 'top' else "Rising query"
                doc = self._create_document(
                    source="trends_related_queries",
                    title=f"{title_prefix}: {query_data.get('query', 'Unknown')}",
                    content=f"Related to: {query_data.get('keyword', 'N/A')}\nQuery: {query_data.get('query', 'Unknown')}\nRelevance: {query_data.get('relevance', 0)}",
                    metadata={
                        'parent_keyword': query_data.get('keyword', ''),
                        'query_type': query_type,
                        'relevance': query_data.get('relevance', 0)
                    }
                )

                # Check for duplicates
                if self.deduplicator.is_duplicate(doc.content):
                    logger.debug("Skipping duplicate query", query=doc.title)
                    continue

                documents.append(doc)

            self._stats['total_queries'] += 1
            self._stats['total_documents'] += len(documents)

            logger.info(
                "Related queries collected",
                keywords=keywords,
                query_type=query_type,
                count=len(documents)
            )

            return documents

        except Exception as e:
            self._stats['failed_queries'] += 1
            logger.error(
                "Failed to collect related queries",
                keywords=keywords,
                error=str(e)
            )
            raise TrendsCollectorError(f"Failed to collect related queries: {e}")

    def collect_interest_over_time(
        self,
        keywords: List[str],
        timeframe: str = 'today 3-m'
    ) -> List[Document]:
        """
        Collect interest over time for keywords using Gemini API

        Args:
            keywords: List of keywords to analyze
            timeframe: Time range (e.g., 'today 3-m', '2025-01-01 2025-11-04')

        Returns:
            List of Document objects with interest trends

        Raises:
            TrendsCollectorError: If collection fails
        """
        f"interest_over_time_{'_'.join(keywords)}"

        # Check cache (24 hour TTL)
        cache_key = f"interest_over_time_{'_'.join(keywords)}_{timeframe}"
        cached = self._get_from_cache(cache_key, ttl_hours=24)
        if cached:
            logger.info("Interest over time retrieved from cache", keywords=keywords)
            self._stats['cache_hits'] += 1
            return self._create_documents_from_cache(cached, "trends_interest_over_time")

        self._stats['cache_misses'] += 1

        try:
            # Parse timeframe for context
            timeframe_desc = self._parse_timeframe(timeframe)
            keywords_str = ', '.join(keywords)

            # Build Gemini prompt for interest trends
            prompt = f"""Analyze the search interest trends for these keywords over {timeframe_desc}: {keywords_str}

Provide trend analysis including:
- Overall trend direction (increasing, decreasing, stable)
- Relative interest level (high, medium, low)
- Notable spikes or changes

Search the web for current trend data."""

            # Define response schema
            response_schema = {
                "type": "object",
                "properties": {
                    "trends": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "keyword": {"type": "string"},
                                "trend": {"type": "string"},
                                "interest_level": {"type": "string"},
                                "analysis": {"type": "string"}
                            },
                            "required": ["keyword", "trend", "interest_level", "analysis"]
                        }
                    }
                },
                "required": ["trends"]
            }

            logger.info(
                "Fetching interest over time via Gemini API",
                keywords=keywords,
                timeframe=timeframe
            )

            # Call Gemini API
            result = self._call_gemini_api(prompt, response_schema)

            # Extract trends array
            interest_data = result if isinstance(result, list) else result.get('trends', [])

            if not interest_data:
                logger.warning("No interest data found", keywords=keywords)
                return []

            # Cache results
            self._save_to_cache(cache_key, interest_data)

            # Create documents
            documents = []
            for data in interest_data:
                doc = self._create_document(
                    source="trends_interest_over_time",
                    title=f"Interest over time: {data.get('keyword', 'Unknown')}",
                    content=f"Keyword: {data.get('keyword', 'Unknown')}\nTrend: {data.get('trend', 'N/A')}\nInterest level: {data.get('interest_level', 'N/A')}\nAnalysis: {data.get('analysis', 'N/A')}",
                    metadata=data
                )

                documents.append(doc)

            self._stats['total_queries'] += 1
            self._stats['total_documents'] += len(documents)

            logger.info(
                "Interest over time collected",
                keywords=keywords,
                count=len(documents)
            )

            return documents

        except Exception as e:
            self._stats['failed_queries'] += 1
            logger.error(
                "Failed to collect interest over time",
                keywords=keywords,
                error=str(e)
            )
            raise TrendsCollectorError(f"Failed to collect interest over time: {e}")

    def _call_gemini_api(self, prompt: str, response_schema: Dict) -> List[Dict]:
        """
        Call Gemini API with a prompt and response schema

        Args:
            prompt: Prompt to send to Gemini
            response_schema: JSON schema for structured output

        Returns:
            Parsed JSON response as list of dictionaries

        Raises:
            TrendsCollectorError: If API call fails
        """
        try:
            result = self.gemini_agent.generate(
                prompt=prompt,
                response_schema=response_schema,
                enable_grounding=True
            )

            # Extract response content
            if 'content' in result and isinstance(result['content'], list):
                return result['content']
            elif 'content' in result:
                # Single object, wrap in list
                return [result['content']]
            else:
                # Try to find array in response
                for key in result:
                    if isinstance(result[key], list):
                        return result[key]

                raise TrendsCollectorError("No valid array found in Gemini response")

        except GeminiAgentError as e:
            raise TrendsCollectorError(f"Gemini API error: {e}")
        except Exception as e:
            logger.error("Failed to call Gemini API", error=str(e))
            raise TrendsCollectorError(f"Gemini API call failed: {e}")


    def _parse_timeframe(self, timeframe: str) -> str:
        """Parse timeframe into human-readable description"""
        timeframe_map = {
            'today 3-m': 'the past 3 months',
            'today 12-m': 'the past 12 months',
            'today 1-y': 'the past year',
            'today 5-y': 'the past 5 years',
            'all': 'all time'
        }

        return timeframe_map.get(timeframe, timeframe)

    def _create_document(
        self,
        source: str,
        title: str,
        content: str,
        metadata: Optional[Dict] = None,
        published_at: Optional[datetime] = None
    ) -> Document:
        """Create Document from trend data"""
        doc_id = self._generate_document_id(source, title)

        # Generate source URL for Google Trends
        keyword_slug = title.lower().replace(' ', '-')[:50]
        source_url = f"https://trends.google.com/trends/explore?q={keyword_slug}"
        canonical_url = self.deduplicator.get_canonical_url(source_url)

        # Use current time if no published_at provided
        if published_at is None:
            published_at = datetime.now()

        return Document(
            id=doc_id,
            source=source,
            source_url=source_url,
            canonical_url=canonical_url,
            title=title,
            content=content,
            language=self.config.market.language,
            domain=self.config.market.domain,
            market=self.config.market.market,
            vertical=self.config.market.vertical,
            published_at=published_at,
            fetched_at=datetime.now(),
            content_hash=self.deduplicator.compute_content_hash(content)
        )

    def _generate_document_id(self, source: str, title: str) -> str:
        """Generate unique document ID"""
        unique_string = f"{source}:{title}"
        return hashlib.md5(unique_string.encode()).hexdigest()

    def _get_from_cache(
        self,
        cache_key: str,
        ttl_hours: int
    ) -> Optional[List[Dict]]:
        """Get data from cache if not expired"""
        if cache_key not in self._cache:
            return None

        cached = self._cache[cache_key]
        cache_time = cached.get('timestamp')

        if not cache_time:
            return None

        # Check if expired
        if datetime.now() - cache_time > timedelta(hours=ttl_hours):
            del self._cache[cache_key]
            return None

        return cached.get('data')

    def _save_to_cache(self, cache_key: str, data: List[Dict]):
        """Save data to cache"""
        self._cache[cache_key] = {
            'timestamp': datetime.now(),
            'data': data
        }

    def _create_documents_from_cache(
        self,
        cached_data: List[Dict],
        source: str
    ) -> List[Document]:
        """Create documents from cached data"""
        documents = []

        for data in cached_data:
            # Reconstruct document based on data format
            if 'topic' in data:
                # Trending searches format (Gemini)
                doc = self._create_document(
                    source=source,
                    title=data['topic'],
                    content=f"Trending topic: {data['topic']}\nCategory: {data.get('category', 'N/A')}\nDescription: {data.get('description', 'N/A')}",
                    metadata=data
                )
            elif 'query' in data:
                # Related queries format
                query_type = data.get('query_type', 'top')
                title_prefix = "Related query" if query_type == 'top' else "Rising query"
                doc = self._create_document(
                    source=source,
                    title=f"{title_prefix}: {data['query']}",
                    content=f"Related to: {data.get('keyword', 'N/A')}\nQuery: {data['query']}\nRelevance: {data.get('relevance', data.get('value', 0))}",
                    metadata=data
                )
            elif 'keyword' in data and ('trend' in data or 'average_interest' in data):
                # Interest over time format (Gemini or pytrends)
                if 'trend' in data:
                    # Gemini format
                    doc = self._create_document(
                        source=source,
                        title=f"Interest over time: {data['keyword']}",
                        content=f"Keyword: {data['keyword']}\nTrend: {data.get('trend', 'N/A')}\nInterest level: {data.get('interest_level', 'N/A')}\nAnalysis: {data.get('analysis', 'N/A')}",
                        metadata=data
                    )
                else:
                    # pytrends format (backward compatibility)
                    doc = self._create_document(
                        source=source,
                        title=f"Interest over time: {data['keyword']}",
                        content=f"Keyword: {data['keyword']}\nAverage interest: {data.get('average_interest', 0)}\nMax: {data.get('max_interest', 0)}\nMin: {data.get('min_interest', 0)}",
                        metadata=data
                    )
            else:
                continue

            # Check for duplicates
            if self.deduplicator.is_duplicate(doc.content):
                logger.debug("Skipping duplicate (from cache)", title=doc.title)
                continue

            documents.append(doc)

        return documents

    def _should_skip_query(self, query_id: str) -> bool:
        """Check if query should be skipped due to poor health"""
        if query_id not in self.query_health:
            return False

        health = self.query_health[query_id]
        return not health.is_healthy(self.max_consecutive_failures)

    def _record_query_success(self, query_id: str):
        """Record successful query"""
        if query_id not in self.query_health:
            self.query_health[query_id] = QueryHealth(query_id=query_id)

        self.query_health[query_id].record_success()

    def _record_query_failure(self, query_id: str):
        """Record failed query"""
        if query_id not in self.query_health:
            self.query_health[query_id] = QueryHealth(query_id=query_id)

        self.query_health[query_id].record_failure()

    def get_statistics(self) -> Dict:
        """Get collection statistics"""
        return self._stats.copy()

    def save_cache(self):
        """Save cache to disk"""
        cache_file = self.cache_dir / "trends_cache.json"

        # Prepare cache for serialization
        serializable_cache = {}
        for key, value in self._cache.items():
            serializable_cache[key] = {
                'timestamp': value['timestamp'].isoformat(),
                'data': value['data']
            }

        try:
            with open(cache_file, 'w') as f:
                json.dump(serializable_cache, f, indent=2)
            logger.info("Cache saved", file=str(cache_file))
        except Exception as e:
            logger.error("Failed to save cache", error=str(e))

    def load_cache(self):
        """Load cache from disk"""
        cache_file = self.cache_dir / "trends_cache.json"

        if not cache_file.exists():
            return

        try:
            with open(cache_file, 'r') as f:
                serialized_cache = json.load(f)

            # Deserialize cache
            for key, value in serialized_cache.items():
                self._cache[key] = {
                    'timestamp': datetime.fromisoformat(value['timestamp']),
                    'data': value['data']
                }

            logger.info("Cache loaded", entries=len(self._cache))
        except Exception as e:
            logger.error("Failed to load cache", error=str(e))

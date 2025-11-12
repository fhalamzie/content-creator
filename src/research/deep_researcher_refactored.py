"""
Deep Researcher - Multi-Backend Orchestrator

Parallel multi-backend research system with graceful degradation.

Architecture:
- SEARCH: 3 backends in parallel (Tavily DEPTH + SearXNG BREADTH + Gemini TRENDS)
- CONTENT: 2 collectors in parallel (RSS FEEDS + TheNewsAPI BREAKING NEWS)
- REPORT: gpt-researcher for final report generation
- FUSION: Merge & deduplicate sources with diversity scoring

Example:
    from src.research.deep_researcher_refactored import DeepResearcher

    researcher = DeepResearcher()

    config = {
        'domain': 'SaaS',
        'market': 'Germany',
        'language': 'de',
        'vertical': 'Proptech'
    }

    result = await researcher.research_topic("PropTech Trends 2025", config)
    print(f"Report: {result['report']}")
    print(f"Sources: {len(result['sources'])}")  # 25-30 source objects
    print(f"URLs: {result['source_urls']}")  # List of URLs
"""

import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from urllib.parse import urlparse
import os

from datasketch import MinHash, MinHashLSH

from src.research.backends.tavily_backend import TavilyBackend
from src.research.backends.searxng_backend import SearXNGBackend
from src.research.backends.gemini_api_backend import GeminiAPIBackend
from src.research.backends.base import BackendHealth, SearchResult
from src.research.backends.exceptions import BackendUnavailableError, AuthenticationError
from src.collectors.rss_collector import RSSCollector
from src.collectors.thenewsapi_collector import TheNewsAPICollector, TheNewsAPIError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Lazy import to avoid dependency issues in tests
GPTResearcher = None


class DeepResearchError(Exception):
    """Raised when deep research fails"""
    pass


class DeepResearcher:
    """
    Multi-backend research orchestrator with parallel search and graceful degradation

    Features:
    - 5 sources in parallel:
      - SEARCH: Tavily (DEPTH) + SearXNG (BREADTH) + Gemini API (TRENDS)
      - CONTENT: RSS Feeds (CURATED) + TheNewsAPI (BREAKING NEWS)
    - Graceful degradation: Continue if ≥1 source succeeds
    - Source fusion: Merge & deduplicate 25-30 sources
    - Quality scoring: Sources + backend health + domain diversity
    - Cost: $0.02/topic (only Tavily paid, TheNewsAPI 100/day free)
    - Statistics: Backend/collector success rates, health monitoring
    """

    def __init__(
        self,
        tavily_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        thenewsapi_api_key: Optional[str] = None,
        searxng_instance_url: Optional[str] = None,
        config=None,
        db_manager=None,
        deduplicator=None,
        enable_tavily: bool = True,
        enable_searxng: bool = True,
        enable_gemini: bool = True,
        enable_rss: bool = True,
        enable_thenewsapi: bool = True,
        _testing_mode: bool = False
    ):
        """
        Initialize multi-backend orchestrator with 5 parallel sources

        Args:
            tavily_api_key: Tavily API key (auto-loads if None)
            gemini_api_key: Gemini API key (auto-loads if None)
            thenewsapi_api_key: TheNewsAPI API key (auto-loads if None)
            searxng_instance_url: Custom SearXNG instance (uses public if None)
            config: Market configuration (required for RSS/TheNewsAPI)
            db_manager: Database manager (required for RSS)
            deduplicator: Deduplicator (required for RSS/TheNewsAPI)
            enable_tavily: Enable Tavily backend (default: True)
            enable_searxng: Enable SearXNG backend (default: True)
            enable_gemini: Enable Gemini API backend (default: True)
            enable_rss: Enable RSS collector (default: True)
            enable_thenewsapi: Enable TheNewsAPI collector (default: True)
            _testing_mode: Skip source validation for testing (default: False)
        """
        # Store dependencies for collectors
        self.config = config
        self.db_manager = db_manager
        self.deduplicator = deduplicator

        # Initialize backends (search)
        self.backends = {}
        self.backend_stats = {
            'tavily': {'success': 0, 'failed': 0, 'total_sources': 0},
            'searxng': {'success': 0, 'failed': 0, 'total_sources': 0},
            'gemini': {'success': 0, 'failed': 0, 'total_sources': 0},
            'rss': {'success': 0, 'failed': 0, 'total_sources': 0},
            'thenewsapi': {'success': 0, 'failed': 0, 'total_sources': 0}
        }

        # Initialize collectors (content)
        self.collectors = {}

        # Initialize Tavily (DEPTH horizon)
        if enable_tavily:
            try:
                self.backends['tavily'] = TavilyBackend(api_key=tavily_api_key)
                logger.info("tavily_backend_enabled", horizon="DEPTH")
            except (BackendUnavailableError, AuthenticationError) as e:
                logger.warning("tavily_backend_disabled", reason=str(e))

        # Initialize SearXNG (BREADTH horizon)
        if enable_searxng:
            try:
                self.backends['searxng'] = SearXNGBackend(instance_url=searxng_instance_url)
                logger.info("searxng_backend_enabled", horizon="BREADTH")
            except BackendUnavailableError as e:
                logger.warning("searxng_backend_disabled", reason=str(e))

        # Initialize Gemini API (TRENDS horizon)
        if enable_gemini:
            try:
                self.backends['gemini'] = GeminiAPIBackend(api_key=gemini_api_key)
                logger.info("gemini_backend_enabled", horizon="TRENDS")
            except (BackendUnavailableError, AuthenticationError) as e:
                logger.warning("gemini_backend_disabled", reason=str(e))

        # Initialize RSS Collector (CURATED horizon)
        if enable_rss and config and db_manager and deduplicator:
            try:
                self.collectors['rss'] = RSSCollector(
                    config=config,
                    db_manager=db_manager,
                    deduplicator=deduplicator
                )
                logger.info("rss_collector_enabled", horizon="CURATED")
            except Exception as e:
                logger.warning("rss_collector_disabled", reason=str(e))

        # Initialize TheNewsAPI Collector (BREAKING NEWS horizon)
        if enable_thenewsapi and config and deduplicator:
            try:
                self.collectors['thenewsapi'] = TheNewsAPICollector(
                    api_key=thenewsapi_api_key,
                    config=config,
                    db_manager=db_manager,
                    deduplicator=deduplicator
                )
                logger.info("thenewsapi_collector_enabled", horizon="BREAKING_NEWS")
            except TheNewsAPIError as e:
                logger.warning("thenewsapi_collector_disabled", reason=str(e))

        # Check if at least one source is available (skip in testing mode)
        total_sources = len(self.backends) + len(self.collectors)
        if not _testing_mode and total_sources == 0:
            raise DeepResearchError(
                "No search backends or collectors available. At least one source must be enabled."
            )

        if total_sources > 0:
            logger.info(
                "orchestrator_initialized",
                backends_enabled=list(self.backends.keys()),
                collectors_enabled=list(self.collectors.keys()),
                total_sources=total_sources
            )

        # Overall statistics
        self.total_research = 0
        self.failed_research = 0
        self.total_sources_found = 0

    async def research_topic(
        self,
        topic: str,
        config: Dict,
        competitor_gaps: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None
    ) -> Dict:
        """
        Research topic using parallel multi-backend search

        Args:
            topic: Topic to research
            config: Research config (domain, market, language, vertical)
            competitor_gaps: Optional content gaps from competitor research
            keywords: Optional keywords to focus on

        Returns:
            Dictionary with:
            - topic: Original topic
            - report: Markdown report (5-6 pages)
            - sources: List of source objects (dicts with url, title, content, backend, etc.)
            - source_urls: List of source URLs only (for convenience)
            - word_count: Approximate word count
            - researched_at: ISO timestamp
            - backend_stats: Backend performance metrics
            - quality_score: Research quality score (0-100)

        Raises:
            DeepResearchError: If all backends fail
        """
        if not topic or len(topic.strip()) == 0:
            raise DeepResearchError("Topic cannot be empty")

        self.total_research += 1

        try:
            logger.info(
                "research_started",
                topic=topic,
                domain=config.get('domain'),
                market=config.get('market'),
                backends=list(self.backends.keys())
            )

            print(f"[DEBUG] DeepResearcher.research_topic STARTED for: {topic}")
            import sys
            sys.stdout.flush()

            # Build specialized queries for each horizon
            depth_query = self._build_depth_query(topic, config, keywords)
            breadth_query = self._build_breadth_query(topic, config, competitor_gaps)
            trends_query = self._build_trends_query(topic, config)

            print(f"[DEBUG] Queries built successfully")
            sys.stdout.flush()

            # Execute ALL sources in parallel (3 search backends + 2 collectors)
            all_tasks = []
            source_names = []

            # Add search backend tasks
            if 'tavily' in self.backends:
                all_tasks.append(self._search_with_logging(
                    'tavily',
                    depth_query,
                    max_results=10
                ))
                source_names.append('tavily')

            if 'searxng' in self.backends:
                all_tasks.append(self._search_with_logging(
                    'searxng',
                    breadth_query,
                    max_results=30
                ))
                source_names.append('searxng')

            if 'gemini' in self.backends:
                all_tasks.append(self._search_with_logging(
                    'gemini',
                    trends_query,
                    max_results=12
                ))
                source_names.append('gemini')

            # Add collector tasks
            if 'rss' in self.collectors:
                all_tasks.append(self._collect_from_rss(
                    topic=topic,
                    config=config,
                    keywords=keywords
                ))
                source_names.append('rss')

            if 'thenewsapi' in self.collectors:
                all_tasks.append(self._collect_from_thenewsapi(
                    topic=topic,
                    config=config,
                    keywords=keywords
                ))
                source_names.append('thenewsapi')

            # Gather results (graceful degradation: continue if ≥1 succeeds)
            all_results = await asyncio.gather(*all_tasks, return_exceptions=True)

            # Process results from all sources
            all_sources = []
            successful_sources = []
            failed_sources = []

            for source_name, result in zip(source_names, all_results):
                if isinstance(result, Exception):
                    logger.error(
                        "source_exception",
                        source=source_name,
                        error=str(result)
                    )
                    failed_sources.append(source_name)
                    self.backend_stats[source_name]['failed'] += 1
                elif isinstance(result, list):
                    all_sources.extend(result)
                    successful_sources.append(source_name)
                    self.backend_stats[source_name]['success'] += 1
                    self.backend_stats[source_name]['total_sources'] += len(result)

            logger.info(
                "sources_complete",
                successful=len(successful_sources),
                failed=len(failed_sources),
                total_sources_raw=len(all_sources)
            )

            # Check if minimum sources succeeded
            if not successful_sources:
                raise DeepResearchError(
                    f"All sources failed: {', '.join(failed_sources)}"
                )

            # Merge and deduplicate sources
            merged_sources = self._merge_with_diversity(all_sources)

            # Update statistics
            self.total_sources_found += len(merged_sources)

            # Calculate quality score
            quality_score = self._calculate_quality_score(
                sources_count=len(merged_sources),
                successful_backends=successful_sources,
                failed_backends=failed_sources
            )

            logger.info(
                "sources_processed",
                merged_count=len(merged_sources),
                quality_score=quality_score
            )

            # Generate report using gpt-researcher (placeholder for now)
            # In production, pass merged_sources to gpt-researcher for report generation
            report = f"# Research Report: {topic}\n\n" \
                     f"**Sources Found**: {len(merged_sources)}\n" \
                     f"**Quality Score**: {quality_score}/100\n\n" \
                     f"## Sources\n\n" + \
                     "\n".join(f"- {s['url']}" for s in merged_sources[:10])

            word_count = len(report.split())

            result = {
                'topic': topic,
                'report': report,
                'sources': merged_sources,  # Return full source objects (not just URLs)
                'source_urls': [s['url'] for s in merged_sources],  # Also provide just URLs for convenience
                'word_count': word_count,
                'researched_at': datetime.now().isoformat(),
                'backend_stats': {
                    'successful': successful_sources,
                    'failed': failed_sources,
                    'sources_per_source': {
                        name: len([s for s in all_sources if s.get('backend') == name or s.get('source', '').startswith(name)])
                        for name in source_names
                    }
                },
                'quality_score': quality_score
            }

            logger.info(
                "research_complete",
                topic=topic,
                sources=len(merged_sources),
                quality_score=quality_score
            )

            return result

        except Exception as e:
            self.failed_research += 1
            logger.error("research_failed", topic=topic, error=str(e))
            raise DeepResearchError(f"Research failed for '{topic}': {e}")

    async def _search_with_logging(
        self,
        backend_name: str,
        query: str,
        max_results: int
    ) -> List[SearchResult]:
        """
        Execute search with comprehensive error logging

        Args:
            backend_name: Backend to use
            query: Search query
            max_results: Maximum results

        Returns:
            List of SearchResult dicts

        Raises:
            Exception: If backend search fails (for graceful degradation tracking)
        """
        logger.info(
            "backend_search_start",
            backend=backend_name,
            query=query[:100],
            max_results=max_results
        )

        backend = self.backends[backend_name]
        results = await backend.search(query, max_results=max_results)

        logger.info(
            "backend_search_success",
            backend=backend_name,
            results_count=len(results)
        )

        return results

    async def _collect_from_rss(
        self,
        topic: str,
        config: Dict,
        keywords: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Collect from RSS feeds and convert to SearchResult format

        Args:
            topic: Research topic
            config: Market configuration
            keywords: Optional keywords to filter

        Returns:
            List of SearchResult dicts (compatible with backends)

        Raises:
            Exception: If collection fails (for graceful degradation tracking)
        """
        logger.info("rss_collection_start", topic=topic)

        # Get feed URLs from config
        feed_urls = config.get('collectors', {}).get('custom_feeds', [])
        if not feed_urls:
            logger.warning("rss_no_feeds_configured")
            return []

        # Collect documents from feeds
        collector = self.collectors['rss']
        documents = collector.collect_from_feeds(feed_urls, skip_errors=True)

        # Convert Documents to SearchResult format for consistency
        search_results = []
        for doc in documents:
            search_result = {
                'url': doc.source_url,
                'title': doc.title,
                'content': doc.content or doc.summary or "",
                'published_date': doc.published_at.isoformat() if doc.published_at else None,
                'backend': 'rss',
                'source': doc.source
            }
            search_results.append(search_result)

        logger.info("rss_collection_success", documents_count=len(search_results))
        return search_results

    async def _collect_from_thenewsapi(
        self,
        topic: str,
        config: Dict,
        keywords: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Collect from TheNewsAPI and convert to SearchResult format

        Args:
            topic: Research topic
            config: Market configuration
            keywords: Optional keywords to filter

        Returns:
            List of SearchResult dicts (compatible with backends)

        Raises:
            Exception: If collection fails (for graceful degradation tracking)
        """
        logger.info("thenewsapi_collection_start", topic=topic)

        # Build search query
        search_query = topic
        if keywords and len(keywords) > 0:
            # Add top keywords to query
            kw_text = ", ".join(
                str(kw) if not isinstance(kw, dict) else kw.get('keyword', str(kw))
                for kw in keywords[:2]
            )
            search_query = f"{topic} {kw_text}"

        # Determine categories from vertical
        categories = []
        vertical = config.get('vertical', '').lower()
        if 'tech' in vertical or 'saas' in vertical:
            categories = ['tech', 'business']
        elif 'proptech' in vertical:
            categories = ['tech', 'business']

        # Calculate date range (last 7 days for freshness)
        published_after = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        # Collect documents
        collector = self.collectors['thenewsapi']
        documents = await collector.collect(
            query=search_query,
            categories=categories if categories else None,
            published_after=published_after,
            limit=50
        )

        # Convert Documents to SearchResult format
        search_results = []
        for doc in documents:
            search_result = {
                'url': doc.source_url,
                'title': doc.title,
                'content': doc.content or doc.summary or "",
                'published_date': doc.published_at.isoformat() if doc.published_at else None,
                'backend': 'thenewsapi',
                'source': doc.source
            }
            search_results.append(search_result)

        logger.info("thenewsapi_collection_success", documents_count=len(search_results))
        return search_results

    def _build_depth_query(
        self,
        topic: str,
        config: Dict,
        keywords: Optional[List[str]] = None
    ) -> str:
        """
        Build query for DEPTH horizon (academic/authoritative sources)

        Args:
            topic: Base topic
            config: Research config
            keywords: Optional keywords

        Returns:
            Query emphasizing depth and authority
        """
        parts = [topic]

        # Add authoritative context
        if config.get('vertical'):
            parts.append(f"{config['vertical']} research")
        if config.get('domain'):
            parts.append(f"{config['domain']} industry analysis")

        # Add keywords for precision
        if keywords and len(keywords) > 0:
            kw_text = ", ".join(str(kw) if not isinstance(kw, dict) else kw.get('keyword', str(kw)) for kw in keywords[:2])
            parts.append(f"focusing on: {kw_text}")

        return " ".join(parts)[:300]  # Limit to 300 chars

    def _build_breadth_query(
        self,
        topic: str,
        config: Dict,
        competitor_gaps: Optional[List[str]] = None
    ) -> str:
        """
        Build query for BREADTH horizon (recent content, diverse perspectives)

        Args:
            topic: Base topic
            config: Research config
            competitor_gaps: Optional content gaps

        Returns:
            Query emphasizing breadth and recency
        """
        parts = [topic, "recent developments"]

        if config.get('market'):
            parts.append(f"in {config['market']}")

        # Add competitor gaps for unique angles
        if competitor_gaps and len(competitor_gaps) > 0:
            gap_text = str(competitor_gaps[0]) if not isinstance(competitor_gaps[0], dict) else competitor_gaps[0].get('gap', str(competitor_gaps[0]))
            parts.append(f"covering: {gap_text[:80]}")

        return " ".join(parts)[:300]

    def _build_trends_query(
        self,
        topic: str,
        config: Dict
    ) -> str:
        """
        Build query for TRENDS horizon (emerging patterns, predictions)

        Args:
            topic: Base topic
            config: Research config

        Returns:
            Query emphasizing trends and future outlook
        """
        parts = [topic, "trends", "emerging developments", "future outlook"]

        if config.get('domain'):
            parts.append(f"in {config['domain']}")

        if config.get('vertical'):
            parts.append(config['vertical'])

        return " ".join(parts)[:300]

    def _reciprocal_rank_fusion(
        self,
        sources: List[SearchResult],
        k: int = 60
    ) -> List[SearchResult]:
        """
        Merge ranked lists using Reciprocal Rank Fusion (RRF) algorithm

        RRF is a data fusion method that combines ranked lists from multiple
        sources by assigning scores based on ranks. URLs appearing in multiple
        sources get boosted due to score accumulation.

        Formula: RRF_score(url) = Σ(1 / (k + rank))
        where k=60 is the standard RRF constant

        Args:
            sources: List of search results from all sources (in rank order per source)
            k: RRF constant (default: 60, standard value)

        Returns:
            Merged list sorted by RRF score (highest first)

        Reference:
            Cormack et al. (2009) - "Reciprocal Rank Fusion outperforms the best
            known automatic runs on the TREC-2009 Web Track"
        """
        # Group sources by backend to preserve rank order
        sources_by_backend = {}
        for source in sources:
            backend = source.get('backend', 'unknown')
            if backend not in sources_by_backend:
                sources_by_backend[backend] = []
            sources_by_backend[backend].append(source)

        # Calculate RRF scores for each URL
        rrf_scores = {}  # url -> accumulated RRF score
        url_metadata = {}  # url -> source metadata (first occurrence)

        for backend, backend_sources in sources_by_backend.items():
            for rank, source in enumerate(backend_sources, start=1):
                url = source.get('url', '')
                if not url:
                    continue

                # Calculate RRF score: 1 / (k + rank)
                score = 1.0 / (k + rank)

                # Accumulate scores for URLs appearing in multiple sources
                if url in rrf_scores:
                    rrf_scores[url] += score
                else:
                    rrf_scores[url] = score
                    # Store metadata from first occurrence
                    url_metadata[url] = source

        # Sort URLs by RRF score (descending)
        sorted_urls = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Build result list with RRF scores
        merged_sources = []
        for url, score in sorted_urls:
            source = url_metadata[url].copy()
            source['rrf_score'] = score
            merged_sources.append(source)

        logger.info(
            "rrf_fusion_complete",
            input_count=len(sources),
            unique_urls=len(merged_sources),
            top_score=merged_sources[0]['rrf_score'] if merged_sources else 0
        )

        return merged_sources

    def _minhash_deduplicate(
        self,
        sources: List[SearchResult],
        similarity_threshold: float = 0.8,
        num_perm: int = 128
    ) -> List[SearchResult]:
        """
        Deduplicate sources using MinHash LSH for near-duplicate detection

        MinHash LSH detects near-duplicate content by:
        1. Creating MinHash signatures for each content
        2. Using LSH to efficiently find similar signatures
        3. Removing duplicates above similarity threshold

        Args:
            sources: List of search results (must have 'content' field)
            similarity_threshold: Jaccard similarity threshold (0-1, default: 0.8)
            num_perm: Number of permutations for MinHash (default: 128)

        Returns:
            Deduplicated list with first occurrence preserved

        Reference:
            Broder (1997) - "On the resemblance and containment of documents"
        """
        if not sources:
            return []

        if len(sources) == 1:
            return sources

        # Initialize LSH index
        lsh = MinHashLSH(threshold=similarity_threshold, num_perm=num_perm)

        # Track which sources to keep
        unique_sources = []
        duplicate_count = 0

        for idx, source in enumerate(sources):
            content = source.get('content', '')
            url = source.get('url', '')

            # Skip sources without content
            if not content or len(content.strip()) == 0:
                logger.debug("minhash_skip_no_content", url=url)
                continue

            # Create MinHash signature for content
            minhash = MinHash(num_perm=num_perm)

            # Tokenize content into shingles (3-grams of words)
            words = content.lower().split()
            shingles = [' '.join(words[i:i+3]) for i in range(len(words) - 2)]

            # Add shingles to MinHash
            for shingle in shingles:
                minhash.update(shingle.encode('utf-8'))

            # Query LSH to check for near-duplicates
            key = f"source_{idx}"
            duplicates = lsh.query(minhash)

            if duplicates:
                # Near-duplicate found, skip this source
                duplicate_count += 1
                logger.debug(
                    "minhash_duplicate_detected",
                    url=url,
                    similar_to=len(duplicates)
                )
                continue

            # No duplicates, add to index and keep source
            lsh.insert(key, minhash)
            unique_sources.append(source)

        logger.info(
            "minhash_deduplication_complete",
            input_count=len(sources),
            output_count=len(unique_sources),
            duplicates_removed=duplicate_count,
            threshold=similarity_threshold
        )

        return unique_sources

    def _merge_with_diversity(self, sources: List[SearchResult]) -> List[SearchResult]:
        """
        Merge sources with RRF fusion and MinHash deduplication

        Pipeline:
        1. RRF Fusion - Merge ranked lists from 5 sources, boost multi-source URLs
        2. MinHash Dedup - Remove near-duplicate content (>80% similar)

        Args:
            sources: List of search results from all sources (backends + collectors)

        Returns:
            Deduplicated list of sources sorted by RRF score, with near-duplicates removed
        """
        # Step 1: Apply Reciprocal Rank Fusion to merge and rank sources
        # This boosts URLs appearing in multiple sources and creates unified ranking
        rrf_merged = self._reciprocal_rank_fusion(sources)

        # Step 2: Apply MinHash deduplication to remove near-duplicate content
        # This catches same content on different URLs (scraper sites, syndicated content)
        final_sources = self._minhash_deduplicate(
            rrf_merged,
            similarity_threshold=0.8  # Remove content >80% similar
        )

        logger.info(
            "sources_merged_and_deduplicated",
            raw_count=len(sources),
            after_rrf=len(rrf_merged),
            after_minhash=len(final_sources),
            duplicates_removed=len(rrf_merged) - len(final_sources)
        )

        return final_sources

    def _calculate_quality_score(
        self,
        sources_count: int,
        successful_backends: List[str],
        failed_backends: List[str]
    ) -> int:
        """
        Calculate research quality score (0-100)

        Args:
            sources_count: Number of unique sources found
            successful_backends: List of successful backend names
            failed_backends: List of failed backend names

        Returns:
            Quality score (0-100)
        """
        score = 0

        # Sources component (max 50 points)
        # 20+ sources = 50 points, linear scale
        sources_score = min(50, (sources_count / 20) * 50)
        score += sources_score

        # Backend health component (max 30 points)
        # All backends = 30, 2/3 = 20, 1/3 = 10
        total_backends = len(successful_backends) + len(failed_backends)
        backend_score = (len(successful_backends) / total_backends) * 30
        score += backend_score

        # Diversity component (max 20 points)
        # Multiple backends = better diversity
        if len(successful_backends) >= 3:
            diversity_score = 20
        elif len(successful_backends) == 2:
            diversity_score = 13
        else:
            diversity_score = 7
        score += diversity_score

        return int(score)

    async def get_backend_health(self) -> Dict[str, BackendHealth]:
        """
        Check health of all backends

        Returns:
            Dictionary mapping backend names to BackendHealth status
        """
        health_checks = {}

        for name, backend in self.backends.items():
            try:
                health = await backend.health_check()
                health_checks[name] = health
            except Exception as e:
                logger.error("health_check_failed", backend=name, error=str(e))
                health_checks[name] = BackendHealth.FAILED

        return health_checks

    def get_backend_statistics(self) -> Dict:
        """
        Get backend performance statistics

        Returns:
            Dictionary with backend stats and overall metrics
        """
        return {
            'backend_stats': self.backend_stats,
            'overall': {
                'total_research': self.total_research,
                'failed_research': self.failed_research,
                'total_sources_found': self.total_sources_found,
                'success_rate': (
                    (self.total_research - self.failed_research) / self.total_research
                    if self.total_research > 0
                    else 0.0
                )
            }
        }

    def reset_statistics(self) -> None:
        """Reset all statistics to zero"""
        self.total_research = 0
        self.failed_research = 0
        self.total_sources_found = 0

        # Reset all source statistics (backends + collectors)
        for source_name in self.backend_stats:
            self.backend_stats[source_name] = {
                'success': 0,
                'failed': 0,
                'total_sources': 0
            }

        logger.info("statistics_reset")

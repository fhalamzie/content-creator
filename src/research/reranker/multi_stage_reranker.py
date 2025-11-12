"""
Multi-Stage Cascaded Reranker for SEO-optimized content sources

3-stage pipeline:
1. BM25 Lexical Filter - Fast CPU-based relevance filtering
2. Voyage Lite - Semantic reranking with lightweight model
3. Voyage Full + Custom Metrics - Deep semantic + 6 SEO metrics

Metrics (Stage 3):
- Relevance (30%): Voyage API cross-encoder score
- Novelty (25%): MMR + MinHash distance from selected sources
- Authority (20%): Domain trust (.edu/.gov) + E-E-A-T signals
- Freshness (15%): Recency scoring with exponential decay (QDF)
- Diversity (5%): Root-domain bucketing (max 2 per domain)
- Locality (5%): Market/language matching

Example:
    from src.research.reranker.multi_stage_reranker import MultiStageReranker
    from src.utils.config_loader import ConfigLoader

    reranker = MultiStageReranker(voyage_api_key="your_key")

    # Load Pydantic config
    loader = ConfigLoader()
    config = loader.load("proptech_de")

    # Rerank sources from 5-source orchestrator
    reranked = await reranker.rerank(
        sources=search_results,
        query="PropTech AI trends",
        config=config
    )

    # Top 25 SEO-optimized sources
    print(f"Top source: {reranked[0]['url']} (score: {reranked[0]['final_score']:.3f})")
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse
import math

from rank_bm25 import BM25Okapi
from datasketch import MinHash

from src.utils.logger import get_logger
from src.utils.config_loader import FullConfig

logger = get_logger(__name__)


class RerankingError(Exception):
    """Raised when reranking fails"""
    pass


class MultiStageReranker:
    """
    3-stage cascaded reranker for SEO-optimized source ranking

    Features:
    - Stage 1: BM25 lexical filter (CPU, ~2ms, filters 60 → 30-40)
    - Stage 2: Voyage Lite semantic reranking ($0.02/1M tokens, ~150ms)
    - Stage 3: Voyage Full + 6 metrics ($0.05/1M, ~300ms, final top 25)
    - Graceful fallback to BM25 if Voyage API unavailable
    - Cost: ~$0.02/topic (within FREE 200M Voyage tier)
    """

    # Metric weights (must sum to 1.0)
    WEIGHTS = {
        'relevance': 0.30,   # Voyage cross-encoder score
        'novelty': 0.25,     # MMR + MinHash distance
        'authority': 0.20,   # Domain trust + E-E-A-T
        'freshness': 0.15,   # Recency with exponential decay
        'diversity': 0.05,   # Root-domain bucketing
        'locality': 0.05     # Market/language matching
    }

    # Trusted domain TLDs for authority scoring
    TRUSTED_TLDS = {'.edu', '.gov', '.org', '.ac.uk', '.gov.uk'}

    # Freshness decay parameters (Query Deserves Freshness)
    FRESHNESS_HALF_LIFE_DAYS = 30  # Score halves every 30 days

    def __init__(
        self,
        voyage_api_key: Optional[str] = None,
        enable_voyage: bool = True,
        stage1_threshold: float = 0.0,
        stage2_threshold: float = 0.3,
        stage3_final_count: int = 25
    ):
        """
        Initialize multi-stage reranker

        Args:
            voyage_api_key: Voyage AI API key (auto-loads from env if None)
            enable_voyage: Enable Voyage API (default: True, fallback to BM25 if False)
            stage1_threshold: Minimum BM25 score to pass Stage 1 (default: 0.0 = keep all)
            stage2_threshold: Minimum Voyage Lite score to pass Stage 2 (default: 0.3)
            stage3_final_count: Number of final sources after Stage 3 (default: 25)
        """
        self.enable_voyage = enable_voyage
        self.stage1_threshold = stage1_threshold
        self.stage2_threshold = stage2_threshold
        self.stage3_final_count = stage3_final_count

        # Initialize Voyage client if enabled
        self.voyage_client = None
        if enable_voyage:
            try:
                import voyageai

                api_key = voyage_api_key or os.getenv('VOYAGE_API_KEY')
                if api_key:
                    self.voyage_client = voyageai.Client(api_key=api_key)
                    logger.info("voyage_client_initialized", enable_voyage=True)
                else:
                    logger.warning("voyage_api_key_missing", fallback="BM25_only")
                    self.enable_voyage = False
            except ImportError:
                logger.warning("voyageai_not_installed", fallback="BM25_only")
                self.enable_voyage = False

        # Statistics
        self.total_reranks = 0
        self.stage1_filtered = 0
        self.stage2_filtered = 0
        self.stage3_filtered = 0

    async def rerank(
        self,
        sources: List[Dict],
        query: str,
        config
    ) -> List[Dict]:
        """
        Rerank sources using 3-stage pipeline

        Args:
            sources: List of search results from orchestrator (with RRF/MinHash already applied)
            query: Research query
            config: Market configuration (FullConfig Pydantic model or dict)

        Returns:
            Reranked list of sources (top 25) sorted by final_score descending

        Raises:
            RerankingError: If reranking fails
        """
        if not sources:
            return []

        if not query or len(query.strip()) == 0:
            logger.warning("empty_query_reranking", sources_count=len(sources))
            return sources[:self.stage3_final_count]

        self.total_reranks += 1

        try:
            logger.info(
                "reranking_started",
                sources_count=len(sources),
                query=query[:100],
                enable_voyage=self.enable_voyage
            )

            # Stage 1: BM25 Lexical Filter (CPU-based, fast)
            stage1_results = self._stage1_bm25_filter(sources, query)
            self.stage1_filtered += len(sources) - len(stage1_results)

            logger.info(
                "stage1_complete",
                input_count=len(sources),
                output_count=len(stage1_results),
                filtered=len(sources) - len(stage1_results)
            )

            if len(stage1_results) == 0:
                logger.warning("stage1_no_results", returning_original=True)
                return sources[:self.stage3_final_count]

            # Stage 2: Voyage Lite Semantic Reranking (API)
            stage2_results = await self._stage2_voyage_lite(stage1_results, query)
            self.stage2_filtered += len(stage1_results) - len(stage2_results)

            logger.info(
                "stage2_complete",
                input_count=len(stage1_results),
                output_count=len(stage2_results),
                filtered=len(stage1_results) - len(stage2_results)
            )

            if len(stage2_results) == 0:
                logger.warning("stage2_no_results", returning_stage1=True)
                return stage1_results[:self.stage3_final_count]

            # Stage 3: Voyage Full + 6 Custom SEO Metrics (API + CPU)
            stage3_results = await self._stage3_voyage_full_metrics(
                stage2_results,
                query,
                config
            )
            self.stage3_filtered += len(stage2_results) - len(stage3_results)

            logger.info(
                "stage3_complete",
                input_count=len(stage2_results),
                output_count=len(stage3_results),
                final_count=len(stage3_results)
            )

            # Final results (top 25 by final_score)
            final_results = stage3_results[:self.stage3_final_count]

            logger.info(
                "reranking_complete",
                original_count=len(sources),
                final_count=len(final_results),
                top_score=final_results[0]['final_score'] if final_results else 0
            )

            return final_results

        except Exception as e:
            logger.error("reranking_failed", error=str(e))
            raise RerankingError(f"Reranking failed: {e}")

    def _stage1_bm25_filter(
        self,
        sources: List[Dict],
        query: str
    ) -> List[Dict]:
        """
        Stage 1: BM25 lexical filter

        Fast CPU-based relevance scoring using BM25 algorithm.
        Filters out sources below threshold.

        Args:
            sources: List of search results
            query: Research query

        Returns:
            Filtered sources with bm25_score added, sorted by BM25 score descending
        """
        if not sources:
            return []

        # Extract content for BM25 indexing
        corpus = []
        for source in sources:
            content = source.get('content', '')
            title = source.get('title', '')
            # Combine title (3x weight) + content for better relevance
            text = f"{title} {title} {title} {content}"
            corpus.append(text.lower())

        # Tokenize corpus
        tokenized_corpus = [doc.split() for doc in corpus]

        # Build BM25 index
        bm25 = BM25Okapi(tokenized_corpus)

        # Score query against corpus
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)

        # Add BM25 scores to sources
        sources_with_scores = []
        for idx, source in enumerate(sources):
            source_copy = source.copy()
            source_copy['bm25_score'] = float(scores[idx])
            sources_with_scores.append(source_copy)

        # Filter by threshold
        filtered_sources = [
            s for s in sources_with_scores
            if s['bm25_score'] >= self.stage1_threshold
        ]

        # Sort by BM25 score descending
        filtered_sources.sort(key=lambda x: x['bm25_score'], reverse=True)

        logger.debug(
            "stage1_bm25_scoring",
            sources_count=len(sources),
            filtered_count=len(filtered_sources),
            threshold=self.stage1_threshold,
            top_score=filtered_sources[0]['bm25_score'] if filtered_sources else 0
        )

        return filtered_sources

    async def _stage2_voyage_lite(
        self,
        sources: List[Dict],
        query: str
    ) -> List[Dict]:
        """
        Stage 2: Voyage Lite semantic reranking

        Uses Voyage AI rerank-lite-1 model for semantic relevance.
        Fallback to BM25 ranking if API unavailable.

        Args:
            sources: Filtered sources from Stage 1
            query: Research query

        Returns:
            Reranked sources with voyage_lite_score, filtered by threshold
        """
        if not sources:
            return []

        # Fallback to BM25 if Voyage disabled
        if not self.enable_voyage or not self.voyage_client:
            logger.info("stage2_skipped", reason="voyage_disabled", using="BM25_ranking")
            return sources  # Already sorted by BM25

        try:
            # Prepare documents for Voyage API
            documents = [
                f"{s.get('title', '')} {s.get('content', '')}"[:1000]  # Limit to 1000 chars
                for s in sources
            ]

            # Call Voyage Lite API
            rerank_response = self.voyage_client.rerank(
                query=query,
                documents=documents,
                model='rerank-lite-1',
                top_k=len(sources)  # Return all, filter by threshold
            )

            # Build reranked results
            reranked_sources = []
            for result in rerank_response.results:
                source = sources[result.index].copy()
                source['voyage_lite_score'] = float(result.relevance_score)

                # Filter by threshold
                if source['voyage_lite_score'] >= self.stage2_threshold:
                    reranked_sources.append(source)

            logger.info(
                "stage2_voyage_lite_success",
                input_count=len(sources),
                output_count=len(reranked_sources),
                threshold=self.stage2_threshold
            )

            return reranked_sources

        except Exception as e:
            logger.warning(
                "stage2_voyage_lite_failed",
                error=str(e),
                fallback="BM25_ranking"
            )
            # Fallback to BM25 ranking from Stage 1
            return sources

    async def _stage3_voyage_full_metrics(
        self,
        sources: List[Dict],
        query: str,
        config
    ) -> List[Dict]:
        """
        Stage 3: Voyage Full + 6 custom SEO metrics

        Uses Voyage AI rerank-2 (full model) + custom SEO scoring.
        Combines:
        - Relevance (30%): Voyage cross-encoder
        - Novelty (25%): MMR + MinHash
        - Authority (20%): Domain trust + E-E-A-T
        - Freshness (15%): QDF decay
        - Diversity (5%): Domain bucketing
        - Locality (5%): Market matching

        Args:
            sources: Filtered sources from Stage 2
            query: Research query
            config: Market configuration (FullConfig Pydantic model or dict)

        Returns:
            Final ranked sources with all metrics + final_score
        """
        if not sources:
            return []

        # Get Voyage Full scores (if enabled)
        voyage_full_scores = {}
        if self.enable_voyage and self.voyage_client:
            try:
                documents = [
                    f"{s.get('title', '')} {s.get('content', '')}"[:1000]
                    for s in sources
                ]

                rerank_response = self.voyage_client.rerank(
                    query=query,
                    documents=documents,
                    model='rerank-2',  # Full model
                    top_k=len(sources)
                )

                for result in rerank_response.results:
                    voyage_full_scores[result.index] = float(result.relevance_score)

                logger.info("stage3_voyage_full_success", sources_count=len(sources))

            except Exception as e:
                logger.warning("stage3_voyage_full_failed", error=str(e), using_bm25=True)

        # Calculate final scores with all metrics
        final_sources = []
        selected_sources = []  # For novelty/diversity calculations

        for idx, source in enumerate(sources):
            source_copy = source.copy()

            # Get Voyage Full score (or fallback to Voyage Lite or BM25)
            relevance_score = voyage_full_scores.get(idx)
            if relevance_score is None:
                # Fallback to Voyage Lite or BM25
                relevance_score = source.get('voyage_lite_score', source.get('bm25_score', 0.5))
                relevance_score = min(1.0, relevance_score)  # Normalize to [0,1]

            source_copy['voyage_full_score'] = relevance_score

            # Calculate 6 custom metrics
            metrics = {
                'relevance': relevance_score,
                'novelty': self._calculate_novelty(source_copy, selected_sources),
                'authority': self._calculate_authority(source_copy),
                'freshness': self._calculate_freshness(source_copy),
                'diversity': self._calculate_diversity(source_copy, selected_sources),
                'locality': self._calculate_locality(source_copy, config)
            }

            # Combine metrics with weights
            final_score = sum(
                metrics[metric] * self.WEIGHTS[metric]
                for metric in self.WEIGHTS
            )

            source_copy['metrics'] = metrics
            source_copy['final_score'] = final_score

            final_sources.append(source_copy)
            selected_sources.append(source_copy)

        # Sort by final_score descending
        final_sources.sort(key=lambda x: x['final_score'], reverse=True)

        # Limit to final count
        final_sources = final_sources[:self.stage3_final_count]

        logger.info(
            "stage3_metrics_calculated",
            sources_count=len(final_sources),
            top_score=final_sources[0]['final_score'] if final_sources else 0
        )

        return final_sources

    def _calculate_novelty(
        self,
        candidate: Dict,
        selected_sources: List[Dict]
    ) -> float:
        """
        Calculate Novelty metric using MMR (Maximal Marginal Relevance)

        Measures content diversity using MinHash similarity.
        Lower similarity to already-selected sources = higher novelty.

        Args:
            candidate: Source to evaluate
            selected_sources: Already-selected sources

        Returns:
            Novelty score [0,1] (1 = completely novel, 0 = duplicate)
        """
        if not selected_sources:
            return 1.0  # First source is always novel

        # Create MinHash for candidate
        candidate_content = candidate.get('content', '')
        if not candidate_content:
            return 0.5  # Neutral score for missing content

        candidate_minhash = MinHash(num_perm=128)
        words = candidate_content.lower().split()
        shingles = [' '.join(words[i:i+3]) for i in range(len(words) - 2)]
        for shingle in shingles:
            candidate_minhash.update(shingle.encode('utf-8'))

        # Calculate max similarity to selected sources
        max_similarity = 0.0
        for selected in selected_sources:
            selected_content = selected.get('content', '')
            if not selected_content:
                continue

            selected_minhash = MinHash(num_perm=128)
            words = selected_content.lower().split()
            shingles = [' '.join(words[i:i+3]) for i in range(len(words) - 2)]
            for shingle in shingles:
                selected_minhash.update(shingle.encode('utf-8'))

            similarity = candidate_minhash.jaccard(selected_minhash)
            max_similarity = max(max_similarity, similarity)

        # Novelty = 1 - max_similarity
        novelty = 1.0 - max_similarity
        return max(0.0, min(1.0, novelty))

    def _calculate_authority(self, source: Dict) -> float:
        """
        Calculate Authority metric with E-E-A-T signals

        Evaluates:
        - Domain trust (.edu, .gov, .org)
        - HTTPS (security)
        - Domain length (shorter = more established)

        Args:
            source: Source to evaluate

        Returns:
            Authority score [0,1]
        """
        url = source.get('url', '')
        if not url:
            return 0.3  # Low default

        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        score = 0.0

        # Trusted TLD bonus (+0.5)
        for tld in self.TRUSTED_TLDS:
            if domain.endswith(tld):
                score += 0.5
                break

        # HTTPS bonus (+0.2)
        if parsed.scheme == 'https':
            score += 0.2

        # Domain length (shorter = more established)
        # Short domains (< 15 chars) get +0.3
        # Medium domains (15-30 chars) get +0.2
        # Long domains (> 30 chars) get +0.1
        if len(domain) < 15:
            score += 0.3
        elif len(domain) < 30:
            score += 0.2
        else:
            score += 0.1

        return min(1.0, score)

    def _calculate_freshness(self, source: Dict) -> float:
        """
        Calculate Freshness metric with QDF (Query Deserves Freshness) decay

        Uses exponential decay: score = exp(-age_days / half_life)

        Args:
            source: Source to evaluate

        Returns:
            Freshness score [0,1] (1 = published today, 0.5 = 30 days old)
        """
        published_date_str = source.get('published_date')
        if not published_date_str:
            return 0.5  # Neutral for missing date

        try:
            # Parse ISO format
            if isinstance(published_date_str, str):
                published_date = datetime.fromisoformat(published_date_str.replace('Z', '+00:00'))
            else:
                published_date = published_date_str

            # Calculate age in days
            age_days = (datetime.now(published_date.tzinfo or None) - published_date).days

            # Exponential decay: score = exp(-age / half_life)
            freshness = math.exp(-age_days / self.FRESHNESS_HALF_LIFE_DAYS)

            return max(0.0, min(1.0, freshness))

        except (ValueError, TypeError) as e:
            logger.debug("freshness_parse_error", error=str(e))
            return 0.5

    def _calculate_diversity(
        self,
        candidate: Dict,
        selected_sources: List[Dict]
    ) -> float:
        """
        Calculate Diversity metric with domain bucketing

        Limits max 2 sources per root domain.
        Penalizes 3rd+ source from same domain.

        Args:
            candidate: Source to evaluate
            selected_sources: Already-selected sources

        Returns:
            Diversity score [0,1] (1 = unique domain, 0 = 3rd+ from domain)
        """
        url = candidate.get('url', '')
        if not url:
            return 1.0

        parsed = urlparse(url)
        candidate_domain = parsed.netloc.lower()

        # Extract root domain (strip www.)
        if candidate_domain.startswith('www.'):
            candidate_domain = candidate_domain[4:]

        # Count occurrences of this domain in selected sources
        domain_count = 0
        for selected in selected_sources:
            selected_url = selected.get('url', '')
            if not selected_url:
                continue

            selected_parsed = urlparse(selected_url)
            selected_domain = selected_parsed.netloc.lower()
            if selected_domain.startswith('www.'):
                selected_domain = selected_domain[4:]

            if selected_domain == candidate_domain:
                domain_count += 1

        # Scoring:
        # 0-1 sources from domain: score = 1.0 (full diversity)
        # 2 sources from domain: score = 0.5 (reduced diversity)
        # 3+ sources from domain: score = 0.0 (no diversity)
        if domain_count == 0:
            return 1.0
        elif domain_count == 1:
            return 0.5
        else:
            return 0.0

    def _calculate_locality(self, source: Dict, config) -> float:
        """
        Calculate Locality metric for market/language matching

        Evaluates:
        - TLD matching market (.de for Germany)
        - Language matching (heuristic based on content)

        Args:
            source: Source to evaluate
            config: Market configuration (FullConfig Pydantic model or dict)

        Returns:
            Locality score [0,1]
        """
        url = source.get('url', '')

        # Extract market and language (handle both FullConfig and dict)
        if isinstance(config, dict):
            # Plain dict format
            market = str(config.get('market', 'USA')).lower()
            language = str(config.get('language', 'en')).lower()
        else:
            # FullConfig Pydantic model
            market = str(config.market.market).lower()
            language = str(config.market.language).lower()

        if not url:
            return 0.5  # Neutral

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        score = 0.5  # Base score

        # Market-specific TLD matching
        market_tlds = {
            'germany': '.de',
            'france': '.fr',
            'uk': '.co.uk',
            'spain': '.es',
            'italy': '.it'
        }

        if market in market_tlds:
            expected_tld = market_tlds[market]
            if domain.endswith(expected_tld):
                score += 0.5  # Perfect market match

        return min(1.0, score)

    def get_statistics(self) -> Dict:
        """Get reranker performance statistics"""
        return {
            'total_reranks': self.total_reranks,
            'stage1_filtered': self.stage1_filtered,
            'stage2_filtered': self.stage2_filtered,
            'stage3_filtered': self.stage3_filtered
        }

    def reset_statistics(self) -> None:
        """Reset all statistics"""
        self.total_reranks = 0
        self.stage1_filtered = 0
        self.stage2_filtered = 0
        self.stage3_filtered = 0
        logger.info("statistics_reset")

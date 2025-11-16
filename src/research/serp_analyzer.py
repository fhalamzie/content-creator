"""
SERP Analyzer

Analyzes Search Engine Results Pages (SERP) for content intelligence.
Uses DuckDuckGo for free, no-API-key search.

Features:
- Extract top 10 search results
- Domain authority estimation
- SERP position tracking
- Historical SERP comparison

Pattern: Service class with pure functions for analysis
"""

import re
from typing import List, Dict, Optional
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SERPResult:
    """Single SERP result"""
    position: int
    url: str
    title: str
    snippet: str
    domain: str


class SERPAnalyzer:
    """
    SERP Analysis for content intelligence

    Analyzes search engine results to understand:
    - Who ranks for a topic
    - What content format wins
    - Domain authority distribution
    - Content gaps and opportunities

    Uses DuckDuckGo for free, anonymous searches (no API key required).
    """

    def __init__(self):
        """Initialize SERP analyzer"""
        logger.info("serp_analyzer_initialized")

    def search(
        self,
        query: str,
        max_results: int = 10,
        region: str = "wt-wt"
    ) -> List[SERPResult]:
        """
        Search DuckDuckGo and extract top results.

        Args:
            query: Search query
            max_results: Maximum number of results (1-10, default: 10)
            region: Region code (default: "wt-wt" for worldwide)
                   Common regions: "de-de" (Germany), "us-en" (US), "uk-en" (UK)

        Returns:
            List of SERPResult objects, ordered by position

        Raises:
            ImportError: If duckduckgo-search library not installed
            ValueError: If search fails or returns no results

        Example:
            >>> analyzer = SERPAnalyzer()
            >>> results = analyzer.search("PropTech trends 2025")
            >>> print(f"Found {len(results)} results")
            >>> print(f"Top result: {results[0].title} ({results[0].domain})")
        """
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.error("duckduckgo_search_not_installed")
            raise ImportError(
                "duckduckgo-search library not installed. "
                "Install with: pip install duckduckgo-search"
            )

        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        if max_results < 1 or max_results > 10:
            raise ValueError("max_results must be between 1 and 10")

        logger.info(
            "searching_serp",
            query=query,
            max_results=max_results,
            region=region
        )

        try:
            # Search DuckDuckGo
            with DDGS() as ddgs:
                # text() returns iterator, convert to list
                raw_results = list(ddgs.text(
                    keywords=query,
                    region=region,
                    max_results=max_results
                ))

            if not raw_results:
                logger.warning("no_serp_results_found", query=query)
                raise ValueError(f"No SERP results found for query: {query}")

            # Parse results
            serp_results = []
            for i, result in enumerate(raw_results[:max_results], start=1):
                # Extract domain from URL
                domain = self._extract_domain(result.get("href", ""))

                serp_result = SERPResult(
                    position=i,
                    url=result.get("href", ""),
                    title=result.get("title", ""),
                    snippet=result.get("body", ""),
                    domain=domain
                )
                serp_results.append(serp_result)

            logger.info(
                "serp_search_completed",
                query=query,
                results_count=len(serp_results)
            )

            return serp_results

        except Exception as e:
            logger.error(
                "serp_search_failed",
                query=query,
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    def analyze_serp(
        self,
        results: List[SERPResult]
    ) -> Dict:
        """
        Analyze SERP results to extract insights.

        Args:
            results: List of SERP results

        Returns:
            Dict containing:
                - total_results: int
                - unique_domains: int
                - domain_distribution: Dict[str, List[int]]  # domain -> positions
                - top_3_domains: List[str]
                - domain_authority_estimate: Dict[str, str]  # domain -> "high"/"medium"/"low"
                - avg_title_length: float
                - avg_snippet_length: float

        Example:
            >>> results = analyzer.search("PropTech trends")
            >>> analysis = analyzer.analyze_serp(results)
            >>> print(f"Unique domains: {analysis['unique_domains']}")
            >>> print(f"Top 3: {', '.join(analysis['top_3_domains'])}")
        """
        if not results:
            logger.warning("analyze_serp_empty_results")
            return {
                "total_results": 0,
                "unique_domains": 0,
                "domain_distribution": {},
                "top_3_domains": [],
                "domain_authority_estimate": {},
                "avg_title_length": 0.0,
                "avg_snippet_length": 0.0
            }

        # Domain distribution (domain -> list of positions)
        domain_distribution = {}
        for result in results:
            if result.domain not in domain_distribution:
                domain_distribution[result.domain] = []
            domain_distribution[result.domain].append(result.position)

        # Top 3 domains
        top_3_domains = [r.domain for r in results[:3]]

        # Estimate domain authority based on TLD and position
        domain_authority_estimate = {}
        for domain in domain_distribution.keys():
            authority = self._estimate_domain_authority(
                domain,
                min(domain_distribution[domain])  # Best position for this domain
            )
            domain_authority_estimate[domain] = authority

        # Calculate averages
        avg_title_length = sum(len(r.title) for r in results) / len(results)
        avg_snippet_length = sum(len(r.snippet) for r in results) / len(results)

        analysis = {
            "total_results": len(results),
            "unique_domains": len(domain_distribution),
            "domain_distribution": domain_distribution,
            "top_3_domains": top_3_domains,
            "domain_authority_estimate": domain_authority_estimate,
            "avg_title_length": round(avg_title_length, 1),
            "avg_snippet_length": round(avg_snippet_length, 1)
        }

        logger.info(
            "serp_analysis_completed",
            total_results=analysis["total_results"],
            unique_domains=analysis["unique_domains"]
        )

        return analysis

    def compare_snapshots(
        self,
        old_results: List[SERPResult],
        new_results: List[SERPResult]
    ) -> Dict:
        """
        Compare two SERP snapshots to detect ranking changes.

        Args:
            old_results: Earlier SERP results
            new_results: More recent SERP results

        Returns:
            Dict containing:
                - new_entrants: List[str]  # URLs that entered top 10
                - dropouts: List[str]  # URLs that left top 10
                - position_changes: Dict[str, Dict]  # url -> {old_pos, new_pos, change}
                - stable_urls: List[str]  # URLs with no position change

        Example:
            >>> old = analyzer.search("PropTech trends", region="de-de")
            >>> # ... wait some time ...
            >>> new = analyzer.search("PropTech trends", region="de-de")
            >>> changes = analyzer.compare_snapshots(old, new)
            >>> print(f"New entrants: {len(changes['new_entrants'])}")
        """
        old_url_positions = {r.url: r.position for r in old_results}
        new_url_positions = {r.url: r.position for r in new_results}

        # New entrants (in new but not in old)
        new_entrants = [url for url in new_url_positions if url not in old_url_positions]

        # Dropouts (in old but not in new)
        dropouts = [url for url in old_url_positions if url not in new_url_positions]

        # Position changes (in both)
        position_changes = {}
        stable_urls = []

        for url in old_url_positions:
            if url in new_url_positions:
                old_pos = old_url_positions[url]
                new_pos = new_url_positions[url]
                change = old_pos - new_pos  # Positive = moved up, Negative = moved down

                if change != 0:
                    position_changes[url] = {
                        "old_position": old_pos,
                        "new_position": new_pos,
                        "change": change,
                        "direction": "up" if change > 0 else "down"
                    }
                else:
                    stable_urls.append(url)

        comparison = {
            "new_entrants": new_entrants,
            "dropouts": dropouts,
            "position_changes": position_changes,
            "stable_urls": stable_urls
        }

        logger.info(
            "serp_comparison_completed",
            new_entrants=len(new_entrants),
            dropouts=len(dropouts),
            position_changes=len(position_changes),
            stable=len(stable_urls)
        )

        return comparison

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain (e.g., "example.com")

        Example:
            >>> self._extract_domain("https://www.example.com/path?query=1")
            "example.com"
        """
        if not url:
            return ""

        try:
            parsed = urlparse(url)
            domain = parsed.netloc

            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]

            return domain
        except Exception as e:
            logger.warning("domain_extraction_failed", url=url, error=str(e))
            return ""

    def _estimate_domain_authority(self, domain: str, position: int) -> str:
        """
        Estimate domain authority based on TLD and SERP position.

        This is a rough heuristic, not actual domain authority metrics.

        Args:
            domain: Domain name
            position: SERP position (1-10)

        Returns:
            "high", "medium", or "low"

        Logic:
            - .gov, .edu, .org in top 3 = high
            - Major news sites (common patterns) = high
            - Position 1-3 = high
            - Position 4-7 = medium
            - Position 8-10 = low
        """
        domain_lower = domain.lower()

        # High authority TLDs
        high_authority_tlds = ['.gov', '.edu']
        if any(domain_lower.endswith(tld) for tld in high_authority_tlds):
            return "high"

        # Known high-authority news/tech domains
        high_authority_domains = [
            'nytimes.com', 'wsj.com', 'forbes.com', 'bloomberg.com',
            'techcrunch.com', 'wired.com', 'theverge.com', 'reuters.com',
            'bbc.com', 'cnn.com', 'theguardian.com', 'wikipedia.org'
        ]
        if any(domain_lower == d or domain_lower.endswith('.' + d) for d in high_authority_domains):
            return "high"

        # Position-based estimation
        if position <= 3:
            return "high"
        elif position <= 7:
            return "medium"
        else:
            return "low"

    def results_to_dict(self, results: List[SERPResult]) -> List[Dict]:
        """
        Convert SERPResult objects to dictionaries for database storage.

        Args:
            results: List of SERPResult objects

        Returns:
            List of dicts suitable for SQLiteManager.save_serp_results()

        Example:
            >>> results = analyzer.search("PropTech trends")
            >>> dicts = analyzer.results_to_dict(results)
            >>> db.save_serp_results("proptech-trends-2025", "PropTech trends", dicts)
        """
        return [
            {
                "position": r.position,
                "url": r.url,
                "title": r.title,
                "snippet": r.snippet,
                "domain": r.domain
            }
            for r in results
        ]

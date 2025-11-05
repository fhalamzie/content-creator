"""
Unit tests for Reciprocal Rank Fusion (RRF) algorithm

Tests the RRF implementation used to merge ranked lists from multiple search backends.
"""

import pytest
from src.research.deep_researcher_refactored import DeepResearcher


class TestReciprocalRankFusion:
    """Test RRF algorithm for merging ranked search results"""

    @pytest.fixture
    def researcher(self):
        """Create researcher with all backends disabled for testing"""
        return DeepResearcher(
            enable_tavily=False,
            enable_searxng=False,
            enable_gemini=False,
            enable_rss=False,
            enable_thenewsapi=False,
            _testing_mode=True  # Skip backend validation for unit testing
        )

    def test_rrf_single_source(self, researcher):
        """RRF with single source should preserve ranking"""
        sources = [
            {'url': 'https://example.com/1', 'backend': 'tavily', 'title': 'Result 1'},
            {'url': 'https://example.com/2', 'backend': 'tavily', 'title': 'Result 2'},
            {'url': 'https://example.com/3', 'backend': 'tavily', 'title': 'Result 3'}
        ]

        # RRF should preserve order when only one source
        result = researcher._reciprocal_rank_fusion(sources)

        assert len(result) == 3
        assert result[0]['url'] == 'https://example.com/1'
        assert result[1]['url'] == 'https://example.com/2'
        assert result[2]['url'] == 'https://example.com/3'

    def test_rrf_multiple_sources_no_overlap(self, researcher):
        """RRF with multiple sources and no URL overlap"""
        sources = [
            # Tavily results (ranked 1-3)
            {'url': 'https://tavily.com/1', 'backend': 'tavily', 'title': 'Tavily 1'},
            {'url': 'https://tavily.com/2', 'backend': 'tavily', 'title': 'Tavily 2'},
            {'url': 'https://tavily.com/3', 'backend': 'tavily', 'title': 'Tavily 3'},
            # SearXNG results (ranked 1-3)
            {'url': 'https://searxng.com/1', 'backend': 'searxng', 'title': 'SearXNG 1'},
            {'url': 'https://searxng.com/2', 'backend': 'searxng', 'title': 'SearXNG 2'},
            {'url': 'https://searxng.com/3', 'backend': 'searxng', 'title': 'SearXNG 3'},
        ]

        result = researcher._reciprocal_rank_fusion(sources)

        assert len(result) == 6

        # Top results should interleave from both sources
        # RRF score for rank 1: 1/(60+1) ≈ 0.016
        # RRF score for rank 2: 1/(60+2) ≈ 0.016
        urls = [r['url'] for r in result]
        assert 'https://tavily.com/1' in urls[:2]  # Top from tavily should be in top 2
        assert 'https://searxng.com/1' in urls[:2]  # Top from searxng should be in top 2

    def test_rrf_with_duplicate_urls(self, researcher):
        """RRF should boost URLs appearing in multiple sources"""
        sources = [
            # Tavily results
            {'url': 'https://example.com/article', 'backend': 'tavily', 'title': 'Article'},
            {'url': 'https://tavily.com/unique', 'backend': 'tavily', 'title': 'Unique 1'},
            # SearXNG results - same URL appears here
            {'url': 'https://example.com/article', 'backend': 'searxng', 'title': 'Article'},
            {'url': 'https://searxng.com/unique', 'backend': 'searxng', 'title': 'Unique 2'},
        ]

        result = researcher._reciprocal_rank_fusion(sources)

        # Duplicate URL should be merged and boosted to top
        assert len(result) == 3  # 4 sources, 1 duplicate = 3 unique
        assert result[0]['url'] == 'https://example.com/article'

        # Should accumulate RRF scores from both sources
        # Tavily rank 1: 1/(60+1) ≈ 0.0164
        # SearXNG rank 1: 1/(60+1) ≈ 0.0164
        # Total: ≈ 0.0328 (should be highest)

    def test_rrf_empty_list(self, researcher):
        """RRF with empty list returns empty list"""
        result = researcher._reciprocal_rank_fusion([])
        assert result == []

    def test_rrf_k_parameter(self, researcher):
        """RRF should use k=60 as standard (can be configured)"""
        # Standard RRF uses k=60
        sources = [
            {'url': 'https://example.com/1', 'backend': 'tavily', 'title': 'Result 1'},
            {'url': 'https://example.com/2', 'backend': 'tavily', 'title': 'Result 2'},
        ]

        result = researcher._reciprocal_rank_fusion(sources, k=60)

        # Rank 1: 1/(60+1) ≈ 0.0164
        # Rank 2: 1/(60+2) ≈ 0.0161
        assert len(result) == 2
        assert result[0]['url'] == 'https://example.com/1'
        assert result[0]['rrf_score'] > result[1]['rrf_score']

    def test_rrf_preserves_metadata(self, researcher):
        """RRF should preserve all source metadata"""
        sources = [
            {
                'url': 'https://example.com/article',
                'backend': 'tavily',
                'title': 'Great Article',
                'content': 'Content here...',
                'published_date': '2025-01-01',
                'source': 'Example News'
            }
        ]

        result = researcher._reciprocal_rank_fusion(sources)

        assert len(result) == 1
        assert result[0]['url'] == 'https://example.com/article'
        assert result[0]['title'] == 'Great Article'
        assert result[0]['content'] == 'Content here...'
        assert result[0]['published_date'] == '2025-01-01'
        assert result[0]['source'] == 'Example News'
        assert 'rrf_score' in result[0]

    def test_rrf_three_sources_overlap(self, researcher):
        """RRF with 3 sources and overlapping URLs"""
        sources = [
            # Tavily
            {'url': 'https://common.com', 'backend': 'tavily', 'title': 'Common'},
            {'url': 'https://tavily-only.com', 'backend': 'tavily', 'title': 'Tavily Only'},
            # SearXNG
            {'url': 'https://common.com', 'backend': 'searxng', 'title': 'Common'},
            {'url': 'https://searxng-only.com', 'backend': 'searxng', 'title': 'SearXNG Only'},
            # Gemini
            {'url': 'https://common.com', 'backend': 'gemini', 'title': 'Common'},
            {'url': 'https://gemini-only.com', 'backend': 'gemini', 'title': 'Gemini Only'},
        ]

        result = researcher._reciprocal_rank_fusion(sources)

        # Common URL appears 3 times, should be ranked first
        assert len(result) == 4  # 6 sources - 2 duplicates = 4 unique
        assert result[0]['url'] == 'https://common.com'

        # Verify RRF score accumulation
        # 3x rank 1: 3 * 1/(60+1) ≈ 0.0492
        assert result[0]['rrf_score'] > 0.04

    def test_rrf_five_sources_real_scenario(self, researcher):
        """RRF with all 5 sources (Tavily, SearXNG, Gemini, RSS, TheNewsAPI)"""
        sources = [
            # Tavily (10 results)
            {'url': 'https://tavily.com/1', 'backend': 'tavily', 'title': 'T1'},
            {'url': 'https://tavily.com/2', 'backend': 'tavily', 'title': 'T2'},
            {'url': 'https://common.com/article', 'backend': 'tavily', 'title': 'Common'},
            # SearXNG (30 results, showing first 3)
            {'url': 'https://searxng.com/1', 'backend': 'searxng', 'title': 'S1'},
            {'url': 'https://common.com/article', 'backend': 'searxng', 'title': 'Common'},
            {'url': 'https://searxng.com/2', 'backend': 'searxng', 'title': 'S2'},
            # Gemini (12 results, showing first 2)
            {'url': 'https://gemini.com/1', 'backend': 'gemini', 'title': 'G1'},
            {'url': 'https://common.com/article', 'backend': 'gemini', 'title': 'Common'},
            # RSS (varies, showing 2)
            {'url': 'https://rss-blog.com/post1', 'backend': 'rss', 'title': 'RSS1'},
            {'url': 'https://rss-blog.com/post2', 'backend': 'rss', 'title': 'RSS2'},
            # TheNewsAPI (varies, showing 2)
            {'url': 'https://news.com/breaking', 'backend': 'thenewsapi', 'title': 'News1'},
            {'url': 'https://common.com/article', 'backend': 'thenewsapi', 'title': 'Common'},
        ]

        result = researcher._reciprocal_rank_fusion(sources)

        # Common article appears in 4 sources (tavily rank 3, searxng rank 2, gemini rank 2, thenewsapi rank 2)
        # Should be boosted to top due to multiple sources
        assert len(result) == 9  # 12 sources - 3 duplicates = 9 unique

        # Common article should be at or near top
        urls = [r['url'] for r in result]
        assert 'https://common.com/article' in urls[:3]

    def test_rrf_handles_missing_url(self, researcher):
        """RRF should skip results with missing URL"""
        sources = [
            {'url': 'https://valid.com', 'backend': 'tavily', 'title': 'Valid'},
            {'backend': 'tavily', 'title': 'Missing URL'},  # No URL
            {'url': '', 'backend': 'tavily', 'title': 'Empty URL'},  # Empty URL
        ]

        result = researcher._reciprocal_rank_fusion(sources)

        assert len(result) == 1
        assert result[0]['url'] == 'https://valid.com'

    def test_rrf_different_rank_positions(self, researcher):
        """Test RRF scoring with URLs at different rank positions"""
        sources = [
            # Source 1: URL A at rank 1, URL B at rank 10
            {'url': 'https://a.com', 'backend': 'tavily', 'title': 'A'},
            {'url': 'https://filler1.com', 'backend': 'tavily', 'title': 'Filler'},
            {'url': 'https://filler2.com', 'backend': 'tavily', 'title': 'Filler'},
            {'url': 'https://filler3.com', 'backend': 'tavily', 'title': 'Filler'},
            {'url': 'https://filler4.com', 'backend': 'tavily', 'title': 'Filler'},
            {'url': 'https://filler5.com', 'backend': 'tavily', 'title': 'Filler'},
            {'url': 'https://filler6.com', 'backend': 'tavily', 'title': 'Filler'},
            {'url': 'https://filler7.com', 'backend': 'tavily', 'title': 'Filler'},
            {'url': 'https://filler8.com', 'backend': 'tavily', 'title': 'Filler'},
            {'url': 'https://b.com', 'backend': 'tavily', 'title': 'B'},
            # Source 2: URL B at rank 1
            {'url': 'https://b.com', 'backend': 'searxng', 'title': 'B'},
        ]

        result = researcher._reciprocal_rank_fusion(sources)

        # URL B appears at rank 10 in tavily (score: 1/70) and rank 1 in searxng (score: 1/61)
        # Combined score: 1/70 + 1/61 ≈ 0.0307
        # URL A appears only at rank 1 in tavily (score: 1/61 ≈ 0.0164)
        # URL B should rank higher than URL A

        urls = [r['url'] for r in result]
        b_index = urls.index('https://b.com')
        a_index = urls.index('https://a.com')

        assert b_index < a_index, "URL B should rank higher due to appearing in 2 sources"

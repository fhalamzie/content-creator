"""
Unit tests for MinHash-based content deduplication

Tests MinHash LSH for detecting near-duplicate content across different URLs.
"""

import pytest
from src.research.deep_researcher_refactored import DeepResearcher


class TestMinHashDeduplication:
    """Test MinHash LSH deduplication for near-duplicate content detection"""

    @pytest.fixture
    def researcher(self):
        """Create researcher with all backends disabled for testing"""
        return DeepResearcher(
            enable_tavily=False,
            enable_searxng=False,
            enable_gemini=False,
            enable_rss=False,
            enable_thenewsapi=False,
            _testing_mode=True
        )

    def test_minhash_identical_content(self, researcher):
        """Identical content should be detected as duplicates"""
        sources = [
            {
                'url': 'https://site1.com/article',
                'title': 'PropTech Trends',
                'content': 'The property technology sector is experiencing rapid growth with AI-powered solutions.',
                'backend': 'tavily'
            },
            {
                'url': 'https://site2.com/different',
                'title': 'PropTech Article',
                'content': 'The property technology sector is experiencing rapid growth with AI-powered solutions.',
                'backend': 'searxng'
            },
            {
                'url': 'https://site3.com/unique',
                'title': 'Unique Article',
                'content': 'Completely different content about blockchain and cryptocurrency technology.',
                'backend': 'gemini'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # Should remove one duplicate (keep first occurrence)
        assert len(result) == 2
        urls = [r['url'] for r in result]
        assert 'https://site1.com/article' in urls  # First occurrence kept
        assert 'https://site3.com/unique' in urls  # Unique content kept
        assert 'https://site2.com/different' not in urls  # Duplicate removed

    def test_minhash_near_duplicates(self, researcher):
        """Near-duplicate content with high similarity should be detected"""
        # MinHash works best with longer content (100+ words)
        # This test uses realistic article-length content
        base_article = (
            "Artificial intelligence is rapidly transforming the property technology sector. "
            "Real estate companies are increasingly adopting machine learning algorithms to automate "
            "property valuations and provide data-driven investment recommendations. The PropTech "
            "industry has experienced exponential growth over the past five years, with venture capital "
            "funding reaching record levels. Major players in the market are developing sophisticated "
            "platforms that combine computer vision for property inspections, natural language processing "
            "for document analysis, and predictive analytics for market forecasting. Virtual reality "
            "technology is enabling immersive property tours, while blockchain is streamlining "
            "transaction processes through smart contracts. IoT sensors are being deployed to monitor "
            "building conditions and optimize energy usage. Big data analytics platforms are helping "
            "property managers make informed decisions about maintenance and tenant management. "
        )

        sources = [
            {
                'url': 'https://blog1.com/post',
                'title': 'PropTech Revolution',
                'content': base_article + "These innovations are reshaping the real estate landscape.",
                'backend': 'tavily'
            },
            {
                'url': 'https://blog2.com/article',
                'title': 'Real Estate Tech',
                'content': base_article + "These advancements are transforming property markets globally.",  # 90%+ similar
                'backend': 'searxng'
            },
            {
                'url': 'https://blog3.com/different',
                'title': 'Blockchain Finance',
                'content': 'Cryptocurrency and decentralized finance are revolutionizing banking systems worldwide. Digital assets built on blockchain technology enable peer-to-peer transactions without intermediaries.',
                'backend': 'gemini'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # With substantial shared content, should detect near-duplicates
        assert len(result) <= 2, "Should deduplicate highly similar content"
        urls = [r['url'] for r in result]
        assert 'https://blog3.com/different' in urls, "Unique content should be preserved"

    def test_minhash_all_unique(self, researcher):
        """All unique content should be preserved"""
        sources = [
            {
                'url': 'https://a.com',
                'title': 'Article A',
                'content': 'PropTech startups are raising significant venture capital funding in 2025.',
                'backend': 'tavily'
            },
            {
                'url': 'https://b.com',
                'title': 'Article B',
                'content': 'Blockchain technology enables secure peer-to-peer cryptocurrency transactions.',
                'backend': 'searxng'
            },
            {
                'url': 'https://c.com',
                'title': 'Article C',
                'content': 'Machine learning models can predict customer churn with 90% accuracy.',
                'backend': 'gemini'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # All unique, nothing removed
        assert len(result) == 3
        assert {r['url'] for r in result} == {'https://a.com', 'https://b.com', 'https://c.com'}

    def test_minhash_empty_list(self, researcher):
        """Empty list returns empty list"""
        result = researcher._minhash_deduplicate([], similarity_threshold=0.8)
        assert result == []

    def test_minhash_single_item(self, researcher):
        """Single item should be preserved"""
        sources = [
            {
                'url': 'https://single.com',
                'title': 'Only Article',
                'content': 'Some unique content here.',
                'backend': 'tavily'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)
        assert len(result) == 1
        assert result[0]['url'] == 'https://single.com'

    def test_minhash_threshold_80(self, researcher):
        """Test 80% similarity threshold (default)"""
        # Use longer realistic content for reliable detection
        base_content = (
            "The quick brown fox jumps over the lazy dog in the forest. "
            "This ancient proverb has been used for centuries to test typewriters and fonts. "
            "It contains all letters of the English alphabet, making it ideal for pangram tests. "
            "Typography experts often use this sentence when designing new typefaces. "
        )

        sources = [
            {
                'url': 'https://original.com',
                'title': 'Original',
                'content': base_content + "The sentence remains popular today in the digital age.",
                'backend': 'tavily'
            },
            {
                'url': 'https://similar.com',
                'title': 'Similar',
                'content': base_content + "The phrase stays popular today in modern computing.",  # Near-duplicate
                'backend': 'searxng'
            },
            {
                'url': 'https://different.com',
                'title': 'Different',
                'content': 'Cryptocurrency blockchain decentralized finance smart contracts digital assets.',
                'backend': 'gemini'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # Original and similar are >80% similar
        assert len(result) == 2

    def test_minhash_threshold_95(self, researcher):
        """Test 95% similarity threshold (strict)"""
        sources = [
            {
                'url': 'https://original.com',
                'title': 'Original',
                'content': 'The quick brown fox jumps over the lazy dog in the forest.',
                'backend': 'tavily'
            },
            {
                'url': 'https://similar.com',
                'title': 'Similar',
                'content': 'The quick brown fox jumps over the lazy cat in the forest.',
                'backend': 'searxng'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.95)

        # With 95% threshold, small changes should not be flagged as duplicates
        assert len(result) == 2  # Both kept

    def test_minhash_preserves_metadata(self, researcher):
        """Deduplication should preserve all metadata"""
        sources = [
            {
                'url': 'https://example.com/article',
                'title': 'Great Article',
                'content': 'PropTech is revolutionizing real estate.',
                'published_date': '2025-01-01',
                'backend': 'tavily',
                'source': 'Example News',
                'rrf_score': 0.05
            },
            {
                'url': 'https://duplicate.com/copy',
                'title': 'Copy Article',
                'content': 'PropTech is revolutionizing real estate.',  # Duplicate
                'published_date': '2025-01-02',
                'backend': 'searxng',
                'source': 'Duplicate News'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # Should keep first occurrence with all metadata
        assert len(result) == 1
        assert result[0]['url'] == 'https://example.com/article'
        assert result[0]['title'] == 'Great Article'
        assert result[0]['published_date'] == '2025-01-01'
        assert result[0]['rrf_score'] == 0.05

    def test_minhash_handles_missing_content(self, researcher):
        """Should skip sources with missing content field"""
        sources = [
            {
                'url': 'https://valid.com',
                'title': 'Valid Article',
                'content': 'This has content.',
                'backend': 'tavily'
            },
            {
                'url': 'https://no-content.com',
                'title': 'Missing Content',
                # No content field
                'backend': 'searxng'
            },
            {
                'url': 'https://empty-content.com',
                'title': 'Empty Content',
                'content': '',  # Empty content
                'backend': 'gemini'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # Should only keep sources with valid content
        assert len(result) == 1
        assert result[0]['url'] == 'https://valid.com'

    def test_minhash_three_way_duplicates(self, researcher):
        """Handle 3 sources with same content"""
        sources = [
            {
                'url': 'https://source1.com',
                'title': 'Source 1',
                'content': 'PropTech market size reached $18 billion in 2024.',
                'backend': 'tavily'
            },
            {
                'url': 'https://source2.com',
                'title': 'Source 2',
                'content': 'PropTech market size reached $18 billion in 2024.',
                'backend': 'searxng'
            },
            {
                'url': 'https://source3.com',
                'title': 'Source 3',
                'content': 'PropTech market size reached $18 billion in 2024.',
                'backend': 'gemini'
            },
            {
                'url': 'https://unique.com',
                'title': 'Unique',
                'content': 'Completely different content about blockchain technology.',
                'backend': 'rss'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # Should keep first occurrence + unique
        assert len(result) == 2
        urls = [r['url'] for r in result]
        assert 'https://source1.com' in urls  # First kept
        assert 'https://unique.com' in urls

    def test_minhash_short_content(self, researcher):
        """Handle very short content (< 50 chars)"""
        sources = [
            {
                'url': 'https://short1.com',
                'title': 'Short 1',
                'content': 'PropTech trends.',  # Very short
                'backend': 'tavily'
            },
            {
                'url': 'https://short2.com',
                'title': 'Short 2',
                'content': 'PropTech trends.',  # Identical short content
                'backend': 'searxng'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # Should still detect duplicates even with short content
        assert len(result) == 1

    def test_minhash_mixed_languages(self, researcher):
        """Handle content in different languages"""
        sources = [
            {
                'url': 'https://en.com',
                'title': 'English',
                'content': 'PropTech is transforming real estate with artificial intelligence.',
                'backend': 'tavily'
            },
            {
                'url': 'https://de.com',
                'title': 'German',
                'content': 'PropTech transformiert Immobilien mit künstlicher Intelligenz.',
                'backend': 'searxng'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # Different languages should not be flagged as duplicates
        assert len(result) == 2

    def test_minhash_preserves_order(self, researcher):
        """Deduplication should preserve order of unique items"""
        sources = [
            {
                'url': 'https://first.com',
                'title': 'First',
                'content': 'PropTech startups are growing rapidly.',
                'backend': 'tavily'
            },
            {
                'url': 'https://second.com',
                'title': 'Second',
                'content': 'Blockchain enables decentralized finance.',
                'backend': 'searxng'
            },
            {
                'url': 'https://third.com',
                'title': 'Third',
                'content': 'Machine learning predicts customer behavior.',
                'backend': 'gemini'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # Order should be preserved
        assert len(result) == 3
        assert result[0]['url'] == 'https://first.com'
        assert result[1]['url'] == 'https://second.com'
        assert result[2]['url'] == 'https://third.com'

    def test_minhash_long_content(self, researcher):
        """Handle long content (>1000 chars)"""
        long_content_1 = (
            "PropTech, or property technology, is revolutionizing the real estate industry "
            "with innovative solutions. AI-powered valuation tools provide instant property "
            "assessments. Virtual reality enables immersive property tours. Blockchain "
            "streamlines transactions with smart contracts. IoT sensors monitor building "
            "conditions. Big data analytics optimize property management. Machine learning "
            "predicts market trends. Digital platforms connect buyers and sellers globally. "
        ) * 3  # ~600 chars * 3 = ~1800 chars

        long_content_2 = (
            "PropTech, or property technology, is revolutionizing the real estate industry "
            "with innovative solutions. AI-powered valuation tools provide instant property "
            "assessments. Virtual reality enables immersive property tours. Blockchain "
            "streamlines transactions with smart contracts. IoT sensors monitor building "
            "conditions. Big data analytics optimize property management. Machine learning "
            "predicts market trends. Digital platforms connect buyers and sellers globally. "
        ) * 3  # Identical

        sources = [
            {
                'url': 'https://long1.com',
                'title': 'Long Article 1',
                'content': long_content_1,
                'backend': 'tavily'
            },
            {
                'url': 'https://long2.com',
                'title': 'Long Article 2',
                'content': long_content_2,
                'backend': 'searxng'
            }
        ]

        result = researcher._minhash_deduplicate(sources, similarity_threshold=0.8)

        # Should detect duplicates even with long content
        assert len(result) == 1

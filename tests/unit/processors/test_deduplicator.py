"""
Tests for Deduplicator

Tests MinHash/LSH-based near-duplicate detection and canonical URL normalization.
"""

import pytest
from datetime import datetime
from src.processors.deduplicator import Deduplicator
from src.models.document import Document


class TestDeduplicatorInit:
    """Test deduplicator initialization"""

    def test_init_default_threshold(self):
        """Should initialize with default threshold of 0.7"""
        dedup = Deduplicator()
        assert dedup.threshold == 0.7

    def test_init_custom_threshold(self):
        """Should allow custom threshold"""
        dedup = Deduplicator(threshold=0.85)
        assert dedup.threshold == 0.85

    def test_init_creates_lsh_index(self):
        """Should create LSH index on initialization"""
        dedup = Deduplicator()
        assert dedup.lsh is not None


class TestDuplicateDetection:
    """Test duplicate detection functionality"""

    @pytest.fixture
    def dedup(self):
        """Create deduplicator for tests"""
        return Deduplicator(threshold=0.7)

    @pytest.fixture
    def sample_doc(self):
        """Create sample document"""
        return Document(
            id="doc_1",
            source="test",
            source_url="https://example.com/article-1",
            title="PropTech Trends in Germany",
            content="This is an article about proptech trends in Germany and how they are transforming the real estate industry.",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="test_hash_1",
            canonical_url="https://example.com/article-1",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

    def test_first_document_not_duplicate(self, dedup, sample_doc):
        """First document should not be marked as duplicate"""
        assert not dedup.is_duplicate(sample_doc)

    def test_exact_duplicate_detected(self, dedup, sample_doc):
        """Should detect exact duplicate content"""
        # Add first document
        dedup.add(sample_doc)

        # Create second document with same content
        doc2 = sample_doc.model_copy(deep=True)
        doc2.id = "doc_2"
        doc2.source_url = "https://different-domain.com/article"

        # Should be detected as duplicate
        assert dedup.is_duplicate(doc2)

    def test_near_duplicate_detected(self, dedup, sample_doc):
        """Should detect near-duplicate content (>70% similar)"""
        # Add first document
        dedup.add(sample_doc)

        # Create document with very similar content (80% same words)
        doc2 = sample_doc.model_copy(deep=True)
        doc2.id = "doc_2"
        doc2.content = "This is an article about proptech trends in Germany and their impact on real estate."

        # Should be detected as duplicate
        assert dedup.is_duplicate(doc2)

    def test_different_content_not_duplicate(self, dedup, sample_doc):
        """Should not detect completely different content as duplicate"""
        # Add first document
        dedup.add(sample_doc)

        # Create document with completely different content AND different URL
        doc2 = sample_doc.model_copy(deep=True)
        doc2.id = "doc_2"
        doc2.source_url = "https://different-site.com/article"
        doc2.canonical_url = "https://different-site.com/article"
        doc2.content = "Cloud computing security best practices for enterprise deployments."

        # Should NOT be detected as duplicate
        assert not dedup.is_duplicate(doc2)

    def test_add_document(self, dedup, sample_doc):
        """Should add document to LSH index"""
        dedup.add(sample_doc)

        # Now it should be detected as duplicate
        assert dedup.is_duplicate(sample_doc)

    def test_multiple_documents(self, dedup):
        """Should handle multiple documents correctly"""
        # Create 3 different documents
        doc1 = Document(
            id="doc_1", source="test", source_url="http://test1.com",
            title="Test 1", content="This is about AI and machine learning",
            language="en", domain="Tech", market="US", vertical="AI",
            content_hash="hash1", canonical_url="http://test1.com",
            published_at=datetime.now(), fetched_at=datetime.now()
        )
        doc2 = Document(
            id="doc_2", source="test", source_url="http://test2.com",
            title="Test 2", content="This is about cloud computing and infrastructure",
            language="en", domain="Tech", market="US", vertical="Cloud",
            content_hash="hash2", canonical_url="http://test2.com",
            published_at=datetime.now(), fetched_at=datetime.now()
        )
        doc3 = Document(
            id="doc_3", source="test", source_url="http://test3.com",
            title="Test 3", content="This is about AI and machine learning applications",  # Similar to doc1
            language="en", domain="Tech", market="US", vertical="AI",
            content_hash="hash3", canonical_url="http://test3.com",
            published_at=datetime.now(), fetched_at=datetime.now()
        )

        # Add first two
        dedup.add(doc1)
        dedup.add(doc2)

        # Check doc3 (similar to doc1)
        assert dedup.is_duplicate(doc3)


class TestCanonicalURLNormalization:
    """Test canonical URL normalization"""

    @pytest.fixture
    def dedup(self):
        """Create deduplicator for tests"""
        return Deduplicator()

    def test_normalize_url_removes_www(self, dedup):
        """Should remove www prefix"""
        url = "https://www.example.com/article"
        normalized = dedup.normalize_url(url)
        assert normalized == "https://example.com/article"

    def test_normalize_url_lowercase(self, dedup):
        """Should convert URL to lowercase"""
        url = "https://Example.COM/Article"
        normalized = dedup.normalize_url(url)
        assert normalized == "https://example.com/article"

    def test_normalize_url_removes_tracking_params(self, dedup):
        """Should remove common tracking parameters"""
        url = "https://example.com/article?utm_source=twitter&utm_medium=social&ref=homepage"
        normalized = dedup.normalize_url(url)
        assert "utm_source" not in normalized
        assert "utm_medium" not in normalized

    def test_normalize_url_keeps_important_params(self, dedup):
        """Should keep non-tracking parameters"""
        url = "https://example.com/article?id=123&page=2"
        normalized = dedup.normalize_url(url)
        assert "id=123" in normalized
        assert "page=2" in normalized

    def test_normalize_url_removes_trailing_slash(self, dedup):
        """Should remove trailing slash"""
        url = "https://example.com/article/"
        normalized = dedup.normalize_url(url)
        assert normalized == "https://example.com/article"

    def test_normalize_url_removes_fragment(self, dedup):
        """Should remove URL fragment (hash)"""
        url = "https://example.com/article#section-2"
        normalized = dedup.normalize_url(url)
        assert normalized == "https://example.com/article"

    def test_canonical_url_duplicate_detection(self, dedup):
        """Should detect duplicates by canonical URL"""
        doc1 = Document(
            id="doc_1", source="test",
            source_url="https://www.Example.com/article?utm_source=twitter",
            title="Test", content="Different content here",
            language="en", domain="Tech", market="US", vertical="AI",
            content_hash="hash1",
            canonical_url="https://example.com/article",  # Already normalized
            published_at=datetime.now(), fetched_at=datetime.now()
        )
        doc2 = Document(
            id="doc_2", source="test",
            source_url="https://example.com/article/?ref=homepage#top",  # Different URL params/fragments
            title="Test", content="Completely different content",
            language="en", domain="Tech", market="US", vertical="AI",
            content_hash="hash2",
            canonical_url="https://example.com/article",  # Same canonical URL
            published_at=datetime.now(), fetched_at=datetime.now()
        )

        # Should detect as duplicate by canonical URL even with different content
        assert dedup.is_canonical_duplicate(doc1, doc2)


class TestContentHashing:
    """Test content hashing functionality"""

    @pytest.fixture
    def dedup(self):
        """Create deduplicator for tests"""
        return Deduplicator()

    def test_compute_minhash_returns_hash(self, dedup):
        """Should compute MinHash for content"""
        content = "This is test content for hashing"
        minhash = dedup.compute_minhash(content)
        assert minhash is not None

    def test_same_content_same_hash(self, dedup):
        """Same content should produce same MinHash"""
        import numpy as np
        content = "This is test content"
        hash1 = dedup.compute_minhash(content)
        hash2 = dedup.compute_minhash(content)

        # MinHash should be deterministic (use numpy array comparison)
        assert np.array_equal(hash1.digest(), hash2.digest())

    def test_similar_content_similar_hash(self, dedup):
        """Similar content should have similar MinHash (high Jaccard similarity)"""
        content1 = "This is an article about machine learning and artificial intelligence"
        content2 = "This is an article about machine learning and AI systems"

        hash1 = dedup.compute_minhash(content1)
        hash2 = dedup.compute_minhash(content2)

        # Estimate Jaccard similarity
        similarity = hash1.jaccard(hash2)
        assert similarity > 0.5  # Should be somewhat similar

    def test_different_content_different_hash(self, dedup):
        """Different content should have different MinHash (low Jaccard similarity)"""
        content1 = "This is about machine learning"
        content2 = "Completely unrelated topic about cooking recipes"

        hash1 = dedup.compute_minhash(content1)
        hash2 = dedup.compute_minhash(content2)

        # Estimate Jaccard similarity
        similarity = hash1.jaccard(hash2)
        assert similarity < 0.3  # Should be dissimilar


class TestStatistics:
    """Test deduplication statistics tracking"""

    @pytest.fixture
    def dedup(self):
        """Create deduplicator for tests"""
        return Deduplicator()

    def test_get_stats_initial(self, dedup):
        """Should return initial statistics"""
        stats = dedup.get_stats()
        assert stats['total_documents'] == 0
        assert stats['duplicates_found'] == 0
        assert stats['deduplication_rate'] == 0.0

    def test_get_stats_after_additions(self, dedup):
        """Should track statistics correctly"""
        # Add 3 documents, check 1 duplicate
        doc1 = Document(
            id="doc_1", source="test", source_url="http://test1.com",
            title="Test", content="Content about AI",
            language="en", domain="Tech", market="US", vertical="AI",
            content_hash="hash1", canonical_url="http://test1.com",
            published_at=datetime.now(), fetched_at=datetime.now()
        )
        doc2 = Document(
            id="doc_2", source="test", source_url="http://test2.com",
            title="Test", content="Content about Cloud",
            language="en", domain="Tech", market="US", vertical="Cloud",
            content_hash="hash2", canonical_url="http://test2.com",
            published_at=datetime.now(), fetched_at=datetime.now()
        )
        doc3 = Document(
            id="doc_3", source="test", source_url="http://test3.com",
            title="Test", content="Content about AI systems",  # Similar to doc1
            language="en", domain="Tech", market="US", vertical="AI",
            content_hash="hash3", canonical_url="http://test3.com",
            published_at=datetime.now(), fetched_at=datetime.now()
        )

        # Only check/add what gets counted
        dedup.add(doc1)
        dedup.add(doc2)

        # Check if doc3 is duplicate (this counts as 1 document checked)
        is_dup = dedup.is_duplicate(doc3)
        if is_dup:
            dedup.mark_duplicate(doc3)

        stats = dedup.get_stats()
        assert stats['total_documents'] == 1  # Only doc3 was checked via is_duplicate()
        assert stats['duplicates_found'] >= 1  # doc3 should be duplicate
        assert stats['deduplication_rate'] > 0.0

    def test_reset_stats(self, dedup):
        """Should reset statistics"""
        doc = Document(
            id="doc_1", source="test", source_url="http://test1.com",
            title="Test", content="Content",
            language="en", domain="Tech", market="US", vertical="AI",
            content_hash="hash1", canonical_url="http://test1.com",
            published_at=datetime.now(), fetched_at=datetime.now()
        )
        dedup.add(doc)

        # Reset
        dedup.reset_stats()

        stats = dedup.get_stats()
        assert stats['total_documents'] == 0
        assert stats['duplicates_found'] == 0

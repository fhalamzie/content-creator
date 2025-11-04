"""
E2E Integration Tests for EntityExtractor

Tests entity extraction with real LLM API calls (OpenRouter).
Requires OPENROUTER_API_KEY environment variable.

Run with: pytest tests/unit/processors/test_entity_extractor_e2e.py -v -m "not skip_ci"
"""

import pytest
from datetime import datetime
import os

from src.processors.entity_extractor import EntityExtractor, EntityExtractionError
from src.models.document import Document


# Skip if no API key (CI environment)
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set"
)


@pytest.fixture
def german_document():
    """Create German PropTech document"""
    return Document(
        id="test_doc_de",
        source="test_source",
        source_url="https://example.com/proptech",
        title="PropTech-Trends 2025 in Deutschland",
        content="""
        Die PropTech-Branche in Deutschland boomt. Unternehmen wie PropStack und
        Immobilienscout24 revolutionieren den Immobilienmarkt mit KI und IoT-Technologien.
        In Berlin entstehen täglich neue Start-ups, die Smart Building-Lösungen anbieten.
        Die DSGVO-konformen Systeme ermöglichen effiziente Verwaltung von Mietobjekten.
        Investoren aus München und Hamburg investieren Millionen in PropTech-Innovationen.
        """,
        language="de",
        domain="SaaS",
        market="Germany",
        vertical="Proptech",
        content_hash="hash_de",
        canonical_url="https://example.com/proptech",
        published_at=datetime.now(),
        fetched_at=datetime.now()
    )


@pytest.fixture
def english_document():
    """Create English Tech document"""
    return Document(
        id="test_doc_en",
        source="test_source",
        source_url="https://example.com/ai",
        title="AI Revolution in 2025",
        content="""
        Artificial intelligence is transforming industries worldwide. Companies like
        OpenAI and Google are leading the way with Large Language Models (LLMs).
        Machine learning algorithms now power everything from healthcare diagnostics
        to financial trading systems. The rise of GPT-4 and Claude has democratized
        access to advanced AI capabilities. Silicon Valley continues to invest billions
        in AI research and development.
        """,
        language="en",
        domain="Technology",
        market="US",
        vertical="AI",
        content_hash="hash_en",
        canonical_url="https://example.com/ai",
        published_at=datetime.now(),
        fetched_at=datetime.now()
    )


class TestEntityExtractorE2E:
    """E2E tests with real LLM calls"""

    def test_e2e_extract_german_entities(self, german_document):
        """Should extract entities from German content"""
        extractor = EntityExtractor()

        result = extractor.process(german_document)

        # Verify document was updated
        assert result.status == "processed"
        assert result.entities is not None
        assert result.keywords is not None

        # Check entities (companies, places, technologies)
        assert len(result.entities) > 0
        # Should extract German entities (case-insensitive check)
        entities_lower = [e.lower() for e in result.entities]
        assert any("berlin" in e for e in entities_lower) or any("deutschland" in e for e in entities_lower) or any("propstack" in e for e in entities_lower)

        # Check keywords
        assert len(result.keywords) > 0
        keywords_lower = [k.lower() for k in result.keywords]
        assert any("proptech" in k for k in keywords_lower) or any("immobilien" in k for k in keywords_lower)

        # Statistics
        assert extractor.processed_documents == 1
        assert extractor.failed_documents == 0

    def test_e2e_extract_english_entities(self, english_document):
        """Should extract entities from English content"""
        extractor = EntityExtractor()

        result = extractor.process(english_document)

        # Verify document was updated
        assert result.status == "processed"
        assert result.entities is not None
        assert result.keywords is not None

        # Check entities (companies, technologies)
        assert len(result.entities) > 0
        entities_lower = [e.lower() for e in result.entities]
        assert any("openai" in e or "google" in e or "gpt" in e or "claude" in e or "silicon valley" in e for e in entities_lower)

        # Check keywords
        assert len(result.keywords) > 0
        keywords_lower = [k.lower() for k in result.keywords]
        assert any("ai" in k or "artificial intelligence" in k or "machine learning" in k for k in keywords_lower)

    def test_e2e_batch_processing(self, german_document, english_document):
        """Should process multiple documents in batch"""
        extractor = EntityExtractor()

        docs = [german_document, english_document]
        results = extractor.process_batch(docs)

        # All documents should be processed
        assert len(results) == 2
        assert all(doc.status == "processed" for doc in results)
        assert all(doc.has_entities() for doc in results)
        assert all(doc.has_keywords() for doc in results)

        # Statistics
        assert extractor.processed_documents == 2
        assert extractor.failed_documents == 0

        stats = extractor.get_statistics()
        assert stats['success_rate'] == 1.0

    def test_e2e_skip_already_processed(self, german_document):
        """Should skip documents that are already processed"""
        extractor = EntityExtractor()

        # First processing
        result1 = extractor.process(german_document)
        entities_first = result1.entities.copy()

        # Second processing (should skip)
        result2 = extractor.process(result1)

        # Should be same document
        assert result2.entities == entities_first

        # Statistics should only count once
        assert extractor.processed_documents == 1

    def test_e2e_force_reprocess(self, german_document):
        """Should reprocess document when force=True"""
        extractor = EntityExtractor()

        # First processing
        result1 = extractor.process(german_document)

        # Force reprocess
        result2 = extractor.process(result1, force=True)

        # Should have entities (possibly different)
        assert result2.entities is not None
        assert result2.keywords is not None

        # Statistics should count both
        assert extractor.processed_documents == 2

    def test_e2e_empty_content_error(self):
        """Should raise error for empty content"""
        doc = Document(
            id="empty_doc",
            source="test",
            source_url="https://example.com",
            title="Empty",
            content="",
            language="en",
            domain="Tech",
            market="US",
            vertical="General",
            content_hash="hash",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        extractor = EntityExtractor()

        with pytest.raises(EntityExtractionError, match="empty content"):
            extractor.process(doc)

        assert extractor.failed_documents == 1

    def test_e2e_batch_with_errors(self, german_document):
        """Should handle batch processing with some failures"""
        # Create empty document
        empty_doc = Document(
            id="empty",
            source="test",
            source_url="https://example.com",
            title="Empty",
            content="",
            language="en",
            domain="Tech",
            market="US",
            vertical="General",
            content_hash="hash",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        extractor = EntityExtractor()

        # Batch with skip_errors=True
        results = extractor.process_batch([german_document, empty_doc], skip_errors=True)

        # Only successful document returned
        assert len(results) == 1
        assert results[0].id == "test_doc_de"

        # Statistics
        assert extractor.processed_documents == 1
        assert extractor.failed_documents == 1

    def test_e2e_statistics_tracking(self, german_document, english_document):
        """Should accurately track processing statistics"""
        extractor = EntityExtractor()

        # Process first document
        extractor.process(german_document)

        stats1 = extractor.get_statistics()
        assert stats1['total_documents'] == 1
        assert stats1['processed_documents'] == 1
        assert stats1['success_rate'] == 1.0

        # Process second document
        extractor.process(english_document)

        stats2 = extractor.get_statistics()
        assert stats2['total_documents'] == 2
        assert stats2['processed_documents'] == 2
        assert stats2['success_rate'] == 1.0

        # Reset statistics
        extractor.reset_statistics()

        stats3 = extractor.get_statistics()
        assert stats3['total_documents'] == 0
        assert stats3['success_rate'] == 0.0

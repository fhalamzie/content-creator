"""
Tests for EntityExtractor

Tests entity and keyword extraction from Document objects using LLMProcessor.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.processors.entity_extractor import EntityExtractor, EntityExtractionError
from src.processors.llm_processor import EntityExtraction
from src.models.document import Document


class TestEntityExtractorInit:
    """Test EntityExtractor initialization"""

    def test_init_default(self):
        """Should initialize with default model"""
        with patch('src.processors.entity_extractor.LLMProcessor') as mock_llm:
            extractor = EntityExtractor()

            mock_llm.assert_called_once_with(model="qwen/qwen-2.5-7b-instruct")
            assert extractor.total_documents == 0
            assert extractor.processed_documents == 0
            assert extractor.failed_documents == 0

    def test_init_custom_model(self):
        """Should initialize with custom model"""
        with patch('src.processors.entity_extractor.LLMProcessor') as mock_llm:
            EntityExtractor(model="custom/model")

            mock_llm.assert_called_once_with(model="custom/model")

    def test_init_without_api_key(self, monkeypatch):
        """Should raise ValueError if LLMProcessor init fails"""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            EntityExtractor()


class TestEntityExtractorProcess:
    """Test entity extraction from documents"""

    @pytest.fixture
    def sample_document(self):
        """Create sample document"""
        return Document(
            id="test_doc_123",
            source="test_source",
            source_url="https://example.com/article",
            title="PropTech Trends 2025",
            content="Article about PropTech startups in Berlin using IoT and AI. Companies like PropStack are leading the market.",
            language="en",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc123",
            canonical_url="https://example.com/article",
            published_at=datetime(2025, 11, 1),
            fetched_at=datetime(2025, 11, 2)
        )

    @pytest.fixture
    def mock_extraction_result(self):
        """Create mock entity extraction result"""
        return EntityExtraction(
            entities=["Berlin", "PropStack", "IoT", "AI"],
            keywords=["PropTech", "startups", "market", "companies"]
        )

    def test_process_document_success(self, sample_document, mock_extraction_result):
        """Should extract entities and keywords from document"""
        with patch('src.processors.entity_extractor.LLMProcessor') as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.extract_entities_keywords.return_value = mock_extraction_result

            extractor = EntityExtractor()
            result = extractor.process(sample_document)

            # Check LLM was called correctly
            mock_llm.extract_entities_keywords.assert_called_once_with(
                content=sample_document.content,
                language=sample_document.language
            )

            # Check document was updated
            assert result.entities == ["Berlin", "PropStack", "IoT", "AI"]
            assert result.keywords == ["PropTech", "startups", "market", "companies"]
            assert result.status == "processed"

            # Check statistics
            assert extractor.total_documents == 1
            assert extractor.processed_documents == 1
            assert extractor.failed_documents == 0

    def test_process_document_already_processed(self, sample_document, mock_extraction_result):
        """Should skip document that already has entities"""
        sample_document.entities = ["existing", "entities"]
        sample_document.keywords = ["existing", "keywords"]
        sample_document.status = "processed"

        with patch('src.processors.entity_extractor.LLMProcessor') as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            extractor = EntityExtractor()
            result = extractor.process(sample_document)

            # Should not call LLM
            mock_llm.extract_entities_keywords.assert_not_called()

            # Document should be unchanged
            assert result.entities == ["existing", "entities"]
            assert result.keywords == ["existing", "keywords"]
            assert result.status == "processed"

            # Statistics should not change
            assert extractor.total_documents == 0
            assert extractor.processed_documents == 0

    def test_process_document_force_reprocess(self, sample_document, mock_extraction_result):
        """Should reprocess document when force=True"""
        sample_document.entities = ["old"]
        sample_document.keywords = ["old"]

        with patch('src.processors.entity_extractor.LLMProcessor') as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.extract_entities_keywords.return_value = mock_extraction_result

            extractor = EntityExtractor()
            result = extractor.process(sample_document, force=True)

            # Should call LLM
            mock_llm.extract_entities_keywords.assert_called_once()

            # Should update with new data
            assert result.entities == ["Berlin", "PropStack", "IoT", "AI"]
            assert result.keywords == ["PropTech", "startups", "market", "companies"]

    def test_process_document_empty_content(self, sample_document):
        """Should handle documents with empty content"""
        sample_document.content = ""

        with patch('src.processors.entity_extractor.LLMProcessor') as mock_llm_class:
            mock_llm_class.return_value = Mock()

            extractor = EntityExtractor()

            with pytest.raises(EntityExtractionError, match="Document has empty content"):
                extractor.process(sample_document)

            assert extractor.failed_documents == 1

    def test_process_document_llm_failure(self, sample_document):
        """Should handle LLM failures gracefully"""
        with patch('src.processors.entity_extractor.LLMProcessor') as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.extract_entities_keywords.side_effect = Exception("LLM API error")

            extractor = EntityExtractor()

            with pytest.raises(EntityExtractionError, match="Failed to extract entities"):
                extractor.process(sample_document)

            assert extractor.failed_documents == 1


class TestEntityExtractorBatch:
    """Test batch processing of documents"""

    @pytest.fixture
    def sample_documents(self):
        """Create list of sample documents"""
        return [
            Document(
                id=f"doc_{i}",
                source="test",
                source_url=f"https://example.com/{i}",
                title=f"Article {i}",
                content=f"Content about topic {i}",
                language="en",
                domain="SaaS",
                market="US",
                vertical="Tech",
                content_hash=f"hash_{i}",
                canonical_url=f"https://example.com/{i}",
                published_at=datetime.now(),
                fetched_at=datetime.now()
            )
            for i in range(5)
        ]

    def test_process_batch_success(self, sample_documents):
        """Should process multiple documents in batch"""
        mock_result = EntityExtraction(
            entities=["Entity1", "Entity2"],
            keywords=["keyword1", "keyword2"]
        )

        with patch('src.processors.entity_extractor.LLMProcessor') as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.extract_entities_keywords.return_value = mock_result

            extractor = EntityExtractor()
            results = extractor.process_batch(sample_documents)

            # All documents should be processed
            assert len(results) == 5
            assert all(doc.status == "processed" for doc in results)
            assert all(len(doc.entities) == 2 for doc in results)
            assert all(len(doc.keywords) == 2 for doc in results)

            # Statistics
            assert extractor.total_documents == 5
            assert extractor.processed_documents == 5
            assert extractor.failed_documents == 0

    def test_process_batch_partial_failure(self, sample_documents):
        """Should handle partial failures in batch"""
        mock_result = EntityExtraction(
            entities=["Entity1"],
            keywords=["keyword1"]
        )

        with patch('src.processors.entity_extractor.LLMProcessor') as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            # Fail on 3rd document
            def side_effect(content, language):
                if "topic 2" in content:
                    raise Exception("LLM failure")
                return mock_result

            mock_llm.extract_entities_keywords.side_effect = side_effect

            extractor = EntityExtractor()
            results = extractor.process_batch(sample_documents, skip_errors=True)

            # 4 successful, 1 failed
            assert len(results) == 4
            assert extractor.processed_documents == 4
            assert extractor.failed_documents == 1

    def test_process_batch_empty_list(self):
        """Should handle empty document list"""
        with patch('src.processors.entity_extractor.LLMProcessor'):
            extractor = EntityExtractor()
            results = extractor.process_batch([])

            assert results == []
            assert extractor.total_documents == 0


class TestEntityExtractorStatistics:
    """Test statistics tracking"""

    def test_get_statistics(self):
        """Should return processing statistics"""
        with patch('src.processors.entity_extractor.LLMProcessor'):
            extractor = EntityExtractor()
            extractor.total_documents = 100
            extractor.processed_documents = 95
            extractor.failed_documents = 5

            stats = extractor.get_statistics()

            assert stats['total_documents'] == 100
            assert stats['processed_documents'] == 95
            assert stats['failed_documents'] == 5
            assert stats['success_rate'] == 0.95
            assert stats['failure_rate'] == 0.05

    def test_get_statistics_no_documents(self):
        """Should handle statistics when no documents processed"""
        with patch('src.processors.entity_extractor.LLMProcessor'):
            extractor = EntityExtractor()

            stats = extractor.get_statistics()

            assert stats['total_documents'] == 0
            assert stats['success_rate'] == 0.0
            assert stats['failure_rate'] == 0.0

    def test_reset_statistics(self):
        """Should reset all statistics to zero"""
        with patch('src.processors.entity_extractor.LLMProcessor'):
            extractor = EntityExtractor()
            extractor.total_documents = 100
            extractor.processed_documents = 95
            extractor.failed_documents = 5

            extractor.reset_statistics()

            assert extractor.total_documents == 0
            assert extractor.processed_documents == 0
            assert extractor.failed_documents == 0

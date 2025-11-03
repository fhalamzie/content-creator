"""
Tests for Document data model

The Document model is the unified data structure used across all collectors.
It ensures consistency in how content is stored and processed.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.models.document import Document


class TestDocumentCreation:
    """Test Document model creation and validation"""

    def test_create_document_with_required_fields_only(self):
        """Test creating document with only required fields"""
        doc = Document(
            id="doc123",
            source="rss_heise",
            source_url="https://heise.de/article123",
            title="Test Article",
            content="This is test content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc123",
            canonical_url="https://heise.de/article123",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc.id == "doc123"
        assert doc.source == "rss_heise"
        assert doc.title == "Test Article"
        assert doc.language == "de"
        assert doc.domain == "SaaS"

    def test_create_document_with_all_fields(self):
        """Test creating document with all fields including optional"""
        now = datetime.now()

        doc = Document(
            id="doc123",
            source="rss_heise",
            source_url="https://heise.de/article123",
            title="Test Article",
            content="This is test content",
            summary="Test summary",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc123",
            canonical_url="https://heise.de/article123",
            published_at=now,
            fetched_at=now,
            author="John Doe",
            entities=["Berlin", "PropTech"],
            keywords=["SaaS", "PropTech", "Germany"],
            reliability_score=0.8,
            paywall=False,
            status="processed"
        )

        assert doc.summary == "Test summary"
        assert doc.author == "John Doe"
        assert doc.entities == ["Berlin", "PropTech"]
        assert doc.keywords == ["SaaS", "PropTech", "Germany"]
        assert doc.reliability_score == 0.8
        assert doc.paywall is False
        assert doc.status == "processed"

    def test_missing_required_field_raises_error(self):
        """Test that missing required fields raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            Document(
                id="doc123",
                # Missing source
                source_url="https://example.com",
                title="Test",
                content="Content",
                language="de",
                domain="SaaS",
                market="Germany",
                vertical="Proptech",
                content_hash="abc",
                canonical_url="https://example.com",
                published_at=datetime.now(),
                fetched_at=datetime.now()
            )

        assert "source" in str(exc_info.value)


class TestDocumentDefaults:
    """Test default values for optional fields"""

    def test_default_summary_is_none(self):
        """Test summary defaults to None"""
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc.summary is None

    def test_default_author_is_none(self):
        """Test author defaults to None"""
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc.author is None

    def test_default_entities_is_none(self):
        """Test entities defaults to None (not processed yet)"""
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc.entities is None

    def test_default_keywords_is_none(self):
        """Test keywords defaults to None (not processed yet)"""
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc.keywords is None

    def test_default_reliability_score_is_0_5(self):
        """Test reliability_score defaults to 0.5"""
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc.reliability_score == 0.5

    def test_default_paywall_is_false(self):
        """Test paywall defaults to False"""
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc.paywall is False

    def test_default_status_is_new(self):
        """Test status defaults to 'new'"""
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc.status == "new"


class TestDocumentSerialization:
    """Test serialization to dict and JSON"""

    def test_to_dict(self):
        """Test converting Document to dictionary"""
        now = datetime.now()

        doc = Document(
            id="doc123",
            source="rss_heise",
            source_url="https://heise.de/article123",
            title="Test Article",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc123",
            canonical_url="https://heise.de/article123",
            published_at=now,
            fetched_at=now
        )

        doc_dict = doc.model_dump()

        assert isinstance(doc_dict, dict)
        assert doc_dict["id"] == "doc123"
        assert doc_dict["source"] == "rss_heise"
        assert doc_dict["title"] == "Test Article"

    def test_to_json(self):
        """Test converting Document to JSON string"""
        now = datetime.now()

        doc = Document(
            id="doc123",
            source="rss_heise",
            source_url="https://heise.de/article123",
            title="Test Article",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc123",
            canonical_url="https://heise.de/article123",
            published_at=now,
            fetched_at=now
        )

        json_str = doc.model_dump_json()

        assert isinstance(json_str, str)
        assert "doc123" in json_str
        assert "rss_heise" in json_str
        assert "Test Article" in json_str

    def test_from_dict(self):
        """Test creating Document from dictionary"""
        now = datetime.now()

        doc_dict = {
            "id": "doc123",
            "source": "rss_heise",
            "source_url": "https://heise.de/article123",
            "title": "Test Article",
            "content": "Content",
            "language": "de",
            "domain": "SaaS",
            "market": "Germany",
            "vertical": "Proptech",
            "content_hash": "abc123",
            "canonical_url": "https://heise.de/article123",
            "published_at": now.isoformat(),
            "fetched_at": now.isoformat()
        }

        doc = Document(**doc_dict)

        assert doc.id == "doc123"
        assert doc.source == "rss_heise"
        assert doc.title == "Test Article"


class TestDocumentValidation:
    """Test field validation"""

    def test_language_iso_639_1_format(self):
        """Test language field accepts ISO 639-1 codes"""
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",  # ISO 639-1
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc.language == "de"

    def test_reliability_score_range(self):
        """Test reliability_score is between 0 and 1"""
        # Valid score
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now(),
            reliability_score=0.7
        )

        assert 0 <= doc.reliability_score <= 1

    def test_status_values(self):
        """Test status field accepts expected values"""
        for status in ["new", "processed", "rejected"]:
            doc = Document(
                id=f"doc_{status}",
                source="rss_test",
                source_url="https://example.com",
                title="Test",
                content="Content",
                language="de",
                domain="SaaS",
                market="Germany",
                vertical="Proptech",
                content_hash="abc",
                canonical_url="https://example.com",
                published_at=datetime.now(),
                fetched_at=datetime.now(),
                status=status
            )

            assert doc.status == status


class TestDocumentHelpers:
    """Test helper methods"""

    def test_is_processed(self):
        """Test helper to check if document is processed"""
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now(),
            status="processed"
        )

        assert doc.is_processed() is True

    def test_is_not_processed(self):
        """Test document with status='new' is not processed"""
        doc = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now(),
            status="new"
        )

        assert doc.is_processed() is False

    def test_has_entities(self):
        """Test helper to check if document has entities extracted"""
        doc_with_entities = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now(),
            entities=["Berlin", "PropTech"]
        )

        doc_without_entities = Document(
            id="doc456",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="def",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc_with_entities.has_entities() is True
        assert doc_without_entities.has_entities() is False

    def test_has_keywords(self):
        """Test helper to check if document has keywords extracted"""
        doc_with_keywords = Document(
            id="doc123",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now(),
            keywords=["SaaS", "PropTech"]
        )

        doc_without_keywords = Document(
            id="doc456",
            source="rss_test",
            source_url="https://example.com",
            title="Test",
            content="Content",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="def",
            canonical_url="https://example.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        assert doc_with_keywords.has_keywords() is True
        assert doc_without_keywords.has_keywords() is False

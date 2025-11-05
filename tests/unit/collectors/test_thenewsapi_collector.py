"""
Unit tests for TheNewsAPI Collector

Tests:
- API client initialization
- News article collection
- Document conversion
- Error handling and graceful degradation
- Deduplication integration
- Rate limiting
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import json

from src.collectors.thenewsapi_collector import (
    TheNewsAPICollector,
    TheNewsAPIError
)
from src.models.document import Document


@pytest.fixture
def mock_config():
    """Mock market configuration"""
    config = Mock()
    config.domain = "SaaS"
    config.market = "Germany"
    config.language = "de"
    config.vertical = "Proptech"
    return config


@pytest.fixture
def mock_db_manager():
    """Mock database manager"""
    return Mock()


@pytest.fixture
def mock_deduplicator():
    """Mock deduplicator"""
    dedup = Mock()
    dedup.is_duplicate = Mock(return_value=False)
    dedup.compute_content_hash = Mock(return_value="hash123")
    dedup.get_canonical_url = Mock(side_effect=lambda url: url)
    return dedup


@pytest.fixture
def collector(mock_config, mock_db_manager, mock_deduplicator, tmp_path):
    """Create collector instance for testing"""
    return TheNewsAPICollector(
        api_key="test_api_key",
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=str(tmp_path / "thenewsapi_cache")
    )


@pytest.fixture
def sample_api_response():
    """Sample API response from TheNewsAPI"""
    return {
        "meta": {
            "found": 150,
            "returned": 3,
            "limit": 3,
            "page": 1
        },
        "data": [
            {
                "uuid": "abc-123",
                "title": "PropTech Innovation in Germany",
                "description": "New PropTech startups emerge in Berlin",
                "keywords": "proptech,innovation,germany",
                "snippet": "PropTech sector grows...",
                "url": "https://example.com/article1",
                "image_url": "https://example.com/image1.jpg",
                "language": "de",
                "published_at": "2025-11-05 10:00:00",
                "source": "TechNews",
                "categories": ["tech", "business"],
                "relevance_score": None
            },
            {
                "uuid": "def-456",
                "title": "Smart Building Technology",
                "description": "IoT integration in commercial buildings",
                "keywords": "smart building,iot,technology",
                "snippet": "Smart building tech advances...",
                "url": "https://example.com/article2",
                "image_url": "https://example.com/image2.jpg",
                "language": "de",
                "published_at": "2025-11-05 09:30:00",
                "source": "BuildingNews",
                "categories": ["tech"],
                "relevance_score": None
            },
            {
                "uuid": "ghi-789",
                "title": "Real Estate SaaS Tools",
                "description": "Cloud solutions for property management",
                "keywords": "saas,real estate,cloud",
                "snippet": "SaaS tools transform...",
                "url": "https://example.com/article3",
                "image_url": "https://example.com/image3.jpg",
                "language": "de",
                "published_at": "2025-11-05 09:00:00",
                "source": "SaaSDaily",
                "categories": ["business", "tech"],
                "relevance_score": None
            }
        ]
    }


class TestTheNewsAPICollectorInit:
    """Test collector initialization"""

    def test_init_with_api_key(self, mock_config, mock_db_manager, mock_deduplicator, tmp_path):
        """Test initialization with explicit API key"""
        collector = TheNewsAPICollector(
            api_key="test_key",
            config=mock_config,
            db_manager=mock_db_manager,
            deduplicator=mock_deduplicator,
            cache_dir=str(tmp_path / "cache")
        )

        assert collector.api_key == "test_key"
        assert collector.config == mock_config
        assert collector.db_manager == mock_db_manager
        assert collector.deduplicator == mock_deduplicator

    def test_init_without_api_key_loads_from_env(self, mock_config, mock_db_manager, mock_deduplicator, tmp_path, monkeypatch):
        """Test API key auto-loads from environment"""
        monkeypatch.setenv("THENEWSAPI_API_KEY", "env_key")

        collector = TheNewsAPICollector(
            api_key=None,
            config=mock_config,
            db_manager=mock_db_manager,
            deduplicator=mock_deduplicator
        )

        assert collector.api_key == "env_key"

    def test_init_without_api_key_raises_error(self, mock_config, mock_db_manager, mock_deduplicator):
        """Test initialization fails without API key"""
        with pytest.raises(TheNewsAPIError, match="API key required"):
            TheNewsAPICollector(
                api_key=None,
                config=mock_config,
                db_manager=mock_db_manager,
                deduplicator=mock_deduplicator
            )

    def test_cache_directory_created(self, collector):
        """Test cache directory is created on init"""
        assert collector.cache_dir.exists()
        assert collector.cache_dir.is_dir()


class TestTheNewsAPICollectorCollect:
    """Test news article collection"""

    @pytest.mark.asyncio
    async def test_collect_success(self, collector, sample_api_response, mock_deduplicator):
        """Test successful article collection"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_get.return_value = mock_response

            documents = await collector.collect(
                query="PropTech",
                limit=3
            )

            assert len(documents) == 3
            assert all(isinstance(doc, Document) for doc in documents)
            assert documents[0].title == "PropTech Innovation in Germany"
            assert documents[0].source == "thenewsapi_TechNews"
            assert documents[0].language == "de"

    @pytest.mark.asyncio
    async def test_collect_with_filters(self, collector, sample_api_response):
        """Test collection with category and date filters"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_get.return_value = mock_response

            await collector.collect(
                query="PropTech",
                categories=["tech", "business"],
                published_after="2025-11-01",
                limit=10
            )

            # Verify API call parameters
            call_args = mock_get.call_args
            params = call_args.kwargs.get('params', call_args[1] if len(call_args) > 1 else {})

            assert "categories" in params
            assert "published_after" in params
            assert params["limit"] == 10

    @pytest.mark.asyncio
    async def test_collect_empty_results(self, collector):
        """Test collection with no results"""
        empty_response = {
            "meta": {"found": 0, "returned": 0, "limit": 10, "page": 1},
            "data": []
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = empty_response
            mock_get.return_value = mock_response

            documents = await collector.collect(query="NonexistentTopic")

            assert len(documents) == 0

    @pytest.mark.asyncio
    async def test_collect_deduplication(self, collector, sample_api_response, mock_deduplicator):
        """Test deduplication integration"""
        # Mark second article as duplicate
        mock_deduplicator.is_duplicate.side_effect = [False, True, False]

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_get.return_value = mock_response

            documents = await collector.collect(query="PropTech")

            # Should skip the duplicate (middle one)
            assert len(documents) == 2
            assert documents[0].title == "PropTech Innovation in Germany"
            assert documents[1].title == "Real Estate SaaS Tools"

    @pytest.mark.asyncio
    async def test_collect_api_error_graceful_degradation(self, collector):
        """Test graceful handling of API errors"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("API connection failed")

            # Should not raise, return empty list
            documents = await collector.collect(query="PropTech")

            assert len(documents) == 0
            assert collector.get_statistics()["total_failures"] == 1

    @pytest.mark.asyncio
    async def test_collect_http_error_status(self, collector):
        """Test handling of HTTP error status codes"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429  # Rate limit
            mock_response.text = "Rate limit exceeded"
            mock_get.return_value = mock_response

            documents = await collector.collect(query="PropTech")

            assert len(documents) == 0
            assert collector.get_statistics()["total_failures"] == 1

    @pytest.mark.asyncio
    async def test_collect_malformed_response(self, collector):
        """Test handling of malformed JSON response"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
            mock_get.return_value = mock_response

            documents = await collector.collect(query="PropTech")

            assert len(documents) == 0


class TestTheNewsAPICollectorDocumentConversion:
    """Test article to Document conversion"""

    @pytest.mark.asyncio
    async def test_document_fields_populated(self, collector, sample_api_response, mock_deduplicator):
        """Test all Document fields are correctly populated"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_get.return_value = mock_response

            documents = await collector.collect(query="PropTech")
            doc = documents[0]

            assert doc.id.startswith("thenewsapi_")
            assert doc.source == "thenewsapi_TechNews"
            assert doc.source_url == "https://example.com/article1"
            assert doc.title == "PropTech Innovation in Germany"
            assert doc.content == "New PropTech startups emerge in Berlin"
            assert doc.summary == "PropTech sector grows..."
            assert doc.language == "de"
            assert doc.domain == "SaaS"
            assert doc.market == "Germany"
            assert doc.vertical == "Proptech"
            assert isinstance(doc.published_at, datetime)
            assert isinstance(doc.fetched_at, datetime)

    @pytest.mark.asyncio
    async def test_document_handles_missing_fields(self, collector):
        """Test Document creation with missing optional fields"""
        minimal_response = {
            "meta": {"found": 1, "returned": 1, "limit": 1, "page": 1},
            "data": [
                {
                    "uuid": "min-123",
                    "title": "Minimal Article",
                    "url": "https://example.com/minimal",
                    "language": "de",
                    "published_at": "2025-11-05 10:00:00",
                    "source": "MinSource"
                }
            ]
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = minimal_response
            mock_get.return_value = mock_response

            documents = await collector.collect(query="Test")

            assert len(documents) == 1
            doc = documents[0]
            assert doc.title == "Minimal Article"
            assert doc.content == ""  # Missing description
            assert doc.summary == ""  # Missing snippet

    @pytest.mark.asyncio
    async def test_document_date_parsing(self, collector):
        """Test published_at date parsing"""
        response = {
            "meta": {"found": 1, "returned": 1, "limit": 1, "page": 1},
            "data": [
                {
                    "uuid": "date-test",
                    "title": "Date Test",
                    "url": "https://example.com/date",
                    "language": "de",
                    "published_at": "2025-11-05 14:30:45",
                    "source": "DateSource"
                }
            ]
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = response
            mock_get.return_value = mock_response

            documents = await collector.collect(query="Test")
            doc = documents[0]

            assert doc.published_at.year == 2025
            assert doc.published_at.month == 11
            assert doc.published_at.day == 5
            assert doc.published_at.hour == 14
            assert doc.published_at.minute == 30


class TestTheNewsAPICollectorStatistics:
    """Test statistics tracking"""

    @pytest.mark.asyncio
    async def test_statistics_updated_on_success(self, collector, sample_api_response):
        """Test statistics are updated after successful collection"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_api_response
            mock_get.return_value = mock_response

            await collector.collect(query="PropTech")

            stats = collector.get_statistics()
            assert stats["total_requests"] == 1
            assert stats["total_documents_collected"] == 3
            assert stats["total_failures"] == 0

    @pytest.mark.asyncio
    async def test_statistics_updated_on_failure(self, collector):
        """Test statistics are updated after failed collection"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("API error")

            await collector.collect(query="PropTech")

            stats = collector.get_statistics()
            assert stats["total_requests"] == 1
            assert stats["total_failures"] == 1

    def test_reset_statistics(self, collector):
        """Test statistics can be reset"""
        collector._stats["total_requests"] = 10
        collector._stats["total_failures"] = 2

        collector.reset_statistics()

        stats = collector.get_statistics()
        assert stats["total_requests"] == 0
        assert stats["total_failures"] == 0


class TestTheNewsAPICollectorHelpers:
    """Test helper methods"""

    def test_build_query_params_basic(self, collector):
        """Test basic query parameter building"""
        params = collector._build_query_params(
            query="PropTech",
            limit=10
        )

        assert params["api_token"] == "test_api_key"
        assert params["search"] == "PropTech"
        assert params["limit"] == 10
        assert params["language"] == "de"

    def test_build_query_params_with_filters(self, collector):
        """Test query parameters with all filters"""
        params = collector._build_query_params(
            query="PropTech",
            categories=["tech", "business"],
            published_after="2025-11-01",
            limit=20
        )

        assert params["categories"] == "tech,business"
        assert params["published_after"] == "2025-11-01"
        assert params["limit"] == 20

    def test_parse_article_to_document(self, collector, mock_deduplicator):
        """Test article parsing to Document"""
        article = {
            "uuid": "test-uuid",
            "title": "Test Article",
            "description": "Test description",
            "snippet": "Test snippet",
            "url": "https://example.com/test",
            "language": "de",
            "published_at": "2025-11-05 10:00:00",
            "source": "TestSource",
            "categories": ["tech"]
        }

        doc = collector._parse_article_to_document(article)

        assert isinstance(doc, Document)
        assert doc.title == "Test Article"
        assert doc.content == "Test description"
        assert doc.summary == "Test snippet"
        assert doc.source_url == "https://example.com/test"

    def test_parse_date(self, collector):
        """Test date string parsing"""
        date_str = "2025-11-05 14:30:00"
        parsed = collector._parse_date(date_str)

        assert isinstance(parsed, datetime)
        assert parsed.year == 2025
        assert parsed.month == 11
        assert parsed.day == 5

    def test_parse_date_invalid_defaults_to_now(self, collector):
        """Test invalid date defaults to current time"""
        parsed = collector._parse_date("invalid-date")

        assert isinstance(parsed, datetime)
        # Should be very recent (within last minute)
        assert (datetime.now() - parsed).total_seconds() < 60

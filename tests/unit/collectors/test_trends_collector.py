"""
Tests for Trends Collector (Gemini CLI Backend)

**BREAKING CHANGE (Nov 2025)**: Updated tests for Gemini CLI backend

Test Coverage:
- Trending searches collection (via Gemini web search)
- Related queries collection (via Gemini)
- Interest over time collection (via Gemini)
- Regional targeting (DE, US, etc.)
- Caching (1 hour for trending, 24 hours for interest)
- Query health tracking (failures, timeouts)
- Error handling (Gemini CLI errors, parsing errors)
- Document model creation with all required fields
- Deduplication integration
- Gemini CLI subprocess mocking
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import json
import subprocess

from src.collectors.trends_collector import (
    TrendsCollector,
    TrendsCollectorError,
)
from src.models.document import Document


# ==================== Fixtures ====================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory for trends collector"""
    cache_dir = tmp_path / "trends_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def mock_config():
    """Mock market configuration"""
    config = Mock()
    config.market.domain = "SaaS"
    config.market.market = "Germany"
    config.market.language = "de"
    config.market.vertical = "Proptech"
    return config


@pytest.fixture
def mock_db_manager():
    """Mock DatabaseManager"""
    db = Mock()
    db.insert_document = Mock(return_value=True)
    db.get_document_by_url = Mock(return_value=None)
    return db


@pytest.fixture
def mock_deduplicator():
    """Mock Deduplicator"""
    dedup = Mock()
    dedup.is_duplicate = Mock(return_value=False)
    dedup.get_canonical_url = Mock(side_effect=lambda url: url.lower().rstrip('/'))
    dedup.compute_content_hash = Mock(side_effect=lambda content: hashlib.md5(content.encode()).hexdigest())
    return dedup


@pytest.fixture
def mock_gemini_agent():
    """Mock GeminiAgent for tests"""
    agent = Mock()
    agent.generate = Mock()
    return agent


@pytest.fixture
def trends_collector(mock_config, mock_db_manager, mock_deduplicator, mock_gemini_agent, temp_cache_dir):
    """Create TrendsCollector instance for tests"""
    return TrendsCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        gemini_agent=mock_gemini_agent,
        cache_dir=temp_cache_dir,
        region="DE"  # Germany
    )


@pytest.fixture
def mock_gemini_trending_response():
    """Mock GeminiAgent API response for trending searches"""
    return {
        "content": [
            {"topic": "PropTech Deutschland", "category": "tech", "description": "Property technology trends in Germany"},
            {"topic": "Smart Building IoT", "category": "tech", "description": "IoT solutions for smart buildings"},
            {"topic": "DSGVO Immobilien", "category": "news", "description": "GDPR compliance for real estate"}
        ]
    }


@pytest.fixture
def mock_gemini_related_queries_response():
    """Mock GeminiAgent API response for related queries"""
    return {
        "content": [
            {"keyword": "PropTech", "query": "proptech startup", "relevance": 100},
            {"keyword": "PropTech", "query": "proptech immobilien", "relevance": 75},
            {"keyword": "PropTech", "query": "proptech software", "relevance": 50}
        ]
    }


@pytest.fixture
def mock_gemini_interest_response():
    """Mock GeminiAgent API response for interest over time"""
    return {
        "content": [
            {"keyword": "PropTech", "trend": "increasing", "interest_level": "high", "analysis": "Strong upward trend over past 3 months"}
        ]
    }


# ==================== Constructor Tests ====================

def test_trends_collector_initialization(trends_collector, temp_cache_dir):
    """Test TrendsCollector initializes with correct parameters"""
    assert trends_collector.config is not None
    assert trends_collector.db_manager is not None
    assert trends_collector.deduplicator is not None
    assert trends_collector.gemini_agent is not None
    assert trends_collector.cache_dir == Path(temp_cache_dir)
    assert trends_collector.region == "DE"
    assert trends_collector.query_health == {}


def test_trends_collector_creates_cache_dir(mock_config, mock_db_manager, mock_deduplicator, mock_gemini_agent, tmp_path):
    """Test TrendsCollector creates cache directory if missing"""
    cache_dir = tmp_path / "new_trends_cache"
    assert not cache_dir.exists()

    TrendsCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        gemini_agent=mock_gemini_agent,
        cache_dir=str(cache_dir)
    )

    assert cache_dir.exists()


# ==================== Trending Searches Tests ====================

def test_collect_trending_searches_success(trends_collector, mock_gemini_trending_response):
    """Test collecting trending searches successfully via Gemini API"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_trending_response

    documents = trends_collector.collect_trending_searches(pn='germany')

    # Verify gemini_agent was called
    assert trends_collector.gemini_agent.generate.called

    # Verify documents created
    assert len(documents) == 3
    assert all(isinstance(doc, Document) for doc in documents)
    assert documents[0].title == "PropTech Deutschland"
    assert documents[0].source == "trends_trending_searches_germany"
    assert "tech" in documents[0].content


def test_collect_trending_searches_empty(trends_collector):
    """Test handling of empty trending searches"""
    # Gemini returns empty array
    trends_collector.gemini_agent.generate.return_value = {"content": []}

    documents = trends_collector.collect_trending_searches(pn='germany')

    assert len(documents) == 0


def test_collect_trending_searches_error(trends_collector):
    """Test error handling when Gemini API fails"""
    from src.agents.gemini_agent import GeminiAgentError
    trends_collector.gemini_agent.generate.side_effect = GeminiAgentError("API error")

    with pytest.raises(TrendsCollectorError, match="Gemini API"):
        trends_collector.collect_trending_searches(pn='germany')


# ==================== Related Queries Tests ====================

def test_collect_related_queries_top(trends_collector, mock_gemini_related_queries_response):
    """Test collecting top related queries via Gemini API"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_related_queries_response

    documents = trends_collector.collect_related_queries(keywords=['PropTech'], query_type='top')

    # Verify gemini_agent was called
    assert trends_collector.gemini_agent.generate.called

    # Verify documents created
    assert len(documents) == 3
    assert all(isinstance(doc, Document) for doc in documents)
    assert "Related query:" in documents[0].title
    assert "proptech startup" in documents[0].title


def test_collect_related_queries_rising(trends_collector, mock_gemini_related_queries_response):
    """Test collecting rising related queries via Gemini API"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_related_queries_response

    documents = trends_collector.collect_related_queries(keywords=['PropTech'], query_type='rising')

    assert len(documents) == 3
    assert "Rising query:" in documents[0].title


def test_collect_related_queries_multiple_keywords(trends_collector):
    """Test collecting related queries for multiple keywords"""
    response = {
        "content": [
            {"keyword": "PropTech", "query": "proptech startup", "relevance": 100},
            {"keyword": "Smart Building", "query": "smart building automation", "relevance": 90}
        ]
    }
    trends_collector.gemini_agent.generate.return_value = response

    documents = trends_collector.collect_related_queries(keywords=['PropTech', 'Smart Building'])

    assert len(documents) == 2
    # Verify keywords are different
    keywords_in_content = [doc.content for doc in documents]
    assert any("PropTech" in content for content in keywords_in_content)
    assert any("Smart Building" in content for content in keywords_in_content)


# ==================== Interest Over Time Tests ====================

def test_collect_interest_over_time_success(trends_collector, mock_gemini_interest_response):
    """Test collecting interest over time via Gemini API"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_interest_response

    documents = trends_collector.collect_interest_over_time(keywords=['PropTech'])

    # Verify gemini_agent was called
    assert trends_collector.gemini_agent.generate.called

    # Verify documents created
    assert len(documents) == 1
    assert isinstance(documents[0], Document)
    assert "Interest over time: PropTech" == documents[0].title
    assert "increasing" in documents[0].content
    assert "high" in documents[0].content


def test_collect_interest_over_time_custom_timeframe(trends_collector, mock_gemini_interest_response):
    """Test interest over time with custom timeframe"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_interest_response

    documents = trends_collector.collect_interest_over_time(
        keywords=['PropTech'],
        timeframe='today 12-m'
    )

    assert len(documents) == 1
    # Verify gemini_agent was called
    assert trends_collector.gemini_agent.generate.called


# ==================== Caching Tests ====================

def test_trending_searches_caching(trends_collector, mock_gemini_trending_response):
    """Test trending searches are cached (1 hour TTL)"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_trending_response

    # First call - should hit Gemini API
    docs1 = trends_collector.collect_trending_searches(pn='germany')
    assert trends_collector.gemini_agent.generate.call_count == 1
    assert trends_collector._stats['cache_misses'] == 1

    # Second call - should use cache
    docs2 = trends_collector.collect_trending_searches(pn='germany')
    assert trends_collector.gemini_agent.generate.call_count == 1  # No additional call
    assert trends_collector._stats['cache_hits'] == 1

    # Results should be identical
    assert len(docs1) == len(docs2)
    assert docs1[0].title == docs2[0].title


def test_trending_searches_cache_expiry(trends_collector, mock_gemini_trending_response):
    """Test cache expires after TTL"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_trending_response

    # First call
    trends_collector.collect_trending_searches(pn='germany')
    assert trends_collector.gemini_agent.generate.call_count == 1

    # Expire cache manually
    cache_key = "trending_searches_germany"
    trends_collector._cache[cache_key]['timestamp'] = datetime.now() - timedelta(hours=2)

    # Second call - cache expired, should hit Gemini API again
    trends_collector.collect_trending_searches(pn='germany')
    assert trends_collector.gemini_agent.generate.call_count == 2


def test_interest_over_time_caching(trends_collector, mock_gemini_interest_response):
    """Test interest data is cached (24 hour TTL)"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_interest_response

    # First call
    trends_collector.collect_interest_over_time(keywords=['PropTech'])
    assert trends_collector.gemini_agent.generate.call_count == 1

    # Second call - should use cache
    trends_collector.collect_interest_over_time(keywords=['PropTech'])
    assert trends_collector.gemini_agent.generate.call_count == 1  # No additional call


# ==================== Query Health Tests ====================

def test_query_health_initialization(trends_collector, mock_gemini_trending_response):
    """Test query health is initialized on first query"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_trending_response

    query_id = "trending_searches_germany"
    assert query_id not in trends_collector.query_health

    trends_collector.collect_trending_searches(pn='germany')

    assert query_id in trends_collector.query_health
    assert trends_collector.query_health[query_id].success_count == 1


def test_query_health_success_tracking(trends_collector, mock_gemini_trending_response):
    """Test query health tracks successful queries"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_trending_response

    query_id = "trending_searches_germany"

    # Multiple successful queries
    for _ in range(3):
        # Clear cache to force new query
        trends_collector._cache.clear()
        trends_collector.collect_trending_searches(pn='germany')

    health = trends_collector.query_health[query_id]
    assert health.success_count == 3
    assert health.consecutive_failures == 0


def test_query_health_failure_tracking(trends_collector):
    """Test query health tracks failures"""
    from src.agents.gemini_agent import GeminiAgentError
    trends_collector.gemini_agent.generate.side_effect = GeminiAgentError("API error")

    query_id = "trending_searches_germany"

    # Trigger failure
    with pytest.raises(TrendsCollectorError):
        trends_collector.collect_trending_searches(pn='germany')

    health = trends_collector.query_health[query_id]
    assert health.failure_count == 1
    assert health.consecutive_failures == 1


def test_should_skip_unhealthy_query(trends_collector):
    """Test unhealthy queries are skipped"""
    from src.agents.gemini_agent import GeminiAgentError
    trends_collector.gemini_agent.generate.side_effect = GeminiAgentError("API error")

    # Trigger 5 consecutive failures
    for _ in range(5):
        with pytest.raises(TrendsCollectorError):
            trends_collector.collect_trending_searches(pn='germany')

    # Next call should be skipped (unhealthy)
    documents = trends_collector.collect_trending_searches(pn='germany')
    assert len(documents) == 0  # Skipped


# ==================== Document Creation Tests ====================

def test_document_creation_with_all_fields(trends_collector, mock_gemini_trending_response):
    """Test Document model is created with all required fields"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_trending_response

    documents = trends_collector.collect_trending_searches(pn='germany')
    doc = documents[0]

    # Required fields
    assert doc.id is not None
    assert doc.source == "trends_trending_searches_germany"
    assert doc.source_url.startswith("https://trends.google.com")
    assert doc.canonical_url is not None
    assert doc.title == "PropTech Deutschland"
    assert doc.content is not None
    assert doc.language == "de"
    assert doc.domain == "SaaS"
    assert doc.market == "Germany"
    assert doc.vertical == "Proptech"
    assert doc.published_at is not None
    assert doc.fetched_at is not None
    assert doc.content_hash is not None


def test_document_id_generation(trends_collector, mock_gemini_trending_response):
    """Test document ID generation is consistent"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_trending_response

    # Collect twice (second from cache)
    docs1 = trends_collector.collect_trending_searches(pn='germany')
    docs2 = trends_collector.collect_trending_searches(pn='germany')

    # IDs should be consistent
    assert docs1[0].id == docs2[0].id
    assert docs1[1].id == docs2[1].id

    # IDs should be unique per document
    assert docs1[0].id != docs1[1].id


def test_skip_duplicate_documents(trends_collector, mock_gemini_trending_response):
    """Test duplicate documents are skipped"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_trending_response

    # Mark first document as duplicate
    trends_collector.deduplicator.is_duplicate = Mock(side_effect=[True, False, False])

    documents = trends_collector.collect_trending_searches(pn='germany')

    # First document should be skipped
    assert len(documents) == 2  # Only 2 out of 3


# ==================== Statistics Tests ====================

def test_collection_statistics(trends_collector, mock_gemini_trending_response):
    """Test collection statistics are tracked"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_trending_response

    # Initial stats
    stats = trends_collector.get_statistics()
    assert stats['total_queries'] == 0
    assert stats['total_documents'] == 0

    # Collect documents
    trends_collector.collect_trending_searches(pn='germany')

    stats = trends_collector.get_statistics()
    assert stats['total_queries'] == 1
    assert stats['total_documents'] == 3
    assert stats['cache_misses'] == 1


# ==================== Error Handling Tests ====================

def test_network_error_handling(trends_collector):
    """Test handling of API timeout"""
    from src.agents.gemini_agent import GeminiAgentError
    trends_collector.gemini_agent.generate.side_effect = GeminiAgentError("Request timeout")

    with pytest.raises(TrendsCollectorError, match="Gemini API"):
        trends_collector.collect_trending_searches(pn='germany')


def test_invalid_region_handling(trends_collector):
    """Test handling of invalid region (Gemini still works)"""
    trends_collector.gemini_agent.generate.return_value = {"content": []}

    # Invalid region - Gemini should handle gracefully
    documents = trends_collector.collect_trending_searches(pn='invalid_region')
    assert len(documents) == 0  # Empty but no error


def test_gemini_api_error(trends_collector):
    """Test handling when Gemini API error occurs"""
    from src.agents.gemini_agent import GeminiAgentError
    trends_collector.gemini_agent.generate.side_effect = GeminiAgentError("API unavailable")

    with pytest.raises(TrendsCollectorError, match="Gemini API"):
        trends_collector.collect_trending_searches(pn='germany')


def test_invalid_response_handling(trends_collector):
    """Test handling of invalid response from Gemini"""
    trends_collector.gemini_agent.generate.return_value = {}

    # Empty response should handle gracefully
    with pytest.raises(TrendsCollectorError, match="No valid array"):
        trends_collector.collect_trending_searches(pn='germany')


# ==================== Cache Persistence Tests ====================

def test_save_and_load_query_cache(trends_collector, mock_gemini_trending_response, mock_config, mock_db_manager, mock_deduplicator, mock_gemini_agent):
    """Test cache persistence to disk"""
    trends_collector.gemini_agent.generate.return_value = mock_gemini_trending_response

    # Collect and cache
    docs1 = trends_collector.collect_trending_searches(pn='germany')

    # Save cache
    trends_collector.save_cache()

    # Create new collector (loads cache from disk)
    # Should load from cache, no API call needed
    new_collector = TrendsCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        gemini_agent=mock_gemini_agent,
        cache_dir=str(trends_collector.cache_dir),
        region="DE"
    )

    # Should load from cache (no additional API call)
    docs2 = new_collector.collect_trending_searches(pn='germany')

    assert len(docs2) == len(docs1)
    assert docs2[0].title == docs1[0].title
    # Gemini API should only be called once (first collector)
    assert trends_collector.gemini_agent.generate.call_count == 1

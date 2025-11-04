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
def trends_collector(mock_config, mock_db_manager, mock_deduplicator, temp_cache_dir):
    """Create TrendsCollector instance for tests"""
    return TrendsCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=temp_cache_dir,
        region="DE",  # Germany
        rate_limit=0.5,  # Kept for compatibility (unused in Gemini)
        request_timeout=30
    )


@pytest.fixture
def mock_gemini_trending_response():
    """Mock Gemini CLI response for trending searches"""
    return json.dumps({
        "response": json.dumps([
            {"topic": "PropTech Deutschland", "category": "tech", "description": "Property technology trends in Germany"},
            {"topic": "Smart Building IoT", "category": "tech", "description": "IoT solutions for smart buildings"},
            {"topic": "DSGVO Immobilien", "category": "news", "description": "GDPR compliance for real estate"}
        ])
    })


@pytest.fixture
def mock_gemini_related_queries_response():
    """Mock Gemini CLI response for related queries"""
    return json.dumps({
        "response": json.dumps([
            {"keyword": "PropTech", "query": "proptech startup", "relevance": 100},
            {"keyword": "PropTech", "query": "proptech immobilien", "relevance": 75},
            {"keyword": "PropTech", "query": "proptech software", "relevance": 50}
        ])
    })


@pytest.fixture
def mock_gemini_interest_response():
    """Mock Gemini CLI response for interest over time"""
    return json.dumps({
        "response": json.dumps([
            {"keyword": "PropTech", "trend": "increasing", "interest_level": "high", "analysis": "Strong upward trend over past 3 months"}
        ])
    })


def create_mock_subprocess_result(stdout: str, returncode: int = 0, stderr: str = ""):
    """Helper to create mock subprocess.CompletedProcess"""
    result = Mock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.returncode = returncode
    result.stderr = stderr
    return result


# ==================== Constructor Tests ====================

def test_trends_collector_initialization(trends_collector, temp_cache_dir):
    """Test TrendsCollector initializes with correct parameters"""
    assert trends_collector.config is not None
    assert trends_collector.db_manager is not None
    assert trends_collector.deduplicator is not None
    assert trends_collector.cache_dir == Path(temp_cache_dir)
    assert trends_collector.region == "DE"
    assert trends_collector.rate_limit == 0.5
    assert trends_collector.query_health == {}
    assert trends_collector.last_request_time is None


def test_trends_collector_creates_cache_dir(mock_config, mock_db_manager, mock_deduplicator, tmp_path):
    """Test TrendsCollector creates cache directory if missing"""
    cache_dir = tmp_path / "new_trends_cache"
    assert not cache_dir.exists()

    TrendsCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=str(cache_dir)
    )

    assert cache_dir.exists()


# ==================== Trending Searches Tests ====================

@patch('subprocess.run')
def test_collect_trending_searches_success(mock_subprocess, trends_collector, mock_gemini_trending_response):
    """Test collecting trending searches successfully via Gemini CLI"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_trending_response)

    documents = trends_collector.collect_trending_searches(pn='germany')

    # Verify subprocess called
    assert mock_subprocess.called
    call_args = mock_subprocess.call_args[0][0]
    assert call_args[0] == 'gemini'
    assert isinstance(call_args[1], str)  # Prompt
    assert call_args[2] == '--output-format'
    assert call_args[3] == 'json'

    # Verify documents created
    assert len(documents) == 3
    assert all(isinstance(doc, Document) for doc in documents)
    assert documents[0].title == "PropTech Deutschland"
    assert documents[0].source == "trends_trending_searches_germany"
    assert "tech" in documents[0].content


@patch('subprocess.run')
def test_collect_trending_searches_empty(mock_subprocess, trends_collector):
    """Test handling of empty trending searches"""
    # Gemini returns empty array
    mock_subprocess.return_value = create_mock_subprocess_result(json.dumps({"response": "[]"}))

    documents = trends_collector.collect_trending_searches(pn='germany')

    assert len(documents) == 0


@patch('subprocess.run')
def test_collect_trending_searches_error(mock_subprocess, trends_collector):
    """Test error handling when Gemini CLI fails"""
    mock_subprocess.return_value = create_mock_subprocess_result("", returncode=1, stderr="Gemini CLI error")

    with pytest.raises(TrendsCollectorError, match="Gemini CLI failed"):
        trends_collector.collect_trending_searches(pn='germany')


# ==================== Related Queries Tests ====================

@patch('subprocess.run')
def test_collect_related_queries_top(mock_subprocess, trends_collector, mock_gemini_related_queries_response):
    """Test collecting top related queries via Gemini CLI"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_related_queries_response)

    documents = trends_collector.collect_related_queries(keywords=['PropTech'], query_type='top')

    # Verify subprocess called
    assert mock_subprocess.called

    # Verify documents created
    assert len(documents) == 3
    assert all(isinstance(doc, Document) for doc in documents)
    assert "Related query:" in documents[0].title
    assert "proptech startup" in documents[0].title


@patch('subprocess.run')
def test_collect_related_queries_rising(mock_subprocess, trends_collector, mock_gemini_related_queries_response):
    """Test collecting rising related queries via Gemini CLI"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_related_queries_response)

    documents = trends_collector.collect_related_queries(keywords=['PropTech'], query_type='rising')

    assert len(documents) == 3
    assert "Rising query:" in documents[0].title


@patch('subprocess.run')
def test_collect_related_queries_multiple_keywords(mock_subprocess, trends_collector):
    """Test collecting related queries for multiple keywords"""
    response = json.dumps({
        "response": json.dumps([
            {"keyword": "PropTech", "query": "proptech startup", "relevance": 100},
            {"keyword": "Smart Building", "query": "smart building automation", "relevance": 90}
        ])
    })
    mock_subprocess.return_value = create_mock_subprocess_result(response)

    documents = trends_collector.collect_related_queries(keywords=['PropTech', 'Smart Building'])

    assert len(documents) == 2
    # Verify keywords are different
    keywords_in_content = [doc.content for doc in documents]
    assert any("PropTech" in content for content in keywords_in_content)
    assert any("Smart Building" in content for content in keywords_in_content)


# ==================== Interest Over Time Tests ====================

@patch('subprocess.run')
def test_collect_interest_over_time_success(mock_subprocess, trends_collector, mock_gemini_interest_response):
    """Test collecting interest over time via Gemini CLI"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_interest_response)

    documents = trends_collector.collect_interest_over_time(keywords=['PropTech'])

    # Verify subprocess called
    assert mock_subprocess.called

    # Verify documents created
    assert len(documents) == 1
    assert isinstance(documents[0], Document)
    assert "Interest over time: PropTech" == documents[0].title
    assert "increasing" in documents[0].content
    assert "high" in documents[0].content


@patch('subprocess.run')
def test_collect_interest_over_time_custom_timeframe(mock_subprocess, trends_collector, mock_gemini_interest_response):
    """Test interest over time with custom timeframe"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_interest_response)

    documents = trends_collector.collect_interest_over_time(
        keywords=['PropTech'],
        timeframe='today 12-m'
    )

    assert len(documents) == 1
    # Verify timeframe was parsed (prompt should mention "past 12 months")
    call_args = mock_subprocess.call_args[0][0]
    assert 'past 12 months' in call_args[1] or 'past year' in call_args[1]


# ==================== Caching Tests ====================

@patch('subprocess.run')
def test_trending_searches_caching(mock_subprocess, trends_collector, mock_gemini_trending_response):
    """Test trending searches are cached (1 hour TTL)"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_trending_response)

    # First call - should hit Gemini CLI
    docs1 = trends_collector.collect_trending_searches(pn='germany')
    assert mock_subprocess.call_count == 1
    assert trends_collector._stats['cache_misses'] == 1

    # Second call - should use cache
    docs2 = trends_collector.collect_trending_searches(pn='germany')
    assert mock_subprocess.call_count == 1  # No additional call
    assert trends_collector._stats['cache_hits'] == 1

    # Results should be identical
    assert len(docs1) == len(docs2)
    assert docs1[0].title == docs2[0].title


@patch('subprocess.run')
def test_trending_searches_cache_expiry(mock_subprocess, trends_collector, mock_gemini_trending_response):
    """Test cache expires after TTL"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_trending_response)

    # First call
    trends_collector.collect_trending_searches(pn='germany')
    assert mock_subprocess.call_count == 1

    # Expire cache manually
    cache_key = "trending_searches_germany"
    trends_collector._cache[cache_key]['timestamp'] = datetime.now() - timedelta(hours=2)

    # Second call - cache expired, should hit Gemini CLI again
    trends_collector.collect_trending_searches(pn='germany')
    assert mock_subprocess.call_count == 2


@patch('subprocess.run')
def test_interest_over_time_caching(mock_subprocess, trends_collector, mock_gemini_interest_response):
    """Test interest data is cached (24 hour TTL)"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_interest_response)

    # First call
    trends_collector.collect_interest_over_time(keywords=['PropTech'])
    assert mock_subprocess.call_count == 1

    # Second call - should use cache
    trends_collector.collect_interest_over_time(keywords=['PropTech'])
    assert mock_subprocess.call_count == 1  # No additional call


# ==================== Query Health Tests ====================

@patch('subprocess.run')
def test_query_health_initialization(mock_subprocess, trends_collector, mock_gemini_trending_response):
    """Test query health is initialized on first query"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_trending_response)

    query_id = "trending_searches_germany"
    assert query_id not in trends_collector.query_health

    trends_collector.collect_trending_searches(pn='germany')

    assert query_id in trends_collector.query_health
    assert trends_collector.query_health[query_id].success_count == 1


@patch('subprocess.run')
def test_query_health_success_tracking(mock_subprocess, trends_collector, mock_gemini_trending_response):
    """Test query health tracks successful queries"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_trending_response)

    query_id = "trending_searches_germany"

    # Multiple successful queries
    for _ in range(3):
        # Clear cache to force new query
        trends_collector._cache.clear()
        trends_collector.collect_trending_searches(pn='germany')

    health = trends_collector.query_health[query_id]
    assert health.success_count == 3
    assert health.consecutive_failures == 0


@patch('subprocess.run')
def test_query_health_failure_tracking(mock_subprocess, trends_collector):
    """Test query health tracks failures"""
    mock_subprocess.return_value = create_mock_subprocess_result("", returncode=1, stderr="Error")

    query_id = "trending_searches_germany"

    # Trigger failure
    with pytest.raises(TrendsCollectorError):
        trends_collector.collect_trending_searches(pn='germany')

    health = trends_collector.query_health[query_id]
    assert health.failure_count == 1
    assert health.consecutive_failures == 1


@patch('subprocess.run')
def test_should_skip_unhealthy_query(mock_subprocess, trends_collector):
    """Test unhealthy queries are skipped"""
    mock_subprocess.return_value = create_mock_subprocess_result("", returncode=1, stderr="Error")


    # Trigger 5 consecutive failures
    for _ in range(5):
        with pytest.raises(TrendsCollectorError):
            trends_collector.collect_trending_searches(pn='germany')

    # Next call should be skipped (unhealthy)
    documents = trends_collector.collect_trending_searches(pn='germany')
    assert len(documents) == 0  # Skipped


# ==================== Document Creation Tests ====================

@patch('subprocess.run')
def test_document_creation_with_all_fields(mock_subprocess, trends_collector, mock_gemini_trending_response):
    """Test Document model is created with all required fields"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_trending_response)

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


@patch('subprocess.run')
def test_document_id_generation(mock_subprocess, trends_collector, mock_gemini_trending_response):
    """Test document ID generation is consistent"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_trending_response)

    # Collect twice (second from cache)
    docs1 = trends_collector.collect_trending_searches(pn='germany')
    docs2 = trends_collector.collect_trending_searches(pn='germany')

    # IDs should be consistent
    assert docs1[0].id == docs2[0].id
    assert docs1[1].id == docs2[1].id

    # IDs should be unique per document
    assert docs1[0].id != docs1[1].id


@patch('subprocess.run')
def test_skip_duplicate_documents(mock_subprocess, trends_collector, mock_gemini_trending_response):
    """Test duplicate documents are skipped"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_trending_response)

    # Mark first document as duplicate
    trends_collector.deduplicator.is_duplicate = Mock(side_effect=[True, False, False])

    documents = trends_collector.collect_trending_searches(pn='germany')

    # First document should be skipped
    assert len(documents) == 2  # Only 2 out of 3


# ==================== Statistics Tests ====================

@patch('subprocess.run')
def test_collection_statistics(mock_subprocess, trends_collector, mock_gemini_trending_response):
    """Test collection statistics are tracked"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_trending_response)

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

@patch('subprocess.run')
def test_network_error_handling(mock_subprocess, trends_collector):
    """Test handling of subprocess timeout"""
    mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd=['gemini'], timeout=30)

    with pytest.raises(TrendsCollectorError, match="timeout"):
        trends_collector.collect_trending_searches(pn='germany')


@patch('subprocess.run')
def test_invalid_region_handling(mock_subprocess, trends_collector):
    """Test handling of invalid region (Gemini still works)"""
    response = json.dumps({"response": "[]"})
    mock_subprocess.return_value = create_mock_subprocess_result(response)

    # Invalid region - Gemini should handle gracefully
    documents = trends_collector.collect_trending_searches(pn='invalid_region')
    assert len(documents) == 0  # Empty but no error


@patch('subprocess.run')
def test_gemini_cli_not_found(mock_subprocess, trends_collector):
    """Test handling when Gemini CLI not installed"""
    mock_subprocess.side_effect = FileNotFoundError("gemini command not found")

    with pytest.raises(TrendsCollectorError, match="Gemini CLI not found"):
        trends_collector.collect_trending_searches(pn='germany')


@patch('subprocess.run')
def test_invalid_json_response(mock_subprocess, trends_collector):
    """Test handling of invalid JSON from Gemini"""
    mock_subprocess.return_value = create_mock_subprocess_result("invalid json")

    with pytest.raises(TrendsCollectorError, match="Invalid JSON"):
        trends_collector.collect_trending_searches(pn='germany')


# ==================== Cache Persistence Tests ====================

@patch('subprocess.run')
def test_save_and_load_query_cache(mock_subprocess, trends_collector, mock_gemini_trending_response):
    """Test cache persistence to disk"""
    mock_subprocess.return_value = create_mock_subprocess_result(mock_gemini_trending_response)

    # Collect and cache
    docs1 = trends_collector.collect_trending_searches(pn='germany')

    # Save cache
    trends_collector.save_cache()

    # Create new collector (loads cache from disk)
    new_collector = TrendsCollector(
        config=trends_collector.config,
        db_manager=trends_collector.db_manager,
        deduplicator=trends_collector.deduplicator,
        cache_dir=str(trends_collector.cache_dir),
        region="DE"
    )

    # Should load from cache (no subprocess call)
    docs2 = new_collector.collect_trending_searches(pn='germany')

    assert len(docs2) == len(docs1)
    assert docs2[0].title == docs1[0].title
    # Subprocess should only be called once (first collector)
    assert mock_subprocess.call_count == 1

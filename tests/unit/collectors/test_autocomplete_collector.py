"""
Tests for Autocomplete Collector (Google Autocomplete Suggestions)

Test Coverage:
- Alphabet expansion (a-z patterns)
- Question prefix expansion (what, how, why, when, where, who)
- Preposition expansion (for, with, without, etc.)
- Multi-keyword batch collection
- Caching (30-day TTL)
- Rate limiting (10 req/sec - Google autocomplete is lenient)
- Error handling (network errors, invalid responses, rate limits)
- Document model creation with all required fields
- Deduplication integration
- Language support (de, en, fr, etc.)
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import httpx

from src.collectors.autocomplete_collector import (
    AutocompleteCollector,
    AutocompleteCollectorError,
    ExpansionType,
)
from src.models.document import Document


# ==================== Fixtures ====================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory for autocomplete collector"""
    cache_dir = tmp_path / "autocomplete_cache"
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
def autocomplete_collector(mock_config, mock_db_manager, mock_deduplicator, temp_cache_dir):
    """Create AutocompleteCollector instance for tests"""
    return AutocompleteCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=temp_cache_dir,
        language="de",  # German
        rate_limit=10.0,  # 10 req/sec
        request_timeout=10
    )


@pytest.fixture
def mock_autocomplete_response():
    """Mock Google autocomplete API successful response"""
    return [
        "proptech",  # Query echo
        [
            "proptech deutschland",
            "proptech startup",
            "proptech immobilien",
            "proptech software",
            "proptech trends 2025"
        ],
        [],  # Relevance scores (not used)
        {}   # Additional metadata (not used)
    ]


# ==================== Constructor Tests ====================

def test_autocomplete_collector_initialization(autocomplete_collector, temp_cache_dir):
    """Test AutocompleteCollector initializes with correct parameters"""
    assert autocomplete_collector.config is not None
    assert autocomplete_collector.db_manager is not None
    assert autocomplete_collector.deduplicator is not None
    assert autocomplete_collector.cache_dir == Path(temp_cache_dir)
    assert autocomplete_collector.language == "de"
    assert autocomplete_collector.rate_limit == 10.0
    assert autocomplete_collector.last_request_time is None
    assert autocomplete_collector._cache == {}


def test_autocomplete_collector_creates_cache_dir(mock_config, mock_db_manager, mock_deduplicator, tmp_path):
    """Test AutocompleteCollector creates cache directory if missing"""
    cache_dir = tmp_path / "new_autocomplete_cache"
    assert not cache_dir.exists()

    AutocompleteCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=str(cache_dir)
    )

    assert cache_dir.exists()


# ==================== Alphabet Expansion Tests ====================

@patch('httpx.get')
def test_collect_alphabet_expansion_success(mock_httpx_get, autocomplete_collector, mock_autocomplete_response):
    """Test collecting suggestions with alphabet expansion (a-z)"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=mock_autocomplete_response)
    )

    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['PropTech'],
        expansion_types=[ExpansionType.ALPHABET],
        max_per_keyword=5  # Limit to 5 letters for testing
    )

    # Should have results from alphabet expansion
    assert len(documents) > 0
    assert all(isinstance(doc, Document) for doc in documents)

    # Check first document structure
    doc = documents[0]
    assert doc.source == "autocomplete_suggestions"
    assert doc.language == "de"
    assert doc.domain == "SaaS"
    assert doc.market == "Germany"
    assert "proptech" in doc.title.lower()


@patch('httpx.get')
def test_alphabet_expansion_all_letters(mock_httpx_get, autocomplete_collector):
    """Test alphabet expansion covers all 26 letters"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion 1"], [], {}])
    )

    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.ALPHABET]
    )

    # Should make 26 requests (a-z)
    assert mock_httpx_get.call_count == 26


# ==================== Question Prefix Tests ====================

@patch('httpx.get')
def test_collect_question_prefix_success(mock_httpx_get, autocomplete_collector, mock_autocomplete_response):
    """Test collecting suggestions with question prefixes"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=mock_autocomplete_response)
    )

    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['PropTech'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    assert len(documents) > 0
    # Should make 6 requests (what, how, why, when, where, who)
    assert mock_httpx_get.call_count == 6


@patch('httpx.get')
def test_question_prefix_all_patterns(mock_httpx_get, autocomplete_collector):
    """Test question prefix covers all 6 patterns"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion"], [], {}])
    )

    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    # Verify all 6 question patterns were used
    calls = [call.args[0] for call in mock_httpx_get.call_args_list]
    assert any('what' in str(call) for call in calls)
    assert any('how' in str(call) for call in calls)
    assert any('why' in str(call) for call in calls)
    assert any('when' in str(call) for call in calls)
    assert any('where' in str(call) for call in calls)
    assert any('who' in str(call) for call in calls)


# ==================== Preposition Expansion Tests ====================

@patch('httpx.get')
def test_collect_preposition_expansion_success(mock_httpx_get, autocomplete_collector):
    """Test collecting suggestions with preposition patterns"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion 1", "suggestion 2"], [], {}])
    )

    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['PropTech'],
        expansion_types=[ExpansionType.PREPOSITIONS]
    )

    assert len(documents) > 0
    # Should make requests for: for, with, without, near, vs, versus
    assert mock_httpx_get.call_count >= 6


# ==================== Multi-Expansion Tests ====================

@patch('httpx.get')
def test_collect_multiple_expansion_types(mock_httpx_get, autocomplete_collector):
    """Test collecting with multiple expansion types"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion"], [], {}])
    )

    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.ALPHABET, ExpansionType.QUESTIONS, ExpansionType.PREPOSITIONS],
        max_per_keyword=3  # Limit alphabet to 3
    )

    # Should make 3 (alphabet) + 6 (questions) + 6 (prepositions) = 15 requests
    assert mock_httpx_get.call_count == 15


# ==================== Multi-Keyword Tests ====================

@patch('httpx.get')
def test_collect_multiple_keywords(mock_httpx_get, autocomplete_collector):
    """Test collecting suggestions for multiple keywords"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion"], [], {}])
    )

    autocomplete_collector.collect_suggestions(
        seed_keywords=['PropTech', 'Smart Building'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    # Should make 6 requests per keyword = 12 total
    assert mock_httpx_get.call_count == 12


# ==================== Caching Tests ====================

@patch('httpx.get')
def test_suggestions_caching(mock_httpx_get, autocomplete_collector):
    """Test suggestions are cached (30-day TTL)"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion"], [], {}])
    )

    # First call - should fetch from API
    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )
    first_call_count = mock_httpx_get.call_count

    # Second call - should use cache
    docs2 = autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    # No additional API calls
    assert mock_httpx_get.call_count == first_call_count
    assert len(docs2) > 0


@patch('httpx.get')
def test_suggestions_cache_expiry(mock_httpx_get, autocomplete_collector):
    """Test suggestions cache expires after 30 days"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion"], [], {}])
    )

    # First call
    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )
    first_call_count = mock_httpx_get.call_count

    # Manually expire cache
    cache_key = "autocomplete_test_questions"
    if cache_key in autocomplete_collector._cache:
        autocomplete_collector._cache[cache_key]['timestamp'] = datetime.now() - timedelta(days=31)

    # Second call - should fetch from API again
    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    # Should have made additional API calls
    assert mock_httpx_get.call_count > first_call_count


# ==================== Rate Limiting Tests ====================

@patch('httpx.get')
@patch('src.collectors.autocomplete_collector.time.sleep')
def test_rate_limiting_enforcement(mock_sleep, mock_httpx_get, autocomplete_collector):
    """Test rate limiting enforces delay between requests"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion"], [], {}])
    )

    # Clear cache to force requests
    autocomplete_collector._cache = {}

    # Make multiple requests
    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    # Should have rate limiting delays (not on first request)
    assert mock_sleep.call_count >= 5  # 6 requests - 1 = 5 delays


# ==================== Deduplication Tests ====================

@patch('httpx.get')
def test_deduplication_across_expansions(mock_httpx_get, autocomplete_collector):
    """Test duplicate suggestions are removed across expansion types"""
    # Return same suggestions for different queries
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["proptech deutschland", "proptech startup"], [], {}])
    )

    # Autocomplete deduplicator to detect duplicates for 2nd occurrence
    autocomplete_collector.deduplicator.is_duplicate.side_effect = [False, False, True, True]

    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['PropTech'],
        expansion_types=[ExpansionType.ALPHABET],
        max_per_keyword=2  # Only a, b
    )

    # Should have 2 unique documents (duplicates skipped)
    assert len(documents) == 2


# ==================== Document Creation Tests ====================

@patch('httpx.get')
def test_document_creation_with_all_fields(mock_httpx_get, autocomplete_collector):
    """Test Document is created with all required fields"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["proptech deutschland"], [], {}])
    )

    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['PropTech'],
        expansion_types=[ExpansionType.ALPHABET],
        max_per_keyword=1
    )

    doc = documents[0]

    # Required fields
    assert doc.id is not None
    assert doc.source == "autocomplete_suggestions"
    assert doc.source_url.startswith("https://suggestqueries.google.com")
    assert doc.canonical_url is not None
    assert doc.title == "proptech deutschland"
    assert doc.content is not None
    assert "seed keyword: proptech" in doc.content.lower()
    assert doc.language == "de"
    assert doc.domain == "SaaS"
    assert doc.market == "Germany"
    assert doc.vertical == "Proptech"

    # Timestamps
    assert doc.published_at is not None
    assert doc.fetched_at is not None
    assert isinstance(doc.published_at, datetime)
    assert isinstance(doc.fetched_at, datetime)


@patch('httpx.get')
def test_document_id_generation(mock_httpx_get, autocomplete_collector):
    """Test Document IDs are unique and deterministic"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion 1", "suggestion 2"], [], {}])
    )

    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.ALPHABET],
        max_per_keyword=1
    )

    # All IDs should be unique
    ids = [doc.id for doc in documents]
    assert len(ids) == len(set(ids))

    # IDs should be deterministic (based on source + title)
    assert documents[0].id == autocomplete_collector._generate_document_id(
        "autocomplete_suggestions",
        documents[0].title
    )


# ==================== Statistics Tests ====================

@patch('httpx.get')
def test_collection_statistics(mock_httpx_get, autocomplete_collector):
    """Test collection statistics are tracked"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion 1", "suggestion 2"], [], {}])
    )

    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    stats = autocomplete_collector.get_statistics()
    assert stats['total_requests'] >= 6  # 6 question patterns
    assert stats['total_suggestions'] >= len(documents)
    assert stats['cache_hits'] >= 0
    assert stats['cache_misses'] >= 6


# ==================== Error Handling Tests ====================

@patch('httpx.get')
def test_network_error_handling(mock_httpx_get, autocomplete_collector):
    """Test network error handling"""
    mock_httpx_get.side_effect = httpx.ConnectError("Network error")

    with pytest.raises(AutocompleteCollectorError, match="Failed to collect suggestions"):
        autocomplete_collector.collect_suggestions(
            seed_keywords=['test'],
            expansion_types=[ExpansionType.ALPHABET],
            max_per_keyword=1
        )


@patch('httpx.get')
def test_invalid_json_response(mock_httpx_get, autocomplete_collector):
    """Test handling of invalid JSON response"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(side_effect=ValueError("Invalid JSON"))
    )

    with pytest.raises(AutocompleteCollectorError):
        autocomplete_collector.collect_suggestions(
            seed_keywords=['test'],
            expansion_types=[ExpansionType.ALPHABET],
            max_per_keyword=1
        )


@patch('httpx.get')
def test_http_error_handling(mock_httpx_get, autocomplete_collector):
    """Test HTTP error handling (rate limits, 500 errors)"""
    mock_httpx_get.return_value = Mock(
        status_code=429,
        json=Mock(return_value=["query", [], [], {}])
    )

    with pytest.raises(AutocompleteCollectorError, match="HTTP error"):
        autocomplete_collector.collect_suggestions(
            seed_keywords=['test'],
            expansion_types=[ExpansionType.ALPHABET],
            max_per_keyword=1
        )


@patch('httpx.get')
def test_empty_suggestions_handling(mock_httpx_get, autocomplete_collector):
    """Test handling of empty suggestions (no results)"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", [], [], {}])
    )

    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.ALPHABET],
        max_per_keyword=1
    )

    assert documents == []


# ==================== Language Support Tests ====================

@patch('httpx.get')
def test_language_parameter_german(mock_httpx_get, autocomplete_collector):
    """Test German language parameter is used"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion"], [], {}])
    )

    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.ALPHABET],
        max_per_keyword=1
    )

    # Verify language parameter in request
    call_url = mock_httpx_get.call_args[0][0]
    assert 'hl=de' in call_url


@patch('httpx.get')
def test_language_parameter_english(mock_httpx_get, mock_config, mock_db_manager, mock_deduplicator, temp_cache_dir):
    """Test English language parameter"""
    collector = AutocompleteCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=temp_cache_dir,
        language="en"
    )

    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion"], [], {}])
    )

    collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.ALPHABET],
        max_per_keyword=1
    )

    call_url = mock_httpx_get.call_args[0][0]
    assert 'hl=en' in call_url


# ==================== Save/Load Cache Tests ====================

@patch('httpx.get')
def test_save_and_load_suggestions_cache(mock_httpx_get, autocomplete_collector):
    """Test suggestions cache persistence"""
    mock_httpx_get.return_value = Mock(
        status_code=200,
        json=Mock(return_value=["query", ["suggestion"], [], {}])
    )

    # Collect and cache
    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    # Save cache
    autocomplete_collector.save_cache()

    # Create new collector and load cache
    new_collector = AutocompleteCollector(
        config=autocomplete_collector.config,
        db_manager=autocomplete_collector.db_manager,
        deduplicator=autocomplete_collector.deduplicator,
        cache_dir=str(autocomplete_collector.cache_dir)
    )
    new_collector.load_cache()

    # Should find cached data
    assert len(new_collector._cache) > 0

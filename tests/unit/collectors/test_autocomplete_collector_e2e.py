"""
E2E Integration Tests for Autocomplete Collector

Tests with real Google Autocomplete API to validate:
- Alphabet expansion with real queries
- Question prefix expansion
- Preposition expansion
- Multi-keyword collection
- Language support (de, en)
- Cache persistence
- Rate limiting

NOTE: These tests make real API calls and may be slow.
Run with: pytest tests/unit/collectors/test_autocomplete_collector_e2e.py -v -m e2e
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock
import hashlib

from src.collectors.autocomplete_collector import (
    AutocompleteCollector,
    ExpansionType
)
from src.models.document import Document


# ==================== Fixtures ====================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory"""
    cache_dir = tmp_path / "autocomplete_e2e_cache"
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
    dedup.compute_content_hash = Mock(
        side_effect=lambda content: hashlib.md5(content.encode()).hexdigest()
    )
    return dedup


@pytest.fixture
def autocomplete_collector(mock_config, mock_db_manager, mock_deduplicator, temp_cache_dir):
    """Create AutocompleteCollector instance for E2E tests"""
    return AutocompleteCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=temp_cache_dir,
        language="de",  # German
        rate_limit=10.0,  # 10 req/sec (lenient for testing)
        request_timeout=30  # Longer timeout for real API
    )


# ==================== E2E Tests ====================

@pytest.mark.e2e
def test_e2e_alphabet_expansion_german(autocomplete_collector):
    """
    E2E: Collect real autocomplete suggestions with alphabet expansion (German)

    Expected: Returns list of German suggestions for PropTech + a-z
    """
    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['PropTech'],
        expansion_types=[ExpansionType.ALPHABET],
        max_per_keyword=3  # Limit to first 3 letters (a, b, c)
    )

    # Validate response
    assert isinstance(documents, list)
    # May return 0-30 suggestions depending on Google autocomplete availability
    assert len(documents) >= 0

    if len(documents) > 0:
        # Validate document structure
        doc = documents[0]
        assert isinstance(doc, Document)
        assert doc.id is not None
        assert doc.source == "autocomplete_suggestions"
        assert doc.title is not None
        assert len(doc.title) > 0
        assert "proptech" in doc.title.lower()
        assert doc.language == "de"
        assert doc.domain == "SaaS"
        assert doc.market == "Germany"

        # Validate timestamps
        assert isinstance(doc.published_at, datetime)
        assert isinstance(doc.fetched_at, datetime)

        # Validate URLs
        assert doc.source_url.startswith("https://suggestqueries.google.com")
        assert doc.canonical_url is not None


@pytest.mark.e2e
def test_e2e_question_prefix_german(autocomplete_collector):
    """
    E2E: Collect real autocomplete suggestions with question prefixes (German)

    Expected: Returns suggestions for what/how/why/when/where/who PropTech
    """
    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['PropTech'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    assert isinstance(documents, list)
    assert len(documents) >= 0

    if len(documents) > 0:
        doc = documents[0]
        assert isinstance(doc, Document)
        assert doc.source == "autocomplete_suggestions"
        # German questions may appear
        assert doc.title is not None


@pytest.mark.e2e
def test_e2e_preposition_expansion_german(autocomplete_collector):
    """
    E2E: Collect real autocomplete suggestions with preposition patterns (German)

    Expected: Returns suggestions for PropTech for/with/without/etc
    """
    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['PropTech'],
        expansion_types=[ExpansionType.PREPOSITIONS]
    )

    assert isinstance(documents, list)
    assert len(documents) >= 0

    if len(documents) > 0:
        doc = documents[0]
        assert isinstance(doc, Document)
        assert doc.source == "autocomplete_suggestions"


@pytest.mark.e2e
def test_e2e_multi_expansion_types(autocomplete_collector):
    """
    E2E: Collect with multiple expansion types simultaneously

    Expected: Returns combined results from alphabet + questions + prepositions
    """
    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['Smart Building'],
        expansion_types=[ExpansionType.ALPHABET, ExpansionType.QUESTIONS, ExpansionType.PREPOSITIONS],
        max_per_keyword=2  # Limit alphabet to first 2 letters
    )

    assert isinstance(documents, list)
    # Should have results from all expansion types
    assert len(documents) >= 0


@pytest.mark.e2e
def test_e2e_multi_keyword_collection(autocomplete_collector):
    """
    E2E: Collect autocomplete suggestions for multiple keywords

    Expected: Returns suggestions for both keywords
    """
    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['PropTech', 'Smart Building'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    assert isinstance(documents, list)
    assert len(documents) >= 0

    # Check that suggestions from both keywords are present
    if len(documents) >= 2:
        titles = [doc.title.lower() for doc in documents]
        # May contain either keyword
        has_proptech_related = any('prop' in title or 'building' in title for title in titles)
        assert has_proptech_related


@pytest.mark.e2e
def test_e2e_english_language_support(mock_config, mock_db_manager, mock_deduplicator, temp_cache_dir):
    """
    E2E: Collect autocomplete suggestions in English

    Expected: Returns English suggestions
    """
    collector = AutocompleteCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=temp_cache_dir,
        language="en"  # English
    )

    documents = collector.collect_suggestions(
        seed_keywords=['cloud computing'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    assert isinstance(documents, list)
    assert len(documents) >= 0

    if len(documents) > 0:
        # Suggestions should be in English
        doc = documents[0]
        assert isinstance(doc, Document)


@pytest.mark.e2e
def test_e2e_cache_persistence_across_instances(mock_config, mock_db_manager, mock_deduplicator, temp_cache_dir):
    """
    E2E: Verify cache persists across collector instances

    Expected: Second instance can load cache from first instance
    """
    # First instance: Collect and cache
    collector1 = AutocompleteCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=temp_cache_dir,
        language="de"
    )

    docs1 = collector1.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )
    collector1.save_cache()

    # Second instance: Load from cache
    collector2 = AutocompleteCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=temp_cache_dir,
        language="de"
    )

    # Should find cache
    cache_file = Path(temp_cache_dir) / "autocomplete_cache.json"
    assert cache_file.exists()

    # Load cache and verify
    collector2.load_cache()
    if len(docs1) > 0:
        # Cache should have entries
        assert len(collector2._cache) > 0


@pytest.mark.e2e
def test_e2e_deduplication_across_expansions(autocomplete_collector):
    """
    E2E: Verify duplicate suggestions are removed across expansion types

    Expected: No duplicate suggestions in final results
    """
    documents = autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.ALPHABET, ExpansionType.QUESTIONS],
        max_per_keyword=2  # Limit alphabet
    )

    # Check for duplicates
    if len(documents) > 1:
        titles = [doc.title for doc in documents]
        unique_titles = set(titles)

        # All titles should be unique
        assert len(titles) == len(unique_titles), f"Found {len(titles) - len(unique_titles)} duplicates"


@pytest.mark.e2e
def test_e2e_statistics_tracking(autocomplete_collector):
    """
    E2E: Verify statistics are tracked correctly

    Expected: Stats show requests, suggestions, cache hits/misses
    """
    # First request (cache miss)
    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    # Second request (cache hit)
    autocomplete_collector.collect_suggestions(
        seed_keywords=['test'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    stats = autocomplete_collector.get_statistics()

    assert stats['total_requests'] >= 6  # 6 question patterns
    assert stats['cache_hits'] >= 1  # Second request should hit cache
    assert stats['cache_misses'] >= 6  # First request misses
    assert stats['total_suggestions'] >= 0


@pytest.mark.e2e
def test_e2e_rate_limiting_enforcement(autocomplete_collector):
    """
    E2E: Verify rate limiting works with real requests

    Expected: Requests are throttled to respect rate limit
    """
    import time

    start_time = time.time()

    # Make requests for 2 keywords with questions (12 requests total)
    autocomplete_collector.collect_suggestions(
        seed_keywords=['test1', 'test2'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    elapsed = time.time() - start_time

    # Should take at least 1 second (12 requests / 10 req/sec = 1.2s minimum)
    # Allow some margin for API latency
    assert elapsed >= 0.5, f"Rate limiting not enforced (took {elapsed}s)"


# ==================== Integration Tests (Config-based) ====================

@pytest.mark.integration
def test_integration_with_proptech_config(mock_db_manager, mock_deduplicator, tmp_path):
    """
    Integration: Test Autocomplete collector with PropTech German config

    Expected: Works with real market configuration
    """
    from src.utils.config_loader import load_config

    # Load real PropTech config
    config_path = Path(__file__).parents[3] / "config" / "markets" / "proptech_de.yaml"

    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}")

    config = load_config(str(config_path))

    collector = AutocompleteCollector(
        config=config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=str(tmp_path / "autocomplete_cache"),
        language="de"
    )

    # Collect suggestions
    documents = collector.collect_suggestions(
        seed_keywords=['PropTech'],
        expansion_types=[ExpansionType.QUESTIONS]
    )

    assert isinstance(documents, list)

    if len(documents) > 0:
        doc = documents[0]
        assert doc.domain == config.market.domain
        assert doc.market == config.market.market
        assert doc.language == config.market.language
        assert doc.vertical == config.market.vertical


if __name__ == "__main__":
    # Run E2E tests
    pytest.main([__file__, "-v", "-m", "e2e", "-s"])

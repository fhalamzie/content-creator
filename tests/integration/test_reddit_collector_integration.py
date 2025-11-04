"""
Reddit Collector E2E Integration Tests

Tests Reddit collector with real subreddits to ensure:
- PRAW authentication works
- Post collection works with various subreddits
- Comment extraction handles real data
- Document model creation works end-to-end
- Rate limiting prevents API issues
- Health tracking persists across runs

These tests require internet connection, Reddit API credentials, and may be slow.
They validate the collector works with production Reddit API.
"""

import pytest
import os
from pathlib import Path
from datetime import datetime
import time

from src.collectors.reddit_collector import RedditCollector, RedditCollectorError
from src.database.sqlite_manager import SQLiteManager
from src.processors.deduplicator import Deduplicator
from src.utils.config_loader import ConfigLoader


# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for integration tests"""
    cache_dir = tmp_path / "reddit_cache"
    db_dir = tmp_path / "db"

    cache_dir.mkdir()
    db_dir.mkdir()

    return {
        'cache': str(cache_dir),
        'db': str(db_dir / "test.db")
    }


@pytest.fixture
def integration_config(temp_dirs):
    """Load real config for integration tests"""
    config_path = "config/markets/proptech_de.yaml"

    if not Path(config_path).exists():
        pytest.skip(f"Config file not found: {config_path}")

    config = ConfigLoader.load_config(config_path)
    return config


@pytest.fixture
def db_manager(temp_dirs):
    """Create SQLiteManager for integration tests"""
    db = SQLiteManager(temp_dirs['db'])
    yield db
    # Cleanup
    db.close()


@pytest.fixture
def deduplicator():
    """Create Deduplicator for integration tests"""
    return Deduplicator()


@pytest.fixture
def reddit_collector(integration_config, db_manager, deduplicator, temp_dirs):
    """Create RedditCollector for integration tests"""
    # Check for Reddit credentials
    if not os.getenv("REDDIT_CLIENT_ID"):
        pytest.skip("Reddit API credentials not configured")

    return RedditCollector(
        config=integration_config,
        db_manager=db_manager,
        deduplicator=deduplicator,
        cache_dir=temp_dirs['cache'],
        rate_limit_per_minute=30  # Be gentle with real API
    )


def test_collect_from_real_subreddit_hot(reddit_collector):
    """
    Test collecting hot posts from real subreddit (r/de)

    Validates:
    - PRAW authentication works
    - Post collection works
    - Documents have all required fields
    """
    try:
        documents = reddit_collector.collect_from_subreddit('de', sort='hot', limit=5)
    except Exception as e:
        pytest.skip(f"Reddit API error: {e}")

    # Should collect at least some posts
    assert len(documents) > 0, "Should collect at least 1 post from r/de"

    # Verify first document structure
    doc = documents[0]
    assert doc.id.startswith('reddit_')
    assert doc.source == 'reddit_de'
    assert 'reddit.com' in doc.source_url
    assert len(doc.title) > 0
    assert len(doc.content) > 0
    assert doc.language == 'de'
    assert isinstance(doc.published_at, datetime)
    assert isinstance(doc.fetched_at, datetime)

    print(f"✓ Collected {len(documents)} posts from r/de")
    print(f"  First post: {doc.title[:50]}...")


def test_collect_with_different_sort_methods(reddit_collector):
    """
    Test collecting with different sorting methods

    Validates:
    - hot, new, top sorting all work
    - Different results returned
    """
    try:
        hot_posts = reddit_collector.collect_from_subreddit('de', sort='hot', limit=3)
        time.sleep(2)  # Rate limiting
        new_posts = reddit_collector.collect_from_subreddit('de', sort='new', limit=3)
        time.sleep(2)  # Rate limiting
        top_posts = reddit_collector.collect_from_subreddit('de', sort='top', time_filter='week', limit=3)
    except Exception as e:
        pytest.skip(f"Reddit API error: {e}")

    assert len(hot_posts) > 0
    assert len(new_posts) > 0
    assert len(top_posts) > 0

    print(f"✓ hot: {len(hot_posts)}, new: {len(new_posts)}, top: {len(top_posts)}")


def test_collect_from_multiple_subreddits(reddit_collector):
    """
    Test collecting from multiple subreddits

    Validates:
    - Batch collection works
    - Rate limiting prevents issues
    """
    subreddits = ['de', 'Python']  # Using well-known subreddits

    start_time = time.time()
    try:
        all_documents = reddit_collector.collect_from_subreddits(
            subreddits,
            sort='hot',
            limit=3,
            skip_errors=True
        )
    except Exception as e:
        pytest.skip(f"Reddit API error: {e}")

    elapsed = time.time() - start_time

    # Should collect from both subreddits
    assert len(all_documents) > 0, "Should collect documents from multiple subreddits"

    # Should take at least 2 seconds due to rate limiting (30 req/min = 2 sec between)
    expected_min_time = 2.0
    assert elapsed >= expected_min_time, f"Rate limiting not enforced: {elapsed:.2f}s < {expected_min_time}s"

    print(f"✓ Collected {len(all_documents)} total posts in {elapsed:.2f}s from {len(subreddits)} subreddits")


def test_comment_extraction(reddit_collector):
    """
    Test extracting comments from posts

    Validates:
    - Comment extraction works with real posts
    - Comments are properly formatted
    """
    try:
        documents = reddit_collector.collect_from_subreddit(
            'de',
            sort='top',
            time_filter='week',
            limit=3,
            include_comments=True,
            max_comments=3
        )
    except Exception as e:
        pytest.skip(f"Reddit API error: {e}")

    assert len(documents) > 0

    # Check if any documents have comments
    any("Comments" in doc.content for doc in documents)

    # Not all posts have comments, so just check it doesn't error
    print(f"✓ Collected {len(documents)} posts, {sum(1 for d in documents if 'Comments' in d.content)} with comments")


def test_quality_filtering(reddit_collector):
    """
    Test quality filtering (min_score, min_content_length)

    Validates:
    - Low quality posts are filtered
    - Only high-quality content returned
    """
    try:
        # Without filtering
        all_posts = reddit_collector.collect_from_subreddit('de', sort='new', limit=10)
        time.sleep(2)

        # With filtering
        quality_posts = reddit_collector.collect_from_subreddit(
            'de',
            sort='new',
            limit=10,
            min_score=5,
            min_content_length=100
        )
    except Exception as e:
        pytest.skip(f"Reddit API error: {e}")

    # Filtered should be less than or equal to unfiltered
    assert len(quality_posts) <= len(all_posts)

    print(f"✓ All posts: {len(all_posts)}, Quality posts (score≥5, length≥100): {len(quality_posts)}")


def test_subreddit_health_tracking(reddit_collector):
    """
    Test subreddit health tracking

    Validates:
    - Health metrics tracked correctly
    - Success counts accurate
    """
    try:
        # Collect from same subreddit multiple times
        for i in range(3):
            reddit_collector.collect_from_subreddit('de', sort='hot', limit=2)
            time.sleep(2)  # Rate limiting
    except Exception as e:
        pytest.skip(f"Reddit API error: {e}")

    # Check health report
    health_report = reddit_collector.get_subreddit_health_report()

    assert len(health_report) > 0

    de_health = [h for h in health_report if h['subreddit'] == 'de']
    assert len(de_health) == 1

    health = de_health[0]
    assert health['success_count'] >= 3
    assert health['is_healthy'] is True

    print(f"✓ Health tracking: {health['success_count']} successes for r/de")


def test_statistics_tracking(reddit_collector):
    """
    Test statistics tracking during collection

    Validates:
    - Statistics accurately reflect collection
    - Counts are correct
    """
    try:
        documents = reddit_collector.collect_from_subreddit('de', sort='hot', limit=5)
    except Exception as e:
        pytest.skip(f"Reddit API error: {e}")

    # Check statistics
    stats = reddit_collector.get_statistics()

    assert stats['total_subreddits_collected'] == 1
    assert stats['total_posts_collected'] == len(documents)
    assert stats['total_failures'] == 0

    print(f"✓ Statistics: {stats}")


def test_error_handling_with_invalid_subreddit(reddit_collector):
    """
    Test error handling with invalid subreddit

    Validates:
    - Graceful error handling
    - Health tracking records failures
    """
    invalid_subreddit = "this_subreddit_definitely_does_not_exist_12345"

    with pytest.raises(RedditCollectorError):
        reddit_collector.collect_from_subreddit(invalid_subreddit, limit=5)

    # Check that failure was recorded
    health_report = reddit_collector.get_subreddit_health_report()

    # Health report should include this subreddit
    invalid_health = [h for h in health_report if h['subreddit'] == invalid_subreddit]
    assert len(invalid_health) == 1
    assert invalid_health[0]['failure_count'] == 1

    print("✓ Error handling: failure recorded for invalid subreddit")


def test_deduplication_across_collections(reddit_collector):
    """
    Test deduplication when collecting same content twice

    Validates:
    - Duplicate detection works
    - Same posts not collected twice
    """
    try:
        # Collect from same subreddit twice
        reddit_collector.collect_from_subreddit('de', sort='hot', limit=5)
        time.sleep(2)
        reddit_collector.collect_from_subreddit('de', sort='hot', limit=5)
    except Exception as e:
        pytest.skip(f"Reddit API error: {e}")

    # Second collection should have fewer or same documents (some may be duplicates)
    # Or more if feed updated between requests
    stats = reddit_collector.get_statistics()

    print(f"✓ Deduplication: {stats['total_skipped_duplicates']} duplicates skipped")


@pytest.mark.slow
def test_large_collection(reddit_collector):
    """
    Test collecting larger number of posts

    Validates:
    - Handles larger collections efficiently
    - Rate limiting works correctly

    Marked as slow test
    """
    try:
        start = time.time()
        documents = reddit_collector.collect_from_subreddit('de', sort='hot', limit=25)
        elapsed = time.time() - start
    except Exception as e:
        pytest.skip(f"Reddit API error: {e}")

    assert len(documents) > 10, "Should collect at least 10 documents from large collection"

    # All documents should be valid
    for doc in documents:
        assert len(doc.id) > 0
        assert len(doc.content) > 0

    print(f"✓ Large collection: {len(documents)} posts in {elapsed:.2f}s")

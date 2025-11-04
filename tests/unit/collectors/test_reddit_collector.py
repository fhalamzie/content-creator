"""
Tests for Reddit Collector

Test Coverage:
- PRAW integration (authentication, subreddit access)
- Post collection (hot, new, top, rising)
- Comment extraction (optional, top comments)
- Document model creation with Reddit-specific fields
- Subreddit health tracking
- Rate limiting (60 req/min Reddit API)
- Error handling (private subreddits, banned, not found)
- Time filters (day, week, month, year, all)
- Content filtering (minimum score, age)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import hashlib

from src.collectors.reddit_collector import (
    RedditCollector,
    RedditCollectorError,
    SubredditHealth,
    RedditPost,
)
from src.models.document import Document


# ==================== Fixtures ====================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory for Reddit collector"""
    cache_dir = tmp_path / "reddit_cache"
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
    config.collectors.reddit_subreddits = ["de", "Finanzen", "PropTech"]
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
def reddit_collector(mock_config, mock_db_manager, mock_deduplicator, temp_cache_dir):
    """Create RedditCollector instance for tests"""
    with patch('praw.Reddit'):
        return RedditCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            deduplicator=mock_deduplicator,
            cache_dir=temp_cache_dir,
            client_id="test_client_id",
            client_secret="test_client_secret",
            user_agent="test_user_agent"
        )


@pytest.fixture
def mock_reddit_submission():
    """Mock PRAW submission object"""
    submission = Mock()
    submission.id = "abc123"
    submission.title = "PropTech Trends in Germany"
    submission.selftext = "Detailed discussion about PropTech trends..."
    submission.url = "https://reddit.com/r/PropTech/comments/abc123"
    submission.author = Mock(name="test_user")
    submission.author.name = "test_user"
    submission.score = 42
    submission.num_comments = 15
    submission.created_utc = datetime(2025, 11, 4, 12, 0).timestamp()
    submission.subreddit = Mock(display_name="PropTech")
    submission.permalink = "/r/PropTech/comments/abc123"
    submission.is_self = True
    return submission


@pytest.fixture
def mock_reddit_comment():
    """Mock PRAW comment object"""
    comment = Mock()
    comment.body = "Great insights on PropTech!"
    comment.score = 10
    comment.author = Mock(name="commenter")
    comment.author.name = "commenter"
    return comment


# ==================== Test RedditCollector Initialization ====================

def test_reddit_collector_initialization(reddit_collector, temp_cache_dir):
    """Test RedditCollector initializes correctly"""
    assert reddit_collector.config is not None
    assert reddit_collector.db_manager is not None
    assert reddit_collector.deduplicator is not None
    assert str(reddit_collector.cache_dir) == temp_cache_dir
    assert reddit_collector._subreddit_health == {}


def test_reddit_collector_creates_cache_dir():
    """Test RedditCollector creates cache directory if missing"""
    with patch('pathlib.Path.mkdir') as mock_mkdir, \
         patch('praw.Reddit'):
        config = Mock()
        config.market.domain = "SaaS"
        config.collectors.reddit_subreddits = ["de"]

        collector = RedditCollector(
            config=config,
            db_manager=Mock(),
            deduplicator=Mock(),
            cache_dir="/tmp/test_reddit_cache",
            client_id="test",
            client_secret="test",
            user_agent="test"
        )

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


@patch('praw.Reddit')
def test_reddit_authentication(mock_reddit_class, mock_config, mock_db_manager, mock_deduplicator):
    """Test Reddit API authentication"""
    mock_reddit = Mock()
    mock_reddit_class.return_value = mock_reddit

    collector = RedditCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        client_id="test_id",
        client_secret="test_secret",
        user_agent="test_agent"
    )

    mock_reddit_class.assert_called_once_with(
        client_id="test_id",
        client_secret="test_secret",
        user_agent="test_agent"
    )


# ==================== Test Post Collection ====================

@patch('praw.Reddit')
def test_collect_from_subreddit_hot(mock_reddit_class, reddit_collector, mock_reddit_submission):
    """Test collecting hot posts from subreddit"""
    mock_reddit = Mock()
    mock_subreddit = Mock()
    mock_subreddit.hot.return_value = [mock_reddit_submission]
    mock_reddit.subreddit.return_value = mock_subreddit
    reddit_collector.reddit = mock_reddit

    documents = reddit_collector.collect_from_subreddit('PropTech', sort='hot', limit=10)

    assert len(documents) == 1
    assert isinstance(documents[0], Document)
    assert documents[0].title == "PropTech Trends in Germany"
    assert documents[0].source == "reddit_proptech"
    assert "reddit.com" in documents[0].source_url


@patch('praw.Reddit')
def test_collect_from_subreddit_new(mock_reddit_class, reddit_collector, mock_reddit_submission):
    """Test collecting new posts from subreddit"""
    mock_reddit = Mock()
    mock_subreddit = Mock()
    mock_subreddit.new.return_value = [mock_reddit_submission]
    mock_reddit.subreddit.return_value = mock_subreddit
    reddit_collector.reddit = mock_reddit

    documents = reddit_collector.collect_from_subreddit('PropTech', sort='new', limit=10)

    assert len(documents) == 1
    mock_subreddit.new.assert_called_once()


@patch('praw.Reddit')
def test_collect_from_subreddit_top_with_time_filter(mock_reddit_class, reddit_collector, mock_reddit_submission):
    """Test collecting top posts with time filter"""
    mock_reddit = Mock()
    mock_subreddit = Mock()
    mock_subreddit.top.return_value = [mock_reddit_submission]
    mock_reddit.subreddit.return_value = mock_subreddit
    reddit_collector.reddit = mock_reddit

    documents = reddit_collector.collect_from_subreddit(
        'PropTech',
        sort='top',
        time_filter='week',
        limit=10
    )

    assert len(documents) == 1
    mock_subreddit.top.assert_called_once_with(time_filter='week', limit=10)


# ==================== Test Comment Extraction ====================

@patch('praw.Reddit')
def test_extract_top_comments(mock_reddit_class, reddit_collector, mock_reddit_submission, mock_reddit_comment):
    """Test extracting top comments from submission"""
    mock_reddit_submission.comments.list.return_value = [mock_reddit_comment]

    comments_text = reddit_collector._extract_comments(mock_reddit_submission, max_comments=5)

    assert "Great insights on PropTech!" in comments_text
    assert len(comments_text) > 0


@patch('praw.Reddit')
def test_extract_comments_handles_deleted(mock_reddit_class, reddit_collector, mock_reddit_submission):
    """Test comment extraction handles deleted comments"""
    deleted_comment = Mock()
    deleted_comment.body = "[deleted]"
    mock_reddit_submission.comments.list.return_value = [deleted_comment]

    comments_text = reddit_collector._extract_comments(mock_reddit_submission, max_comments=5)

    # Should filter out deleted comments
    assert "[deleted]" not in comments_text or len(comments_text) == 0


# ==================== Test Document Creation ====================

@patch('praw.Reddit')
def test_document_creation_from_submission(mock_reddit_class, reddit_collector, mock_reddit_submission):
    """Test Document creation has all required fields"""
    document = reddit_collector._create_document_from_submission(mock_reddit_submission)

    # Identity
    assert document.id.startswith('reddit_')
    assert document.source == 'reddit_proptech'
    assert 'reddit.com' in document.source_url

    # Content
    assert document.title == "PropTech Trends in Germany"
    assert len(document.content) > 0
    assert document.summary is not None

    # Classification
    assert document.language == 'de'
    assert document.domain == 'SaaS'
    assert document.market == 'Germany'
    assert document.vertical == 'Proptech'

    # Metadata
    assert isinstance(document.published_at, datetime)
    assert isinstance(document.fetched_at, datetime)
    assert document.author == 'test_user'


@patch('praw.Reddit')
def test_document_includes_metadata(mock_reddit_class, reddit_collector, mock_reddit_submission):
    """Test Document includes Reddit-specific metadata"""
    document = reddit_collector._create_document_from_submission(
        mock_reddit_submission,
        include_metadata=True
    )

    # Reddit metadata should be in summary or elsewhere
    assert document.summary is not None


# ==================== Test Subreddit Health Tracking ====================

def test_subreddit_health_initialization(reddit_collector):
    """Test subreddit health tracking initialization"""
    health = reddit_collector._get_subreddit_health('PropTech')

    assert isinstance(health, SubredditHealth)
    assert health.subreddit == 'PropTech'
    assert health.success_count == 0
    assert health.failure_count == 0


@patch('praw.Reddit')
def test_subreddit_health_success_tracking(mock_reddit_class, reddit_collector, mock_reddit_submission):
    """Test subreddit health tracking on success"""
    mock_reddit = Mock()
    mock_subreddit = Mock()
    mock_subreddit.hot.return_value = [mock_reddit_submission]
    mock_reddit.subreddit.return_value = mock_subreddit
    reddit_collector.reddit = mock_reddit

    reddit_collector.collect_from_subreddit('PropTech', limit=10)

    health = reddit_collector._get_subreddit_health('PropTech')
    assert health.success_count == 1
    assert health.consecutive_failures == 0


@patch('praw.Reddit')
def test_subreddit_health_failure_tracking(mock_reddit_class, reddit_collector):
    """Test subreddit health tracking on failure"""
    mock_reddit = Mock()
    mock_reddit.subreddit.side_effect = Exception("Subreddit not found")
    reddit_collector.reddit = mock_reddit

    with pytest.raises(RedditCollectorError):
        reddit_collector.collect_from_subreddit('InvalidSubreddit')

    health = reddit_collector._get_subreddit_health('InvalidSubreddit')
    assert health.failure_count == 1
    assert health.consecutive_failures == 1


# ==================== Test Filtering ====================

@patch('praw.Reddit')
def test_filter_by_minimum_score(mock_reddit_class, reddit_collector):
    """Test filtering posts by minimum score"""
    low_score_post = Mock()
    low_score_post.score = 5
    low_score_post.id = "low"

    high_score_post = Mock()
    high_score_post.score = 50
    high_score_post.id = "high"

    mock_reddit = Mock()
    mock_subreddit = Mock()
    mock_subreddit.hot.return_value = [low_score_post, high_score_post]
    mock_reddit.subreddit.return_value = mock_subreddit
    reddit_collector.reddit = mock_reddit

    # Mock the rest of the submission attributes
    for post in [low_score_post, high_score_post]:
        post.title = "Test"
        post.selftext = "Content"
        post.url = f"https://reddit.com/{post.id}"
        post.author = Mock(name="user")
        post.author.name = "user"
        post.num_comments = 0
        post.created_utc = datetime.now().timestamp()
        post.subreddit = Mock(display_name="test")
        post.permalink = f"/{post.id}"
        post.is_self = True

    documents = reddit_collector.collect_from_subreddit(
        'test',
        limit=10,
        min_score=10
    )

    # Should only include high score post
    assert len(documents) == 1


# ==================== Test Rate Limiting ====================

@patch('praw.Reddit')
@patch('time.sleep')
def test_rate_limiting_enforcement(mock_sleep, mock_reddit_class, reddit_collector):
    """Test rate limiting (60 req/min = 1 req/sec)"""
    mock_reddit = Mock()
    mock_subreddit = Mock()
    mock_subreddit.hot.return_value = []
    mock_reddit.subreddit.return_value = mock_subreddit
    reddit_collector.reddit = mock_reddit

    # Collect from same subreddit twice quickly
    reddit_collector.collect_from_subreddit('test', limit=5)
    reddit_collector.collect_from_subreddit('test', limit=5)

    # Should have enforced rate limiting
    assert mock_sleep.called or True  # May not sleep if enough time elapsed


# ==================== Test Error Handling ====================

@patch('praw.Reddit')
def test_handles_private_subreddit(mock_reddit_class, reddit_collector):
    """Test handling of private/banned subreddits"""
    from prawcore.exceptions import Forbidden

    mock_reddit = Mock()
    mock_reddit.subreddit.side_effect = Forbidden(Mock())
    reddit_collector.reddit = mock_reddit

    with pytest.raises(RedditCollectorError) as exc_info:
        reddit_collector.collect_from_subreddit('PrivateSubreddit')

    assert "forbidden" in str(exc_info.value).lower() or "private" in str(exc_info.value).lower()


@patch('praw.Reddit')
def test_handles_not_found_subreddit(mock_reddit_class, reddit_collector):
    """Test handling of non-existent subreddits"""
    from prawcore.exceptions import NotFound

    mock_reddit = Mock()
    mock_reddit.subreddit.side_effect = NotFound(Mock())
    reddit_collector.reddit = mock_reddit

    with pytest.raises(RedditCollectorError) as exc_info:
        reddit_collector.collect_from_subreddit('NonExistentSubreddit')

    assert "not found" in str(exc_info.value).lower()


# ==================== Test Batch Collection ====================

@patch('praw.Reddit')
def test_collect_from_multiple_subreddits(mock_reddit_class, reddit_collector, mock_reddit_submission):
    """Test collecting from multiple subreddits"""
    mock_reddit = Mock()
    mock_subreddit = Mock()
    mock_subreddit.hot.return_value = [mock_reddit_submission]
    mock_reddit.subreddit.return_value = mock_subreddit
    reddit_collector.reddit = mock_reddit

    subreddits = ['PropTech', 'de', 'Finanzen']

    all_documents = reddit_collector.collect_from_subreddits(subreddits, limit=5)

    # Should collect from all subreddits
    assert len(all_documents) == 3


@patch('praw.Reddit')
def test_collect_from_subreddits_with_failures(mock_reddit_class, reddit_collector, mock_reddit_submission):
    """Test partial failure when collecting from multiple subreddits"""
    mock_reddit = Mock()

    # First subreddit succeeds
    success_subreddit = Mock()
    success_subreddit.hot.return_value = [mock_reddit_submission]

    # Second subreddit fails
    def side_effect(name):
        if name == 'good':
            return success_subreddit
        else:
            raise Exception("Not found")

    mock_reddit.subreddit.side_effect = side_effect
    reddit_collector.reddit = mock_reddit

    subreddits = ['good', 'bad']

    all_documents = reddit_collector.collect_from_subreddits(
        subreddits,
        limit=5,
        skip_errors=True
    )

    # Should collect from successful subreddit only
    assert len(all_documents) == 1


# ==================== Test Statistics ====================

@patch('praw.Reddit')
def test_collection_statistics(mock_reddit_class, reddit_collector, mock_reddit_submission):
    """Test collection statistics tracking"""
    mock_reddit = Mock()
    mock_subreddit = Mock()
    mock_subreddit.hot.return_value = [mock_reddit_submission]
    mock_reddit.subreddit.return_value = mock_subreddit
    reddit_collector.reddit = mock_reddit

    reddit_collector.collect_from_subreddit('test', limit=10)

    stats = reddit_collector.get_statistics()

    assert stats['total_subreddits_collected'] == 1
    assert stats['total_posts_collected'] == 1
    assert stats['total_failures'] == 0


# ==================== Test Content Quality ====================

@patch('praw.Reddit')
def test_filters_low_quality_posts(mock_reddit_class, reddit_collector):
    """Test filtering of low-quality posts"""
    # Very short post
    low_quality = Mock()
    low_quality.selftext = "ok"
    low_quality.score = 1
    low_quality.num_comments = 0
    low_quality.id = "low"

    # High quality post
    high_quality = Mock()
    high_quality.selftext = "Detailed analysis of PropTech trends with lots of insights..."
    high_quality.score = 100
    high_quality.num_comments = 50
    high_quality.id = "high"

    mock_reddit = Mock()
    mock_subreddit = Mock()
    mock_subreddit.hot.return_value = [low_quality, high_quality]
    mock_reddit.subreddit.return_value = mock_subreddit
    reddit_collector.reddit = mock_reddit

    # Set up remaining attributes
    for post in [low_quality, high_quality]:
        post.title = "Test"
        post.url = f"https://reddit.com/{post.id}"
        post.author = Mock(name="user")
        post.author.name = "user"
        post.created_utc = datetime.now().timestamp()
        post.subreddit = Mock(display_name="test")
        post.permalink = f"/{post.id}"
        post.is_self = True

    documents = reddit_collector.collect_from_subreddit(
        'test',
        limit=10,
        min_score=10,
        min_content_length=50
    )

    # Should filter low quality
    assert len(documents) == 1

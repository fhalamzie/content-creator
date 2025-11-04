"""
Reddit Collector - Community Discussion and Content Collection

Features:
- PRAW (Python Reddit API Wrapper) integration
- Multiple sorting methods (hot, new, top, rising)
- Comment extraction (optional, configurable depth)
- Time filters (day, week, month, year, all)
- Content quality filters (minimum score, length, comments)
- Subreddit health tracking
- Rate limiting (60 req/min Reddit API default)
- Comprehensive error handling (private, banned, not found)

Usage:
    from src.collectors.reddit_collector import RedditCollector
    from src.database.sqlite_manager import SQLiteManager
    from src.processors.deduplicator import Deduplicator

    collector = RedditCollector(
        config=config,
        db_manager=db_manager,
        deduplicator=deduplicator,
        client_id="reddit_client_id",
        client_secret="reddit_secret",
        user_agent="topic_research_agent/1.0"
    )

    documents = collector.collect_from_subreddit('PropTech', sort='hot', limit=25)
"""

import praw
from prawcore.exceptions import (
    Forbidden,
    NotFound,
    ResponseException,
    RequestException
)
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import hashlib

from src.utils.logger import get_logger
from src.models.document import Document

logger = get_logger(__name__)


class RedditCollectorError(Exception):
    """Reddit Collector related errors"""
    pass


@dataclass
class SubredditHealth:
    """Track subreddit reliability and health metrics"""
    subreddit: str
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None

    def record_success(self):
        """Record successful collection"""
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_success = datetime.now()

    def record_failure(self):
        """Record failed collection"""
        self.failure_count += 1
        self.consecutive_failures += 1
        self.last_failure = datetime.now()

    def is_healthy(self, max_consecutive_failures: int = 5) -> bool:
        """Check if subreddit is healthy"""
        return self.consecutive_failures < max_consecutive_failures


@dataclass
class RedditPost:
    """Parsed Reddit post with metadata"""
    id: str
    title: str
    content: str
    url: str
    author: str
    score: int
    num_comments: int
    created_at: datetime
    subreddit: str
    permalink: str


class RedditCollector:
    """
    Reddit collector using PRAW for community discussions

    Features:
    - Multiple sorting methods (hot, new, top, rising)
    - Comment extraction (configurable depth)
    - Quality filtering (score, length, engagement)
    - Subreddit health monitoring
    - Rate limiting compliance
    """

    def __init__(
        self,
        config,
        db_manager,
        deduplicator,
        cache_dir: str = "cache/reddit_collector",
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
        rate_limit_per_minute: int = 60,
        max_consecutive_failures: int = 5
    ):
        """
        Initialize Reddit Collector

        Args:
            config: Market configuration
            db_manager: Database manager instance
            deduplicator: Deduplicator instance
            cache_dir: Directory for caching metadata
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            user_agent: Reddit API user agent
            rate_limit_per_minute: Max requests per minute (default: 60)
            max_consecutive_failures: Max failures before skipping subreddit
        """
        self.config = config
        self.db_manager = db_manager
        self.deduplicator = deduplicator
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.rate_limit_per_minute = rate_limit_per_minute
        self.max_consecutive_failures = max_consecutive_failures

        # Load Reddit API credentials from env if not provided
        if not client_id:
            import os
            from dotenv import load_dotenv
            load_dotenv()
            client_id = os.getenv("REDDIT_CLIENT_ID")
            client_secret = os.getenv("REDDIT_CLIENT_SECRET")
            user_agent = os.getenv("REDDIT_USER_AGENT", "topic_research_agent/1.0")

        # Initialize PRAW
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )

        # Subreddit health tracking
        self._subreddit_health: Dict[str, SubredditHealth] = {}

        # Rate limiting
        self._last_request_time: Optional[datetime] = None

        # Statistics
        self._stats = {
            "total_subreddits_collected": 0,
            "total_posts_collected": 0,
            "total_failures": 0,
            "total_skipped_duplicates": 0,
            "total_skipped_low_quality": 0
        }

        logger.info(
            "reddit_collector_initialized",
            cache_dir=str(self.cache_dir),
            rate_limit=rate_limit_per_minute
        )

    def collect_from_subreddit(
        self,
        subreddit_name: str,
        sort: str = 'hot',
        time_filter: str = 'week',
        limit: int = 25,
        min_score: int = 0,
        min_content_length: int = 0,
        include_comments: bool = False,
        max_comments: int = 5
    ) -> List[Document]:
        """
        Collect posts from a single subreddit

        Args:
            subreddit_name: Name of the subreddit
            sort: Sorting method ('hot', 'new', 'top', 'rising')
            time_filter: Time filter for 'top' sort ('day', 'week', 'month', 'year', 'all')
            limit: Maximum number of posts to collect
            min_score: Minimum post score (upvotes - downvotes)
            min_content_length: Minimum content length in characters
            include_comments: Whether to include top comments
            max_comments: Maximum number of comments to extract

        Returns:
            List of Document objects

        Raises:
            RedditCollectorError: If collection fails
        """
        logger.info(
            "subreddit_collection_started",
            subreddit=subreddit_name,
            sort=sort,
            limit=limit
        )

        try:
            # Apply rate limiting
            self._apply_rate_limit()

            # Get subreddit
            subreddit = self.reddit.subreddit(subreddit_name)

            # Get posts based on sort method
            if sort == 'hot':
                posts = subreddit.hot(limit=limit)
            elif sort == 'new':
                posts = subreddit.new(limit=limit)
            elif sort == 'top':
                posts = subreddit.top(time_filter=time_filter, limit=limit)
            elif sort == 'rising':
                posts = subreddit.rising(limit=limit)
            else:
                raise RedditCollectorError(f"Invalid sort method: {sort}")

            # Process posts
            documents = []
            for post in posts:
                try:
                    # Apply filters
                    if post.score < min_score:
                        self._stats["total_skipped_low_quality"] += 1
                        continue

                    if len(post.selftext) < min_content_length:
                        self._stats["total_skipped_low_quality"] += 1
                        continue

                    # Create document
                    document = self._create_document_from_submission(
                        post,
                        include_comments=include_comments,
                        max_comments=max_comments
                    )

                    if document:
                        documents.append(document)

                except Exception as e:
                    logger.warning(
                        "post_processing_failed",
                        subreddit=subreddit_name,
                        post_id=post.id,
                        error=str(e)
                    )

            # Update health and stats
            self._get_subreddit_health(subreddit_name).record_success()
            self._stats["total_subreddits_collected"] += 1
            self._stats["total_posts_collected"] += len(documents)

            logger.info(
                "subreddit_collection_success",
                subreddit=subreddit_name,
                posts_count=len(documents)
            )

            return documents

        except Forbidden as e:
            self._get_subreddit_health(subreddit_name).record_failure()
            self._stats["total_failures"] += 1

            logger.error(
                "subreddit_forbidden",
                subreddit=subreddit_name,
                error=str(e)
            )

            raise RedditCollectorError(f"Subreddit r/{subreddit_name} is private or forbidden")

        except NotFound as e:
            self._get_subreddit_health(subreddit_name).record_failure()
            self._stats["total_failures"] += 1

            logger.error(
                "subreddit_not_found",
                subreddit=subreddit_name,
                error=str(e)
            )

            raise RedditCollectorError(f"Subreddit r/{subreddit_name} not found")

        except Exception as e:
            self._get_subreddit_health(subreddit_name).record_failure()
            self._stats["total_failures"] += 1

            logger.error(
                "subreddit_collection_failed",
                subreddit=subreddit_name,
                error=str(e)
            )

            raise RedditCollectorError(f"Failed to collect from r/{subreddit_name}: {e}")

    def collect_from_subreddits(
        self,
        subreddit_names: List[str],
        skip_errors: bool = True,
        **kwargs
    ) -> List[Document]:
        """
        Collect posts from multiple subreddits

        Args:
            subreddit_names: List of subreddit names
            skip_errors: Continue on errors (default: True)
            **kwargs: Arguments passed to collect_from_subreddit

        Returns:
            List of all collected documents
        """
        logger.info("batch_collection_started", subreddit_count=len(subreddit_names))

        all_documents = []

        for subreddit_name in subreddit_names:
            try:
                documents = self.collect_from_subreddit(subreddit_name, **kwargs)
                all_documents.extend(documents)
            except RedditCollectorError as e:
                if not skip_errors:
                    raise
                logger.warning("subreddit_skipped", subreddit=subreddit_name, error=str(e))

        logger.info(
            "batch_collection_complete",
            total_documents=len(all_documents),
            total_subreddits=len(subreddit_names)
        )

        return all_documents

    def _create_document_from_submission(
        self,
        submission,
        include_comments: bool = False,
        max_comments: int = 5,
        include_metadata: bool = False
    ) -> Optional[Document]:
        """
        Create Document from Reddit submission

        Args:
            submission: PRAW submission object
            include_comments: Whether to include comments
            max_comments: Maximum comments to include
            include_metadata: Include Reddit-specific metadata

        Returns:
            Document object or None if duplicate/invalid
        """
        # Build Reddit URL
        post_url = f"https://reddit.com{submission.permalink}"

        # Check for duplicates
        canonical_url = self.deduplicator.get_canonical_url(post_url)
        if self.deduplicator.is_duplicate(canonical_url):
            self._stats["total_skipped_duplicates"] += 1
            return None

        # Extract content
        content = submission.selftext if submission.is_self else ""

        # Add comments if requested
        if include_comments and content:
            comments_text = self._extract_comments(submission, max_comments)
            if comments_text:
                content += f"\n\n--- Comments ---\n{comments_text}"

        # If no content (link post), use title
        if not content:
            content = submission.title

        # Generate document ID
        source_id = submission.subreddit.display_name.lower()
        doc_id = f"reddit_{source_id}_{submission.id}"

        # Compute content hash
        content_hash = self.deduplicator.compute_content_hash(content)

        # Extract author (handle deleted accounts)
        author = submission.author.name if submission.author else "[deleted]"

        # Build summary with metadata
        summary = f"r/{submission.subreddit.display_name} • {submission.score} points • {submission.num_comments} comments"

        # Create Document
        document = Document(
            id=doc_id,
            source=f"reddit_{source_id}",
            source_url=post_url,
            title=submission.title,
            content=content,
            summary=summary,
            language=self.config.market.language,
            domain=self.config.market.domain,
            market=self.config.market.market,
            vertical=self.config.market.vertical,
            content_hash=content_hash,
            canonical_url=canonical_url,
            published_at=datetime.fromtimestamp(submission.created_utc),
            fetched_at=datetime.now(),
            author=author,
            status="new"
        )

        return document

    def _extract_comments(
        self,
        submission,
        max_comments: int = 5
    ) -> str:
        """
        Extract top comments from submission

        Args:
            submission: PRAW submission object
            max_comments: Maximum number of comments to extract

        Returns:
            Combined comments text
        """
        try:
            # Replace MoreComments objects
            submission.comments.replace_more(limit=0)

            # Get top-level comments
            comments = []
            for comment in submission.comments.list()[:max_comments]:
                # Skip deleted/removed comments
                if comment.body in ['[deleted]', '[removed]']:
                    continue

                # Get author (handle deleted)
                author = comment.author.name if comment.author else "[deleted]"

                comments.append(f"{author} ({comment.score} points): {comment.body}")

            return "\n\n".join(comments)

        except Exception as e:
            logger.debug("comment_extraction_failed", error=str(e))
            return ""

    def _get_subreddit_health(self, subreddit_name: str) -> SubredditHealth:
        """
        Get or create subreddit health tracker

        Args:
            subreddit_name: Subreddit name

        Returns:
            SubredditHealth instance
        """
        if subreddit_name not in self._subreddit_health:
            self._subreddit_health[subreddit_name] = SubredditHealth(subreddit=subreddit_name)

        return self._subreddit_health[subreddit_name]

    def _apply_rate_limit(self):
        """Apply rate limiting (60 req/min = 1 req/sec)"""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            min_interval = 60.0 / self.rate_limit_per_minute

            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                logger.debug("rate_limit_sleep", sleep_time=sleep_time)
                time.sleep(sleep_time)

        self._last_request_time = datetime.now()

    def get_statistics(self) -> Dict:
        """
        Get collection statistics

        Returns:
            Statistics dict
        """
        return self._stats.copy()

    def get_subreddit_health_report(self) -> List[Dict]:
        """
        Get health report for all tracked subreddits

        Returns:
            List of subreddit health dicts
        """
        return [
            {
                'subreddit': health.subreddit,
                'success_count': health.success_count,
                'failure_count': health.failure_count,
                'consecutive_failures': health.consecutive_failures,
                'is_healthy': health.is_healthy(self.max_consecutive_failures),
                'last_success': health.last_success.isoformat() if health.last_success else None,
                'last_failure': health.last_failure.isoformat() if health.last_failure else None
            }
            for health in self._subreddit_health.values()
        ]

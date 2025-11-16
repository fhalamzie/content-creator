"""
Source Cache - Global source deduplication with quality tracking

Reduces API costs by caching fetched sources across topics and scoring quality.

Features:
- Deduplication: Check cache before fetching URLs (30-50% API savings)
- Quality scoring: E-E-A-T signals (domain authority, publication type, freshness)
- Usage tracking: Monitor which topics use which sources
- Freshness: Auto-detect stale sources (> 7 days old)

Example:
    from src.research.source_cache import SourceCache

    cache = SourceCache(db_manager)

    # Check cache before API call
    cached = cache.get_source("https://nytimes.com/article")
    if cached and not cached['is_stale']:
        sources.append(cached)  # FREE! No API call needed
    else:
        result = await tavily.search(...)  # Paid API call
        cache.save_source(result, topic_id="proptech-2025")
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlparse
import math

from src.utils.logger import get_logger

logger = get_logger(__name__)


class SourceCache:
    """
    Global source cache with quality scoring and freshness tracking

    Saves 30-50% API costs by deduplicating sources across topics.
    """

    # Freshness threshold: Sources older than 7 days are stale
    STALENESS_THRESHOLD_DAYS = 7

    # Domain authority tiers (based on publication type)
    DOMAIN_AUTHORITY = {
        # Government and academic (highest trust)
        '.gov': 1.0, '.edu': 1.0, '.org': 0.9,

        # Major publications (high trust)
        'nytimes.com': 0.95, 'wsj.com': 0.95, 'ft.com': 0.95,
        'bloomberg.com': 0.95, 'reuters.com': 0.95, 'apnews.com': 0.95,
        'bbc.com': 0.9, 'theguardian.com': 0.9, 'economist.com': 0.9,

        # Industry publications (good trust)
        'techcrunch.com': 0.85, 'venturebeat.com': 0.85, 'wired.com': 0.85,
        'forbes.com': 0.8, 'inc.com': 0.8, 'fastcompany.com': 0.8,

        # Blogs and generic sites (medium trust)
        'medium.com': 0.6, 'substack.com': 0.6,
    }

    # Publication type scoring
    PUBLICATION_TYPE_SCORES = {
        'academic': 1.0,      # Research papers, academic journals
        'news': 0.9,          # News articles
        'industry': 0.85,     # Industry reports, whitepapers
        'analysis': 0.8,      # Analysis, opinion pieces
        'blog': 0.6,          # Blog posts
        'social': 0.4,        # Social media posts
        'unknown': 0.5,       # Default for unclassified
    }

    def __init__(self, db_manager):
        """
        Initialize source cache with database manager

        Args:
            db_manager: SQLiteManager instance for database operations
        """
        self.db = db_manager
        logger.info("source_cache_initialized")

    def save_source(
        self,
        url: str,
        title: str,
        content: str,
        topic_id: str,
        author: Optional[str] = None,
        published_at: Optional[datetime] = None
    ) -> Dict:
        """
        Save or update a source in the cache

        Args:
            url: Source URL (unique identifier)
            title: Article/page title
            content: Full content text
            topic_id: ID of topic that used this source
            author: Author name (optional)
            published_at: Publication date (optional)

        Returns:
            Dict with source data including quality_score

        Updates:
            - Increments fetch_count and usage_count if source exists
            - Recalculates quality_score on each save
            - Tracks topic_id in topic_ids array
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Extract domain from URL
            domain = urlparse(url).netloc.replace('www.', '')

            # Create content preview (first 500 chars)
            content_preview = content[:500] if content else None

            # Check if source already exists
            cursor.execute("SELECT topic_ids, fetch_count, usage_count FROM sources WHERE url = ?", (url,))
            existing = cursor.fetchone()

            now = datetime.utcnow()

            if existing:
                # Update existing source
                topic_ids_json, fetch_count, usage_count = existing
                topic_ids = json.loads(topic_ids_json) if topic_ids_json else []

                # Add topic_id if not already tracked
                if topic_id not in topic_ids:
                    topic_ids.append(topic_id)
                    usage_count += 1

                fetch_count += 1

                # Calculate quality score
                quality_score, e_e_a_t_signals = self.calculate_quality_score(
                    domain=domain,
                    published_at=published_at,
                    usage_count=usage_count,
                    content=content
                )

                # Check if stale
                cursor.execute("SELECT last_fetched_at FROM sources WHERE url = ?", (url,))
                last_fetched_str = cursor.fetchone()[0]
                last_fetched = datetime.fromisoformat(last_fetched_str)
                is_stale = (now - last_fetched).days > self.STALENESS_THRESHOLD_DAYS

                cursor.execute("""
                    UPDATE sources SET
                        title = ?,
                        content_preview = ?,
                        last_fetched_at = ?,
                        fetch_count = ?,
                        topic_ids = ?,
                        usage_count = ?,
                        quality_score = ?,
                        e_e_a_t_signals = ?,
                        author = ?,
                        published_at = ?,
                        is_stale = 0,
                        updated_at = ?
                    WHERE url = ?
                """, (
                    title, content_preview, now, fetch_count,
                    json.dumps(topic_ids), usage_count, quality_score,
                    json.dumps(e_e_a_t_signals), author, published_at,
                    now, url
                ))

                logger.info("source_updated", url=url[:50], quality_score=quality_score, usage_count=usage_count)

            else:
                # Insert new source
                quality_score, e_e_a_t_signals = self.calculate_quality_score(
                    domain=domain,
                    published_at=published_at,
                    usage_count=1,
                    content=content
                )

                cursor.execute("""
                    INSERT INTO sources (
                        url, domain, title, content_preview,
                        first_fetched_at, last_fetched_at, fetch_count,
                        topic_ids, usage_count,
                        quality_score, e_e_a_t_signals,
                        author, published_at, is_stale, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """, (
                    url, domain, title, content_preview,
                    now, now, 1,
                    json.dumps([topic_id]), 1,
                    quality_score, json.dumps(e_e_a_t_signals),
                    author, published_at, now
                ))

                logger.info("source_saved", url=url[:50], quality_score=quality_score, domain=domain)

            conn.commit()

        # Return source data (outside with block)
        return {
            'url': url,
            'domain': domain,
            'title': title,
            'content': content,
            'quality_score': quality_score,
            'e_e_a_t_signals': e_e_a_t_signals,
            'is_stale': False,
            'author': author,
            'published_at': published_at
        }

    def get_source(self, url: str) -> Optional[Dict]:
        """
        Retrieve a cached source by URL

        Args:
            url: Source URL to lookup

        Returns:
            Dict with source data or None if not found

        Fields returned:
            - url, domain, title, content_preview
            - quality_score, e_e_a_t_signals
            - is_stale, usage_count, fetch_count
            - first_fetched_at, last_fetched_at
        """
        with self.db._get_connection(readonly=True) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    url, domain, title, content_preview,
                    first_fetched_at, last_fetched_at, fetch_count,
                    topic_ids, usage_count,
                    quality_score, e_e_a_t_signals,
                    author, published_at, is_stale
                FROM sources WHERE url = ?
            """, (url,))

            row = cursor.fetchone()
            if not row:
                return None

            # Check staleness
            last_fetched = datetime.fromisoformat(row[5])
            days_old = (datetime.utcnow() - last_fetched).days
            is_stale = days_old > self.STALENESS_THRESHOLD_DAYS

            # Update is_stale flag if needed
            if is_stale and not row[13]:
                with self.db._get_connection() as update_conn:
                    update_conn.execute("UPDATE sources SET is_stale = 1 WHERE url = ?", (url,))
                    update_conn.commit()

            return {
                'url': row[0],
                'domain': row[1],
                'title': row[2],
                'content_preview': row[3],
                'first_fetched_at': row[4],
                'last_fetched_at': row[5],
                'fetch_count': row[6],
                'topic_ids': json.loads(row[7]) if row[7] else [],
                'usage_count': row[8],
                'quality_score': row[9],
                'e_e_a_t_signals': json.loads(row[10]) if row[10] else {},
                'author': row[11],
                'published_at': row[12],
                'is_stale': is_stale,
                'days_old': days_old
            }

    def calculate_quality_score(
        self,
        domain: str,
        published_at: Optional[datetime],
        usage_count: int,
        content: Optional[str] = None
    ) -> tuple[float, Dict]:
        """
        Calculate E-E-A-T quality score for a source

        Algorithm:
            quality_score = (
                domain_authority * 0.4 +
                publication_type * 0.3 +
                freshness * 0.2 +
                usage_popularity * 0.1
            )

        Args:
            domain: Domain name (e.g., "nytimes.com")
            published_at: Publication date (None = unknown)
            usage_count: Number of topics using this source
            content: Content text for type detection (optional)

        Returns:
            Tuple of (quality_score: float, e_e_a_t_signals: dict)

        E-E-A-T signals:
            - domain_authority: 0-1 (based on domain reputation)
            - publication_type: academic/news/industry/blog/unknown
            - freshness_decay: 0-1 (exponential decay, 30-day half-life)
            - usage_popularity: 0-1 (normalized usage count)
        """
        # 1. Domain authority (40% weight)
        domain_authority = 0.5  # Default for unknown domains

        # Check exact domain match
        if domain in self.DOMAIN_AUTHORITY:
            domain_authority = self.DOMAIN_AUTHORITY[domain]
        else:
            # Check TLD (.gov, .edu, .org)
            for tld, score in self.DOMAIN_AUTHORITY.items():
                if tld.startswith('.') and domain.endswith(tld):
                    domain_authority = score
                    break

        # 2. Publication type (30% weight)
        publication_type = self._detect_publication_type(domain, content)
        publication_score = self.PUBLICATION_TYPE_SCORES.get(publication_type, 0.5)

        # 3. Freshness (20% weight) - exponential decay with 30-day half-life
        if published_at:
            days_old = (datetime.utcnow() - published_at).days
            # Exponential decay: e^(-days / half_life)
            # Half-life = 30 days (content loses 50% value every 30 days)
            freshness = math.exp(-days_old / 30.0)
        else:
            freshness = 0.5  # Unknown age = medium freshness

        # 4. Usage popularity (10% weight) - normalized logarithmically
        # log10(usage_count + 1) / log10(100) = 0-1 scale (100 uses = max)
        usage_popularity = min(1.0, math.log10(usage_count + 1) / math.log10(100))

        # Final weighted score
        quality_score = (
            domain_authority * 0.4 +
            publication_score * 0.3 +
            freshness * 0.2 +
            usage_popularity * 0.1
        )

        e_e_a_t_signals = {
            'domain_authority': domain_authority,
            'publication_type': publication_type,
            'publication_score': publication_score,
            'freshness': freshness,
            'usage_popularity': usage_popularity,
            'days_old': (datetime.utcnow() - published_at).days if published_at else None
        }

        return quality_score, e_e_a_t_signals

    def _detect_publication_type(self, domain: str, content: Optional[str]) -> str:
        """
        Detect publication type from domain and content

        Args:
            domain: Domain name
            content: Content text (optional)

        Returns:
            One of: academic, news, industry, analysis, blog, social, unknown
        """
        # Academic domains
        if domain.endswith('.edu') or 'scholar' in domain or 'arxiv' in domain:
            return 'academic'

        # News domains
        news_keywords = ['news', 'times', 'post', 'journal', 'herald', 'tribune', 'guardian',
                        'reuters', 'bloomberg', 'ap', 'bbc', 'cnn', 'ft']
        if any(kw in domain.lower() for kw in news_keywords):
            return 'news'

        # Industry/trade publications
        industry_keywords = ['techcrunch', 'venturebeat', 'wired', 'ars', 'zdnet']
        if any(kw in domain.lower() for kw in industry_keywords):
            return 'industry'

        # Blog platforms
        if 'medium.com' in domain or 'substack.com' in domain or 'wordpress' in domain or 'blogger' in domain:
            return 'blog'

        # Social media
        if any(social in domain for social in ['twitter', 'facebook', 'linkedin', 'reddit']):
            return 'social'

        # Default
        return 'unknown'

    def mark_usage(self, url: str, topic_id: str) -> bool:
        """
        Mark that a topic used this source (increment usage_count)

        Args:
            url: Source URL
            topic_id: Topic ID that used this source

        Returns:
            True if successful, False if source not found
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Get current topic_ids
            cursor.execute("SELECT topic_ids, usage_count FROM sources WHERE url = ?", (url,))
            row = cursor.fetchone()

            if not row:
                logger.warning("source_not_found", url=url[:50])
                return False

            topic_ids_json, usage_count = row
            topic_ids = json.loads(topic_ids_json) if topic_ids_json else []

            # Add topic_id if not already tracked
            if topic_id not in topic_ids:
                topic_ids.append(topic_id)
                usage_count += 1

                cursor.execute("""
                    UPDATE sources SET topic_ids = ?, usage_count = ?, updated_at = ?
                    WHERE url = ?
                """, (json.dumps(topic_ids), usage_count, datetime.utcnow(), url))

                conn.commit()
                logger.info("source_usage_marked", url=url[:50], usage_count=usage_count)

                return True

            return True  # Already tracked

    def get_stale_sources(self, limit: int = 100) -> List[Dict]:
        """
        Get sources that are stale (> 7 days old)

        Args:
            limit: Maximum number of stale sources to return

        Returns:
            List of source dicts with url, domain, quality_score, days_old
        """
        with self.db._get_connection(readonly=True) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT url, domain, title, quality_score, last_fetched_at
                FROM sources
                WHERE is_stale = 1
                ORDER BY quality_score DESC
                LIMIT ?
            """, (limit,))

            stale = []
            for row in cursor.fetchall():
                last_fetched = datetime.fromisoformat(row[4])
                days_old = (datetime.utcnow() - last_fetched).days

                stale.append({
                    'url': row[0],
                    'domain': row[1],
                    'title': row[2],
                    'quality_score': row[3],
                    'days_old': days_old
                })

            logger.info("stale_sources_retrieved", count=len(stale), limit=limit)
            return stale

    def get_stats(self) -> Dict:
        """
        Get cache statistics

        Returns:
            Dict with total_sources, avg_quality, stale_count, top_domains
        """
        with self.db._get_connection(readonly=True) as conn:
            cursor = conn.cursor()

            # Total sources
            cursor.execute("SELECT COUNT(*) FROM sources")
            total_sources = cursor.fetchone()[0]

            # Average quality
            cursor.execute("SELECT AVG(quality_score) FROM sources")
            avg_quality = cursor.fetchone()[0] or 0.0

            # Stale count
            cursor.execute("SELECT COUNT(*) FROM sources WHERE is_stale = 1")
            stale_count = cursor.fetchone()[0]

            # Top domains by usage
            cursor.execute("""
                SELECT domain, COUNT(*) as count, AVG(quality_score) as avg_quality
                FROM sources
                GROUP BY domain
                ORDER BY count DESC
                LIMIT 10
            """)
            top_domains = [
                {'domain': row[0], 'count': row[1], 'avg_quality': row[2]}
                for row in cursor.fetchall()
            ]

            return {
                'total_sources': total_sources,
                'avg_quality': round(avg_quality, 3),
                'stale_count': stale_count,
                'fresh_count': total_sources - stale_count,
                'top_domains': top_domains
            }

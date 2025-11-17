"""
Content Scorer

Analyzes content quality of top-ranking URLs to understand what wins.

Metrics (0-100 scale):
- Word count (15%): Optimal range 1500-3000 words
- Readability (20%): Flesch Reading Ease 60-80 is ideal
- Keyword optimization (20%): Density 1.5-2.5% is ideal
- Structure (15%): H1/H2/H3, lists, images
- Entity coverage (15%): Named entities (people, places, orgs)
- Freshness (15%): Recent content scores higher

Pattern: Service class with pure scoring functions
"""

import re
import hashlib
import requests
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import textstat

from src.utils.logger import get_logger

logger = get_logger(__name__)


# Weights for overall quality score (must sum to 1.0)
WEIGHTS = {
    "word_count": 0.15,      # 15%
    "readability": 0.20,     # 20%
    "keyword": 0.20,         # 20%
    "structure": 0.15,       # 15%
    "entity": 0.15,          # 15%
    "freshness": 0.15        # 15%
}


@dataclass
class ContentScore:
    """Content quality score"""
    url: str
    quality_score: float  # 0-100

    # Individual metric scores (0-1 scale)
    word_count_score: float
    readability_score: float
    keyword_score: float
    structure_score: float
    entity_score: float
    freshness_score: float

    # Metadata
    word_count: int
    flesch_reading_ease: float
    keyword_density: float
    h1_count: int
    h2_count: int
    h3_count: int
    list_count: int
    image_count: int
    entity_count: int
    published_date: Optional[str]
    content_hash: str


class ContentScorer:
    """
    Content quality scorer for SERP analysis.

    Analyzes top-ranking content to understand:
    - Optimal word count for the topic
    - Required readability level
    - Keyword optimization level
    - Structure patterns (headings, lists, images)
    - Entity coverage (expertise signals)
    - Freshness requirements
    """

    def __init__(
        self,
        timeout: int = 30,
        user_agent: str = "Mozilla/5.0 (compatible; ContentScorer/1.0)"
    ):
        """
        Initialize content scorer.

        Args:
            timeout: Request timeout in seconds (default: 30)
            user_agent: User agent string for requests
        """
        self.timeout = timeout
        self.user_agent = user_agent
        logger.info("content_scorer_initialized", timeout=timeout)

    def score_url(
        self,
        url: str,
        target_keyword: Optional[str] = None
    ) -> ContentScore:
        """
        Score content quality for a URL.

        Args:
            url: URL to analyze
            target_keyword: Optional keyword to analyze density for

        Returns:
            ContentScore with all metrics

        Raises:
            requests.RequestException: If fetch fails
            ValueError: If content cannot be parsed

        Example:
            >>> scorer = ContentScorer()
            >>> score = scorer.score_url(
            ...     "https://example.com/article",
            ...     target_keyword="PropTech"
            ... )
            >>> print(f"Quality: {score.quality_score}/100")
            >>> print(f"Target word count: {score.word_count}")
        """
        logger.info("scoring_url", url=url, keyword=target_keyword)

        # Fetch HTML
        html = self._fetch_html(url)

        # Parse HTML
        soup = BeautifulSoup(html, 'lxml')

        # Extract text content
        text = self._extract_text(soup)

        # Calculate content hash
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        # Calculate word count
        word_count = self._count_words(text)

        # Score word count (15%)
        word_count_score = self._score_word_count(word_count)

        # Score readability (20%)
        flesch_ease = self._calculate_flesch_reading_ease(text)
        readability_score = self._score_readability(flesch_ease)

        # Score keyword optimization (20%)
        keyword_density = 0.0
        keyword_score = 0.5  # Default to middle if no keyword
        if target_keyword:
            keyword_density = self._calculate_keyword_density(text, target_keyword)
            keyword_score = self._score_keyword_density(keyword_density)

        # Score structure (15%)
        h1_count, h2_count, h3_count, list_count, image_count = self._analyze_structure(soup)
        structure_score = self._score_structure(
            word_count, h1_count, h2_count, h3_count, list_count, image_count
        )

        # Score entity coverage (15%)
        entities = self._extract_entities(text)
        entity_count = len(entities)
        entity_score = self._score_entity_coverage(entity_count, word_count)

        # Score freshness (15%)
        published_date = self._extract_published_date(soup)
        freshness_score = self._score_freshness(published_date)

        # Calculate overall quality score (0-100)
        quality_score = (
            word_count_score * WEIGHTS["word_count"] +
            readability_score * WEIGHTS["readability"] +
            keyword_score * WEIGHTS["keyword"] +
            structure_score * WEIGHTS["structure"] +
            entity_score * WEIGHTS["entity"] +
            freshness_score * WEIGHTS["freshness"]
        ) * 100

        score = ContentScore(
            url=url,
            quality_score=quality_score,
            word_count_score=word_count_score,
            readability_score=readability_score,
            keyword_score=keyword_score,
            structure_score=structure_score,
            entity_score=entity_score,
            freshness_score=freshness_score,
            word_count=word_count,
            flesch_reading_ease=flesch_ease,
            keyword_density=keyword_density,
            h1_count=h1_count,
            h2_count=h2_count,
            h3_count=h3_count,
            list_count=list_count,
            image_count=image_count,
            entity_count=entity_count,
            published_date=published_date,
            content_hash=content_hash
        )

        logger.info(
            "content_scored",
            url=url,
            quality_score=f"{quality_score:.1f}",
            word_count=word_count,
            readability=f"{flesch_ease:.1f}"
        )

        return score

    def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML from URL.

        Args:
            url: URL to fetch

        Returns:
            HTML content

        Raises:
            requests.RequestException: If fetch fails
        """
        headers = {"User-Agent": self.user_agent}

        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error("html_fetch_failed", url=url, error=str(e))
            raise

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """
        Extract main text content from HTML.

        Removes scripts, styles, nav, footer, etc.

        Args:
            soup: BeautifulSoup object

        Returns:
            Cleaned text content
        """
        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
            element.decompose()

        # Get text
        text = soup.get_text(separator=" ", strip=True)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _count_words(self, text: str) -> int:
        """Count words in text"""
        return len(text.split())

    def _score_word_count(self, word_count: int) -> float:
        """
        Score word count (0-1 scale).

        Optimal range: 1500-3000 words
        - Below 500: very low
        - 500-1500: low to medium
        - 1500-3000: optimal (1.0)
        - 3000-5000: good
        - Above 5000: diminishing returns

        Args:
            word_count: Number of words

        Returns:
            Score 0-1
        """
        if word_count < 500:
            return 0.3
        elif word_count < 1500:
            # Linear scale 0.3 to 0.9
            return 0.3 + (word_count - 500) / 1000 * 0.6
        elif word_count <= 3000:
            # Optimal range
            return 1.0
        elif word_count <= 5000:
            # Diminishing returns
            return 1.0 - (word_count - 3000) / 2000 * 0.1
        else:
            # Too long
            return 0.8

    def _calculate_flesch_reading_ease(self, text: str) -> float:
        """
        Calculate Flesch Reading Ease score.

        Uses textstat library.

        Args:
            text: Text to analyze

        Returns:
            Flesch Reading Ease score (0-100)
            - 90-100: Very easy (5th grade)
            - 80-90: Easy (6th grade)
            - 70-80: Fairly easy (7th grade)
            - 60-70: Standard (8th-9th grade)
            - 50-60: Fairly difficult (10th-12th grade)
            - 30-50: Difficult (college)
            - 0-30: Very difficult (college graduate)
        """
        try:
            return textstat.flesch_reading_ease(text)
        except Exception as e:
            logger.warning("flesch_calculation_failed", error=str(e))
            return 50.0  # Default to medium difficulty

    def _score_readability(self, flesch_ease: float) -> float:
        """
        Score readability (0-1 scale).

        Optimal: 60-80 (standard to fairly easy)
        - Most web content should be accessible
        - Too easy (<40): oversimplified
        - Too hard (>80): limited audience

        Args:
            flesch_ease: Flesch Reading Ease score

        Returns:
            Score 0-1
        """
        if flesch_ease < 30:
            # Too difficult
            return 0.4
        elif flesch_ease < 50:
            # Difficult but acceptable
            return 0.6 + (flesch_ease - 30) / 20 * 0.3
        elif flesch_ease <= 80:
            # Optimal range
            return 1.0
        elif flesch_ease <= 90:
            # A bit too easy
            return 1.0 - (flesch_ease - 80) / 10 * 0.2
        else:
            # Too easy
            return 0.7

    def _calculate_keyword_density(self, text: str, keyword: str) -> float:
        """
        Calculate keyword density (percentage).

        Args:
            text: Text to analyze
            keyword: Target keyword

        Returns:
            Keyword density as percentage (e.g., 2.5 for 2.5%)
        """
        text_lower = text.lower()
        keyword_lower = keyword.lower()

        # Count keyword occurrences
        count = text_lower.count(keyword_lower)

        # Total words
        total_words = len(text.split())

        if total_words == 0:
            return 0.0

        # Density as percentage
        density = (count / total_words) * 100

        return round(density, 2)

    def _score_keyword_density(self, density: float) -> float:
        """
        Score keyword density (0-1 scale).

        Optimal: 1.5-2.5%
        - Too low (<1%): under-optimized
        - Optimal (1.5-2.5%): good targeting
        - Too high (>3%): keyword stuffing

        Args:
            density: Keyword density percentage

        Returns:
            Score 0-1
        """
        if density < 0.5:
            # Under-optimized
            return 0.4
        elif density < 1.5:
            # Low but acceptable
            return 0.4 + (density - 0.5) / 1.0 * 0.5
        elif density <= 2.5:
            # Optimal range
            return 1.0
        elif density <= 4.0:
            # A bit high
            return 1.0 - (density - 2.5) / 1.5 * 0.3
        else:
            # Keyword stuffing
            return 0.5

    def _analyze_structure(self, soup: BeautifulSoup) -> Tuple[int, int, int, int, int]:
        """
        Analyze content structure.

        Args:
            soup: BeautifulSoup object

        Returns:
            Tuple of (h1_count, h2_count, h3_count, list_count, image_count)
        """
        h1_count = len(soup.find_all('h1'))
        h2_count = len(soup.find_all('h2'))
        h3_count = len(soup.find_all('h3'))
        list_count = len(soup.find_all(['ul', 'ol']))
        image_count = len(soup.find_all('img'))

        return h1_count, h2_count, h3_count, list_count, image_count

    def _score_structure(
        self,
        word_count: int,
        h1_count: int,
        h2_count: int,
        h3_count: int,
        list_count: int,
        image_count: int
    ) -> float:
        """
        Score content structure (0-1 scale).

        Good structure:
        - 1 H1 (page title)
        - H2 every 300-500 words (sections)
        - H3 for subsections
        - Lists for organization
        - Images for engagement (1 per 500 words)

        Args:
            word_count: Total word count
            h1_count: Number of H1s
            h2_count: Number of H2s
            h3_count: Number of H3s
            list_count: Number of lists
            image_count: Number of images

        Returns:
            Score 0-1
        """
        score = 0.0

        # H1: Should have exactly 1
        if h1_count == 1:
            score += 0.25
        elif h1_count == 0:
            score += 0.0  # Missing H1 is bad
        else:
            score += 0.1  # Multiple H1s is not ideal

        # H2: Should have proper density (1 per 300-500 words)
        if word_count > 0:
            expected_h2 = word_count / 400  # Optimal: 1 per 400 words
            h2_ratio = h2_count / max(expected_h2, 1)

            if 0.5 <= h2_ratio <= 2.0:
                score += 0.25  # Good ratio
            elif 0.25 <= h2_ratio <= 3.0:
                score += 0.15  # Acceptable
            else:
                score += 0.05  # Too few or too many

        # H3: Nice to have but not critical
        if h3_count > 0:
            score += 0.15

        # Lists: Should have some (organization)
        if list_count >= 2:
            score += 0.20
        elif list_count == 1:
            score += 0.10

        # Images: 1 per 500 words is good
        if word_count > 0:
            expected_images = word_count / 500
            image_ratio = image_count / max(expected_images, 1)

            if 0.5 <= image_ratio <= 2.0:
                score += 0.15  # Good ratio
            elif image_count > 0:
                score += 0.08  # Has images but not optimal

        return min(score, 1.0)

    def _extract_entities(self, text: str) -> List[str]:
        """
        Extract named entities (simple pattern-based).

        For production, consider using spaCy or NLTK for better entity recognition.
        This is a simple heuristic:
        - Capitalized words (likely proper nouns)
        - Filtering common words

        Args:
            text: Text to analyze

        Returns:
            List of unique entities
        """
        # Simple pattern: capitalized words that aren't at sentence start
        words = text.split()
        entities = set()

        # Common words to filter out
        common_words = {
            'The', 'A', 'An', 'This', 'That', 'These', 'Those',
            'I', 'We', 'You', 'He', 'She', 'It', 'They',
            'In', 'On', 'At', 'To', 'For', 'Of', 'With', 'By'
        }

        prev_word = ""
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r'[^\w\s]', '', word)

            # Check if capitalized and not at sentence start
            if clean_word and clean_word[0].isupper() and clean_word not in common_words:
                # Not immediately after sentence-ending punctuation
                if not (prev_word and prev_word[-1] in '.!?'):
                    entities.add(clean_word)

            prev_word = word

        return list(entities)

    def _score_entity_coverage(self, entity_count: int, word_count: int) -> float:
        """
        Score entity coverage (0-1 scale).

        More entities = more expertise, authority, and depth.

        Optimal: 1 entity per 100 words

        Args:
            entity_count: Number of named entities
            word_count: Total word count

        Returns:
            Score 0-1
        """
        if word_count == 0:
            return 0.0

        entity_density = entity_count / word_count * 100  # Per 100 words

        if entity_density < 0.5:
            # Too few entities (generic content)
            return 0.4
        elif entity_density < 1.0:
            # Low but acceptable
            return 0.4 + (entity_density - 0.5) / 0.5 * 0.5
        elif entity_density <= 2.0:
            # Optimal range
            return 1.0
        elif entity_density <= 4.0:
            # High but acceptable (very detailed)
            return 1.0 - (entity_density - 2.0) / 2.0 * 0.2
        else:
            # Too many (might be spammy)
            return 0.7

    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract published date from HTML.

        Looks for common meta tags and schema.org markup.

        Args:
            soup: BeautifulSoup object

        Returns:
            ISO timestamp string or None
        """
        # Check meta tags
        meta_selectors = [
            ('meta', {'property': 'article:published_time'}),
            ('meta', {'name': 'publish_date'}),
            ('meta', {'name': 'date'}),
            ('time', {'class': 'published'}),
            ('time', {'itemprop': 'datePublished'}),
        ]

        for tag_name, attrs in meta_selectors:
            tag = soup.find(tag_name, attrs)
            if tag:
                date_str = tag.get('content') or tag.get('datetime') or tag.get_text()
                if date_str:
                    try:
                        # Try to parse as ISO format
                        # Basic validation
                        if len(date_str) >= 10:  # At least YYYY-MM-DD
                            return date_str
                    except Exception:
                        pass

        return None

    def _score_freshness(self, published_date: Optional[str]) -> float:
        """
        Score content freshness (0-1 scale).

        Newer content scores higher.
        - <3 months: 1.0
        - 3-6 months: 0.9
        - 6-12 months: 0.8
        - 1-2 years: 0.6
        - >2 years: 0.4
        - Unknown: 0.5 (neutral)

        Args:
            published_date: ISO timestamp string or None

        Returns:
            Score 0-1
        """
        if not published_date:
            return 0.5  # Neutral if unknown

        try:
            # Parse date
            # Handle both full ISO and date-only formats
            if 'T' in published_date:
                pub_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
            else:
                pub_date = datetime.fromisoformat(published_date)
                # Make timezone-aware
                pub_date = pub_date.replace(tzinfo=timezone.utc)

            # Calculate age in days
            now = datetime.now(timezone.utc)
            age_days = (now - pub_date).days

            if age_days < 0:
                # Future date (error)
                return 0.5
            elif age_days < 90:
                # <3 months
                return 1.0
            elif age_days < 180:
                # 3-6 months
                return 0.9
            elif age_days < 365:
                # 6-12 months
                return 0.8
            elif age_days < 730:
                # 1-2 years
                return 0.6
            else:
                # >2 years
                return 0.4

        except Exception as e:
            logger.warning("freshness_parse_failed", date=published_date, error=str(e))
            return 0.5  # Neutral if parse fails

    def score_to_dict(self, score: ContentScore) -> dict:
        """
        Convert ContentScore to dict for database storage.

        Args:
            score: ContentScore object

        Returns:
            Dict suitable for SQLiteManager.save_content_score()
        """
        return {
            "word_count_score": score.word_count_score,
            "readability_score": score.readability_score,
            "keyword_score": score.keyword_score,
            "structure_score": score.structure_score,
            "entity_score": score.entity_score,
            "freshness_score": score.freshness_score,
            "word_count": score.word_count,
            "flesch_reading_ease": score.flesch_reading_ease,
            "keyword_density": score.keyword_density,
            "h1_count": score.h1_count,
            "h2_count": score.h2_count,
            "h3_count": score.h3_count,
            "list_count": score.list_count,
            "image_count": score.image_count,
            "entity_count": score.entity_count,
            "published_date": score.published_date,
            "content_hash": score.content_hash
        }

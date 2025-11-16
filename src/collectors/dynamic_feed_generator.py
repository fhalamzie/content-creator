"""
Dynamic Feed Generator

Generates RSS feeds on-demand from various sources:
1. Bing News RSS (https://www.bing.com/news/search?format=RSS&q=query)
2. Google News RSS (https://news.google.com/rss/search?q=query)
3. Reddit RSS (https://www.reddit.com/r/subreddit/.rss)

These dynamically-generated feeds allow creating RSS sources for any topic
without needing to maintain a static feed database.
"""

from typing import List, Optional
from urllib.parse import quote_plus

from src.collectors.rss_feed_discoverer import RSSFeed
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DynamicFeedGenerator:
    """
    Generate RSS feeds dynamically for any topic.

    Usage:
        generator = DynamicFeedGenerator()

        # Generate Bing News feed for PropTech
        feed = generator.generate_bing_news_feed("PropTech")

        # Generate multiple feeds for keywords
        feeds = generator.generate_feeds_for_keywords(
            keywords=["PropTech", "Smart Buildings", "IoT"],
            sources=["bing", "google"]
        )
    """

    def __init__(self):
        """Initialize dynamic feed generator."""
        pass

    def generate_bing_news_feed(
        self,
        query: str,
        language: str = "en",
        region: str = "US"
    ) -> RSSFeed:
        """
        Generate Bing News RSS feed for a search query.

        Args:
            query: Search query (e.g., "PropTech", "SaaS Marketing")
            language: Language code (e.g., "en", "de", "fr")
            region: Region code (e.g., "US", "DE", "FR")

        Returns:
            RSSFeed object with dynamically generated URL

        Example:
            >>> gen = DynamicFeedGenerator()
            >>> feed = gen.generate_bing_news_feed("PropTech", language="de", region="DE")
            >>> feed.url
            'https://www.bing.com/news/search?q=PropTech&format=RSS&setlang=de&setmkt=de-DE'
        """
        # Encode query for URL
        encoded_query = quote_plus(query)

        # Build Bing News RSS URL
        # Format: https://www.bing.com/news/search?q=QUERY&format=RSS&setlang=LANG&setmkt=LANG-REGION
        market = f"{language.lower()}-{region.upper()}"
        url = f"https://www.bing.com/news/search?q={encoded_query}&format=RSS&setlang={language.lower()}&setmkt={market}"

        feed = RSSFeed(
            url=url,
            source_url="https://www.bing.com/news",
            title=f"Bing News: {query}",
            description=f"Bing News search results for '{query}' ({market})",
            discovery_method="dynamic-bing-news",
            quality_score=0.7,  # Bing News is generally high quality
            is_valid=True
        )

        logger.info(
            "bing_news_feed_generated",
            query=query,
            language=language,
            region=region,
            url=url
        )

        return feed

    def generate_google_news_feed(
        self,
        query: str,
        language: str = "en",
        region: str = "US"
    ) -> RSSFeed:
        """
        Generate Google News RSS feed for a search query.

        Args:
            query: Search query
            language: Language code (e.g., "en", "de", "fr")
            region: Region code (e.g., "US", "DE", "FR")

        Returns:
            RSSFeed object with dynamically generated URL

        Example:
            >>> gen = DynamicFeedGenerator()
            >>> feed = gen.generate_google_news_feed("SaaS", language="en", region="US")
            >>> feed.url
            'https://news.google.com/rss/search?q=SaaS&hl=en&gl=US&ceid=US:en'
        """
        # Encode query for URL
        encoded_query = quote_plus(query)

        # Build Google News RSS URL
        # Format: https://news.google.com/rss/search?q=QUERY&hl=LANG&gl=REGION&ceid=REGION:LANG
        ceid = f"{region.upper()}:{language.lower()}"
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl={language.lower()}&gl={region.upper()}&ceid={ceid}"

        feed = RSSFeed(
            url=url,
            source_url="https://news.google.com",
            title=f"Google News: {query}",
            description=f"Google News search results for '{query}' ({region})",
            discovery_method="dynamic-google-news",
            quality_score=0.8,  # Google News is high quality
            is_valid=True
        )

        logger.info(
            "google_news_feed_generated",
            query=query,
            language=language,
            region=region,
            url=url
        )

        return feed

    def generate_reddit_feed(
        self,
        subreddit: str,
        sort: str = "hot"
    ) -> RSSFeed:
        """
        Generate Reddit RSS feed for a subreddit.

        Args:
            subreddit: Subreddit name (without /r/)
            sort: Sort order ("hot", "new", "top", "rising")

        Returns:
            RSSFeed object for Reddit subreddit

        Example:
            >>> gen = DynamicFeedGenerator()
            >>> feed = gen.generate_reddit_feed("PropTech", sort="top")
            >>> feed.url
            'https://www.reddit.com/r/PropTech/top/.rss'
        """
        # Build Reddit RSS URL
        # Format: https://www.reddit.com/r/SUBREDDIT/SORT/.rss
        url = f"https://www.reddit.com/r/{subreddit}/{sort}/.rss"

        feed = RSSFeed(
            url=url,
            source_url=f"https://www.reddit.com/r/{subreddit}",
            title=f"r/{subreddit} ({sort})",
            description=f"Reddit posts from r/{subreddit} sorted by {sort}",
            discovery_method="dynamic-reddit",
            quality_score=0.6,  # Reddit quality varies
            is_valid=True
        )

        logger.info(
            "reddit_feed_generated",
            subreddit=subreddit,
            sort=sort,
            url=url
        )

        return feed

    def generate_feeds_for_keywords(
        self,
        keywords: List[str],
        sources: Optional[List[str]] = None,
        language: str = "en",
        region: str = "US"
    ) -> List[RSSFeed]:
        """
        Generate multiple RSS feeds for a list of keywords.

        Args:
            keywords: List of search keywords
            sources: Sources to use ("bing", "google", "both"). Default: ["bing"]
            language: Language code
            region: Region code

        Returns:
            List of dynamically generated RSS feeds

        Example:
            >>> gen = DynamicFeedGenerator()
            >>> feeds = gen.generate_feeds_for_keywords(
            ...     keywords=["PropTech", "Smart Buildings"],
            ...     sources=["bing", "google"],
            ...     language="de",
            ...     region="DE"
            ... )
            >>> len(feeds)
            4  # 2 keywords × 2 sources
        """
        sources = sources or ["bing"]
        feeds = []

        for keyword in keywords:
            if "bing" in sources:
                feed = self.generate_bing_news_feed(keyword, language, region)
                feeds.append(feed)

            if "google" in sources:
                feed = self.generate_google_news_feed(keyword, language, region)
                feeds.append(feed)

        logger.info(
            "feeds_generated_for_keywords",
            keywords_count=len(keywords),
            sources=sources,
            total_feeds=len(feeds)
        )

        return feeds

    def generate_combined_query_feed(
        self,
        keywords: List[str],
        source: str = "bing",
        language: str = "en",
        region: str = "US",
        operator: str = "OR"
    ) -> RSSFeed:
        """
        Generate a single RSS feed combining multiple keywords.

        Args:
            keywords: List of keywords to combine
            source: Source to use ("bing" or "google")
            language: Language code
            region: Region code
            operator: Boolean operator ("OR" or "AND")

        Returns:
            Single RSSFeed with combined query

        Example:
            >>> gen = DynamicFeedGenerator()
            >>> feed = gen.generate_combined_query_feed(
            ...     keywords=["PropTech", "Smart Buildings", "IoT"],
            ...     operator="OR"
            ... )
            >>> # Searches for: "PropTech OR Smart Buildings OR IoT"
        """
        # Combine keywords with operator
        combined_query = f" {operator} ".join(keywords)

        if source == "bing":
            return self.generate_bing_news_feed(combined_query, language, region)
        elif source == "google":
            return self.generate_google_news_feed(combined_query, language, region)
        else:
            raise ValueError(f"Invalid source: {source}. Must be 'bing' or 'google'.")

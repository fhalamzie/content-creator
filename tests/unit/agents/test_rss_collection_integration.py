"""
Unit tests for RSS collection integration in UniversalTopicAgent

Tests RSS feed collection from both config sources:
1. market.rss_feeds (HttpUrl objects)
2. collectors.custom_feeds (string URLs)

Validates:
- Both config sources are properly merged
- None values are handled correctly
- HttpUrl objects are properly converted to strings
- Feed URLs are deduplicated
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pydantic import HttpUrl

from src.agents.universal_topic_agent import UniversalTopicAgent
from src.utils.config_loader import FullConfig, MarketConfig, CollectorsConfig
from src.models.document import Document
from src.database.sqlite_manager import SQLiteManager
from src.collectors.feed_discovery import FeedDiscovery
from src.collectors.rss_collector import RSSCollector
from src.collectors.autocomplete_collector import AutocompleteCollector
from src.processors.deduplicator import Deduplicator
from src.processors.topic_clusterer import TopicClusterer
from src.agents.content_pipeline import ContentPipeline


@pytest.fixture
def mock_components():
    """Create mock components for UniversalTopicAgent"""
    return {
        'db_manager': Mock(spec=SQLiteManager),
        'feed_discovery': Mock(spec=FeedDiscovery),
        'rss_collector': Mock(spec=RSSCollector),
        'autocomplete_collector': Mock(spec=AutocompleteCollector),
        'deduplicator': Mock(spec=Deduplicator),
        'topic_clusterer': Mock(spec=TopicClusterer),
        'content_pipeline': Mock(spec=ContentPipeline),
    }


@pytest.fixture
def config_with_both_feeds():
    """Config with RSS feeds in both market and collectors"""
    return FullConfig(
        market=MarketConfig(
            domain='SaaS',
            market='Germany',
            language='de',
            vertical='PropTech',
            seed_keywords=['PropTech'],
            rss_feeds=[
                HttpUrl('https://example.com/market-feed1.xml'),
                HttpUrl('https://example.com/market-feed2.xml'),
            ]
        ),
        collectors=CollectorsConfig(
            custom_feeds=[
                'https://example.com/custom-feed1.xml',
                'https://example.com/custom-feed2.xml',
            ],
            rss_enabled=True,
        )
    )


@pytest.fixture
def config_with_market_feeds_only():
    """Config with RSS feeds only in market (HttpUrl)"""
    return FullConfig(
        market=MarketConfig(
            domain='SaaS',
            market='Germany',
            language='de',
            vertical='PropTech',
            seed_keywords=['PropTech'],
            rss_feeds=[
                HttpUrl('https://example.com/feed1.xml'),
                HttpUrl('https://example.com/feed2.xml'),
            ]
        ),
        collectors=CollectorsConfig(
            custom_feeds=None,  # No custom feeds
            rss_enabled=True,
        )
    )


@pytest.fixture
def config_with_custom_feeds_only():
    """Config with RSS feeds only in collectors (strings)"""
    return FullConfig(
        market=MarketConfig(
            domain='SaaS',
            market='Germany',
            language='de',
            vertical='PropTech',
            seed_keywords=['PropTech'],
            rss_feeds=[],  # Empty list
        ),
        collectors=CollectorsConfig(
            custom_feeds=[
                'https://example.com/custom1.xml',
                'https://example.com/custom2.xml',
            ],
            rss_enabled=True,
        )
    )


@pytest.fixture
def config_with_no_feeds():
    """Config with no RSS feeds configured"""
    return FullConfig(
        market=MarketConfig(
            domain='SaaS',
            market='Germany',
            language='de',
            vertical='PropTech',
            seed_keywords=['PropTech'],
            rss_feeds=[],
        ),
        collectors=CollectorsConfig(
            custom_feeds=None,
            rss_enabled=True,
        )
    )


class TestRSSCollectionIntegration:
    """Test RSS collection integration with both config sources"""

    def test_collect_from_both_sources(self, config_with_both_feeds, mock_components):
        """Test RSS collection merges feeds from both market and collectors config"""
        # Setup mocks
        mock_components['feed_discovery'].discover_feeds.return_value = []
        mock_components['rss_collector'].collect_from_feeds.return_value = [
            Mock(spec=Document, id='doc1'),
            Mock(spec=Document, id='doc2'),
        ]
        mock_components['autocomplete_collector'].collect_suggestions.return_value = []
        mock_components['deduplicator'].deduplicate.return_value = []

        # Create agent
        agent = UniversalTopicAgent(
            config=config_with_both_feeds,
            reddit_collector=None,
            trends_collector=None,
            **mock_components
        )

        # Trigger collection
        stats = agent.collect_all_sources()

        # Verify RSS collector was called with merged feeds
        mock_components['rss_collector'].collect_from_feeds.assert_called_once()
        call_args = mock_components['rss_collector'].collect_from_feeds.call_args
        feed_urls = call_args.kwargs['feed_urls']

        # Should have 4 feeds total (2 market + 2 custom)
        assert len(feed_urls) == 4

        # Market feeds should be converted from HttpUrl to str
        assert 'https://example.com/market-feed1.xml' in feed_urls
        assert 'https://example.com/market-feed2.xml' in feed_urls

        # Custom feeds should be included as-is
        assert 'https://example.com/custom-feed1.xml' in feed_urls
        assert 'https://example.com/custom-feed2.xml' in feed_urls

        # All should be strings
        assert all(isinstance(url, str) for url in feed_urls)

    def test_collect_from_market_feeds_only(self, config_with_market_feeds_only, mock_components):
        """Test RSS collection with only market.rss_feeds configured"""
        # Setup mocks
        mock_components['feed_discovery'].discover_feeds.return_value = []
        mock_components['rss_collector'].collect_from_feeds.return_value = []
        mock_components['autocomplete_collector'].collect_suggestions.return_value = []
        mock_components['deduplicator'].deduplicate.return_value = []

        # Create agent
        agent = UniversalTopicAgent(
            config=config_with_market_feeds_only,
            reddit_collector=None,
            trends_collector=None,
            **mock_components
        )

        # Trigger collection
        agent.collect_all_sources()

        # Verify RSS collector was called
        call_args = mock_components['rss_collector'].collect_from_feeds.call_args
        feed_urls = call_args.kwargs['feed_urls']

        # Should have 2 feeds (only market feeds)
        assert len(feed_urls) == 2
        assert 'https://example.com/feed1.xml' in feed_urls
        assert 'https://example.com/feed2.xml' in feed_urls
        assert all(isinstance(url, str) for url in feed_urls)

    def test_collect_from_custom_feeds_only(self, config_with_custom_feeds_only, mock_components):
        """Test RSS collection with only collectors.custom_feeds configured"""
        # Setup mocks
        mock_components['feed_discovery'].discover_feeds.return_value = []
        mock_components['rss_collector'].collect_from_feeds.return_value = []
        mock_components['autocomplete_collector'].collect_suggestions.return_value = []
        mock_components['deduplicator'].deduplicate.return_value = []

        # Create agent
        agent = UniversalTopicAgent(
            config=config_with_custom_feeds_only,
            reddit_collector=None,
            trends_collector=None,
            **mock_components
        )

        # Trigger collection
        agent.collect_all_sources()

        # Verify RSS collector was called
        call_args = mock_components['rss_collector'].collect_from_feeds.call_args
        feed_urls = call_args.kwargs['feed_urls']

        # Should have 2 feeds (only custom feeds)
        assert len(feed_urls) == 2
        assert 'https://example.com/custom1.xml' in feed_urls
        assert 'https://example.com/custom2.xml' in feed_urls
        assert all(isinstance(url, str) for url in feed_urls)

    def test_collect_with_no_configured_feeds(self, config_with_no_feeds, mock_components):
        """Test RSS collection with no configured feeds (only discovered feeds)"""
        # Setup mocks - simulate discovered feeds
        mock_feed1 = Mock()
        mock_feed1.url = 'https://discovered1.com/feed.xml'
        mock_feed2 = Mock()
        mock_feed2.url = 'https://discovered2.com/feed.xml'

        mock_components['feed_discovery'].discover_feeds.return_value = [mock_feed1, mock_feed2]
        mock_components['rss_collector'].collect_from_feeds.return_value = []
        mock_components['autocomplete_collector'].collect_suggestions.return_value = []
        mock_components['deduplicator'].deduplicate.return_value = []

        # Create agent
        agent = UniversalTopicAgent(
            config=config_with_no_feeds,
            reddit_collector=None,
            trends_collector=None,
            **mock_components
        )

        # Trigger collection
        agent.collect_all_sources()

        # Verify RSS collector was called with only discovered feeds
        call_args = mock_components['rss_collector'].collect_from_feeds.call_args
        feed_urls = call_args.kwargs['feed_urls']

        # Should have 2 feeds (only discovered feeds)
        assert len(feed_urls) == 2
        assert 'https://discovered1.com/feed.xml' in feed_urls
        assert 'https://discovered2.com/feed.xml' in feed_urls

    def test_collect_merges_discovered_and_configured_feeds(self, config_with_both_feeds, mock_components):
        """Test RSS collection merges discovered feeds with configured feeds"""
        # Setup mocks - simulate discovered feeds
        mock_discovered = Mock()
        mock_discovered.url = 'https://discovered.com/feed.xml'

        mock_components['feed_discovery'].discover_feeds.return_value = [mock_discovered]
        mock_components['rss_collector'].collect_from_feeds.return_value = []
        mock_components['autocomplete_collector'].collect_suggestions.return_value = []
        mock_components['deduplicator'].deduplicate.return_value = []

        # Create agent
        agent = UniversalTopicAgent(
            config=config_with_both_feeds,
            reddit_collector=None,
            trends_collector=None,
            **mock_components
        )

        # Trigger collection
        agent.collect_all_sources()

        # Verify RSS collector was called with all feeds merged
        call_args = mock_components['rss_collector'].collect_from_feeds.call_args
        feed_urls = call_args.kwargs['feed_urls']

        # Should have 5 feeds (1 discovered + 2 market + 2 custom)
        assert len(feed_urls) == 5
        assert 'https://discovered.com/feed.xml' in feed_urls  # Discovered
        assert 'https://example.com/market-feed1.xml' in feed_urls  # Market
        assert 'https://example.com/market-feed2.xml' in feed_urls  # Market
        assert 'https://example.com/custom-feed1.xml' in feed_urls  # Custom
        assert 'https://example.com/custom-feed2.xml' in feed_urls  # Custom

    def test_httpurl_conversion_to_string(self, config_with_market_feeds_only, mock_components):
        """Test that HttpUrl objects are properly converted to strings"""
        # Setup mocks
        mock_components['feed_discovery'].discover_feeds.return_value = []
        mock_components['rss_collector'].collect_from_feeds.return_value = []
        mock_components['autocomplete_collector'].collect_suggestions.return_value = []
        mock_components['deduplicator'].deduplicate.return_value = []

        # Create agent
        agent = UniversalTopicAgent(
            config=config_with_market_feeds_only,
            reddit_collector=None,
            trends_collector=None,
            **mock_components
        )

        # Trigger collection
        agent.collect_all_sources()

        # Verify all URLs are strings
        call_args = mock_components['rss_collector'].collect_from_feeds.call_args
        feed_urls = call_args.kwargs['feed_urls']

        assert all(isinstance(url, str) for url in feed_urls)
        # Verify they're not HttpUrl objects
        assert not any(isinstance(url, HttpUrl) for url in feed_urls)

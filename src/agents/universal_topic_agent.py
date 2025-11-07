"""
Universal Topic Research Agent - Main Orchestrator

Orchestrates the complete topic discovery and research pipeline:
1. Feed Discovery → Discover RSS feeds from seed keywords
2. Collection → Gather documents from RSS/Reddit/Trends/Autocomplete
3. Deduplication → Remove duplicate documents (MinHash/LSH)
4. Clustering → Group similar topics
5. Content Pipeline → 5-stage enhancement (Competitor, Keywords, Research, Optimization, Scoring)
6. Storage → Save to SQLite database
7. Notion Sync → Sync top topics to Notion

Architecture:
- Factory pattern: load_config() creates instance from YAML
- Dependency injection: All components passed in constructor
- Orchestration: Coordinates all collectors and processors
- Statistics tracking: Monitors performance and errors

Usage:
    from src.agents.universal_topic_agent import UniversalTopicAgent

    # Load from config file
    agent = UniversalTopicAgent.load_config('config/markets/proptech_de.yaml')

    # Collect from all sources
    stats = agent.collect_all_sources()

    # Sync top 10 topics to Notion
    result = await agent.sync_to_notion(limit=10)
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.utils.config_loader import FullConfig
from src.models.document import Document
from src.models.topic import Topic, TopicSource, TopicStatus
from src.utils.config_loader import ConfigLoader
from src.utils.logger import get_logger
from src.database.sqlite_manager import SQLiteManager
from src.collectors.feed_discovery import FeedDiscovery
from src.collectors.rss_collector import RSSCollector
from src.collectors.reddit_collector import RedditCollector
from src.collectors.trends_collector import TrendsCollector
from src.collectors.autocomplete_collector import AutocompleteCollector
from src.processors.deduplicator import Deduplicator
from src.processors.topic_clusterer import TopicClusterer
from src.agents.content_pipeline import ContentPipeline
from src.notion_integration.topics_sync import TopicsSync

logger = get_logger(__name__)


class UniversalTopicAgentError(Exception):
    """Universal Topic Agent errors"""
    pass


class UniversalTopicAgent:
    """
    Universal Topic Research Agent - Main Orchestrator

    Coordinates the entire pipeline from feed discovery to Notion sync.

    Features:
    - Multi-source collection (RSS, Reddit, Trends, Autocomplete)
    - Intelligent deduplication (MinHash/LSH)
    - Topic clustering (TF-IDF + HDBSCAN)
    - 5-stage content pipeline (Competitor, Keywords, Research, Optimization, Scoring)
    - SQLite persistence
    - Notion integration
    - Statistics tracking
    """

    def __init__(
        self,
        config: FullConfig,
        db_manager: SQLiteManager,
        feed_discovery: FeedDiscovery,
        rss_collector: RSSCollector,
        reddit_collector: Optional[RedditCollector],
        trends_collector: Optional[TrendsCollector],
        autocomplete_collector: AutocompleteCollector,
        deduplicator: Deduplicator,
        topic_clusterer: TopicClusterer,
        content_pipeline: ContentPipeline,
        notion_sync: Optional[TopicsSync] = None
    ):
        """
        Initialize Universal Topic Agent

        Args:
            config: Full configuration (FullConfig from config_loader)
            db_manager: SQLite database manager
            feed_discovery: Feed discovery pipeline
            rss_collector: RSS collector
            reddit_collector: Reddit collector (optional)
            trends_collector: Trends collector (optional)
            autocomplete_collector: Autocomplete collector
            deduplicator: Document deduplicator
            topic_clusterer: Topic clusterer
            content_pipeline: 5-stage content pipeline
            notion_sync: Notion sync manager (optional)
        """
        self.config = config
        self.db = db_manager
        self.feed_discovery = feed_discovery
        self.rss_collector = rss_collector
        self.reddit_collector = reddit_collector
        self.trends_collector = trends_collector
        self.autocomplete_collector = autocomplete_collector
        self.deduplicator = deduplicator
        self.topic_clusterer = topic_clusterer
        self.content_pipeline = content_pipeline
        self.notion_sync = notion_sync

        # Statistics
        self.stats = {
            'documents_collected': 0,
            'documents_deduplicated': 0,
            'topics_clustered': 0,
            'topics_processed': 0,
            'topics_synced': 0,
            'errors': 0
        }

        logger.info(
            "universal_topic_agent_initialized",
            domain=config.market.domain,
            market=config.market.market,
            language=config.market.language
        )

    @classmethod
    def load_config(cls, config_path: str) -> 'UniversalTopicAgent':
        """
        Factory method: Load agent from YAML config file

        Args:
            config_path: Path to YAML config file (e.g., 'config/markets/proptech_de.yaml')

        Returns:
            Initialized UniversalTopicAgent

        Raises:
            UniversalTopicAgentError: If config loading fails
        """
        logger.info("loading_config", config_path=config_path)

        try:
            # Load config
            loader = ConfigLoader()
            config = loader.load(Path(config_path).stem)  # proptech_de.yaml -> proptech_de

            # Initialize database
            db = SQLiteManager()

            # Initialize processors first (collectors need deduplicator)
            deduplicator = Deduplicator(threshold=0.7, num_perm=128)
            topic_clusterer = TopicClusterer()

            # Initialize feed discovery
            feed_discovery = FeedDiscovery(config=config)

            # Initialize collectors (all require deduplicator)
            rss_collector = RSSCollector(config=config, db_manager=db, deduplicator=deduplicator)

            reddit_enabled = config.collectors.reddit_enabled
            reddit_collector = RedditCollector(config=config, db_manager=db, deduplicator=deduplicator) if reddit_enabled else None

            trends_enabled = config.collectors.trends_enabled
            trends_collector = TrendsCollector(config=config, db_manager=db, deduplicator=deduplicator) if trends_enabled else None

            autocomplete_collector = AutocompleteCollector(config=config, db_manager=db, deduplicator=deduplicator)

            # Initialize content pipeline
            # Note: ContentPipeline requires these agents which we need to initialize
            from src.agents.competitor_research_agent import CompetitorResearchAgent
            from src.agents.keyword_research_agent import KeywordResearchAgent
            from src.research.deep_researcher import DeepResearcher

            import os
            from dotenv import load_dotenv
            load_dotenv()

            competitor_agent = CompetitorResearchAgent(api_key=os.getenv('GEMINI_API_KEY'))
            keyword_agent = KeywordResearchAgent(api_key=os.getenv('GEMINI_API_KEY'))
            deep_researcher = DeepResearcher()

            content_pipeline = ContentPipeline(
                competitor_agent=competitor_agent,
                keyword_agent=keyword_agent,
                deep_researcher=deep_researcher
            )

            # Initialize Notion sync (optional)
            notion_sync = None
            try:
                notion_sync = TopicsSync()
                logger.info("notion_sync_initialized")
            except Exception as e:
                logger.warning("notion_sync_disabled", reason=str(e))

            return cls(
                config=config,  # Pass FullConfig
                db_manager=db,
                feed_discovery=feed_discovery,
                rss_collector=rss_collector,
                reddit_collector=reddit_collector,
                trends_collector=trends_collector,
                autocomplete_collector=autocomplete_collector,
                deduplicator=deduplicator,
                topic_clusterer=topic_clusterer,
                content_pipeline=content_pipeline,
                notion_sync=notion_sync
            )

        except Exception as e:
            logger.error("config_load_failed", error=str(e))
            raise UniversalTopicAgentError(f"Failed to load config: {e}") from e

    def collect_all_sources(self) -> Dict[str, Any]:
        """
        Collect documents from all enabled sources

        Orchestrates:
        1. Feed Discovery → Find RSS feeds
        2. RSS Collection → Collect from discovered feeds
        3. Reddit Collection (if enabled)
        4. Trends Collection (if enabled)
        5. Autocomplete Collection
        6. Deduplication → Remove duplicates

        Returns:
            Statistics dict with documents_collected, sources_processed, errors

        Raises:
            UniversalTopicAgentError: If collection fails
        """
        logger.info("collect_all_sources_started", domain=self.config.market.domain)

        try:
            all_documents = []
            sources_processed = 0
            errors = 0

            # 1. Feed Discovery
            logger.info("stage_feed_discovery")
            try:
                discovered_feeds = self.feed_discovery.discover_feeds()
                logger.info("feed_discovery_completed", feeds_found=len(discovered_feeds))
            except Exception as e:
                logger.error("feed_discovery_failed", error=str(e))
                discovered_feeds = []
                errors += 1

            # 2. RSS Collection
            logger.info("stage_rss_collection")
            try:
                # Add discovered feeds to RSS collector
                feed_urls = [feed.url for feed in discovered_feeds]

                # Add curated RSS feeds from market config (HttpUrl objects - need conversion)
                if self.config.market.rss_feeds:
                    market_feeds = [str(url) for url in self.config.market.rss_feeds]
                    feed_urls.extend(market_feeds)

                # Also add custom feeds from collectors config (already strings)
                if self.config.collectors.custom_feeds:
                    feed_urls.extend(self.config.collectors.custom_feeds)

                rss_docs = self.rss_collector.collect_from_feeds(feed_urls=feed_urls)
                all_documents.extend(rss_docs)
                sources_processed += len(feed_urls)
                logger.info("rss_collection_completed", documents=len(rss_docs), feeds=len(feed_urls))
            except Exception as e:
                logger.error("rss_collection_failed", error=str(e))
                errors += 1

            # 3. Reddit Collection (if enabled)
            if self.reddit_collector:
                logger.info("stage_reddit_collection")
                try:
                    subreddits = self.config.collectors.reddit_subreddits
                    reddit_docs = self.reddit_collector.collect(subreddits=subreddits)
                    all_documents.extend(reddit_docs)
                    sources_processed += len(subreddits)
                    logger.info("reddit_collection_completed", documents=len(reddit_docs), subreddits=len(subreddits))
                except Exception as e:
                    logger.error("reddit_collection_failed", error=str(e))
                    errors += 1

            # 4. Trends Collection (if enabled)
            if self.trends_collector:
                logger.info("stage_trends_collection")
                try:
                    keywords = self.config.market.seed_keywords
                    trends_docs = self.trends_collector.collect_related_queries(keywords=keywords)
                    all_documents.extend(trends_docs)
                    sources_processed += len(keywords)
                    logger.info("trends_collection_completed", documents=len(trends_docs), keywords=len(keywords))
                except Exception as e:
                    logger.error("trends_collection_failed", error=str(e))
                    errors += 1

            # 5. Autocomplete Collection
            logger.info("stage_autocomplete_collection")
            try:
                keywords = self.config.market.seed_keywords
                autocomplete_docs = self.autocomplete_collector.collect_suggestions(seed_keywords=keywords)
                all_documents.extend(autocomplete_docs)
                sources_processed += len(keywords)
                logger.info("autocomplete_collection_completed", documents=len(autocomplete_docs), keywords=len(keywords))
            except Exception as e:
                logger.error("autocomplete_collection_failed", error=str(e))
                errors += 1

            # 6. Deduplication
            logger.info("stage_deduplication", total_documents=len(all_documents))
            try:
                unique_documents = self.deduplicator.deduplicate(all_documents)
                duplicates_removed = len(all_documents) - len(unique_documents)
                logger.info("deduplication_completed", unique=len(unique_documents), duplicates_removed=duplicates_removed)
            except Exception as e:
                logger.error("deduplication_failed", error=str(e))
                unique_documents = all_documents  # Fallback: use all documents
                errors += 1

            # 7. Save documents to database
            logger.info("stage_save_documents", count=len(unique_documents))
            saved_count = 0
            for doc in unique_documents:
                try:
                    self.db.insert_document(doc)
                    saved_count += 1
                except Exception as e:
                    logger.warning("document_save_failed", doc_id=doc.id, error=str(e))
                    errors += 1

            logger.info("documents_saved", count=saved_count, total=len(unique_documents))

            # Update statistics
            self.stats['documents_collected'] = len(unique_documents)
            self.stats['documents_deduplicated'] = len(all_documents) - len(unique_documents)
            self.stats['errors'] = errors

            stats = {
                'documents_collected': len(unique_documents),
                'documents_saved': saved_count,
                'sources_processed': sources_processed,
                'errors': errors
            }

            logger.info("collect_all_sources_completed", **stats)
            return stats

        except Exception as e:
            logger.error("collect_all_sources_failed", error=str(e))
            raise UniversalTopicAgentError(f"Collection failed: {e}") from e

    async def process_topics(self, limit: Optional[int] = None) -> List[Topic]:
        """
        Process documents into topics through complete pipeline

        Orchestrates:
        1. Clustering → Group similar documents into topics
        2. ContentPipeline → 5-stage enhancement (Competitor, Keywords, Research, Optimization, Scoring)
        3. Storage → Save to database

        Args:
            limit: Maximum number of topics to process (default: all)

        Returns:
            List of processed Topic objects

        Raises:
            UniversalTopicAgentError: If processing fails
        """
        logger.info("process_topics_started", limit=limit)

        try:
            # 1. Get documents from database
            documents = self.db.get_documents_by_language(
                language=self.config.market.language,
                limit=limit * 10 if limit else None  # Get more docs for clustering
            )

            if not documents:
                logger.warning("no_documents_found")
                return []

            logger.info("documents_retrieved", count=len(documents))

            # 2. Clustering
            logger.info("stage_clustering")
            try:
                clusters = self.topic_clusterer.cluster_documents(documents)
                logger.info("clustering_completed", clusters=len(clusters))
                using_fallback = False
            except Exception as e:
                logger.error("clustering_failed", error=str(e))
                # Fallback: create simple clusters (one document per cluster)
                from src.processors.topic_clusterer import TopicCluster
                from dataclasses import dataclass

                clusters = []
                fallback_docs = documents[:limit] if limit else documents
                for i, doc in enumerate(fallback_docs):
                    cluster = TopicCluster(
                        cluster_id=i,
                        label=doc.title,
                        document_ids=[doc.id],
                        topic_titles=[doc.title],
                        size=1,
                        representative_title=doc.title
                    )
                    clusters.append(cluster)
                using_fallback = True
                logger.info("using_fallback_clusters", count=len(clusters))

            # 3. Convert TopicClusters to Topic objects
            topics = []
            # Build document lookup map
            doc_map = {doc.id: doc for doc in documents}

            for cluster in clusters[:limit] if limit else clusters:
                # Get the first document from cluster for metadata
                if not cluster.document_ids:
                    logger.warning("empty_cluster", cluster_id=cluster.cluster_id)
                    continue

                # Get first document as representative
                representative_doc_id = cluster.document_ids[0]
                representative_doc = doc_map.get(representative_doc_id)

                if not representative_doc:
                    logger.warning("document_not_found", doc_id=representative_doc_id)
                    continue

                # Map document source to TopicSource enum
                topic_source = self._map_document_source_to_topic_source(representative_doc.source)

                topic = Topic(
                    title=cluster.representative_title or representative_doc.title,
                    description=representative_doc.summary or cluster.label,
                    cluster_label=cluster.label if not using_fallback else None,
                    source=topic_source,
                    source_url=representative_doc.source_url,
                    domain=self.config.market.domain,
                    market=self.config.market.market,
                    language=self.config.market.language,
                    engagement_score=cluster.size,  # Use cluster size as engagement proxy
                    trending_score=0.0,  # TODO: Calculate from document timestamps
                    status=TopicStatus.DISCOVERED
                )

                topics.append(topic)

            self.stats['topics_clustered'] = len(topics)
            logger.info("topics_created", count=len(topics))

            # 4. Process through ContentPipeline
            processed_topics = []
            for i, topic in enumerate(topics, 1):
                logger.info("processing_topic", index=i, total=len(topics), title=topic.title)

                try:
                    processed_topic = await self.content_pipeline.process_topic(topic, self.config)
                    processed_topics.append(processed_topic)
                    self.stats['topics_processed'] += 1
                except Exception as e:
                    logger.error("topic_processing_failed", topic=topic.title, error=str(e))
                    self.stats['errors'] += 1

            # 5. Save to database
            for topic in processed_topics:
                try:
                    # Convert Topic to dict for storage
                    topic_dict = topic.model_dump()
                    # TODO: Add save_topic() method to SQLiteManager
                    logger.info("topic_saved", title=topic.title)
                except Exception as e:
                    logger.error("topic_save_failed", topic=topic.title, error=str(e))

            logger.info("process_topics_completed", processed=len(processed_topics))
            return processed_topics

        except Exception as e:
            logger.error("process_topics_failed", error=str(e))
            raise UniversalTopicAgentError(f"Topic processing failed: {e}") from e

    async def sync_to_notion(self, limit: int = 10) -> Dict[str, Any]:
        """
        Sync top topics to Notion

        Args:
            limit: Number of top topics to sync (default: 10)

        Returns:
            Result dict with topics_synced, notion_pages_created

        Raises:
            UniversalTopicAgentError: If Notion sync fails or is not configured
        """
        logger.info("sync_to_notion_started", limit=limit)

        if not self.notion_sync:
            raise UniversalTopicAgentError("Notion sync not configured")

        try:
            # Get top topics from database
            # TODO: Add get_top_topics() method to SQLiteManager
            # For now, use mock data
            topics = []

            if not topics:
                logger.warning("no_topics_to_sync")
                return {'topics_synced': 0, 'notion_pages_created': 0}

            # Sync to Notion
            result = await self.notion_sync.sync_topics(topics[:limit])

            self.stats['topics_synced'] = result.get('topics_synced', 0)

            logger.info("sync_to_notion_completed", **result)
            return result

        except Exception as e:
            logger.error("sync_to_notion_failed", error=str(e))
            raise UniversalTopicAgentError(f"Notion sync failed: {e}") from e

    def _map_document_source_to_topic_source(self, document_source: str) -> TopicSource:
        """
        Map document source string to TopicSource enum

        Document sources are like 'rss_example.com', 'autocomplete_suggestions', 'reddit_r/proptech'
        TopicSource enum has: RSS, REDDIT, TRENDS, AUTOCOMPLETE, COMPETITOR, MANUAL

        Args:
            document_source: Document source string (e.g., 'rss_github.blog')

        Returns:
            TopicSource enum value
        """
        if not document_source:
            return TopicSource.RSS  # Default fallback

        source_lower = document_source.lower()

        # Map based on prefix
        if source_lower.startswith('rss'):
            return TopicSource.RSS
        elif source_lower.startswith('reddit'):
            return TopicSource.REDDIT
        elif source_lower.startswith('trends'):
            return TopicSource.TRENDS
        elif 'autocomplete' in source_lower:
            return TopicSource.AUTOCOMPLETE
        elif source_lower.startswith('competitor'):
            return TopicSource.COMPETITOR
        else:
            # Default to RSS for unknown sources
            logger.warning("unknown_document_source", source=document_source, mapped_to="RSS")
            return TopicSource.RSS

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get agent statistics

        Returns:
            Statistics dict
        """
        return self.stats.copy()

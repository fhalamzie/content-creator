"""
Configuration Models

Universal configuration system for ANY domain/market/language.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class CollectorsConfig(BaseModel):
    """
    Collectors configuration

    Controls which collectors are enabled and their settings.
    """
    # Collector toggles
    rss_enabled: bool = Field(default=True, description="Enable RSS collector")
    reddit_enabled: bool = Field(default=False, description="Enable Reddit collector")
    trends_enabled: bool = Field(default=False, description="Enable Trends collector")
    autocomplete_enabled: bool = Field(default=False, description="Enable Autocomplete collector")

    # Custom feeds for RSS collector
    custom_feeds: List[HttpUrl] = Field(
        default_factory=list,
        description="Custom RSS feed URLs"
    )

    # Reddit subreddits
    reddit_subreddits: List[str] = Field(
        default_factory=list,
        description="Subreddits to monitor (without r/ prefix)"
    )

    class Config:
        extra = "allow"  # Allow additional collector-specific settings


class MarketConfig(BaseModel):
    """
    Universal market configuration

    One config works for ANY niche: proptech, fashion, fintech, etc.
    """
    # Identity
    domain: str = Field(..., description="Domain (e.g., 'proptech', 'fashion')")
    market: str = Field(..., description="Market code (e.g., 'de', 'fr', 'us')")
    language: str = Field(..., description="Language code (e.g., 'de', 'en', 'fr')")
    vertical: Optional[str] = Field(None, description="Optional vertical/niche (e.g., 'Proptech', 'Fashion')")
    target_audience: Optional[str] = Field(None, description="Optional target audience description")

    # Discovery sources
    seed_keywords: List[str] = Field(
        ...,
        description="Seed keywords for discovery (5-10 keywords)",
        min_items=1
    )

    # RSS Feeds
    rss_feeds: List[HttpUrl] = Field(
        default_factory=list,
        description="Curated RSS feeds for this domain"
    )
    opml_file: Optional[str] = Field(
        None,
        description="Path to OPML file with feeds"
    )

    # Reddit
    reddit_subreddits: List[str] = Field(
        default_factory=list,
        description="Target subreddits (without r/ prefix)"
    )

    # Competitors
    competitor_urls: List[HttpUrl] = Field(
        default_factory=list,
        description="Competitor websites to analyze"
    )

    # Filtering
    excluded_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords to filter out"
    )

    # Scheduling
    discovery_schedule_cron: str = Field(
        default="0 6 * * *",  # 6 AM daily
        description="Cron expression for discovery runs"
    )

    # Research settings
    research_max_sources: int = Field(default=8, ge=3, le=20)
    research_depth: str = Field(default="balanced", pattern="^(quick|balanced|deep)$")

    # Collectors configuration
    collectors: CollectorsConfig = Field(
        default_factory=CollectorsConfig,
        description="Collectors configuration and toggles"
    )


class LLMConfig(BaseModel):
    """LLM provider configuration"""
    provider: str = Field(default="google_genai", description="LLM provider")
    model: str = Field(default="gemini-1.5-flash", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, ge=100, le=100000)


class SearchConfig(BaseModel):
    """Search/retriever configuration"""
    retriever: str = Field(default="duckduckgo", description="Search provider")
    max_results: int = Field(default=10, ge=3, le=50)


class DatabaseConfig(BaseModel):
    """Database configuration"""
    type: str = Field(default="sqlite", pattern="^(sqlite|postgres)$")
    path: str = Field(default="data/topics.db")
    # For postgres
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None


class NotionConfig(BaseModel):
    """Notion integration (Phase 3)"""
    enabled: bool = False
    api_token: Optional[str] = None
    database_id: Optional[str] = None


class AppConfig(BaseModel):
    """
    Complete application configuration

    Loaded from YAML file: config/markets/{domain}_{market}.yaml
    """
    market: MarketConfig
    llm: LLMConfig = Field(default_factory=LLMConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    notion: NotionConfig = Field(default_factory=NotionConfig)

    # Logging
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")

    class Config:
        extra = "allow"  # Allow additional fields for extensibility

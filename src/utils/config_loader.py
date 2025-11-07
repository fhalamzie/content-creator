"""
Configuration System

Loads market-specific configurations from YAML files with Pydantic validation.
Supports multiple markets/domains/languages through separate config files.

Example:
    from src.utils.config_loader import ConfigLoader

    # Load German PropTech config
    loader = ConfigLoader()
    config = loader.load("proptech_de")

    # Access config values
    print(config.market.domain)       # "SaaS"
    print(config.market.language)     # "de"
    print(config.market.seed_keywords)  # ["PropTech", "Smart Building"]
    print(config.collectors.rss_enabled)  # True

    # Use in collectors
    feeds = config.collectors.custom_feeds
    subreddits = config.collectors.reddit_subreddits
"""

from pathlib import Path
from typing import List, Optional
import yaml
from pydantic import BaseModel, Field, ConfigDict, field_validator, HttpUrl


class MarketConfig(BaseModel):
    """
    Market-specific configuration

    Defines the domain, market, language, and vertical for content collection.
    Each unique combination should have its own config file.
    """

    domain: str = Field(
        ...,
        description="Business domain (SaaS, E-commerce, etc.)"
    )
    market: str = Field(
        ...,
        description="Target market (Germany, France, US, etc.)"
    )
    language: str = Field(
        ...,
        description="ISO 639-1 language code (de, en, fr, etc.)"
    )
    vertical: str = Field(
        ...,
        description="Industry vertical (Proptech, Fashion, etc.)"
    )
    seed_keywords: List[str] = Field(
        ...,
        description="Seed keywords for feed discovery (min 1)",
        min_length=1
    )
    competitor_urls: Optional[List[str]] = Field(
        None,
        description="Known competitor URLs for analysis"
    )
    target_audience: Optional[str] = Field(
        None,
        description="Target audience description (e.g., 'German SMBs')"
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

    @field_validator('seed_keywords')
    @classmethod
    def validate_seed_keywords_not_empty(cls, v):
        """Ensure seed_keywords is not empty"""
        if not v or len(v) == 0:
            raise ValueError("seed_keywords must contain at least one keyword")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "domain": "SaaS",
                "market": "Germany",
                "language": "de",
                "vertical": "Proptech",
                "seed_keywords": ["PropTech", "Smart Building", "DSGVO"],
                "competitor_urls": [
                    "https://www.immobilienscout24.de",
                    "https://www.propstack.de"
                ],
                "target_audience": "German SMBs in real estate"
            }
        }
    )


class CollectorsConfig(BaseModel):
    """
    Collectors configuration

    Controls which collectors are enabled and their settings.
    """

    rss_enabled: bool = Field(
        True,
        description="Enable RSS feed collection"
    )
    reddit_enabled: bool = Field(
        True,
        description="Enable Reddit collection"
    )
    trends_enabled: bool = Field(
        True,
        description="Enable Google Trends collection"
    )
    autocomplete_enabled: bool = Field(
        True,
        description="Enable autocomplete suggestion collection"
    )
    custom_feeds: Optional[List[str]] = Field(
        None,
        description="Custom RSS feed URLs (OPML seed list)"
    )
    reddit_subreddits: Optional[List[str]] = Field(
        None,
        description="Reddit subreddits to monitor"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rss_enabled": True,
                "reddit_enabled": True,
                "trends_enabled": True,
                "autocomplete_enabled": True,
                "custom_feeds": [
                    "https://www.heise.de/rss/heise-atom.xml",
                    "https://t3n.de/rss.xml"
                ],
                "reddit_subreddits": ["de", "Finanzen"]
            }
        }
    )


class SchedulingConfig(BaseModel):
    """
    Scheduling configuration

    Controls when automated tasks run.
    """

    collection_time: str = Field(
        "02:00",
        description="Daily collection time (HH:MM format)"
    )
    notion_sync_day: str = Field(
        "monday",
        description="Day of week for Notion sync (monday, tuesday, etc.)"
    )
    lookback_days: int = Field(
        7,
        description="How many days to look back for content",
        ge=1
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection_time": "02:00",
                "notion_sync_day": "monday",
                "lookback_days": 7
            }
        }
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


class FullConfig(BaseModel):
    """
    Complete configuration combining all sections

    This is the main config object returned by ConfigLoader.load()
    """

    market: MarketConfig
    collectors: CollectorsConfig = Field(default_factory=CollectorsConfig)
    scheduling: SchedulingConfig = Field(default_factory=SchedulingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    notion: NotionConfig = Field(default_factory=NotionConfig)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "market": {
                    "domain": "SaaS",
                    "market": "Germany",
                    "language": "de",
                    "vertical": "Proptech",
                    "seed_keywords": ["PropTech", "Smart Building"]
                },
                "collectors": {
                    "rss_enabled": True,
                    "reddit_enabled": True,
                    "custom_feeds": ["https://www.heise.de/rss/heise-atom.xml"]
                },
                "scheduling": {
                    "collection_time": "02:00",
                    "notion_sync_day": "monday",
                    "lookback_days": 7
                }
            }
        }
    )


class ConfigLoader:
    """
    Configuration loader

    Loads YAML configuration files and validates them with Pydantic.

    Example:
        loader = ConfigLoader()
        config = loader.load("proptech_de")

        # Access nested config
        print(config.market.domain)
        print(config.collectors.rss_enabled)
        print(config.scheduling.collection_time)
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize ConfigLoader

        Args:
            config_dir: Directory containing config YAML files.
                       Defaults to "config/markets" in project root.
        """
        if config_dir is None:
            # Default to config/markets directory
            project_root = Path(__file__).parent.parent.parent
            self.config_dir = project_root / "config" / "markets"
        else:
            self.config_dir = Path(config_dir)

    def load(self, config_name: str) -> FullConfig:
        """
        Load configuration from YAML file

        Args:
            config_name: Config file name without .yaml extension
                        (e.g., "proptech_de" loads "proptech_de.yaml")

        Returns:
            FullConfig object with market, collectors, and scheduling

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValidationError: If config fails Pydantic validation
            Exception: If YAML parsing fails
        """
        config_path = self.config_dir / f"{config_name}.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}"
            )

        # Load YAML
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)

        # Parse into Pydantic models
        # Extract sections from flat YAML structure
        market_data = {}

        # Required fields
        for field in ['domain', 'market', 'language', 'vertical', 'seed_keywords']:
            if field in yaml_data:
                market_data[field] = yaml_data[field]

        # Optional market fields
        if 'competitor_urls' in yaml_data:
            market_data['competitor_urls'] = yaml_data['competitor_urls']
        if 'target_audience' in yaml_data:
            market_data['target_audience'] = yaml_data['target_audience']
        if 'rss_feeds' in yaml_data:
            market_data['rss_feeds'] = yaml_data['rss_feeds']
        if 'opml_file' in yaml_data:
            market_data['opml_file'] = yaml_data['opml_file']
        if 'reddit_subreddits' in yaml_data:
            market_data['reddit_subreddits'] = yaml_data['reddit_subreddits']
        if 'excluded_keywords' in yaml_data:
            market_data['excluded_keywords'] = yaml_data['excluded_keywords']
        if 'discovery_schedule_cron' in yaml_data:
            market_data['discovery_schedule_cron'] = yaml_data['discovery_schedule_cron']
        if 'research_max_sources' in yaml_data:
            market_data['research_max_sources'] = yaml_data['research_max_sources']
        if 'research_depth' in yaml_data:
            market_data['research_depth'] = yaml_data['research_depth']

        # Let Pydantic validation handle missing required fields
        market_config = MarketConfig(**market_data)

        # Collectors (optional section)
        collectors_config = CollectorsConfig()
        if 'collectors' in yaml_data:
            collectors_config = CollectorsConfig(**yaml_data['collectors'])

        # Scheduling (optional section)
        scheduling_config = SchedulingConfig()
        if 'scheduling' in yaml_data:
            scheduling_config = SchedulingConfig(**yaml_data['scheduling'])

        # Combine into full config
        full_config = FullConfig(
            market=market_config,
            collectors=collectors_config,
            scheduling=scheduling_config
        )

        return full_config


# === Convenience Functions ===

def load_config(config_path: str) -> FullConfig:
    """
    Convenience function to load config from file path

    Args:
        config_path: Full path to YAML config file

    Returns:
        FullConfig object

    Example:
        config = load_config("config/markets/proptech_de.yaml")
    """
    config_file = Path(config_path)

    # Load and parse YAML
    with open(config_file, 'r', encoding='utf-8') as f:
        yaml_data = yaml.safe_load(f)

    # Handle flat structure (domain, market, language at top level)
    # Extract market config fields from top level
    market_fields = ['domain', 'market', 'language', 'vertical', 'target_audience', 'seed_keywords', 'competitor_urls']
    market_data = {k: v for k, v in yaml_data.items() if k in market_fields}

    # Validate required market fields
    required_fields = {'domain', 'market', 'language', 'vertical'}
    missing_fields = required_fields - set(market_data.keys())
    if missing_fields:
        raise ValueError(f"Missing required fields in {config_file}: {missing_fields}")

    market_config = MarketConfig(**market_data)

    # Collectors (optional section)
    collectors_config = CollectorsConfig()
    if 'collectors' in yaml_data:
        collectors_config = CollectorsConfig(**yaml_data['collectors'])

    # Scheduling (optional section)
    scheduling_config = SchedulingConfig()
    if 'scheduling' in yaml_data:
        scheduling_config = SchedulingConfig(**yaml_data['scheduling'])

    # Combine into full config
    return FullConfig(
        market=market_config,
        collectors=collectors_config,
        scheduling=scheduling_config
    )

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
from pydantic import BaseModel, Field, ConfigDict, field_validator


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


class CollectorConfig(BaseModel):
    """
    Collector configuration

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


class FullConfig(BaseModel):
    """
    Complete configuration combining all sections

    This is the main config object returned by ConfigLoader.load()
    """

    market: MarketConfig
    collectors: CollectorConfig = Field(default_factory=CollectorConfig)
    scheduling: SchedulingConfig = Field(default_factory=SchedulingConfig)

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

        # Let Pydantic validation handle missing required fields
        market_config = MarketConfig(**market_data)

        # Collectors (optional section)
        collectors_config = CollectorConfig()
        if 'collectors' in yaml_data:
            collectors_config = CollectorConfig(**yaml_data['collectors'])

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

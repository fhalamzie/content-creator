"""
Tests for Configuration System

The configuration system loads market-specific configs (domain, market, language, vertical)
and validates them using Pydantic. Supports YAML files with OPML seed lists.
"""

import pytest
from pydantic import ValidationError

from src.utils.config_loader import (
    ConfigLoader,
    MarketConfig,
    CollectorConfig,
    SchedulingConfig
)


class TestMarketConfig:
    """Test MarketConfig model validation"""

    def test_create_market_config_with_required_fields(self):
        """Test creating MarketConfig with required fields"""
        config = MarketConfig(
            domain="SaaS",
            market="Germany",
            language="de",
            vertical="Proptech",
            seed_keywords=["PropTech", "Smart Building"]
        )

        assert config.domain == "SaaS"
        assert config.market == "Germany"
        assert config.language == "de"
        assert config.vertical == "Proptech"
        assert len(config.seed_keywords) == 2

    def test_create_market_config_with_optional_fields(self):
        """Test creating MarketConfig with optional fields"""
        config = MarketConfig(
            domain="SaaS",
            market="Germany",
            language="de",
            vertical="Proptech",
            seed_keywords=["PropTech"],
            competitor_urls=["https://example.com"],
            target_audience="German SMBs"
        )

        assert config.competitor_urls == ["https://example.com"]
        assert config.target_audience == "German SMBs"

    def test_missing_required_field_raises_error(self):
        """Test missing required fields raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            MarketConfig(
                domain="SaaS",
                market="Germany",
                # Missing language
                vertical="Proptech",
                seed_keywords=["PropTech"]
            )

        assert "language" in str(exc_info.value)

    def test_seed_keywords_cannot_be_empty(self):
        """Test seed_keywords list cannot be empty"""
        with pytest.raises(ValidationError):
            MarketConfig(
                domain="SaaS",
                market="Germany",
                language="de",
                vertical="Proptech",
                seed_keywords=[]  # Empty list
            )


class TestCollectorConfig:
    """Test CollectorConfig model"""

    def test_create_collector_config_with_defaults(self):
        """Test CollectorConfig with default values"""
        config = CollectorConfig()

        # All collectors enabled by default
        assert config.rss_enabled is True
        assert config.reddit_enabled is True
        assert config.trends_enabled is True
        assert config.autocomplete_enabled is True

    def test_create_collector_config_with_custom_values(self):
        """Test CollectorConfig with custom values"""
        config = CollectorConfig(
            rss_enabled=True,
            reddit_enabled=False,
            trends_enabled=True,
            autocomplete_enabled=False,
            custom_feeds=["https://example.com/feed.xml"],
            reddit_subreddits=["de", "Finanzen"]
        )

        assert config.rss_enabled is True
        assert config.reddit_enabled is False
        assert config.custom_feeds == ["https://example.com/feed.xml"]
        assert config.reddit_subreddits == ["de", "Finanzen"]


class TestSchedulingConfig:
    """Test SchedulingConfig model"""

    def test_create_scheduling_config_with_defaults(self):
        """Test SchedulingConfig with default values"""
        config = SchedulingConfig()

        assert config.collection_time == "02:00"
        assert config.notion_sync_day == "monday"
        assert config.lookback_days == 7

    def test_create_scheduling_config_with_custom_values(self):
        """Test SchedulingConfig with custom values"""
        config = SchedulingConfig(
            collection_time="03:30",
            notion_sync_day="wednesday",
            lookback_days=14
        )

        assert config.collection_time == "03:30"
        assert config.notion_sync_day == "wednesday"
        assert config.lookback_days == 14


class TestConfigLoader:
    """Test ConfigLoader functionality"""

    def test_load_config_from_yaml(self, tmp_path):
        """Test loading config from YAML file"""
        # Create test config file
        config_content = """
domain: SaaS
market: Germany
language: de
vertical: Proptech

seed_keywords:
  - PropTech
  - Smart Building
  - DSGVO

competitor_urls:
  - https://www.immobilienscout24.de
  - https://www.propstack.de

collectors:
  rss_enabled: true
  reddit_enabled: true
  trends_enabled: true
  autocomplete_enabled: true
  custom_feeds:
    - https://www.heise.de/rss/heise-atom.xml
    - https://t3n.de/rss.xml
  reddit_subreddits:
    - de
    - Finanzen

scheduling:
  collection_time: "02:00"
  notion_sync_day: monday
  lookback_days: 7
"""
        config_file = tmp_path / "proptech_de.yaml"
        config_file.write_text(config_content)

        # Load config
        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load("proptech_de")

        assert config.market.domain == "SaaS"
        assert config.market.market == "Germany"
        assert config.market.language == "de"
        assert len(config.market.seed_keywords) == 3
        assert len(config.market.competitor_urls) == 2

    def test_load_config_from_yaml_with_minimal_fields(self, tmp_path):
        """Test loading config with only required fields"""
        config_content = """
domain: E-commerce
market: France
language: fr
vertical: Fashion

seed_keywords:
  - Mode
  - E-commerce
"""
        config_file = tmp_path / "fashion_fr.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load("fashion_fr")

        assert config.market.domain == "E-commerce"
        assert config.market.market == "France"
        assert config.market.language == "fr"
        assert config.market.vertical == "Fashion"

    def test_load_nonexistent_config_raises_error(self, tmp_path):
        """Test loading non-existent config raises FileNotFoundError"""
        loader = ConfigLoader(config_dir=str(tmp_path))

        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent")

    def test_load_invalid_yaml_raises_error(self, tmp_path):
        """Test loading invalid YAML raises error"""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: syntax: error:")

        loader = ConfigLoader(config_dir=str(tmp_path))

        with pytest.raises(Exception):  # YAML parsing error
            loader.load("invalid")

    def test_load_config_missing_required_field_raises_error(self, tmp_path):
        """Test loading config missing required field raises ValidationError"""
        config_content = """
domain: SaaS
market: Germany
# Missing language field
vertical: Proptech

seed_keywords:
  - PropTech
"""
        config_file = tmp_path / "incomplete.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(config_dir=str(tmp_path))

        with pytest.raises(ValidationError):
            loader.load("incomplete")


class TestConfigLoaderDefaults:
    """Test ConfigLoader default values"""

    def test_default_collectors_all_enabled(self, tmp_path):
        """Test collectors default to enabled if not specified"""
        config_content = """
domain: SaaS
market: Germany
language: de
vertical: Proptech

seed_keywords:
  - PropTech
"""
        config_file = tmp_path / "defaults.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load("defaults")

        # Default collector config
        assert config.collectors.rss_enabled is True
        assert config.collectors.reddit_enabled is True
        assert config.collectors.trends_enabled is True
        assert config.collectors.autocomplete_enabled is True

    def test_default_scheduling(self, tmp_path):
        """Test scheduling defaults if not specified"""
        config_content = """
domain: SaaS
market: Germany
language: de
vertical: Proptech

seed_keywords:
  - PropTech
"""
        config_file = tmp_path / "defaults.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load("defaults")

        assert config.scheduling.collection_time == "02:00"
        assert config.scheduling.notion_sync_day == "monday"
        assert config.scheduling.lookback_days == 7


class TestConfigLoaderMultipleConfigs:
    """Test loading multiple configs"""

    def test_load_multiple_configs(self, tmp_path):
        """Test loading different market configs"""
        # German PropTech config
        config1_content = """
domain: SaaS
market: Germany
language: de
vertical: Proptech
seed_keywords:
  - PropTech
"""
        (tmp_path / "proptech_de.yaml").write_text(config1_content)

        # French Fashion config
        config2_content = """
domain: E-commerce
market: France
language: fr
vertical: Fashion
seed_keywords:
  - Mode
"""
        (tmp_path / "fashion_fr.yaml").write_text(config2_content)

        loader = ConfigLoader(config_dir=str(tmp_path))

        # Load both configs
        config1 = loader.load("proptech_de")
        config2 = loader.load("fashion_fr")

        assert config1.market.language == "de"
        assert config1.market.vertical == "Proptech"

        assert config2.market.language == "fr"
        assert config2.market.vertical == "Fashion"


class TestConfigLoaderHelpers:
    """Test helper methods"""

    def test_get_opml_feeds(self, tmp_path):
        """Test extracting custom feeds from config"""
        config_content = """
domain: SaaS
market: Germany
language: de
vertical: Proptech

seed_keywords:
  - PropTech

collectors:
  custom_feeds:
    - https://www.heise.de/rss/heise-atom.xml
    - https://t3n.de/rss.xml
    - https://www.golem.de/rss.php
"""
        config_file = tmp_path / "opml_test.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load("opml_test")

        # Get custom feeds
        feeds = config.collectors.custom_feeds

        assert len(feeds) == 3
        assert "https://www.heise.de/rss/heise-atom.xml" in feeds
        assert "https://t3n.de/rss.xml" in feeds

    def test_get_reddit_subreddits(self, tmp_path):
        """Test extracting Reddit subreddits from config"""
        config_content = """
domain: SaaS
market: Germany
language: de
vertical: Proptech

seed_keywords:
  - PropTech

collectors:
  reddit_subreddits:
    - de
    - Finanzen
    - PropTech
"""
        config_file = tmp_path / "reddit_test.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load("reddit_test")

        # Get subreddits
        subreddits = config.collectors.reddit_subreddits

        assert len(subreddits) == 3
        assert "de" in subreddits
        assert "Finanzen" in subreddits


class TestConfigValidation:
    """Test configuration validation rules"""

    def test_language_iso_639_1_format(self, tmp_path):
        """Test language field accepts ISO 639-1 codes"""
        for lang_code in ["de", "en", "fr", "es", "it"]:
            config_content = f"""
domain: SaaS
market: Test
language: {lang_code}
vertical: Test
seed_keywords:
  - test
"""
            config_file = tmp_path / f"lang_{lang_code}.yaml"
            config_file.write_text(config_content)

            loader = ConfigLoader(config_dir=str(tmp_path))
            config = loader.load(f"lang_{lang_code}")

            assert config.market.language == lang_code

    def test_seed_keywords_minimum_one(self, tmp_path):
        """Test seed_keywords requires at least one keyword"""
        config_content = """
domain: SaaS
market: Germany
language: de
vertical: Proptech
seed_keywords:
  - PropTech
"""
        config_file = tmp_path / "min_keywords.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load("min_keywords")

        assert len(config.market.seed_keywords) >= 1

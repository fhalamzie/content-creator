"""
Settings Loader

Loads and validates configuration from .env file.

Design Principles:
- Fail fast on missing required settings
- Type validation for numeric settings
- Clear error messages
- Single source of truth for configuration
"""

import os
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

logger.info(f"Loaded environment from: {env_path}")


class SettingsError(Exception):
    """Raised when settings are invalid or missing"""
    pass


class Settings:
    """
    Application settings loaded from environment variables.

    Usage:
        from config.settings import settings

        # Access settings
        token = settings.NOTION_TOKEN
        rate = settings.NOTION_RATE_LIMIT
    """

    # ==================== Notion Settings ====================

    @property
    def NOTION_TOKEN(self) -> str:
        """Notion integration token (required)"""
        token = os.getenv("NOTION_TOKEN", "").strip()
        if not token:
            raise SettingsError(
                "NOTION_TOKEN is required. "
                "Create an integration at https://www.notion.so/my-integrations"
            )
        return token

    @property
    def NOTION_PAGE_ID(self) -> str:
        """Notion parent page ID for creating databases (required)"""
        page_id = os.getenv("NOTION_PAGE_ID", "").strip()
        if not page_id:
            raise SettingsError(
                "NOTION_PAGE_ID is required. "
                "This is the page where databases will be created."
            )
        return page_id

    @property
    def NOTION_RATE_LIMIT(self) -> float:
        """Notion API rate limit (requests per second)"""
        rate = os.getenv("NOTION_RATE_LIMIT", "2.5")
        try:
            rate_float = float(rate)
            if rate_float <= 0:
                raise ValueError("Rate limit must be positive")
            return rate_float
        except ValueError as e:
            raise SettingsError(f"Invalid NOTION_RATE_LIMIT: {rate}. Must be a positive number.") from e

    # ==================== OpenRouter Settings ====================

    @property
    def OPENROUTER_API_KEY(self) -> str:
        """OpenRouter API key (required)"""
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise SettingsError(
                "OPENROUTER_API_KEY is required. "
                "Get your key at https://openrouter.ai/keys"
            )
        return key

    @property
    def MODEL_WRITING(self) -> str:
        """Model for blog post writing"""
        return os.getenv("MODEL_WRITING", "qwen/qwq-32b-preview")

    @property
    def MODEL_REPURPOSING(self) -> str:
        """Model for social media repurposing"""
        return os.getenv("MODEL_REPURPOSING", "qwen/qwq-32b-preview")

    # ==================== Content Settings ====================

    @property
    def CONTENT_LANGUAGE(self) -> str:
        """Content language (ISO 639-1 code)"""
        return os.getenv("CONTENT_LANGUAGE", "de")

    @property
    def CACHE_DIR(self) -> str:
        """Cache directory path"""
        return os.getenv("CACHE_DIR", "cache")

    # ==================== Logging Settings ====================

    @property
    def LOG_LEVEL(self) -> str:
        """Logging level"""
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level not in valid_levels:
            logger.warning(f"Invalid LOG_LEVEL: {level}. Using INFO.")
            return "INFO"
        return level

    @property
    def LOG_FILE(self) -> str:
        """Log file path"""
        return os.getenv("LOG_FILE", "logs/app.log")

    # ==================== Validation ====================

    def validate_all(self) -> None:
        """
        Validate all required settings.

        Raises:
            SettingsError: If any required setting is missing or invalid
        """
        required_settings = [
            "NOTION_TOKEN",
            "NOTION_PAGE_ID",
            "OPENROUTER_API_KEY"
        ]

        errors = []
        for setting_name in required_settings:
            try:
                getattr(self, setting_name)
            except SettingsError as e:
                errors.append(str(e))

        if errors:
            raise SettingsError(
                "Configuration errors:\n" + "\n".join(f"  - {err}" for err in errors)
            )

        logger.info("All settings validated successfully")

    def to_dict(self, mask_secrets: bool = True) -> dict:
        """
        Convert settings to dict for display.

        Args:
            mask_secrets: Mask sensitive values (default: True)

        Returns:
            Dict of all settings
        """
        def mask(value: str) -> str:
            if not mask_secrets or len(value) <= 8:
                return value
            return value[:4] + "****" + value[-4:]

        try:
            return {
                # Notion
                "NOTION_TOKEN": mask(self.NOTION_TOKEN),
                "NOTION_PAGE_ID": mask(self.NOTION_PAGE_ID),
                "NOTION_RATE_LIMIT": self.NOTION_RATE_LIMIT,
                # OpenRouter
                "OPENROUTER_API_KEY": mask(self.OPENROUTER_API_KEY),
                "MODEL_WRITING": self.MODEL_WRITING,
                "MODEL_REPURPOSING": self.MODEL_REPURPOSING,
                # Content
                "CONTENT_LANGUAGE": self.CONTENT_LANGUAGE,
                "CACHE_DIR": self.CACHE_DIR,
                # Logging
                "LOG_LEVEL": self.LOG_LEVEL,
                "LOG_FILE": self.LOG_FILE,
            }
        except SettingsError:
            # If validation fails, return partial dict
            return {"error": "Some settings are missing or invalid"}


# Global settings instance
settings = Settings()


# ==================== Convenience Functions ====================

def get_notion_client_config() -> dict:
    """
    Get configuration for NotionClient.

    Returns:
        Dict with 'token' and 'rate_limit'
    """
    return {
        "token": settings.NOTION_TOKEN,
        "rate_limit": settings.NOTION_RATE_LIMIT
    }


def get_cache_manager_config() -> dict:
    """
    Get configuration for CacheManager.

    Returns:
        Dict with 'cache_dir'
    """
    return {
        "cache_dir": settings.CACHE_DIR
    }


def setup_logging() -> None:
    """
    Configure application logging based on settings.
    """
    log_file = Path(settings.LOG_FILE)
    log_file.parent.mkdir(exist_ok=True, parents=True)

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    logger.info(f"Logging configured: level={settings.LOG_LEVEL}, file={log_file}")

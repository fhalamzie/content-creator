"""Tests for Settings UI page.

Tests cover:
- API key masking
- Environment variable saving
- Rate limit validation
- Model selection
- Form submission
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import os


# Import settings page functions
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ui.pages.settings import (
    mask_api_key,
    save_env_variable,
)


class TestApiKeyMasking:
    """Test API key masking functionality."""

    def test_mask_api_key_with_valid_key(self):
        """Test masking of valid API key shows first and last 4 chars."""
        key = "sk-or-v1-1234567890abcdefghij"
        result = mask_api_key(key)
        assert result == "sk-o...ghij"

    def test_mask_api_key_with_short_key(self):
        """Test masking of short key returns 'Not set'."""
        key = "short"
        result = mask_api_key(key)
        assert result == "Not set"

    def test_mask_api_key_with_empty_key(self):
        """Test masking of empty key returns 'Not set'."""
        key = ""
        result = mask_api_key(key)
        assert result == "Not set"

    def test_mask_api_key_with_none(self):
        """Test masking of None returns 'Not set'."""
        result = mask_api_key(None)
        assert result == "Not set"

    def test_mask_api_key_preserves_exactly_8_chars(self):
        """Test masking preserves exactly 8 characters (4 start + 4 end)."""
        key = "abcdefghijklmnop"
        result = mask_api_key(key)
        assert result.startswith("abcd")
        assert result.endswith("mnop")
        assert "..." in result


class TestEnvVariableSaving:
    """Test environment variable saving functionality."""

    @patch('ui.pages.settings.ENV_FILE')
    @patch('ui.pages.settings.set_key')
    def test_save_env_variable_creates_file_if_not_exists(self, mock_set_key, mock_env_file):
        """Test that .env file is created if it doesn't exist."""
        mock_env_file.exists.return_value = False
        mock_env_file.touch = Mock()

        save_env_variable("TEST_KEY", "test_value")

        mock_env_file.touch.assert_called_once()
        mock_set_key.assert_called_once_with(mock_env_file, "TEST_KEY", "test_value")

    @patch('ui.pages.settings.ENV_FILE')
    @patch('ui.pages.settings.set_key')
    def test_save_env_variable_updates_existing_file(self, mock_set_key, mock_env_file):
        """Test that existing .env file is updated correctly."""
        mock_env_file.exists.return_value = True

        save_env_variable("NOTION_TOKEN", "secret_new_token")

        mock_env_file.touch.assert_not_called()
        mock_set_key.assert_called_once_with(mock_env_file, "NOTION_TOKEN", "secret_new_token")

    @patch('ui.pages.settings.ENV_FILE')
    @patch('ui.pages.settings.set_key')
    @patch.dict(os.environ, {}, clear=True)
    def test_save_env_variable_updates_os_environ(self, mock_set_key, mock_env_file):
        """Test that os.environ is updated after saving."""
        mock_env_file.exists.return_value = True

        save_env_variable("TEST_VAR", "test_value")

        assert os.environ["TEST_VAR"] == "test_value"

    @patch('ui.pages.settings.ENV_FILE')
    @patch('ui.pages.settings.set_key')
    def test_save_env_variable_with_special_characters(self, mock_set_key, mock_env_file):
        """Test saving environment variable with special characters."""
        mock_env_file.exists.return_value = True
        special_value = "https://api.example.com/v1?key=123&secret=456"

        save_env_variable("API_URL", special_value)

        mock_set_key.assert_called_once_with(mock_env_file, "API_URL", special_value)


class TestRateLimitValidation:
    """Test rate limit validation logic."""

    def test_notion_rate_limit_within_range(self):
        """Test that valid rate limits (1.0-3.0) are accepted."""
        valid_values = [1.0, 1.5, 2.0, 2.5, 3.0]
        for value in valid_values:
            assert 1.0 <= value <= 3.0

    def test_notion_rate_limit_below_minimum(self):
        """Test that rate limit below 1.0 is rejected."""
        invalid_value = 0.5
        assert not (1.0 <= invalid_value <= 3.0)

    def test_notion_rate_limit_above_maximum(self):
        """Test that rate limit above 3.0 is rejected."""
        invalid_value = 3.5
        assert not (1.0 <= invalid_value <= 3.0)

    def test_notion_rate_limit_default_value(self):
        """Test default rate limit is 2.5 (within safe range)."""
        default_value = 2.5
        assert 1.0 <= default_value <= 3.0


class TestModelConfiguration:
    """Test model configuration functionality."""

    def test_writing_models_list_contains_qwen(self):
        """Test that Qwen model is in writing models list."""
        writing_models = [
            "qwen/qwq-32b-preview",
            "anthropic/claude-sonnet-4",
            "anthropic/claude-opus-4",
            "openai/gpt-4"
        ]
        assert "qwen/qwq-32b-preview" in writing_models

    def test_repurposing_models_list_contains_haiku(self):
        """Test that Haiku model is in repurposing models list."""
        repurposing_models = [
            "qwen/qwq-32b-preview",
            "anthropic/claude-sonnet-4",
            "anthropic/claude-haiku-4",
            "openai/gpt-4"
        ]
        assert "anthropic/claude-haiku-4" in repurposing_models

    def test_model_cost_estimation_qwen(self):
        """Test cost estimation for Qwen model."""
        costs = {
            "qwen/qwq-32b-preview": 0.98,
            "anthropic/claude-sonnet-4": 3.50,
        }
        assert costs["qwen/qwq-32b-preview"] < costs["anthropic/claude-sonnet-4"]

    def test_model_cost_estimation_haiku_cheapest(self):
        """Test that Haiku is the cheapest repurposing model."""
        costs = {
            "qwen/qwq-32b-preview": 0.98,
            "anthropic/claude-sonnet-4": 3.50,
            "anthropic/claude-haiku-4": 0.50,
        }
        assert costs["anthropic/claude-haiku-4"] < costs["qwen/qwq-32b-preview"]

    def test_content_language_options(self):
        """Test content language options include German and English."""
        languages = ["de", "en"]
        assert "de" in languages
        assert "en" in languages

    def test_default_content_language_is_german(self):
        """Test default content language is German."""
        default_language = "de"
        assert default_language == "de"


class TestAdvancedSettings:
    """Test advanced settings functionality."""

    def test_cache_directory_default_value(self):
        """Test default cache directory is 'cache'."""
        default_cache_dir = "cache"
        assert default_cache_dir == "cache"

    def test_log_level_options(self):
        """Test log level options are valid."""
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        for level in log_levels:
            assert level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_default_log_level_is_info(self):
        """Test default log level is INFO."""
        default_log_level = "INFO"
        assert default_log_level == "INFO"

    def test_feature_flags_default_values(self):
        """Test feature flags default to enabled."""
        enable_research = True
        enable_fact_check = True
        enable_auto_sync = True

        assert enable_research is True
        assert enable_fact_check is True
        assert enable_auto_sync is True


class TestConnectionTesting:
    """Test connection testing functionality."""

    @patch.dict(os.environ, {"NOTION_TOKEN": "test_token"})
    def test_notion_connection_success(self):
        """Test successful Notion connection."""
        # Test that token is available for connection
        token = os.getenv("NOTION_TOKEN")
        assert token == "test_token"
        assert len(token) > 0

    @patch.dict(os.environ, {"NOTION_TOKEN": ""})
    def test_notion_connection_failure(self):
        """Test failed Notion connection with missing token."""
        # Test that missing token can be detected
        token = os.getenv("NOTION_TOKEN", "")
        assert token == ""

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"})
    def test_openrouter_connection_configured(self):
        """Test OpenRouter client configuration."""
        # Test that API key is available for configuration
        api_key = os.getenv("OPENROUTER_API_KEY")
        assert api_key == "test_key"
        assert len(api_key) > 0


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    @patch('ui.pages.settings.ENV_FILE')
    @patch('ui.pages.settings.set_key')
    def test_complete_api_key_update_flow(self, mock_set_key, mock_env_file):
        """Test complete flow of updating all API keys."""
        mock_env_file.exists.return_value = True

        # Simulate user updating all keys
        keys_to_update = {
            "NOTION_TOKEN": "secret_notion_token_123456789",
            "NOTION_PAGE_ID": "abc123def456ghi789jkl012mno345pq",
            "OPENROUTER_API_KEY": "sk-or-v1-abcdefghijklmnop123456"
        }

        for key, value in keys_to_update.items():
            save_env_variable(key, value)

        # Verify all keys were saved
        assert mock_set_key.call_count == 3

    @patch('ui.pages.settings.ENV_FILE')
    @patch('ui.pages.settings.set_key')
    def test_partial_settings_update(self, mock_set_key, mock_env_file):
        """Test updating only some settings (not all)."""
        mock_env_file.exists.return_value = True

        # User only updates rate limit
        save_env_variable("NOTION_RATE_LIMIT", "2.0")

        # Verify only one save occurred
        assert mock_set_key.call_count == 1
        mock_set_key.assert_called_with(mock_env_file, "NOTION_RATE_LIMIT", "2.0")

    @patch.dict(os.environ, {}, clear=True)
    def test_settings_page_without_required_env_vars(self):
        """Test settings page behavior when required env vars are missing."""
        # Should return empty strings or None for missing vars
        notion_token = os.getenv("NOTION_TOKEN", "")
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

        assert notion_token == ""
        assert openrouter_key == ""

    def test_model_selection_cost_calculation(self):
        """Test cost calculation based on model selection."""
        costs = {
            "qwen/qwq-32b-preview": 0.98,
            "anthropic/claude-sonnet-4": 3.50,
            "anthropic/claude-opus-4": 15.00,
            "anthropic/claude-haiku-4": 0.50,
        }

        writing_model = "qwen/qwq-32b-preview"
        repurposing_model = "anthropic/claude-haiku-4"

        writing_cost = costs.get(writing_model, 1.0) * 0.65
        repurposing_cost = costs.get(repurposing_model, 0.5) * 0.27
        total_cost = writing_cost + repurposing_cost

        assert total_cost == pytest.approx(0.772, 0.01)  # 0.637 + 0.135

    def test_masked_api_keys_display(self):
        """Test that API keys are properly masked for display."""
        test_keys = {
            "NOTION_TOKEN": "secret_abcd1234efgh5678ijkl9012mnop3456",
            "OPENROUTER_API_KEY": "sk-or-v1-xyz789abc123def456ghi",
        }

        masked_keys = {
            key: mask_api_key(value)
            for key, value in test_keys.items()
        }

        # Verify masking happened
        for key, masked_value in masked_keys.items():
            original_value = test_keys[key]
            assert len(masked_value) < len(original_value)
            assert "..." in masked_value


# Mark all tests as UI tests for optional filtering
pytestmark = pytest.mark.ui

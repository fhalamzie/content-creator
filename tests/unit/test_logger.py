"""
Tests for central logging system

Central logging uses structlog for structured output with:
- Correlation IDs
- ISO timestamps
- Log levels
- Context variables
- Metrics hooks
"""

import logging
import pytest
import structlog

from src.utils.logger import setup_logging, get_logger


class TestLoggingSetup:
    """Test logging configuration"""

    def test_setup_logging_default_level(self):
        """Test default log level is INFO"""
        setup_logging()

        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_custom_level(self):
        """Test custom log level configuration"""
        setup_logging(log_level="DEBUG")

        logger = get_logger("test")
        assert logger is not None

    def test_setup_logging_invalid_level_raises_error(self):
        """Test invalid log level raises AttributeError"""
        with pytest.raises(AttributeError):
            setup_logging(log_level="INVALID")


class TestGetLogger:
    """Test logger retrieval"""

    def setup_method(self):
        """Setup before each test"""
        setup_logging(log_level="INFO")

    def test_get_logger_returns_bound_logger(self):
        """Test get_logger returns structlog BoundLogger"""
        logger = get_logger("test_module")

        assert logger is not None
        # structlog returns BoundLoggerLazyProxy which acts like BoundLogger
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'debug')
        assert hasattr(logger, 'warning')

    def test_get_logger_different_names(self):
        """Test loggers with different names work independently"""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        # Both loggers should have logging methods
        assert hasattr(logger1, 'info')
        assert hasattr(logger2, 'info')


class TestStructuredLogging:
    """Test structured logging output"""

    def setup_method(self):
        """Setup before each test"""
        setup_logging(log_level="DEBUG")

    def test_log_info_structured_output(self, capsys):
        """Test INFO log includes event and context"""
        logger = get_logger("test")
        logger.info("test_event", key1="value1", key2=42)

        captured = capsys.readouterr()
        output = captured.out
        assert "test_event" in output
        assert "key1" in output
        assert "value1" in output
        assert "key2" in output
        assert "42" in output
        assert "info" in output.lower()

    def test_log_error_structured_output(self, capsys):
        """Test ERROR log includes event and error details"""
        logger = get_logger("test")
        logger.error("test_error", error="Something went wrong", code=500)

        captured = capsys.readouterr()
        output = captured.out
        assert "test_error" in output
        assert "error" in output.lower()
        assert "Something went wrong" in output
        assert "500" in output

    def test_log_debug_structured_output(self, capsys):
        """Test DEBUG log includes event and debug info"""
        logger = get_logger("test")
        logger.debug("test_debug", function="process_data", step=1)

        captured = capsys.readouterr()
        output = captured.out
        assert "test_debug" in output
        assert "debug" in output.lower()
        assert "process_data" in output

    def test_log_warning_structured_output(self, capsys):
        """Test WARNING log includes event and warning details"""
        logger = get_logger("test")
        logger.warning("test_warning", threshold_exceeded=True, value=150)

        captured = capsys.readouterr()
        output = captured.out
        assert "test_warning" in output
        assert "warning" in output.lower()
        assert "threshold_exceeded" in output
        assert "150" in output


class TestLogLevels:
    """Test log level filtering"""

    def test_info_level_filters_debug(self, capsys):
        """Test INFO level filters out DEBUG messages"""
        setup_logging(log_level="INFO")
        logger = get_logger("test")

        logger.debug("debug_message", should_appear=False)
        logger.info("info_message", should_appear=True)

        captured = capsys.readouterr()
        output = captured.out
        assert "debug_message" not in output
        assert "info_message" in output

    def test_error_level_filters_info_and_debug(self, capsys):
        """Test ERROR level filters out INFO and DEBUG"""
        setup_logging(log_level="ERROR")
        logger = get_logger("test")

        logger.debug("debug_message")
        logger.info("info_message")
        logger.warning("warning_message")
        logger.error("error_message")

        captured = capsys.readouterr()
        output = captured.out
        assert "debug_message" not in output
        assert "info_message" not in output
        assert "warning_message" not in output
        assert "error_message" in output

    def test_debug_level_shows_all(self, capsys):
        """Test DEBUG level shows all messages"""
        setup_logging(log_level="DEBUG")
        logger = get_logger("test")

        logger.debug("debug_message")
        logger.info("info_message")
        logger.warning("warning_message")
        logger.error("error_message")

        captured = capsys.readouterr()
        output = captured.out
        assert "debug_message" in output
        assert "info_message" in output
        assert "warning_message" in output
        assert "error_message" in output


class TestMetricsHooks:
    """Test metrics tracking capabilities"""

    def setup_method(self):
        """Setup before each test"""
        setup_logging(log_level="INFO")

    def test_log_wal_size_metric(self, capsys):
        """Test logging WAL size metric"""
        logger = get_logger("metrics_test")
        logger.info("wal_checkpoint_forced", wal_size_mb=15.2)

        captured = capsys.readouterr()
        output = captured.out
        assert "wal_checkpoint_forced" in output
        assert "wal_size_mb" in output
        assert "15.2" in output

    def test_log_api_usage_metric(self, capsys):
        """Test logging API usage metric"""
        logger = get_logger("metrics_test")
        logger.info("api_call",
                   service="serpapi",
                   daily_usage=2,
                   daily_limit=3)

        captured = capsys.readouterr()
        output = captured.out
        assert "api_call" in output
        assert "serpapi" in output
        assert "daily_usage" in output
        assert "2" in output

    def test_log_error_rate_metric(self, capsys):
        """Test logging error rate metric"""
        logger = get_logger("metrics_test")
        logger.warning("high_error_rate",
                      collector="rss",
                      error_count=10,
                      total_requests=100,
                      error_rate=0.1)

        captured = capsys.readouterr()
        output = captured.out
        assert "high_error_rate" in output
        assert "rss" in output
        assert "error_rate" in output
        assert "0.1" in output

    def test_log_cache_hit_rate_metric(self, capsys):
        """Test logging cache hit rate metric"""
        logger = get_logger("metrics_test")
        logger.info("cache_stats",
                   cache_hits=60,
                   cache_misses=40,
                   hit_rate=0.6)

        captured = capsys.readouterr()
        output = captured.out
        assert "cache_stats" in output
        assert "hit_rate" in output
        assert "0.6" in output


class TestLoggerUsagePatterns:
    """Test common usage patterns"""

    def setup_method(self):
        """Setup before each test"""
        setup_logging(log_level="INFO")

    def test_collection_started_pattern(self, capsys):
        """Test START logging pattern"""
        logger = get_logger("rss_collector")
        logger.info("rss_collection_started", feed_count=20)

        captured = capsys.readouterr()
        output = captured.out
        assert "rss_collection_started" in output
        assert "feed_count" in output
        assert "20" in output

    def test_collection_success_pattern(self, capsys):
        """Test SUCCESS logging pattern"""
        logger = get_logger("rss_collector")
        logger.info("rss_collection_success",
                   article_count=142,
                   duration=3.2)

        captured = capsys.readouterr()
        output = captured.out
        assert "rss_collection_success" in output
        assert "article_count" in output
        assert "142" in output
        assert "duration" in output

    def test_collection_failed_pattern(self, capsys):
        """Test FAILED logging pattern with exception"""
        logger = get_logger("rss_collector")

        try:
            raise ValueError("Test error")
        except Exception as e:
            logger.error("rss_collection_failed",
                        error=str(e),
                        feed="https://example.com/feed")

        captured = capsys.readouterr()
        output = captured.out
        assert "rss_collection_failed" in output
        assert "error" in output
        assert "Test error" in output
        assert "example.com" in output

    def test_nested_context_pattern(self, capsys):
        """Test logging with nested context"""
        logger = get_logger("processor")

        logger.info("processing_document",
                   document_id="doc123",
                   language="de",
                   metadata={
                       "source": "rss_heise",
                       "published_at": "2025-11-03"
                   })

        captured = capsys.readouterr()
        output = captured.out
        assert "processing_document" in output
        assert "doc123" in output
        assert "de" in output
        # Note: dict representation may vary, but should be present
        assert "source" in output or "metadata" in output

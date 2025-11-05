"""
Tests for CostTracker

Tests cost tracking for free/paid API calls with fallback scenarios.
"""

import pytest
from datetime import datetime, timedelta

from src.orchestrator.cost_tracker import CostTracker, APICall, APIType


class TestCostTracker:
    """Test CostTracker functionality"""

    def test_init_default(self):
        """Test initialization with default values"""
        tracker = CostTracker()

        assert tracker.total_cost == 0.0
        assert tracker.free_calls_count == 0
        assert tracker.paid_calls_count == 0
        assert len(tracker.get_all_calls()) == 0

    def test_track_free_call(self):
        """Test tracking free API call"""
        tracker = CostTracker()

        tracker.track_call(
            api_type=APIType.GEMINI_FREE,
            stage="stage2",
            success=True,
            cost=0.0
        )

        assert tracker.free_calls_count == 1
        assert tracker.paid_calls_count == 0
        assert tracker.total_cost == 0.0

    def test_track_paid_call(self):
        """Test tracking paid API call"""
        tracker = CostTracker()

        tracker.track_call(
            api_type=APIType.TAVILY,
            stage="stage2",
            success=True,
            cost=0.02
        )

        assert tracker.free_calls_count == 0
        assert tracker.paid_calls_count == 1
        assert tracker.total_cost == 0.02

    def test_track_multiple_calls(self):
        """Test tracking multiple API calls"""
        tracker = CostTracker()

        # Free call
        tracker.track_call(APIType.GEMINI_FREE, "stage2", True, 0.0)

        # Paid calls
        tracker.track_call(APIType.TAVILY, "stage2", True, 0.02)
        tracker.track_call(APIType.PAID_NEWS, "stage4", True, 0.01)

        assert tracker.free_calls_count == 1
        assert tracker.paid_calls_count == 2
        assert tracker.total_cost == 0.03

    def test_track_failed_call(self):
        """Test tracking failed API call"""
        tracker = CostTracker()

        tracker.track_call(
            api_type=APIType.GEMINI_FREE,
            stage="stage2",
            success=False,
            cost=0.0,
            error="Rate limit exceeded"
        )

        assert tracker.free_calls_count == 1
        assert tracker.paid_calls_count == 0

        calls = tracker.get_all_calls()
        assert len(calls) == 1
        assert calls[0].success is False
        assert calls[0].error == "Rate limit exceeded"

    def test_get_stage_stats(self):
        """Test getting statistics by stage"""
        tracker = CostTracker()

        # Stage 2 calls
        tracker.track_call(APIType.GEMINI_FREE, "stage2", True, 0.0)
        tracker.track_call(APIType.TAVILY, "stage2", True, 0.02)

        # Stage 4 calls
        tracker.track_call(APIType.FREE_NEWS, "stage4", True, 0.0)
        tracker.track_call(APIType.PAID_NEWS, "stage4", True, 0.01)

        stage2_stats = tracker.get_stage_stats("stage2")
        assert stage2_stats["calls_count"] == 2
        assert stage2_stats["total_cost"] == 0.02
        assert stage2_stats["free_calls"] == 1
        assert stage2_stats["paid_calls"] == 1

        stage4_stats = tracker.get_stage_stats("stage4")
        assert stage4_stats["calls_count"] == 2
        assert stage4_stats["total_cost"] == 0.01
        assert stage4_stats["free_calls"] == 1
        assert stage4_stats["paid_calls"] == 1

    def test_get_summary(self):
        """Test getting summary statistics"""
        tracker = CostTracker()

        tracker.track_call(APIType.GEMINI_FREE, "stage2", True, 0.0)
        tracker.track_call(APIType.TAVILY, "stage2", True, 0.02)
        tracker.track_call(APIType.FREE_NEWS, "stage4", True, 0.0)
        tracker.track_call(APIType.GEMINI_FREE, "stage2", False, 0.0, "Rate limit")

        summary = tracker.get_summary()

        assert summary["total_calls"] == 4
        assert summary["free_calls"] == 3  # 2 GEMINI_FREE + 1 FREE_NEWS
        assert summary["paid_calls"] == 1  # 1 TAVILY
        assert summary["successful_calls"] == 3
        assert summary["failed_calls"] == 1
        assert summary["total_cost"] == 0.02
        assert summary["success_rate"] == 0.75

    def test_fallback_scenario_stage2(self):
        """Test tracking Stage 2 fallback: Gemini → Tavily"""
        tracker = CostTracker()

        # Initial free call fails
        tracker.track_call(
            api_type=APIType.GEMINI_FREE,
            stage="stage2",
            success=False,
            cost=0.0,
            error="Rate limit exceeded"
        )

        # Fallback to paid API succeeds
        tracker.track_call(
            api_type=APIType.TAVILY,
            stage="stage2",
            success=True,
            cost=0.02
        )

        stage2_stats = tracker.get_stage_stats("stage2")
        assert stage2_stats["calls_count"] == 2
        assert stage2_stats["free_calls"] == 1
        assert stage2_stats["paid_calls"] == 1
        assert stage2_stats["total_cost"] == 0.02
        assert stage2_stats["fallback_triggered"] is True

    def test_fallback_scenario_stage4(self):
        """Test tracking Stage 4 fallback: Free news → Paid news"""
        tracker = CostTracker()

        # Initial free call fails
        tracker.track_call(
            api_type=APIType.FREE_NEWS,
            stage="stage4",
            success=False,
            cost=0.0,
            error="Rate limit exceeded"
        )

        # Fallback to paid API succeeds
        tracker.track_call(
            api_type=APIType.PAID_NEWS,
            stage="stage4",
            success=True,
            cost=0.01
        )

        stage4_stats = tracker.get_stage_stats("stage4")
        assert stage4_stats["calls_count"] == 2
        assert stage4_stats["free_calls"] == 1
        assert stage4_stats["paid_calls"] == 1
        assert stage4_stats["total_cost"] == 0.01
        assert stage4_stats["fallback_triggered"] is True

    def test_reset_tracker(self):
        """Test resetting tracker statistics"""
        tracker = CostTracker()

        tracker.track_call(APIType.GEMINI_FREE, "stage2", True, 0.0)
        tracker.track_call(APIType.TAVILY, "stage2", True, 0.02)

        assert tracker.total_cost == 0.02

        tracker.reset()

        assert tracker.total_cost == 0.0
        assert tracker.free_calls_count == 0
        assert tracker.paid_calls_count == 0
        assert len(tracker.get_all_calls()) == 0


class TestAPICall:
    """Test APICall dataclass"""

    def test_api_call_creation(self):
        """Test creating APICall instance"""
        timestamp = datetime.now()

        call = APICall(
            api_type=APIType.GEMINI_FREE,
            stage="stage2",
            success=True,
            cost=0.0,
            timestamp=timestamp,
            error=None
        )

        assert call.api_type == APIType.GEMINI_FREE
        assert call.stage == "stage2"
        assert call.success is True
        assert call.cost == 0.0
        assert call.timestamp == timestamp
        assert call.error is None

    def test_api_call_with_error(self):
        """Test creating APICall with error"""
        call = APICall(
            api_type=APIType.TAVILY,
            stage="stage2",
            success=False,
            cost=0.0,
            error="Connection timeout"
        )

        assert call.success is False
        assert call.error == "Connection timeout"


class TestAPIType:
    """Test APIType enum"""

    def test_api_type_values(self):
        """Test APIType enum values"""
        assert APIType.GEMINI_FREE.value == "gemini_free"
        assert APIType.TAVILY.value == "tavily"
        assert APIType.FREE_NEWS.value == "free_news"
        assert APIType.PAID_NEWS.value == "paid_news"

    def test_is_free_api(self):
        """Test checking if API is free"""
        tracker = CostTracker()

        assert tracker.is_free_api(APIType.GEMINI_FREE) is True
        assert tracker.is_free_api(APIType.FREE_NEWS) is True
        assert tracker.is_free_api(APIType.TAVILY) is False
        assert tracker.is_free_api(APIType.PAID_NEWS) is False

    def test_is_paid_api(self):
        """Test checking if API is paid"""
        tracker = CostTracker()

        assert tracker.is_paid_api(APIType.TAVILY) is True
        assert tracker.is_paid_api(APIType.PAID_NEWS) is True
        assert tracker.is_paid_api(APIType.GEMINI_FREE) is False
        assert tracker.is_paid_api(APIType.FREE_NEWS) is False

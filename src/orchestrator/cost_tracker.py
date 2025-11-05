"""
Cost Tracker for Hybrid Research Orchestrator

Tracks API costs for free/paid services with automatic fallback monitoring.

Usage:
    tracker = CostTracker()

    # Track free API call
    tracker.track_call(APIType.GEMINI_FREE, "stage2", success=True, cost=0.0)

    # Track paid fallback
    tracker.track_call(
        APIType.TAVILY,
        "stage2",
        success=True,
        cost=0.02,
        error="Rate limit on free API"
    )

    # Get statistics
    summary = tracker.get_summary()
    stage_stats = tracker.get_stage_stats("stage2")
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class APIType(Enum):
    """API types for cost tracking"""
    GEMINI_FREE = "gemini_free"      # Gemini API with grounding (free tier)
    TAVILY = "tavily"                # Tavily search API (paid)
    FREE_NEWS = "free_news"          # Free news APIs (100 req/day)
    PAID_NEWS = "paid_news"          # Paid news APIs


@dataclass
class APICall:
    """Single API call record"""
    api_type: APIType
    stage: str                       # stage2, stage4, etc.
    success: bool
    cost: float
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


class CostTracker:
    """
    Tracks API costs for free/paid services with fallback monitoring.

    Features:
    - Track free vs paid API calls
    - Per-stage cost breakdown
    - Fallback detection (free → paid transitions)
    - Success/failure statistics
    - Cost optimization insights
    """

    # Free API types
    FREE_APIS = {APIType.GEMINI_FREE, APIType.FREE_NEWS}

    # Paid API types
    PAID_APIS = {APIType.TAVILY, APIType.PAID_NEWS}

    def __init__(self):
        """Initialize cost tracker"""
        self._calls: List[APICall] = []
        logger.info("cost_tracker_initialized")

    @property
    def total_cost(self) -> float:
        """Total cost across all API calls"""
        return sum(call.cost for call in self._calls)

    @property
    def free_calls_count(self) -> int:
        """Number of free API calls"""
        return sum(1 for call in self._calls if call.api_type in self.FREE_APIS)

    @property
    def paid_calls_count(self) -> int:
        """Number of paid API calls"""
        return sum(1 for call in self._calls if call.api_type in self.PAID_APIS)

    def track_call(
        self,
        api_type: APIType,
        stage: str,
        success: bool,
        cost: float,
        error: Optional[str] = None
    ) -> None:
        """
        Track single API call.

        Args:
            api_type: API type (GEMINI_FREE, TAVILY, etc.)
            stage: Pipeline stage (stage2, stage4, etc.)
            success: Whether call succeeded
            cost: API call cost in USD
            error: Error message if failed
        """
        call = APICall(
            api_type=api_type,
            stage=stage,
            success=success,
            cost=cost,
            error=error
        )

        self._calls.append(call)

        logger.info(
            "api_call_tracked",
            api_type=api_type.value,
            stage=stage,
            success=success,
            cost=f"${cost:.4f}",
            error=error
        )

    def get_all_calls(self) -> List[APICall]:
        """Get all tracked API calls"""
        return self._calls.copy()

    def get_stage_stats(self, stage: str) -> Dict:
        """
        Get statistics for specific stage.

        Args:
            stage: Pipeline stage (stage2, stage4, etc.)

        Returns:
            Dict with:
                - calls_count: Total calls
                - free_calls: Free API calls
                - paid_calls: Paid API calls
                - total_cost: Total cost
                - successful_calls: Successful calls
                - failed_calls: Failed calls
                - fallback_triggered: Whether fallback was used
        """
        stage_calls = [call for call in self._calls if call.stage == stage]

        if not stage_calls:
            return {
                "calls_count": 0,
                "free_calls": 0,
                "paid_calls": 0,
                "total_cost": 0.0,
                "successful_calls": 0,
                "failed_calls": 0,
                "fallback_triggered": False
            }

        free_calls = sum(1 for c in stage_calls if c.api_type in self.FREE_APIS)
        paid_calls = sum(1 for c in stage_calls if c.api_type in self.PAID_APIS)
        successful = sum(1 for c in stage_calls if c.success)
        failed = sum(1 for c in stage_calls if not c.success)
        total_cost = sum(c.cost for c in stage_calls)

        # Fallback detected if both free and paid calls exist in same stage
        fallback_triggered = free_calls > 0 and paid_calls > 0

        return {
            "calls_count": len(stage_calls),
            "free_calls": free_calls,
            "paid_calls": paid_calls,
            "total_cost": total_cost,
            "successful_calls": successful,
            "failed_calls": failed,
            "fallback_triggered": fallback_triggered
        }

    def get_summary(self) -> Dict:
        """
        Get summary statistics across all stages.

        Returns:
            Dict with:
                - total_calls: Total API calls
                - free_calls: Free API calls
                - paid_calls: Paid API calls
                - successful_calls: Successful calls
                - failed_calls: Failed calls
                - total_cost: Total cost in USD
                - success_rate: Ratio of successful calls
        """
        if not self._calls:
            return {
                "total_calls": 0,
                "free_calls": 0,
                "paid_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_cost": 0.0,
                "success_rate": 0.0
            }

        successful = sum(1 for c in self._calls if c.success)
        failed = sum(1 for c in self._calls if not c.success)

        return {
            "total_calls": len(self._calls),
            "free_calls": self.free_calls_count,
            "paid_calls": self.paid_calls_count,
            "successful_calls": successful,
            "failed_calls": failed,
            "total_cost": self.total_cost,
            "success_rate": successful / len(self._calls) if self._calls else 0.0
        }

    def is_free_api(self, api_type: APIType) -> bool:
        """Check if API type is free"""
        return api_type in self.FREE_APIS

    def is_paid_api(self, api_type: APIType) -> bool:
        """Check if API type is paid"""
        return api_type in self.PAID_APIS

    def reset(self) -> None:
        """Reset all tracked calls"""
        self._calls.clear()
        logger.info("cost_tracker_reset")

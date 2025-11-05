"""
Tests for Hybrid Orchestrator Fallback Behavior

Tests automatic fallback from free APIs to paid APIs when rate limits hit.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator
from src.orchestrator.cost_tracker import APIType


class TestStage2Fallback:
    """Test Stage 2 fallback: Gemini → Tavily"""

    @pytest.mark.asyncio
    async def test_gemini_success_no_fallback(self):
        """Test successful Gemini call without fallback"""
        orchestrator = HybridResearchOrchestrator(enable_tavily=True)

        # Mock Gemini agent
        mock_gemini_agent = Mock()
        mock_gemini_result = {
            "content": {
                "competitors": [
                    {"name": "Comp1", "url": "http://comp1.com", "topics": ["topic1"]}
                ],
                "additional_keywords": ["keyword1", "keyword2"],
                "market_topics": ["topic1", "topic2"]
            },
            "cost": 0.0
        }
        mock_gemini_agent.generate = Mock(return_value=mock_gemini_result)
        orchestrator._gemini_agent = mock_gemini_agent

        result = await orchestrator.research_competitors(
            keywords=["test", "keyword"],
            customer_info={"market": "Germany", "vertical": "PropTech", "domain": "Real Estate"}
        )

        # Verify result
        assert len(result["competitors"]) == 1
        assert len(result["additional_keywords"]) == 2
        assert len(result["market_topics"]) == 2
        assert result["cost"] == 0.0

        # Verify cost tracking (only Gemini call, no fallback)
        summary = orchestrator.cost_tracker.get_summary()
        assert summary["total_calls"] == 1
        assert summary["free_calls"] == 1
        assert summary["paid_calls"] == 0

        stage2_stats = orchestrator.cost_tracker.get_stage_stats("stage2")
        assert stage2_stats["fallback_triggered"] is False

    @pytest.mark.asyncio
    async def test_gemini_rate_limit_fallback_tavily(self):
        """Test Gemini rate limit triggers Tavily fallback"""
        orchestrator = HybridResearchOrchestrator(enable_tavily=True)

        # Mock Gemini agent to raise rate limit error
        mock_gemini_agent = Mock()
        gemini_error = Exception("429 Rate limit exceeded")
        mock_gemini_agent.generate = Mock(side_effect=gemini_error)
        orchestrator._gemini_agent = mock_gemini_agent

        # Mock Tavily backend
        mock_tavily_results = [
            {
                "title": "Competitor 1",
                "url": "http://comp1.com",
                "content": "PropTech software platform",
                "snippet": "Leading property management"
            }
        ]
        mock_tavily_backend = Mock()
        mock_tavily_backend.search = AsyncMock(return_value=mock_tavily_results)
        orchestrator._tavily_backend = mock_tavily_backend

        result = await orchestrator.research_competitors(
            keywords=["proptech", "software"],
            customer_info={"market": "Germany", "vertical": "PropTech", "domain": "Real Estate"}
        )

        # Verify fallback result
        assert len(result["competitors"]) >= 1
        assert result["cost"] == 0.02  # Tavily cost

        # Verify cost tracking (failed Gemini + successful Tavily)
        summary = orchestrator.cost_tracker.get_summary()
        assert summary["total_calls"] == 2
        assert summary["free_calls"] == 1  # Failed Gemini
        assert summary["paid_calls"] == 1  # Successful Tavily
        assert summary["total_cost"] == 0.02

        stage2_stats = orchestrator.cost_tracker.get_stage_stats("stage2")
        assert stage2_stats["fallback_triggered"] is True

    @pytest.mark.asyncio
    async def test_gemini_non_rate_limit_error_no_fallback(self):
        """Test non-rate-limit Gemini error does NOT trigger fallback"""
        orchestrator = HybridResearchOrchestrator(enable_tavily=True)

        # Mock Gemini agent to raise non-rate-limit error
        mock_gemini_agent = Mock()
        gemini_error = Exception("Connection timeout")
        mock_gemini_agent.generate = Mock(side_effect=gemini_error)
        orchestrator._gemini_agent = mock_gemini_agent

        result = await orchestrator.research_competitors(
            keywords=["test"],
            customer_info={"market": "Germany", "vertical": "PropTech", "domain": "Real Estate"}
        )

        # Verify error result
        assert "error" in result
        assert result["cost"] == 0.0

        # Verify cost tracking (only failed Gemini, no fallback)
        summary = orchestrator.cost_tracker.get_summary()
        assert summary["total_calls"] == 0  # Error before tracking
        assert summary["free_calls"] == 0
        assert summary["paid_calls"] == 0

    @pytest.mark.asyncio
    async def test_tavily_fallback_with_tavily_disabled(self):
        """Test fallback fails gracefully when Tavily is disabled"""
        orchestrator = HybridResearchOrchestrator(enable_tavily=False)

        # Mock Gemini agent to raise rate limit error
        mock_gemini_agent = Mock()
        gemini_error = Exception("429 Rate limit exceeded")
        mock_gemini_agent.generate = Mock(side_effect=gemini_error)
        orchestrator._gemini_agent = mock_gemini_agent

        result = await orchestrator.research_competitors(
            keywords=["test"],
            customer_info={"market": "Germany", "vertical": "PropTech", "domain": "Real Estate"}
        )

        # Verify fallback failed gracefully
        assert "error" in result
        assert "Tavily backend not available" in result["error"]
        assert result["cost"] == 0.0

        # Verify cost tracking
        summary = orchestrator.cost_tracker.get_summary()
        assert summary["total_calls"] == 2  # Failed Gemini + failed Tavily
        assert summary["free_calls"] == 1
        assert summary["paid_calls"] == 1
        assert summary["failed_calls"] == 2

    @pytest.mark.asyncio
    async def test_tavily_fallback_search_failure(self):
        """Test Tavily fallback handles search failures"""
        orchestrator = HybridResearchOrchestrator(enable_tavily=True)

        # Mock Gemini agent to raise rate limit error
        mock_gemini_agent = Mock()
        gemini_error = Exception("429 Rate limit exceeded")
        mock_gemini_agent.generate = Mock(side_effect=gemini_error)
        orchestrator._gemini_agent = mock_gemini_agent

        # Mock Tavily backend to raise error
        mock_tavily_backend = Mock()
        tavily_error = Exception("Tavily API error")
        mock_tavily_backend.search = AsyncMock(side_effect=tavily_error)
        orchestrator._tavily_backend = mock_tavily_backend

        result = await orchestrator.research_competitors(
            keywords=["test"],
            customer_info={"market": "Germany", "vertical": "PropTech", "domain": "Real Estate"}
        )

        # Verify fallback failed
        assert "error" in result
        assert "Tavily fallback failed" in result["error"]
        assert result["cost"] == 0.0

        # Verify cost tracking
        summary = orchestrator.cost_tracker.get_summary()
        assert summary["total_calls"] == 2
        assert summary["failed_calls"] == 2

    @pytest.mark.asyncio
    async def test_cost_tracker_integration(self):
        """Test cost tracker properly tracks all fallback scenarios"""
        orchestrator = HybridResearchOrchestrator(enable_tavily=True)

        # Mock Gemini agent
        mock_gemini_agent = Mock()
        orchestrator._gemini_agent = mock_gemini_agent

        # Test 1: Successful Gemini call
        mock_gemini_agent.generate = Mock(return_value={
            "content": {"competitors": [], "additional_keywords": [], "market_topics": []},
            "cost": 0.0
        })

        await orchestrator.research_competitors(
            keywords=["test1"],
            customer_info={"market": "Germany", "vertical": "PropTech", "domain": "Real Estate"}
        )

        # Test 2: Failed Gemini with successful Tavily fallback
        mock_gemini_agent.generate = Mock(side_effect=Exception("429 Rate limit"))

        mock_tavily_backend = Mock()
        mock_tavily_backend.search = AsyncMock(return_value=[])
        orchestrator._tavily_backend = mock_tavily_backend

        await orchestrator.research_competitors(
            keywords=["test2"],
            customer_info={"market": "Germany", "vertical": "PropTech", "domain": "Real Estate"}
        )

        # Verify total cost tracking
        summary = orchestrator.cost_tracker.get_summary()
        assert summary["total_calls"] == 3  # 1 success Gemini + 1 failed Gemini + 1 success Tavily
        assert summary["free_calls"] == 2
        assert summary["paid_calls"] == 1
        assert summary["successful_calls"] == 2
        assert summary["total_cost"] == 0.02  # Only Tavily costs money

    @pytest.mark.asyncio
    async def test_rate_limit_detection_variations(self):
        """Test various rate limit error message formats"""
        rate_limit_messages = [
            "429 Rate limit exceeded",
            "Rate limit reached",
            "Quota exceeded",
            "API limit reached"
        ]

        for i, error_msg in enumerate(rate_limit_messages):
            orchestrator = HybridResearchOrchestrator(enable_tavily=True)

            # Mock Gemini agent with specific error
            mock_gemini_agent = Mock()
            mock_gemini_agent.generate = Mock(side_effect=Exception(error_msg))
            orchestrator._gemini_agent = mock_gemini_agent

            # Mock Tavily backend
            mock_tavily_backend = Mock()
            mock_tavily_backend.search = AsyncMock(return_value=[])
            orchestrator._tavily_backend = mock_tavily_backend

            result = await orchestrator.research_competitors(
                keywords=[f"test{i}"],
                customer_info={"market": "Germany", "vertical": "PropTech", "domain": "Real Estate"}
            )

            # Verify fallback was triggered for all rate limit variations
            stage2_stats = orchestrator.cost_tracker.get_stage_stats("stage2")
            assert stage2_stats["fallback_triggered"] is True, f"Failed for message: {error_msg}"

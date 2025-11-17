"""
Unit Tests for Orchestrator Intelligence Integration (Phase 2D)

Tests the integration without requiring actual API calls.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator


class TestOrchestratorIntelligence:
    """Test intelligence integration in HybridResearchOrchestrator."""

    def test_orchestrator_initialization_with_intelligence(self):
        """Test that orchestrator initializes with intelligence features enabled."""

        orchestrator = HybridResearchOrchestrator(
            enable_tavily=True,
            enable_synthesis=True,
            # Intelligence features
            enable_serp_analysis=True,
            enable_content_scoring=True,
            enable_difficulty_scoring=True,
            db_path="data/topics_test_unit.db"
        )

        assert orchestrator.enable_serp_analysis is True
        assert orchestrator.enable_content_scoring is True
        assert orchestrator.enable_difficulty_scoring is True


    def test_orchestrator_initialization_without_intelligence(self):
        """Test backward compatibility when intelligence features are disabled."""

        orchestrator = HybridResearchOrchestrator(
            enable_tavily=True,
            enable_synthesis=True,
            # Intelligence features DISABLED
            enable_serp_analysis=False,
            enable_content_scoring=False,
            enable_difficulty_scoring=False,
            db_path="data/topics_test_unit.db"
        )

        assert orchestrator.enable_serp_analysis is False
        assert orchestrator.enable_content_scoring is False
        assert orchestrator.enable_difficulty_scoring is False


    def test_lazy_loading_intelligence_components(self):
        """Test that intelligence components are lazy-loaded."""

        orchestrator = HybridResearchOrchestrator(
            enable_serp_analysis=True,
            enable_content_scoring=True,
            enable_difficulty_scoring=True,
            db_path="data/topics_test_unit.db"
        )

        # Components should be None until accessed
        assert orchestrator._serp_analyzer is None
        assert orchestrator._content_scorer is None
        assert orchestrator._difficulty_scorer is None

        # Access properties to trigger lazy loading
        serp_analyzer = orchestrator.serp_analyzer
        content_scorer = orchestrator.content_scorer
        difficulty_scorer = orchestrator.difficulty_scorer

        # Now they should be initialized
        assert serp_analyzer is not None
        assert content_scorer is not None
        assert difficulty_scorer is not None


    def test_intelligence_components_none_when_disabled(self):
        """Test that intelligence components return None when disabled."""

        orchestrator = HybridResearchOrchestrator(
            enable_serp_analysis=False,
            enable_content_scoring=False,
            enable_difficulty_scoring=False,
            db_path="data/topics_test_unit.db"
        )

        # Should return None when disabled
        assert orchestrator.serp_analyzer is None
        assert orchestrator.content_scorer is None
        assert orchestrator.difficulty_scorer is None


    @pytest.mark.asyncio
    async def test_research_topic_returns_intelligence_fields(self):
        """Test that research_topic returns intelligence fields in result dict."""

        orchestrator = HybridResearchOrchestrator(
            enable_tavily=True,
            enable_synthesis=True,
            enable_serp_analysis=True,
            enable_content_scoring=True,
            enable_difficulty_scoring=True,
            db_path="data/topics_test_unit.db"
        )

        # Mock the entire research pipeline
        with patch.object(orchestrator.researcher, 'research_topic', new_callable=AsyncMock) as mock_research, \
             patch.object(orchestrator.synthesizer, 'synthesize', new_callable=AsyncMock) as mock_synthesize, \
             patch.object(orchestrator, 'serp_analyzer') as mock_serp, \
             patch.object(orchestrator, 'content_scorer') as mock_content, \
             patch.object(orchestrator, 'difficulty_scorer') as mock_diff:

            # Setup mocks
            mock_research.return_value = {"sources": [{"url": "https://example.com", "title": "Test"}]}
            mock_synthesize.return_value = {
                "article": "Test article",
                "cost": 0.01,
                "word_count": 100
            }

            # Mock intelligence components
            mock_serp.search = AsyncMock(return_value=[{"link": "https://example.com", "title": "Test"}])
            mock_serp.analyze_serp = Mock(return_value={"avg_position": 5.0, "total_domains": 10})
            mock_serp.db_manager.save_serp_results = Mock()

            mock_content.score_url = AsyncMock(return_value={"url": "https://example.com", "quality_score": 75})

            mock_diff.calculate_difficulty = Mock(return_value={
                "difficulty_score": 50,
                "ranking_time_estimate": "6-8 months"
            })

            # Call research_topic
            result = await orchestrator.research_topic(
                topic="Test Topic",
                config={"market": "US", "language": "en", "domain": "Tech"},
                max_results=1
            )

            # Verify result structure includes intelligence fields
            assert "serp_data" in result
            assert "content_scores" in result
            assert "difficulty_data" in result

            # Verify values are not None
            assert result["serp_data"] is not None
            assert isinstance(result["content_scores"], list)
            assert result["difficulty_data"] is not None


    @pytest.mark.asyncio
    async def test_research_topic_without_intelligence(self):
        """Test that research_topic works with intelligence disabled."""

        orchestrator = HybridResearchOrchestrator(
            enable_tavily=True,
            enable_synthesis=True,
            enable_serp_analysis=False,
            enable_content_scoring=False,
            enable_difficulty_scoring=False,
            db_path="data/topics_test_unit.db"
        )

        # Mock the research pipeline (no intelligence)
        with patch.object(orchestrator.researcher, 'research_topic', new_callable=AsyncMock) as mock_research, \
             patch.object(orchestrator.synthesizer, 'synthesize', new_callable=AsyncMock) as mock_synthesize:

            mock_research.return_value = {"sources": [{"url": "https://example.com", "title": "Test"}]}
            mock_synthesize.return_value = {
                "article": "Test article",
                "cost": 0.01,
                "word_count": 100
            }

            result = await orchestrator.research_topic(
                topic="Test Topic",
                config={"market": "US", "language": "en", "domain": "Tech"},
                max_results=1
            )

            # Verify intelligence fields are present but None/empty
            assert result.get("serp_data") is None
            assert result.get("content_scores") == []
            assert result.get("difficulty_data") is None

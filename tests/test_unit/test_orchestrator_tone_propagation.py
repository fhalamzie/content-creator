"""
Tests for tone propagation through HybridResearchOrchestrator

Verifies that brand tone extracted in Stage 1 flows correctly through
to Stage 5 (synthesis) and that image generation flags are handled correctly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator


class TestTonePropagation:
    """Test tone propagation from Stage 1 → Stage 5"""

    @pytest.mark.asyncio
    async def test_research_topic_inherits_image_generation_from_config(self):
        """Test that generate_images=None inherits from config"""
        # Mock researcher
        mock_researcher = AsyncMock()
        mock_researcher.search = AsyncMock(return_value=[
            {"url": "https://example.com", "title": "Test", "snippet": "content"}
        ])

        # Mock reranker
        mock_reranker = AsyncMock()
        mock_reranker.rerank = AsyncMock(return_value=[
            {"url": "https://example.com", "title": "Test", "snippet": "content"}
        ])

        # Mock synthesizer
        mock_synthesizer = AsyncMock()
        mock_synthesizer.synthesize = AsyncMock(return_value={
            "article": "Test article",
            "citations": [],
            "cost": 0.01,
            "hero_image_url": None,
            "hero_image_alt": None,
            "supporting_images": [],
            "image_cost": 0.0,
            "metadata": {}
        })

        with patch.object(HybridResearchOrchestrator, 'researcher', mock_researcher), \
             patch.object(HybridResearchOrchestrator, 'reranker', mock_reranker), \
             patch.object(HybridResearchOrchestrator, 'synthesizer', mock_synthesizer):

            orchestrator = HybridResearchOrchestrator(enable_tavily=False)

            # Config with enable_image_generation=True
            config = {"enable_image_generation": True, "market": "Germany"}

            # Call with generate_images=None (should inherit from config)
            result = await orchestrator.research_topic(
                topic="Test topic",
                config=config,
                brand_tone=["Professional"],
                generate_images=None,  # Should inherit True from config
                max_results=10
            )

            # Verify synthesizer was called with generate_images=True
            mock_synthesizer.synthesize.assert_called_once()
            call_kwargs = mock_synthesizer.synthesize.call_args.kwargs
            assert call_kwargs["generate_images"] is True
            assert call_kwargs["brand_tone"] == ["Professional"]

            # Verify return structure includes image fields
            assert "hero_image_url" in result
            assert "hero_image_alt" in result
            assert "supporting_images" in result
            assert "image_cost" in result


class TestRunPipelineTonePropagation:
    """Test tone propagation in full pipeline (run_pipeline)"""

    @pytest.mark.asyncio
    async def test_run_pipeline_extracts_and_passes_tone(self):
        """Test that tone extracted in Stage 1 is passed to research_topic in Stage 5"""
        orchestrator = HybridResearchOrchestrator(enable_tavily=False)

        # Mock Stage 1: extract_website_keywords
        orchestrator.extract_website_keywords = AsyncMock(return_value={
            "keywords": ["PropTech", "AI"],
            "tags": ["technology"],
            "themes": ["innovation"],
            "tone": ["Professional", "Technical"],  # ← Tone extracted here
            "cost": 0.0
        })

        # Mock Stage 2: research_competitors
        orchestrator.research_competitors = AsyncMock(return_value={
            "competitors": [],
            "additional_keywords": [],
            "market_topics": [],
            "cost": 0.0
        })

        # Mock Stage 3: consolidate (returns as-is for simplicity)
        orchestrator.consolidate_keywords_and_topics = MagicMock(return_value={
            "consolidated_keywords": ["PropTech", "AI"],
            "consolidated_tags": ["technology"],
            "priority_topics": ["AI in PropTech"]
        })

        # Mock Stage 4: discover_topics_from_collectors
        orchestrator.discover_topics_from_collectors = AsyncMock(return_value={
            "discovered_topics": [
                {"topic": "AI PropTech trends", "source": "autocomplete"}
            ],
            "topics_by_source": {"autocomplete": ["AI PropTech trends"]}
        })

        # Mock Stage 4.5: validate_and_score_topics
        from dataclasses import dataclass

        @dataclass
        class ScoredTopic:
            topic: str
            score: float

        orchestrator.validate_and_score_topics = MagicMock(return_value={
            "scored_topics": [ScoredTopic("AI PropTech trends", 0.85)],
            "avg_score": 0.85
        })

        # Mock Stage 5: research_topic (we'll verify it receives tone)
        orchestrator.research_topic = AsyncMock(return_value={
            "topic": "AI PropTech trends",
            "sources": [],
            "article": "Test article",
            "hero_image_url": None,
            "hero_image_alt": None,
            "supporting_images": [],
            "image_cost": 0.0,
            "cost": 0.01,
            "duration_sec": 1.0
        })

        # Run full pipeline
        result = await orchestrator.run_pipeline(
            website_url="https://proptech-company.com",
            customer_info={"market": "Germany", "vertical": "PropTech"},
            max_topics_to_research=1
        )

        # Verify tone was extracted
        assert result["brand_tone"] == ["Professional", "Technical"]

        # Verify research_topic was called with the extracted tone
        orchestrator.research_topic.assert_called_once()
        call_kwargs = orchestrator.research_topic.call_args.kwargs
        assert call_kwargs["brand_tone"] == ["Professional", "Technical"]
        assert call_kwargs["generate_images"] is None  # Should inherit from config

    @pytest.mark.asyncio
    async def test_run_pipeline_returns_brand_tone(self):
        """Test that run_pipeline includes brand_tone in return dict"""
        orchestrator = HybridResearchOrchestrator(enable_tavily=False)

        # Mock all stages
        orchestrator.extract_website_keywords = AsyncMock(return_value={
            "keywords": ["keyword"],
            "tags": [],
            "themes": [],
            "tone": ["Casual", "Friendly"],
            "cost": 0.0
        })

        orchestrator.research_competitors = AsyncMock(return_value={
            "competitors": [],
            "additional_keywords": [],
            "market_topics": [],
            "cost": 0.0
        })

        orchestrator.consolidate_keywords_and_topics = MagicMock(return_value={
            "consolidated_keywords": ["keyword"],
            "consolidated_tags": [],
            "priority_topics": []
        })

        orchestrator.discover_topics_from_collectors = AsyncMock(return_value={
            "discovered_topics": [],
            "topics_by_source": {}
        })

        from dataclasses import dataclass

        @dataclass
        class ScoredTopic:
            topic: str
            score: float

        orchestrator.validate_and_score_topics = MagicMock(return_value={
            "scored_topics": [],
            "avg_score": 0.0
        })

        # Run pipeline
        result = await orchestrator.run_pipeline(
            website_url="https://example.com",
            customer_info={"market": "US"},
            max_topics_to_research=0
        )

        # Verify brand_tone is in return dict
        assert "brand_tone" in result
        assert result["brand_tone"] == ["Casual", "Friendly"]

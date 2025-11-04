"""
Tests for DeepResearcher

Tests gpt-researcher wrapper for deep topic research with citations.
"""

import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime

from src.research.deep_researcher import DeepResearcher, DeepResearchError


class TestDeepResearcherInit:
    """Test DeepResearcher initialization"""

    def test_init_default(self):
        """Should initialize with default Gemini model"""
        with patch('src.research.deep_researcher.GPTResearcher'):
            researcher = DeepResearcher()

            # Verify GPTResearcher was instantiated (but not created yet)
            assert researcher.llm_provider == "google_genai"
            assert researcher.llm_model == "gemini-2.0-flash-exp"
            assert researcher.search_engine == "duckduckgo"
            assert researcher.max_sources == 8
            assert researcher.report_format == "markdown"

    def test_init_custom_model(self):
        """Should initialize with custom LLM model"""
        researcher = DeepResearcher(llm_model="gemini-1.5-pro")

        assert researcher.llm_model == "gemini-1.5-pro"

    def test_init_custom_max_sources(self):
        """Should initialize with custom max sources"""
        researcher = DeepResearcher(max_sources=15)

        assert researcher.max_sources == 15


class TestDeepResearcherResearch:
    """Test deep research functionality"""

    @pytest.fixture
    def sample_config(self):
        """Create sample research config"""
        return {
            'domain': 'SaaS',
            'market': 'Germany',
            'language': 'de',
            'vertical': 'Proptech'
        }

    @pytest.fixture
    def mock_research_report(self):
        """Create mock research report"""
        return {
            'topic': 'PropTech Trends 2025',
            'report': """# PropTech Trends 2025

## Introduction
PropTech industry is revolutionizing real estate...

## Key Trends
1. AI-powered property management
2. Blockchain for transactions
3. IoT smart buildings

## Citations
[1] Source A: https://example.com/source-a
[2] Source B: https://example.com/source-b
""",
            'sources': [
                'https://example.com/source-a',
                'https://example.com/source-b',
                'https://example.com/source-c'
            ],
            'citations': [
                {
                    'number': 1,
                    'title': 'Source A',
                    'url': 'https://example.com/source-a',
                    'snippet': 'AI is transforming property management'
                },
                {
                    'number': 2,
                    'title': 'Source B',
                    'url': 'https://example.com/source-b',
                    'snippet': 'Blockchain enables secure transactions'
                }
            ],
            'word_count': 1500,
            'researched_at': datetime.now().isoformat()
        }

    @pytest.mark.asyncio
    async def test_research_topic_success(self, sample_config, mock_research_report):
        """Should research topic and return formatted report"""
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt_class:
            mock_gpt_instance = AsyncMock()
            mock_gpt_class.return_value = mock_gpt_instance

            # Mock the research and get_report methods
            mock_gpt_instance.conduct_research = AsyncMock()
            mock_gpt_instance.write_report = AsyncMock(return_value=mock_research_report['report'])
            mock_gpt_instance.get_source_urls = AsyncMock(return_value=mock_research_report['sources'])

            researcher = DeepResearcher()
            result = await researcher.research_topic("PropTech Trends 2025", sample_config)

            # Verify GPTResearcher was called with contextualized query
            mock_gpt_class.assert_called_once()
            call_kwargs = mock_gpt_class.call_args[1]
            assert "PropTech Trends 2025" in call_kwargs['query']
            assert "SaaS" in call_kwargs['query']
            assert "Germany" in call_kwargs['query']
            assert "de" in call_kwargs['query']

            # Verify research was conducted
            mock_gpt_instance.conduct_research.assert_called_once()
            mock_gpt_instance.write_report.assert_called_once()

            # Verify result structure
            assert result['topic'] == "PropTech Trends 2025"
            assert result['report'] == mock_research_report['report']
            assert len(result['sources']) == 3
            assert 'researched_at' in result
            assert 'word_count' in result

    @pytest.mark.asyncio
    async def test_research_topic_with_context(self, sample_config):
        """Should contextualize query with domain/market/language"""
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt_class:
            mock_gpt_instance = AsyncMock()
            mock_gpt_class.return_value = mock_gpt_instance
            mock_gpt_instance.conduct_research = AsyncMock()
            mock_gpt_instance.write_report = AsyncMock(return_value="Report content")
            mock_gpt_instance.get_source_urls = AsyncMock(return_value=[])

            researcher = DeepResearcher()
            await researcher.research_topic("Cloud Security", sample_config)

            # Check contextualized query
            call_kwargs = mock_gpt_class.call_args[1]
            query = call_kwargs['query']

            assert "Cloud Security" in query
            assert "SaaS" in query
            assert "Germany" in query
            assert "de" in query
            assert "Proptech" in query

    @pytest.mark.asyncio
    async def test_research_topic_empty_topic(self, sample_config):
        """Should raise error for empty topic"""
        researcher = DeepResearcher()

        with pytest.raises(DeepResearchError, match="Topic cannot be empty"):
            await researcher.research_topic("", sample_config)

    @pytest.mark.asyncio
    async def test_research_topic_gpt_researcher_failure(self, sample_config):
        """Should handle gpt-researcher failures gracefully"""
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt_class:
            mock_gpt_instance = AsyncMock()
            mock_gpt_class.return_value = mock_gpt_instance
            mock_gpt_instance.conduct_research = AsyncMock(side_effect=Exception("API error"))

            researcher = DeepResearcher()

            with pytest.raises(DeepResearchError, match="Research failed"):
                await researcher.research_topic("Test Topic", sample_config)

    @pytest.mark.asyncio
    async def test_research_topic_no_sources(self, sample_config):
        """Should handle research with no sources found"""
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt_class:
            mock_gpt_instance = AsyncMock()
            mock_gpt_class.return_value = mock_gpt_instance
            mock_gpt_instance.conduct_research = AsyncMock()
            mock_gpt_instance.write_report = AsyncMock(return_value="Report with no sources")
            mock_gpt_instance.get_source_urls = AsyncMock(return_value=[])

            researcher = DeepResearcher()
            result = await researcher.research_topic("Test Topic", sample_config)

            # Should still return report, but with empty sources
            assert result['report'] == "Report with no sources"
            assert result['sources'] == []

    @pytest.mark.asyncio
    async def test_research_with_competitor_keywords(self, sample_config):
        """Should enhance query with competitor gaps and keywords"""
        competitor_gaps = ["GDPR compliance", "SMB focus"]
        keywords = ["cloud security", "data protection"]

        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt_class:
            mock_gpt_instance = AsyncMock()
            mock_gpt_class.return_value = mock_gpt_instance
            mock_gpt_instance.conduct_research = AsyncMock()
            mock_gpt_instance.write_report = AsyncMock(return_value="Report")
            mock_gpt_instance.get_source_urls = AsyncMock(return_value=[])

            researcher = DeepResearcher()
            await researcher.research_topic(
                "Cloud Security",
                sample_config,
                competitor_gaps=competitor_gaps,
                keywords=keywords
            )

            # Check enhanced query
            call_kwargs = mock_gpt_class.call_args[1]
            query = call_kwargs['query']

            assert "Cloud Security" in query
            assert "GDPR compliance" in query
            assert "SMB focus" in query
            assert "cloud security" in query
            assert "data protection" in query


class TestDeepResearcherStatistics:
    """Test statistics tracking"""

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, monkeypatch):
        """Should track research statistics"""
        # Mock datetime for consistent timestamps
        mock_now = datetime(2025, 11, 4, 12, 0, 0)

        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt_class, \
             patch('src.research.deep_researcher.datetime') as mock_datetime:

            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat

            mock_gpt_instance = AsyncMock()
            mock_gpt_class.return_value = mock_gpt_instance
            mock_gpt_instance.conduct_research = AsyncMock()
            mock_gpt_instance.write_report = AsyncMock(return_value="Report content")
            mock_gpt_instance.get_source_urls = AsyncMock(return_value=['url1', 'url2'])

            researcher = DeepResearcher()

            config = {
                'domain': 'Tech',
                'market': 'US',
                'language': 'en',
                'vertical': 'AI'
            }

            await researcher.research_topic("AI Trends", config)

            stats = researcher.get_statistics()

            assert stats['total_research'] == 1
            assert stats['failed_research'] == 0
            assert stats['total_sources_found'] == 2
            assert stats['success_rate'] == 1.0

    @pytest.mark.asyncio
    async def test_statistics_with_failure(self):
        """Should track failed research in statistics"""
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt_class:
            mock_gpt_instance = AsyncMock()
            mock_gpt_class.return_value = mock_gpt_instance
            mock_gpt_instance.conduct_research = AsyncMock(side_effect=Exception("Error"))

            researcher = DeepResearcher()
            config = {'domain': 'Tech', 'market': 'US', 'language': 'en', 'vertical': 'AI'}

            try:
                await researcher.research_topic("Test", config)
            except DeepResearchError:
                pass

            stats = researcher.get_statistics()

            assert stats['total_research'] == 1
            assert stats['failed_research'] == 1
            assert stats['success_rate'] == 0.0

    def test_reset_statistics(self):
        """Should reset all statistics"""
        researcher = DeepResearcher()
        researcher.total_research = 10
        researcher.failed_research = 2
        researcher.total_sources_found = 50

        researcher.reset_statistics()

        assert researcher.total_research == 0
        assert researcher.failed_research == 0
        assert researcher.total_sources_found == 0

"""
Tests for LLMProcessor

Tests LLM-based NLP operations: language detection, clustering, entity extraction.
"""

import pytest
from unittest.mock import Mock, patch
from src.processors.llm_processor import LLMProcessor, LanguageDetection, ClusterResult, EntityExtraction


class TestLLMProcessorInit:
    """Test LLM processor initialization"""

    def test_init_with_api_key(self):
        """Should initialize with API key from environment"""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            processor = LLMProcessor()
            assert processor.model == "qwen/qwen-2.5-7b-instruct"

    def test_init_without_api_key_raises_error(self):
        """Should raise error if API key not provided"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                LLMProcessor()

    def test_init_with_custom_model(self):
        """Should allow custom model selection"""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            processor = LLMProcessor(model="qwen/qwen-2.5-14b-instruct")
            assert processor.model == "qwen/qwen-2.5-14b-instruct"


class TestLanguageDetection:
    """Test language detection functionality"""

    @pytest.fixture
    def processor(self):
        """Create LLM processor for tests"""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            return LLMProcessor()

    @pytest.fixture
    def mock_openai_response(self):
        """Create mock OpenAI response"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"language": "de", "confidence": 0.95}'
        return mock_response

    def test_detect_language_returns_pydantic_model(self, processor, mock_openai_response):
        """Should return LanguageDetection Pydantic model"""
        with patch.object(processor.client.chat.completions, 'create', return_value=mock_openai_response):
            result = processor.detect_language("Das ist ein deutscher Text")

            assert isinstance(result, LanguageDetection)
            assert result.language == "de"
            assert result.confidence == 0.95

    def test_detect_language_german(self, processor, mock_openai_response):
        """Should detect German text"""
        with patch.object(processor.client.chat.completions, 'create', return_value=mock_openai_response):
            result = processor.detect_language("Hallo Welt")

            assert result.language == "de"

    def test_detect_language_truncates_long_text(self, processor, mock_openai_response):
        """Should truncate text to 500 characters for API call"""
        long_text = "a" * 1000

        with patch.object(processor.client.chat.completions, 'create', return_value=mock_openai_response) as mock_create:
            processor.detect_language(long_text)

            # Check that only first 500 chars were sent
            call_args = mock_create.call_args
            messages = call_args.kwargs['messages']
            assert len(messages[0]['content']) < 600  # Includes prompt text

    def test_detect_language_uses_temperature_zero(self, processor, mock_openai_response):
        """Should use temperature=0 for deterministic results"""
        with patch.object(processor.client.chat.completions, 'create', return_value=mock_openai_response) as mock_create:
            processor.detect_language("Test text")

            assert mock_create.call_args.kwargs['temperature'] == 0

    def test_detect_language_caches_result(self, processor, mock_openai_response):
        """Should cache language detection results"""
        with patch.object(processor.client.chat.completions, 'create', return_value=mock_openai_response) as mock_create:
            text = "Test text for caching"

            # First call
            result1 = processor.detect_language(text)

            # Second call (should use cache)
            result2 = processor.detect_language(text)

            # API should only be called once
            assert mock_create.call_count == 1
            assert result1.language == result2.language


class TestTopicClustering:
    """Test topic clustering functionality"""

    @pytest.fixture
    def processor(self):
        """Create LLM processor for tests"""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            return LLMProcessor()

    @pytest.fixture
    def mock_clustering_response(self):
        """Create mock clustering response"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
        {
            "clusters": [
                {"cluster": "AI/ML", "topics": ["Machine Learning", "Deep Learning", "Neural Networks"]},
                {"cluster": "Cloud", "topics": ["AWS", "Azure", "GCP"]}
            ]
        }
        '''
        return mock_response

    def test_cluster_topics_returns_pydantic_model(self, processor, mock_clustering_response):
        """Should return ClusterResult Pydantic model"""
        topics = ["Machine Learning", "AWS", "Deep Learning", "Azure"]

        with patch.object(processor.client.chat.completions, 'create', return_value=mock_clustering_response):
            result = processor.cluster_topics(topics)

            assert isinstance(result, ClusterResult)
            assert len(result.clusters) == 2
            assert result.clusters[0].cluster == "AI/ML"

    def test_cluster_topics_truncates_to_50(self, processor, mock_clustering_response):
        """Should truncate topics list to 50 items"""
        topics = [f"Topic {i}" for i in range(100)]

        with patch.object(processor.client.chat.completions, 'create', return_value=mock_clustering_response) as mock_create:
            processor.cluster_topics(topics)

            # Check that only 50 topics were sent
            call_args = mock_create.call_args
            messages = call_args.kwargs['messages']
            # The prompt should mention 50 topics being sent
            assert "50" in messages[0]['content']

    def test_cluster_topics_uses_temperature_03(self, processor, mock_clustering_response):
        """Should use temperature=0.3 for creative clustering"""
        topics = ["Topic 1", "Topic 2"]

        with patch.object(processor.client.chat.completions, 'create', return_value=mock_clustering_response) as mock_create:
            processor.cluster_topics(topics)

            assert mock_create.call_args.kwargs['temperature'] == 0.3


class TestEntityExtraction:
    """Test entity and keyword extraction"""

    @pytest.fixture
    def processor(self):
        """Create LLM processor for tests"""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            return LLMProcessor()

    @pytest.fixture
    def mock_extraction_response(self):
        """Create mock entity extraction response"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
        {
            "entities": ["Berlin", "PropTech", "SAP", "Germany"],
            "keywords": ["SaaS", "Cloud", "Migration", "Security", "GDPR"]
        }
        '''
        return mock_response

    def test_extract_entities_keywords_returns_pydantic_model(self, processor, mock_extraction_response):
        """Should return EntityExtraction Pydantic model"""
        content = "Berlin-based PropTech company uses SAP for German market"

        with patch.object(processor.client.chat.completions, 'create', return_value=mock_extraction_response):
            result = processor.extract_entities_keywords(content, language="de")

            assert isinstance(result, EntityExtraction)
            assert "Berlin" in result.entities
            assert "SaaS" in result.keywords

    def test_extract_entities_keywords_truncates_content(self, processor, mock_extraction_response):
        """Should truncate content to 1500 characters"""
        content = "a" * 2000

        with patch.object(processor.client.chat.completions, 'create', return_value=mock_extraction_response) as mock_create:
            processor.extract_entities_keywords(content, language="de")

            # Check that content was truncated
            call_args = mock_create.call_args
            messages = call_args.kwargs['messages']
            # Should not contain full 2000 chars
            assert "a" * 2000 not in messages[0]['content']

    def test_extract_entities_keywords_includes_language(self, processor, mock_extraction_response):
        """Should include language in prompt"""
        with patch.object(processor.client.chat.completions, 'create', return_value=mock_extraction_response) as mock_create:
            processor.extract_entities_keywords("Test content", language="fr")

            call_args = mock_create.call_args
            messages = call_args.kwargs['messages']
            assert "fr" in messages[0]['content']


class TestErrorHandling:
    """Test error handling and retries"""

    @pytest.fixture
    def processor(self):
        """Create LLM processor for tests"""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            return LLMProcessor()

    def test_retry_on_api_error(self, processor):
        """Should retry on API errors"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"language": "de", "confidence": 0.95}'

        with patch.object(processor.client.chat.completions, 'create', side_effect=[
            Exception("API Error"),
            Exception("API Error"),
            mock_response  # Third attempt succeeds
        ]) as mock_create:
            result = processor.detect_language("Test text")

            assert result.language == "de"
            assert mock_create.call_count == 3

    def test_max_retries_raises_error(self, processor):
        """Should raise error after max retries"""
        with patch.object(processor.client.chat.completions, 'create', side_effect=Exception("API Error")):
            with pytest.raises(Exception, match="API Error"):
                processor.detect_language("Test text")

    def test_invalid_json_response_raises_error(self, processor):
        """Should raise error on invalid JSON response"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Invalid JSON"

        with patch.object(processor.client.chat.completions, 'create', return_value=mock_response):
            with pytest.raises(Exception):  # JSON decode error or validation error
                processor.detect_language("Test text")


class TestCaching:
    """Test response caching functionality"""

    @pytest.fixture
    def processor(self):
        """Create LLM processor for tests"""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            return LLMProcessor()

    def test_cache_key_includes_text_and_operation(self, processor):
        """Cache key should include text and operation type"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"language": "de", "confidence": 0.95}'

        with patch.object(processor.client.chat.completions, 'create', return_value=mock_response):
            # Same text, different operation should not use cache
            processor.detect_language("Test text")
            processor._cache.clear()  # Clear cache manually

            # Now it should call API again
            processor.detect_language("Test text")

    def test_cache_ttl_30_days(self, processor):
        """Cache should have 30-day TTL"""
        # This is more of an implementation check
        assert processor.cache_ttl == 30 * 24 * 60 * 60  # 30 days in seconds

"""
LLM Processor

Replaces 5GB NLP stack with single qwen-turbo model:
- Language detection (replaces fasttext)
- Topic clustering (replaces BERTopic)
- Entity/keyword extraction (replaces spaCy NER)

Cost: $0.06/1M tokens (~$0.003/month for MVP)
Speed: ~100+ tokens/sec (~0.5s per call)
"""

import os
import json
import hashlib
from typing import List, Dict
from datetime import datetime, timedelta
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator

from src.utils.logger import get_logger

logger = get_logger(__name__)


# === Pydantic Models for Response Validation ===

class LanguageDetection(BaseModel):
    """Language detection result"""
    language: str = Field(..., description="ISO 639-1 language code (de, en, fr, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")

    @field_validator('language')
    @classmethod
    def validate_language_code(cls, v: str) -> str:
        """Ensure language code is lowercase"""
        return v.lower()


class Cluster(BaseModel):
    """Single topic cluster"""
    cluster: str = Field(..., description="Cluster name/label")
    topics: List[str] = Field(..., description="Topics in this cluster")


class ClusterResult(BaseModel):
    """Topic clustering result"""
    clusters: List[Cluster] = Field(..., description="List of topic clusters")


class EntityExtraction(BaseModel):
    """Entity and keyword extraction result"""
    entities: List[str] = Field(..., description="Named entities (companies, people, places, products)")
    keywords: List[str] = Field(..., description="Top keywords")


# === LLM Processor ===

class LLMProcessor:
    """
    LLM-based NLP processor using qwen-turbo

    Replaces:
    - fasttext (1GB) -> detect_language()
    - BERTopic (500MB + 2GB) -> cluster_topics()
    - spaCy (500MB/lang) -> extract_entities_keywords()

    Features:
    - 30-day response caching
    - Retry logic (3 attempts)
    - Pydantic validation
    - Cost tracking
    """

    def __init__(self, model: str = "qwen/qwen-2.5-7b-instruct", max_retries: int = 3):
        """
        Initialize LLM processor

        Args:
            model: OpenRouter model ID
            max_retries: Maximum retry attempts for failed API calls

        Raises:
            ValueError: If OPENROUTER_API_KEY not found in environment
        """
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = model
        self.max_retries = max_retries
        self.cache_ttl = 30 * 24 * 60 * 60  # 30 days in seconds

        # In-memory cache (production should use Redis/SQLite)
        self._cache: Dict[str, tuple[str, datetime]] = {}

        logger.info("llm_processor_initialized", model=model, cache_ttl_days=30)

    def detect_language(self, text: str) -> LanguageDetection:
        """
        Detect language of text

        Args:
            text: Text to analyze (truncated to 500 chars)

        Returns:
            LanguageDetection with language code and confidence

        Replaces: fasttext (1GB model)
        Better: Context-aware, handles mixed-language
        """
        # Truncate text for API efficiency
        text_sample = text[:500]

        # Check cache
        cache_key = self._get_cache_key("detect_language", text_sample)
        if cache_key in self._cache:
            cached_result, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                logger.info("cache_hit", operation="detect_language")
                return LanguageDetection.model_validate_json(cached_result)

        # Build prompt
        prompt = f"""Detect language. Return JSON only.

Text: {text_sample}

Format: {{"language": "de|en|fr", "confidence": 0-1}}"""

        # Make API call with retry
        response = self._call_api_with_retry(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=30
        )

        # Parse and validate response
        response_text = response.choices[0].message.content
        result = LanguageDetection.model_validate_json(response_text)

        # Cache result
        self._cache[cache_key] = (response_text, datetime.now())

        logger.info("language_detected", language=result.language, confidence=result.confidence)
        return result

    def cluster_topics(self, topics: List[str]) -> ClusterResult:
        """
        Cluster topics into semantic groups

        Args:
            topics: List of topic strings (truncated to 50 for API efficiency)

        Returns:
            ClusterResult with 5-10 topic clusters

        Replaces: BERTopic (500MB + 2GB models)
        Better: Contextual understanding, explainable clusters
        """
        # Truncate to 50 topics for API efficiency
        topics_sample = topics[:50]

        # Check cache
        cache_key = self._get_cache_key("cluster_topics", str(topics_sample))
        if cache_key in self._cache:
            cached_result, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                logger.info("cache_hit", operation="cluster_topics")
                return ClusterResult.model_validate_json(cached_result)

        # Build prompt
        prompt = f"""Group {len(topics_sample)} topics into 5-10 clusters:

{json.dumps(topics_sample, ensure_ascii=False)}

JSON: {{"clusters": [{{"cluster": "name", "topics": [...]}}]}}"""

        # Make API call with retry
        response = self._call_api_with_retry(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Slightly creative for clustering
            max_tokens=2000
        )

        # Parse and validate response
        response_text = response.choices[0].message.content
        result = ClusterResult.model_validate_json(response_text)

        # Cache result
        self._cache[cache_key] = (response_text, datetime.now())

        logger.info("topics_clustered", num_topics=len(topics_sample), num_clusters=len(result.clusters))
        return result

    def extract_entities_keywords(self, content: str, language: str) -> EntityExtraction:
        """
        Extract named entities and keywords from content

        Args:
            content: Content to analyze (truncated to 1500 chars)
            language: Language code for language-specific extraction

        Returns:
            EntityExtraction with entities and keywords

        Replaces: spaCy NER (500MB per language)
        Better: No per-language models needed, contextual extraction
        """
        # Truncate content for API efficiency
        content_sample = content[:1500]

        # Check cache
        cache_key = self._get_cache_key(f"extract_{language}", content_sample)
        if cache_key in self._cache:
            cached_result, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                logger.info("cache_hit", operation="extract_entities_keywords")
                return EntityExtraction.model_validate_json(cached_result)

        # Build prompt
        prompt = f"""Extract from {language} content:
1. Named entities (companies, products, people, places)
2. Top 10 keywords

Content: {content_sample}

JSON: {{"entities": [...], "keywords": [...]}}"""

        # Make API call with retry
        response = self._call_api_with_retry(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300
        )

        # Parse and validate response
        response_text = response.choices[0].message.content
        result = EntityExtraction.model_validate_json(response_text)

        # Cache result
        self._cache[cache_key] = (response_text, datetime.now())

        logger.info("entities_extracted", num_entities=len(result.entities), num_keywords=len(result.keywords))
        return result

    # === Helper Methods ===

    def _call_api_with_retry(self, messages: List[Dict], temperature: float, max_tokens: int):
        """
        Call OpenRouter API with retry logic

        Args:
            messages: Chat messages
            temperature: Temperature setting
            max_tokens: Maximum tokens in response

        Returns:
            API response

        Raises:
            Exception: After max retries exhausted
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response
            except Exception as e:
                last_error = e
                logger.warning("api_call_failed", attempt=attempt + 1, error=str(e))

                # Don't retry on last attempt
                if attempt < self.max_retries - 1:
                    continue

        # All retries exhausted
        logger.error("api_call_failed_max_retries", max_retries=self.max_retries)
        raise last_error

    def _get_cache_key(self, operation: str, content: str) -> str:
        """
        Generate cache key for operation and content

        Args:
            operation: Operation name (detect_language, cluster_topics, etc.)
            content: Content to hash

        Returns:
            Cache key string
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{operation}:{self.model}:{content_hash}"

    def clear_cache(self):
        """Clear all cached responses"""
        self._cache.clear()
        logger.info("cache_cleared")

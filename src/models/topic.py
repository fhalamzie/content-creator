"""
Topic Data Models

Pydantic models for topic discovery, research, and content generation.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, HttpUrl


class TopicSource(str, Enum):
    """Source of topic discovery"""
    RSS = "rss"
    REDDIT = "reddit"
    TRENDS = "trends"
    AUTOCOMPLETE = "autocomplete"
    COMPETITOR = "competitor"
    MANUAL = "manual"


class TopicStatus(str, Enum):
    """Topic lifecycle status"""
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    RESEARCHED = "researched"
    DRAFTED = "drafted"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SearchIntent(str, Enum):
    """Search intent classification (NeuralText pattern)"""
    INFORMATIONAL = "informational"
    COMMERCIAL = "commercial"
    TRANSACTIONAL = "transactional"
    NAVIGATIONAL = "navigational"


class Topic(BaseModel):
    """
    Core topic model

    Represents a discovered topic throughout its lifecycle:
    Discovery → Research → Writing → Publishing
    """
    id: Optional[str] = None
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None

    # Discovery metadata
    source: TopicSource
    source_url: Optional[HttpUrl] = None
    discovered_at: datetime = Field(default_factory=datetime.utcnow)

    # Classification
    domain: str = Field(..., description="Domain (e.g., 'proptech', 'fashion')")
    market: str = Field(..., description="Market (e.g., 'de', 'fr', 'us')")
    language: str = Field(..., description="Language code (e.g., 'de', 'en', 'fr')")
    intent: Optional[SearchIntent] = None

    # Engagement metrics (BuzzSumo pattern)
    engagement_score: int = Field(default=0, ge=0)
    trending_score: float = Field(default=0.0, ge=0.0, le=100.0)

    # Status tracking
    status: TopicStatus = TopicStatus.DISCOVERED
    priority: int = Field(default=5, ge=1, le=10)

    # Research results (populated by gpt-researcher)
    research_report: Optional[str] = None
    citations: List[str] = Field(default_factory=list)

    # Content metadata
    word_count: Optional[int] = None
    content_score: Optional[float] = None  # Surfer SEO pattern

    # Image generation (DALL-E 3)
    hero_image_url: Optional[str] = None  # Hero image URL (1792x1024 HD)
    supporting_images: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Supporting images [{url, alt, size, quality}]"
    )

    # ContentPipeline Stage 1: Competitor Research
    competitors: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Competitor analysis results"
    )
    content_gaps: List[str] = Field(
        default_factory=list,
        description="Content gaps identified vs competitors"
    )

    # ContentPipeline Stage 2: Keyword Research
    keywords: Dict[str, Any] = Field(
        default_factory=dict,
        description="Keywords: primary, secondary, long_tail"
    )
    keyword_difficulty: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="SEO difficulty score (0-100)"
    )

    # ContentPipeline Stage 5: Scoring & Ranking
    demand_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Search volume + engagement (0-1)"
    )
    opportunity_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Low competition + content gaps (0-1)"
    )
    fit_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Domain/market/vertical alignment (0-1)"
    )
    novelty_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Trending + uniqueness (0-1)"
    )
    priority_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Weighted combination of all scores (0-1)"
    )

    # Deduplication fingerprint
    minhash_signature: Optional[str] = None

    # Timestamps
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ResearchReport(BaseModel):
    """
    Deep research report from gpt-researcher

    Pattern: Citations-first research (not generic AI content)
    """
    topic_id: str
    query: str
    report: str = Field(..., description="Markdown research report")
    sources: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of source citations {title, url, snippet}"
    )
    word_count: int
    research_duration_seconds: float

    # Quality metrics
    source_count: int = Field(default=0)
    average_source_quality: float = Field(default=0.0, ge=0.0, le=1.0)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContentBrief(BaseModel):
    """
    Content brief for writing phase (NeuralText pattern)

    SERP-based structure recommendations
    """
    topic_id: str
    keyword: str
    intent: SearchIntent

    # Structure recommendations
    word_count_range: tuple[int, int] = Field(..., description="(min, max)")
    common_headings: List[str] = Field(default_factory=list)
    questions_to_answer: List[str] = Field(default_factory=list)
    entities_to_mention: List[str] = Field(default_factory=list)

    # Competitor insights
    competitor_urls: List[str] = Field(default_factory=list)
    difficulty_score: float = Field(default=0.0, ge=0.0, le=100.0)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class EngagementMetrics(BaseModel):
    """
    Multi-platform engagement tracking (BuzzSumo pattern)
    """
    topic_id: str
    platform: str  # reddit, twitter, etc.

    # Metrics
    score: int = Field(default=0)
    comments: int = Field(default=0)
    shares: int = Field(default=0)

    # Viral detection
    is_trending: bool = False
    velocity_score: float = Field(default=0.0, description="Engagement growth rate")

    tracked_at: datetime = Field(default_factory=datetime.utcnow)

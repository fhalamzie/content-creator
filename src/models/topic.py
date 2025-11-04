"""
Topic Data Models

Pydantic models for topic discovery, research, and content generation.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict

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

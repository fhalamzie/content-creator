"""
Universal Document data model

Unified data structure used across all collectors (RSS, Reddit, Trends, etc.).
Ensures consistency in how content is stored, processed, and analyzed.

Example:
    from src.models.document import Document
    from datetime import datetime

    doc = Document(
        id="rss_heise_123",
        source="rss_heise",
        source_url="https://heise.de/article/123",
        title="PropTech Trends 2025",
        content="...",
        language="de",
        domain="SaaS",
        market="Germany",
        vertical="Proptech",
        content_hash="abc123xyz",
        canonical_url="https://heise.de/article/123",
        published_at=datetime.now(),
        fetched_at=datetime.now()
    )

    # Check processing status
    if doc.is_processed():
        print(f"Entities: {doc.entities}")
        print(f"Keywords: {doc.keywords}")
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class Document(BaseModel):
    """
    Universal data model for ALL content sources

    Used by: RSS collectors, Reddit collector, Trends collector, autocomplete,
             competitor content, SERP analysis
    """

    # === Identity ===
    id: str = Field(
        ...,
        description="Unique document ID (e.g., 'rss_heise_123', 'reddit_proptech_456')"
    )
    source: str = Field(
        ...,
        description="Source identifier (e.g., 'rss_heise', 'reddit_proptech', 'trends_de')"
    )
    source_url: str = Field(
        ...,
        description="Original URL where content was found"
    )

    # === Content ===
    title: str = Field(
        ...,
        description="Article/post title"
    )
    content: str = Field(
        ...,
        description="Full content text (extracted from HTML if necessary)"
    )
    summary: Optional[str] = Field(
        None,
        description="Optional summary (from RSS feed or generated)"
    )

    # === Classification ===
    language: str = Field(
        ...,
        description="ISO 639-1 language code (de, en, fr, etc.) - auto-detected by LLM"
    )
    domain: str = Field(
        ...,
        description="Business domain from config (SaaS, E-commerce, etc.)"
    )
    market: str = Field(
        ...,
        description="Market from config (Germany, France, US, etc.)"
    )
    vertical: str = Field(
        ...,
        description="Vertical from config (Proptech, Fashion, etc.)"
    )

    # === Deduplication ===
    content_hash: str = Field(
        ...,
        description="SimHash/MinHash for near-duplicate detection"
    )
    canonical_url: str = Field(
        ...,
        description="Normalized URL (no tracking params, no www, lowercase)"
    )

    # === Metadata ===
    published_at: datetime = Field(
        ...,
        description="When the content was originally published"
    )
    fetched_at: datetime = Field(
        ...,
        description="When we fetched this content"
    )
    author: Optional[str] = Field(
        None,
        description="Content author (if available)"
    )

    # === Enrichment (added in processing stage) ===
    entities: Optional[List[str]] = Field(
        None,
        description="Named entities extracted by LLM (companies, people, places, products)"
    )
    keywords: Optional[List[str]] = Field(
        None,
        description="Keywords extracted by LLM"
    )

    # === Provenance ===
    reliability_score: float = Field(
        0.5,
        description="Source reliability score (0-1), default 0.5",
        ge=0.0,
        le=1.0
    )
    paywall: bool = Field(
        False,
        description="Whether content is behind a paywall"
    )

    # === Status ===
    status: str = Field(
        "new",
        description="Processing status: new, processed, rejected"
    )

    # === Helper Methods ===

    def is_processed(self) -> bool:
        """
        Check if document has been processed

        Returns:
            True if status is 'processed', False otherwise
        """
        return self.status == "processed"

    def has_entities(self) -> bool:
        """
        Check if entities have been extracted

        Returns:
            True if entities list exists and is not empty
        """
        return self.entities is not None and len(self.entities) > 0

    def has_keywords(self) -> bool:
        """
        Check if keywords have been extracted

        Returns:
            True if keywords list exists and is not empty
        """
        return self.keywords is not None and len(self.keywords) > 0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "rss_heise_123",
                "source": "rss_heise",
                "source_url": "https://heise.de/article/123",
                "title": "PropTech Trends 2025",
                "content": "Article content here...",
                "summary": "Summary of PropTech trends",
                "language": "de",
                "domain": "SaaS",
                "market": "Germany",
                "vertical": "Proptech",
                "content_hash": "abc123xyz",
                "canonical_url": "https://heise.de/article/123",
                "published_at": "2025-11-03T12:00:00",
                "fetched_at": "2025-11-03T12:05:00",
                "author": "John Doe",
                "entities": ["Berlin", "PropTech", "IoT"],
                "keywords": ["SaaS", "PropTech", "Germany", "Smart Building"],
                "reliability_score": 0.8,
                "paywall": False,
                "status": "processed"
            }
        }
    )

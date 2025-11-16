"""
Tests for Research Cache Utilities

Tests save_research_to_cache() and load_research_from_cache() functions.
"""

import pytest
from pathlib import Path
from datetime import datetime

from src.utils.research_cache import (
    slugify,
    save_research_to_cache,
    load_research_from_cache,
    clear_research_cache
)
from src.database.sqlite_manager import SQLiteManager


class TestSlugify:
    """Test slug generation"""

    def test_simple_slug(self):
        """Test basic slug generation"""
        assert slugify("PropTech Trends 2025") == "proptech-trends-2025"

    def test_german_umlauts(self):
        """Test German umlaut normalization"""
        assert slugify("Schädlingsbekämpfung für Wohnungen") == "schaedlingsbekaempfung-fuer-wohnungen"
        assert slugify("KI-gestützte Lösungen") == "ki-gestuetzte-loesungen"
        assert slugify("Größere Büroräume") == "groessere-bueroraeume"

    def test_special_characters(self):
        """Test special character removal"""
        assert slugify("AI & ML: The Future!") == "ai-ml-the-future"
        assert slugify("Cost ($100-200) Analysis") == "cost-100-200-analysis"

    def test_max_length(self):
        """Test length limiting"""
        long_text = "This is a very long topic title that should be truncated to a reasonable length"
        slug = slugify(long_text, max_length=50)
        assert len(slug) <= 50
        # Slug should be truncated at word boundary (may not end with hyphen)
        assert '-' in slug  # Should contain hyphens from word separation


class TestResearchCache:
    """Test research cache save/load operations"""

    @pytest.fixture
    def in_memory_db(self, tmp_path):
        """Create temporary database file for testing (in-memory doesn't persist across connections)"""
        return str(tmp_path / "test.db")

    @pytest.fixture
    def sample_research(self):
        """Sample deep research data"""
        return {
            "topic": "PropTech Trends 2025",
            "article": """# PropTech Trends 2025

## Introduction

The property technology (PropTech) industry is experiencing rapid growth...

[Source: Example.com](https://example.com/1)

## Key Trends

1. **AI-Powered Property Management**: Artificial intelligence is transforming...

[Source: TechNews.com](https://example.com/2)

2. **Smart Building Integration**: IoT devices are creating...

3. **Virtual Tours and AR**: Augmented reality is revolutionizing...

## Conclusion

The PropTech sector will continue to evolve...

(2000 words)
""",
            "sources": [
                {"url": "https://example.com/1", "title": "PropTech Report 2025", "snippet": "Latest trends"},
                {"url": "https://example.com/2", "title": "AI in Real Estate", "snippet": "AI applications"}
            ],
            "config": {
                "market": "Germany",
                "vertical": "PropTech",
                "language": "de",
                "domain": "example.com"
            }
        }

    def test_save_and_load_research(self, in_memory_db, sample_research):
        """Test saving and loading research"""
        # Save research
        topic_id = save_research_to_cache(
            topic=sample_research["topic"],
            research_article=sample_research["article"],
            sources=sample_research["sources"],
            config=sample_research["config"],
            db_path=in_memory_db
        )

        assert topic_id == "proptech-trends-2025"

        # Load research
        cached = load_research_from_cache(
            topic=sample_research["topic"],
            db_path=in_memory_db
        )

        assert cached is not None
        assert cached["topic"] == sample_research["topic"]
        assert cached["research_article"] == sample_research["article"]
        assert len(cached["sources"]) == 2
        assert cached["language"] == "de"
        assert cached["word_count"] > 0

    def test_load_nonexistent_research(self, in_memory_db):
        """Test loading research that doesn't exist"""
        cached = load_research_from_cache(
            topic="Nonexistent Topic",
            db_path=in_memory_db
        )

        assert cached is None

    def test_update_existing_research(self, in_memory_db, sample_research):
        """Test updating existing research"""
        # Save initial research
        topic_id = save_research_to_cache(
            topic=sample_research["topic"],
            research_article=sample_research["article"],
            sources=sample_research["sources"],
            config=sample_research["config"],
            db_path=in_memory_db
        )

        # Update with new article
        updated_article = sample_research["article"] + "\n\nUPDATED CONTENT"

        save_research_to_cache(
            topic=sample_research["topic"],
            research_article=updated_article,
            sources=sample_research["sources"],
            config=sample_research["config"],
            db_path=in_memory_db
        )

        # Load and verify update
        cached = load_research_from_cache(
            topic=sample_research["topic"],
            db_path=in_memory_db
        )

        assert "UPDATED CONTENT" in cached["research_article"]

    def test_save_without_config(self, in_memory_db, sample_research):
        """Test saving research without config (should use defaults)"""
        topic_id = save_research_to_cache(
            topic=sample_research["topic"],
            research_article=sample_research["article"],
            sources=sample_research["sources"],
            config=None,  # No config
            db_path=in_memory_db
        )

        assert topic_id == "proptech-trends-2025"

        # Verify it saved with default values
        cached = load_research_from_cache(
            topic=sample_research["topic"],
            db_path=in_memory_db
        )

        assert cached is not None
        assert cached["language"] == "en"  # Default language

    def test_delete_research(self, in_memory_db, sample_research):
        """Test deleting cached research"""
        # Save research
        save_research_to_cache(
            topic=sample_research["topic"],
            research_article=sample_research["article"],
            sources=sample_research["sources"],
            config=sample_research["config"],
            db_path=in_memory_db
        )

        # Verify it exists
        cached = load_research_from_cache(
            topic=sample_research["topic"],
            db_path=in_memory_db
        )
        assert cached is not None

        # Delete
        deleted_count = clear_research_cache(
            topic=sample_research["topic"],
            db_path=in_memory_db
        )

        assert deleted_count == 1

        # Verify it's gone
        cached = load_research_from_cache(
            topic=sample_research["topic"],
            db_path=in_memory_db
        )
        assert cached is None


class TestIntegration:
    """Integration tests with real database"""

    @pytest.fixture
    def test_db_path(self, tmp_path):
        """Create temporary database file"""
        return str(tmp_path / "test_topics.db")

    def test_save_load_with_file_db(self, test_db_path):
        """Test save/load with file-based database"""
        topic = "Cloud Computing Best Practices"
        article = "# Cloud Computing\n\nBest practices for cloud...\n\n(500 words)"
        sources = [{"url": "https://example.com/cloud", "title": "Cloud Guide", "snippet": ""}]

        # Save
        topic_id = save_research_to_cache(
            topic=topic,
            research_article=article,
            sources=sources,
            config={"market": "USA", "language": "en"},
            db_path=test_db_path
        )

        # Load
        cached = load_research_from_cache(topic, db_path=test_db_path)

        assert cached is not None
        assert cached["topic"] == topic
        assert len(cached["research_article"]) > 0

    def test_concurrent_access(self, test_db_path):
        """Test multiple topics saved to same database"""
        topics = [
            "AI in Healthcare",
            "Blockchain Applications",
            "Quantum Computing"
        ]

        # Save multiple topics
        for topic in topics:
            save_research_to_cache(
                topic=topic,
                research_article=f"# {topic}\n\nResearch content...",
                sources=[{"url": f"https://example.com/{slugify(topic)}", "title": topic, "snippet": ""}],
                config={"language": "en"},
                db_path=test_db_path
            )

        # Load each topic
        for topic in topics:
            cached = load_research_from_cache(topic, db_path=test_db_path)
            assert cached is not None
            assert topic in cached["research_article"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

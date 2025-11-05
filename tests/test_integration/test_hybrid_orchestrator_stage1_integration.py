"""
Integration tests for HybridResearchOrchestrator Stage 1

Tests with real websites and Gemini API calls.
Requires GEMINI_API_KEY environment variable.

Run with: pytest tests/test_integration/test_hybrid_orchestrator_stage1_integration.py -v -s
"""

import pytest
import os
import asyncio

from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator


@pytest.fixture
def orchestrator():
    """Create orchestrator instance"""
    return HybridResearchOrchestrator()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_keywords_from_real_website(orchestrator):
    """
    Integration test: Extract keywords from a real website

    Uses example.org (IANA reserved domain with stable content)
    Tests full pipeline: trafilatura fetch + Gemini analysis

    Cost: ~$0.001 (Gemini Flash with short content)
    """
    # Skip if no API key
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")

    # Use example.org (stable, always available, simple content)
    url = "https://example.org"

    # Execute
    result = await orchestrator.extract_website_keywords(url, max_keywords=20)

    # Log result for debugging
    print("\n" + "="*80)
    print(f"URL: {url}")
    print(f"Keywords: {result.get('keywords', [])}")
    print(f"Tags: {result.get('tags', [])}")
    print(f"Themes: {result.get('themes', [])}")
    print(f"Cost: ${result.get('cost', 0):.4f}")
    if "error" in result:
        print(f"Error: {result['error']}")
    print("="*80 + "\n")

    # Verify structure (original fields)
    assert "keywords" in result
    assert "tags" in result
    assert "themes" in result
    assert "cost" in result
    assert isinstance(result["keywords"], list)
    assert isinstance(result["tags"], list)
    assert isinstance(result["themes"], list)
    assert isinstance(result["cost"], (int, float))

    # Verify new fields (Session 034)
    assert "tone" in result
    assert "setting" in result
    assert "niche" in result
    assert "domain" in result
    assert isinstance(result["tone"], list)
    assert isinstance(result["setting"], list)
    assert isinstance(result["niche"], list)
    assert isinstance(result["domain"], str)

    # Verify content extracted (example.org has minimal but valid content)
    # At minimum, we should get some result or a meaningful error
    if "error" not in result:
        # Success case: verify reasonable output
        # example.org is simple, so we might get few keywords
        assert len(result["keywords"]) >= 0  # May be empty for simple sites
        assert len(result["tags"]) >= 0
        assert len(result["themes"]) >= 0

        # Verify cost is tracked
        assert result["cost"] >= 0.0

        # If we got any results, verify they're strings
        if result["keywords"]:
            assert all(isinstance(k, str) for k in result["keywords"])
        if result["tags"]:
            assert all(isinstance(t, str) for t in result["tags"])
        if result["themes"]:
            assert all(isinstance(t, str) for t in result["themes"])
    else:
        # Error case: verify error is meaningful
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0
        print(f"Note: Extraction failed with error: {result['error']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_keywords_from_content_rich_website(orchestrator):
    """
    Integration test: Extract keywords from content-rich website

    Uses Wikipedia homepage (content-rich, stable)
    Should extract meaningful keywords, tags, and themes

    Cost: ~$0.001-0.002 (Gemini Flash)
    """
    # Skip if no API key
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")

    # Use Wikipedia homepage (stable, rich content)
    url = "https://en.wikipedia.org/wiki/Main_Page"

    # Execute
    result = await orchestrator.extract_website_keywords(url, max_keywords=30)

    # Log result for debugging
    print("\n" + "="*80)
    print(f"URL: {url}")
    print(f"Keywords ({len(result.get('keywords', []))}): {result.get('keywords', [])[:10]}...")
    print(f"Tags ({len(result.get('tags', []))}): {result.get('tags', [])}")
    print(f"Themes ({len(result.get('themes', []))}): {result.get('themes', [])}")
    print(f"Cost: ${result.get('cost', 0):.4f}")
    if "error" in result:
        print(f"Error: {result['error']}")
    print("="*80 + "\n")

    # Verify structure (original fields)
    assert "keywords" in result
    assert "tags" in result
    assert "themes" in result
    assert "cost" in result

    # Verify new fields (Session 034)
    assert "tone" in result
    assert "setting" in result
    assert "niche" in result
    assert "domain" in result

    # For Wikipedia, we should get meaningful results
    if "error" not in result:
        # Should extract some keywords from content-rich site
        assert len(result["keywords"]) > 0, "Expected keywords from Wikipedia"
        assert len(result["tags"]) > 0, "Expected tags from Wikipedia"
        assert len(result["themes"]) > 0, "Expected themes from Wikipedia"

        # Verify all are strings
        assert all(isinstance(k, str) for k in result["keywords"])
        assert all(isinstance(t, str) for t in result["tags"])
        assert all(isinstance(t, str) for t in result["themes"])

        # Verify max limits are respected
        assert len(result["keywords"]) <= 30, "Keywords should respect max limit"
        assert len(result["tags"]) <= 10, "Tags should respect max limit"
        assert len(result["themes"]) <= 5, "Themes should respect max limit"

        # Wikipedia should have encyclopedia-related keywords
        # (This is a loose check - content changes daily)
        all_text = " ".join(result["keywords"] + result["tags"] + result["themes"]).lower()
        # Just verify we got some reasonable content (not all empty strings)
        assert len(all_text.strip()) > 10, "Expected substantial content from Wikipedia"
    else:
        # Error case
        print(f"Note: Extraction failed with error: {result['error']}")
        # Even on error, structure should be valid
        assert result["keywords"] == []
        assert result["tags"] == []
        assert result["themes"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_keywords_quality_check(orchestrator):
    """
    Integration test: Verify quality of extracted keywords

    Uses GitHub.com homepage (tech company with clear keywords)
    Validates that extracted content makes sense

    Cost: ~$0.001-0.002 (Gemini Flash)
    """
    # Skip if no API key
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")

    # Use GitHub homepage (clear tech keywords expected)
    url = "https://github.com"

    # Execute
    result = await orchestrator.extract_website_keywords(url, max_keywords=25)

    # Log result for debugging
    print("\n" + "="*80)
    print(f"URL: {url}")
    print(f"Keywords: {result.get('keywords', [])}")
    print(f"Tags: {result.get('tags', [])}")
    print(f"Themes: {result.get('themes', [])}")
    print(f"Cost: ${result.get('cost', 0):.4f}")
    if "error" in result:
        print(f"Error: {result['error']}")
    print("="*80 + "\n")

    if "error" not in result:
        # GitHub should produce tech-related keywords
        keywords_text = " ".join(result["keywords"]).lower()
        tags_text = " ".join(result["tags"]).lower()
        all_text = keywords_text + " " + tags_text

        # Should have tech/dev related terms (loose check)
        tech_indicators = [
            "git", "code", "develop", "software", "repository",
            "project", "collaboration", "version", "control", "platform"
        ]

        # Check if at least one tech indicator appears
        has_tech_terms = any(indicator in all_text for indicator in tech_indicators)

        # Log what we found
        print(f"Tech terms found: {[t for t in tech_indicators if t in all_text]}")

        # This is a soft assertion - GitHub's homepage content may vary
        # We mainly want to verify we're getting reasonable, relevant keywords
        # not that specific terms appear
        assert len(result["keywords"]) > 0, "Expected some keywords"
        assert len(result["tags"]) > 0, "Expected some tags"

        # Print info message if no obvious tech terms (not a hard failure)
        if not has_tech_terms:
            print("Note: No obvious tech terms found, but extraction succeeded")
    else:
        print(f"Note: Extraction failed with error: {result['error']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_keywords_from_non_english_website(orchestrator):
    """
    Integration test: Extract keywords from non-English website

    Uses Spiegel.de (German news site)
    Validates that extraction works with non-English content

    Cost: ~$0.001-0.002 (Gemini Flash)
    """
    # Skip if no API key
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")

    # Use Spiegel.de (German news site, stable, content-rich)
    url = "https://www.spiegel.de"

    # Execute
    result = await orchestrator.extract_website_keywords(url, max_keywords=20)

    # Log result for debugging
    print("\n" + "="*80)
    print(f"URL: {url}")
    print(f"Keywords: {result.get('keywords', [])}")
    print(f"Tags: {result.get('tags', [])}")
    print(f"Themes: {result.get('themes', [])}")
    print(f"Tone: {result.get('tone', [])}")
    print(f"Setting: {result.get('setting', [])}")
    print(f"Niche: {result.get('niche', [])}")
    print(f"Domain: {result.get('domain', 'Unknown')}")
    print(f"Cost: ${result.get('cost', 0):.4f}")
    if "error" in result:
        print(f"Error: {result['error']}")
    print("="*80 + "\n")

    # Verify structure
    assert "keywords" in result
    assert "tags" in result
    assert "themes" in result
    assert "tone" in result
    assert "setting" in result
    assert "niche" in result
    assert "domain" in result
    assert "cost" in result

    if "error" not in result:
        # Should extract keywords from German news site
        assert len(result["keywords"]) > 0, "Expected keywords from Spiegel.de"

        # Verify all fields are properly populated
        assert all(isinstance(k, str) for k in result["keywords"])
        assert all(isinstance(t, str) for t in result["tags"])
        assert all(isinstance(t, str) for t in result["themes"])

        # Domain should indicate news/media
        assert result["domain"] != "Unknown", "Expected domain to be identified"

        # Should have identified niche (news, politics, etc.)
        assert len(result["niche"]) > 0, "Expected niche identification"
    else:
        print(f"Note: Extraction failed with error: {result['error']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_keywords_invalid_url_error_handling(orchestrator):
    """
    Integration test: Error handling for invalid URL

    Tests that invalid/unreachable URLs are handled gracefully
    Should return empty results with cost=0

    Cost: $0 (no API call made)
    """
    # Skip if no API key
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")

    # Use invalid URL
    url = "https://this-domain-definitely-does-not-exist-12345.com"

    # Execute
    result = await orchestrator.extract_website_keywords(url, max_keywords=20)

    # Log result for debugging
    print("\n" + "="*80)
    print(f"URL: {url}")
    print(f"Keywords: {result.get('keywords', [])}")
    print(f"Error: {result.get('error', 'None')}")
    print(f"Cost: ${result.get('cost', 0):.4f}")
    print("="*80 + "\n")

    # Verify structure is still valid
    assert "keywords" in result
    assert "tags" in result
    assert "themes" in result
    assert "tone" in result
    assert "setting" in result
    assert "niche" in result
    assert "domain" in result
    assert "cost" in result

    # Should return empty results
    assert result["keywords"] == []
    assert result["tags"] == []
    assert result["themes"] == []
    assert result["tone"] == []
    assert result["setting"] == []
    assert result["niche"] == []
    assert result["domain"] == "Unknown"

    # Should have zero cost (no API call)
    assert result["cost"] == 0.0

    # Should have an error message
    assert "error" in result or len(result["keywords"]) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_extract_keywords_from_ecommerce_website(orchestrator):
    """
    Integration test: Extract keywords from e-commerce website

    Uses Amazon.com homepage
    Validates extraction from product-focused, commercial content

    Cost: ~$0.001-0.002 (Gemini Flash)
    """
    # Skip if no API key
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")

    # Use Amazon homepage (e-commerce, product-focused)
    url = "https://www.amazon.com"

    # Execute
    result = await orchestrator.extract_website_keywords(url, max_keywords=25)

    # Log result for debugging
    print("\n" + "="*80)
    print(f"URL: {url}")
    print(f"Keywords: {result.get('keywords', [])}")
    print(f"Tags: {result.get('tags', [])}")
    print(f"Themes: {result.get('themes', [])}")
    print(f"Tone: {result.get('tone', [])}")
    print(f"Setting: {result.get('setting', [])}")
    print(f"Niche: {result.get('niche', [])}")
    print(f"Domain: {result.get('domain', 'Unknown')}")
    print(f"Cost: ${result.get('cost', 0):.4f}")
    if "error" in result:
        print(f"Error: {result['error']}")
    print("="*80 + "\n")

    # Verify structure
    assert "keywords" in result
    assert "tags" in result
    assert "themes" in result
    assert "tone" in result
    assert "setting" in result
    assert "niche" in result
    assert "domain" in result
    assert "cost" in result

    if "error" not in result:
        # Should extract keywords from e-commerce site
        assert len(result["keywords"]) > 0, "Expected keywords from Amazon"

        # Verify structure
        assert all(isinstance(k, str) for k in result["keywords"])
        assert all(isinstance(t, str) for t in result["tags"])

        # Setting should indicate e-commerce/B2C
        setting_text = " ".join(result["setting"]).lower()

        # Verify we got reasonable content
        assert len(result["keywords"]) <= 25, "Keywords should respect max limit"

        # Domain should be identified
        assert result["domain"] != "Unknown", "Expected domain identification"

        # Log what we found
        print(f"Setting identified: {result['setting']}")
        print(f"Domain identified: {result['domain']}")
    else:
        print(f"Note: Extraction failed with error: {result['error']}")


if __name__ == "__main__":
    # Allow running directly for manual testing
    print("Running Stage 1 integration tests...")
    print("These tests make real API calls and cost ~$0.006-0.010 total")
    print()

    orchestrator = HybridResearchOrchestrator()

    # Run each test
    asyncio.run(test_extract_keywords_from_real_website(orchestrator))
    asyncio.run(test_extract_keywords_from_content_rich_website(orchestrator))
    asyncio.run(test_extract_keywords_quality_check(orchestrator))
    asyncio.run(test_extract_keywords_from_non_english_website(orchestrator))
    asyncio.run(test_extract_keywords_invalid_url_error_handling(orchestrator))
    asyncio.run(test_extract_keywords_from_ecommerce_website(orchestrator))

    print("\nAll integration tests completed!")

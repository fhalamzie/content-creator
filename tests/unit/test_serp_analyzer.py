"""
Unit tests for SERP Analyzer

Tests:
- Domain extraction
- Domain authority estimation
- SERP analysis
- Snapshot comparison
- Error handling
"""

import pytest
from src.research.serp_analyzer import SERPAnalyzer, SERPResult


class TestSERPAnalyzer:
    """Test SERP Analyzer functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.analyzer = SERPAnalyzer()

    # === Domain Extraction Tests ===

    def test_extract_domain_basic(self):
        """Test basic domain extraction"""
        domain = self.analyzer._extract_domain("https://example.com/path")
        assert domain == "example.com"

    def test_extract_domain_with_www(self):
        """Test domain extraction removes www prefix"""
        domain = self.analyzer._extract_domain("https://www.example.com/path")
        assert domain == "example.com"

    def test_extract_domain_with_subdomain(self):
        """Test domain extraction keeps non-www subdomains"""
        domain = self.analyzer._extract_domain("https://blog.example.com/path")
        assert domain == "blog.example.com"

    def test_extract_domain_with_query_params(self):
        """Test domain extraction ignores query parameters"""
        domain = self.analyzer._extract_domain("https://example.com/path?foo=bar&baz=qux")
        assert domain == "example.com"

    def test_extract_domain_empty_url(self):
        """Test domain extraction handles empty URL"""
        domain = self.analyzer._extract_domain("")
        assert domain == ""

    def test_extract_domain_invalid_url(self):
        """Test domain extraction handles invalid URL gracefully"""
        domain = self.analyzer._extract_domain("not-a-valid-url")
        assert domain == ""

    # === Domain Authority Estimation Tests ===

    def test_estimate_authority_gov_domain(self):
        """Test .gov domains get high authority"""
        authority = self.analyzer._estimate_domain_authority("cdc.gov", 5)
        assert authority == "high"

    def test_estimate_authority_edu_domain(self):
        """Test .edu domains get high authority"""
        authority = self.analyzer._estimate_domain_authority("mit.edu", 8)
        assert authority == "high"

    def test_estimate_authority_known_news_site(self):
        """Test known news sites get high authority"""
        authority = self.analyzer._estimate_domain_authority("nytimes.com", 5)
        assert authority == "high"

    def test_estimate_authority_position_1_3(self):
        """Test positions 1-3 get high authority"""
        authority = self.analyzer._estimate_domain_authority("unknown-site.com", 2)
        assert authority == "high"

    def test_estimate_authority_position_4_7(self):
        """Test positions 4-7 get medium authority"""
        authority = self.analyzer._estimate_domain_authority("unknown-site.com", 5)
        assert authority == "medium"

    def test_estimate_authority_position_8_10(self):
        """Test positions 8-10 get low authority"""
        authority = self.analyzer._estimate_domain_authority("unknown-site.com", 9)
        assert authority == "low"

    # === SERP Analysis Tests ===

    def test_analyze_serp_basic(self):
        """Test basic SERP analysis"""
        results = [
            SERPResult(1, "https://example.com/1", "Title 1", "Snippet 1", "example.com"),
            SERPResult(2, "https://test.com/2", "Title 2", "Snippet 2", "test.com"),
            SERPResult(3, "https://example.com/3", "Title 3", "Snippet 3", "example.com"),
        ]

        analysis = self.analyzer.analyze_serp(results)

        assert analysis["total_results"] == 3
        assert analysis["unique_domains"] == 2
        assert "example.com" in analysis["domain_distribution"]
        assert analysis["domain_distribution"]["example.com"] == [1, 3]
        assert analysis["top_3_domains"] == ["example.com", "test.com", "example.com"]

    def test_analyze_serp_empty(self):
        """Test SERP analysis handles empty results"""
        analysis = self.analyzer.analyze_serp([])

        assert analysis["total_results"] == 0
        assert analysis["unique_domains"] == 0
        assert analysis["domain_distribution"] == {}
        assert analysis["top_3_domains"] == []

    def test_analyze_serp_calculates_averages(self):
        """Test SERP analysis calculates title/snippet averages"""
        results = [
            SERPResult(1, "https://example.com/1", "12345", "1234567890", "example.com"),  # 5 chars, 10 chars
            SERPResult(2, "https://test.com/2", "123456789", "12345", "test.com"),  # 9 chars, 5 chars
        ]

        analysis = self.analyzer.analyze_serp(results)

        # Average title: (5 + 9) / 2 = 7.0
        # Average snippet: (10 + 5) / 2 = 7.5
        assert analysis["avg_title_length"] == 7.0
        assert analysis["avg_snippet_length"] == 7.5

    def test_analyze_serp_domain_authority(self):
        """Test SERP analysis estimates domain authority"""
        results = [
            SERPResult(1, "https://cdc.gov/health", "Title", "Snippet", "cdc.gov"),
            SERPResult(5, "https://blog.com/post", "Title", "Snippet", "blog.com"),
        ]

        analysis = self.analyzer.analyze_serp(results)

        assert analysis["domain_authority_estimate"]["cdc.gov"] == "high"
        assert analysis["domain_authority_estimate"]["blog.com"] == "medium"

    # === Snapshot Comparison Tests ===

    def test_compare_snapshots_new_entrants(self):
        """Test snapshot comparison detects new entrants"""
        old = [
            SERPResult(1, "https://example.com/1", "Title", "Snippet", "example.com"),
        ]
        new = [
            SERPResult(1, "https://example.com/1", "Title", "Snippet", "example.com"),
            SERPResult(2, "https://new.com/2", "New Title", "New Snippet", "new.com"),
        ]

        comparison = self.analyzer.compare_snapshots(old, new)

        assert len(comparison["new_entrants"]) == 1
        assert "https://new.com/2" in comparison["new_entrants"]

    def test_compare_snapshots_dropouts(self):
        """Test snapshot comparison detects dropouts"""
        old = [
            SERPResult(1, "https://example.com/1", "Title", "Snippet", "example.com"),
            SERPResult(2, "https://old.com/2", "Old Title", "Old Snippet", "old.com"),
        ]
        new = [
            SERPResult(1, "https://example.com/1", "Title", "Snippet", "example.com"),
        ]

        comparison = self.analyzer.compare_snapshots(old, new)

        assert len(comparison["dropouts"]) == 1
        assert "https://old.com/2" in comparison["dropouts"]

    def test_compare_snapshots_position_up(self):
        """Test snapshot comparison detects position improvements"""
        old = [
            SERPResult(5, "https://example.com/1", "Title", "Snippet", "example.com"),
        ]
        new = [
            SERPResult(2, "https://example.com/1", "Title", "Snippet", "example.com"),
        ]

        comparison = self.analyzer.compare_snapshots(old, new)

        assert len(comparison["position_changes"]) == 1
        change = comparison["position_changes"]["https://example.com/1"]
        assert change["old_position"] == 5
        assert change["new_position"] == 2
        assert change["change"] == 3  # Moved up 3 positions
        assert change["direction"] == "up"

    def test_compare_snapshots_position_down(self):
        """Test snapshot comparison detects position declines"""
        old = [
            SERPResult(2, "https://example.com/1", "Title", "Snippet", "example.com"),
        ]
        new = [
            SERPResult(7, "https://example.com/1", "Title", "Snippet", "example.com"),
        ]

        comparison = self.analyzer.compare_snapshots(old, new)

        assert len(comparison["position_changes"]) == 1
        change = comparison["position_changes"]["https://example.com/1"]
        assert change["old_position"] == 2
        assert change["new_position"] == 7
        assert change["change"] == -5  # Moved down 5 positions
        assert change["direction"] == "down"

    def test_compare_snapshots_stable_urls(self):
        """Test snapshot comparison detects stable URLs"""
        old = [
            SERPResult(3, "https://example.com/1", "Title", "Snippet", "example.com"),
        ]
        new = [
            SERPResult(3, "https://example.com/1", "Title", "Snippet", "example.com"),
        ]

        comparison = self.analyzer.compare_snapshots(old, new)

        assert len(comparison["stable_urls"]) == 1
        assert "https://example.com/1" in comparison["stable_urls"]
        assert len(comparison["position_changes"]) == 0

    # === Results to Dict Conversion Tests ===

    def test_results_to_dict(self):
        """Test converting SERPResult objects to dicts"""
        results = [
            SERPResult(1, "https://example.com/1", "Title 1", "Snippet 1", "example.com"),
            SERPResult(2, "https://test.com/2", "Title 2", "Snippet 2", "test.com"),
        ]

        dicts = self.analyzer.results_to_dict(results)

        assert len(dicts) == 2
        assert dicts[0]["position"] == 1
        assert dicts[0]["url"] == "https://example.com/1"
        assert dicts[0]["title"] == "Title 1"
        assert dicts[0]["snippet"] == "Snippet 1"
        assert dicts[0]["domain"] == "example.com"

    def test_results_to_dict_empty(self):
        """Test converting empty results list"""
        dicts = self.analyzer.results_to_dict([])
        assert dicts == []

    # === Error Handling Tests ===

    def test_search_empty_query(self):
        """Test search with empty query raises ValueError"""
        with pytest.raises(ValueError, match="Search query cannot be empty"):
            self.analyzer.search("")

    def test_search_whitespace_query(self):
        """Test search with whitespace-only query raises ValueError"""
        with pytest.raises(ValueError, match="Search query cannot be empty"):
            self.analyzer.search("   ")

    def test_search_invalid_max_results_too_low(self):
        """Test search with max_results < 1 raises ValueError"""
        with pytest.raises(ValueError, match="max_results must be between 1 and 10"):
            self.analyzer.search("test query", max_results=0)

    def test_search_invalid_max_results_too_high(self):
        """Test search with max_results > 10 raises ValueError"""
        with pytest.raises(ValueError, match="max_results must be between 1 and 10"):
            self.analyzer.search("test query", max_results=11)

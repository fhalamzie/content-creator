#!/usr/bin/env python
"""
Comprehensive Test Script for DeepResearcher

Tests the fixed _build_query method with:
1. Mock data from Stage 1 (competitor gaps as strings)
2. Mock data from Stage 2 (keywords as dicts)
3. Full research_topic method with gpt-researcher
4. Gemini 2.0 Flash compatibility

Run with:
    python test_deep_researcher_integration.py

Or with pytest:
    pytest test_deep_researcher_integration.py -v -s
"""

import asyncio
import json
from typing import Dict, List, Optional
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.research.deep_researcher import DeepResearcher, DeepResearchError


class TestResults:
    """Container for test results"""
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0

    def add_result(self, test_name: str, passed: bool, message: str, details: Optional[Dict] = None):
        """Add test result"""
        result = {
            'test': test_name,
            'status': 'PASS' if passed else 'FAIL',
            'message': message,
            'details': details or {}
        }
        self.tests.append(result)

        if passed:
            self.passed += 1
        else:
            self.failed += 1

        # Print immediately
        status_str = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status_str}: {test_name}")
        if message:
            print(f"  → {message}")
        if details:
            for key, val in details.items():
                print(f"  - {key}: {val}")
        print()

    def summary(self):
        """Print summary"""
        total = self.passed + self.failed
        print("=" * 70)
        print(f"TEST SUMMARY: {self.passed}/{total} passed")
        print("=" * 70)

        if self.failed > 0:
            print("\nFailed tests:")
            for test in self.tests:
                if test['status'] == 'FAIL':
                    print(f"  - {test['test']}: {test['message']}")

        return {
            'total': total,
            'passed': self.passed,
            'failed': self.failed,
            'results': self.tests
        }


# ============================================================================
# TEST 1: _build_query with String Gaps (Stage 1 format)
# ============================================================================

def test_build_query_string_gaps():
    """Test _build_query with competitor gaps as strings"""
    print("\n" + "=" * 70)
    print("TEST 1: _build_query with String Gaps (Stage 1 format)")
    print("=" * 70)

    results = TestResults()
    researcher = DeepResearcher()

    # Stage 1: Competitor gaps are strings
    competitor_gaps = [
        "GDPR compliance",
        "SMB-focused pricing",
        "API documentation"
    ]

    config = {
        'domain': 'SaaS',
        'market': 'Germany',
        'language': 'de',
        'vertical': 'Proptech'
    }

    try:
        query = researcher._build_query(
            topic="Property Management Trends",
            config=config,
            competitor_gaps=competitor_gaps,
            keywords=None
        )

        # Verify all components are in query
        checks = {
            'contains_topic': 'Property Management Trends' in query,
            'contains_domain': 'SaaS' in query,
            'contains_market': 'Germany' in query,
            'contains_language': 'de' in query,
            'contains_vertical': 'Proptech' in query,
            'contains_gap_1': 'GDPR compliance' in query,
            'contains_gap_2': 'SMB-focused pricing' in query,
            'contains_gap_3': 'API documentation' in query,
        }

        all_passed = all(checks.values())
        results.add_result(
            "String gaps included in query",
            all_passed,
            f"Query: {query[:100]}..." if all_passed else f"Missing components: {[k for k, v in checks.items() if not v]}",
            {'full_query': query}
        )

        # Verify query format
        is_string = isinstance(query, str)
        is_not_empty = len(query) > 0
        results.add_result(
            "String gaps produce valid query format",
            is_string and is_not_empty,
            f"Type: {type(query).__name__}, Length: {len(query)}",
            {'query_length': len(query)}
        )

    except Exception as e:
        results.add_result(
            "String gaps handler",
            False,
            str(e),
            {'error_type': type(e).__name__}
        )

    return results


# ============================================================================
# TEST 2: _build_query with Dict Keywords (Stage 2 format)
# ============================================================================

def test_build_query_dict_keywords():
    """Test _build_query with keywords as dicts from KeywordResearchAgent"""
    print("\n" + "=" * 70)
    print("TEST 2: _build_query with Dict Keywords (Stage 2 format)")
    print("=" * 70)

    results = TestResults()
    researcher = DeepResearcher()

    # Stage 2: Keywords are dicts with 'keyword' key
    keywords = [
        {'keyword': 'ai-powered-management', 'search_volume': 1200},
        {'keyword': 'blockchain-property', 'search_volume': 800},
        {'keyword': 'smart-home-integration', 'search_volume': 1500}
    ]

    config = {
        'domain': 'SaaS',
        'market': 'Germany',
        'language': 'de',
        'vertical': 'Proptech'
    }

    try:
        query = researcher._build_query(
            topic="Property Management Trends",
            config=config,
            competitor_gaps=None,
            keywords=keywords
        )

        # Verify dict keywords are extracted correctly
        checks = {
            'contains_keyword_1': 'ai-powered-management' in query,
            'contains_keyword_2': 'blockchain-property' in query,
            'contains_keyword_3': 'smart-home-integration' in query,
        }

        all_passed = all(checks.values())
        results.add_result(
            "Dict keywords extracted correctly",
            all_passed,
            f"Query: {query[:100]}..." if all_passed else f"Missing keywords: {[k for k, v in checks.items() if not v]}",
            {'full_query': query}
        )

        # Verify query format
        is_string = isinstance(query, str)
        results.add_result(
            "Dict keywords produce valid query format",
            is_string,
            f"Type: {type(query).__name__}",
            {'query_type': type(query).__name__}
        )

    except Exception as e:
        results.add_result(
            "Dict keywords handler",
            False,
            str(e),
            {'error_type': type(e).__name__}
        )

    return results


# ============================================================================
# TEST 3: _build_query with Mixed Formats
# ============================================================================

def test_build_query_mixed_formats():
    """Test _build_query with both string gaps and dict keywords"""
    print("\n" + "=" * 70)
    print("TEST 3: _build_query with Mixed Formats (Strings + Dicts)")
    print("=" * 70)

    results = TestResults()
    researcher = DeepResearcher()

    # Stage 1: String gaps
    competitor_gaps = ["GDPR compliance", "SMB pricing"]

    # Stage 2: Dict keywords
    keywords = [
        {'keyword': 'automation', 'search_volume': 2000},
        {'keyword': 'compliance', 'search_volume': 1500}
    ]

    config = {
        'domain': 'Enterprise',
        'market': 'Europe',
        'language': 'en',
        'vertical': 'Legal Tech'
    }

    try:
        query = researcher._build_query(
            topic="Legal Tech Compliance",
            config=config,
            competitor_gaps=competitor_gaps,
            keywords=keywords
        )

        # Verify all formats are handled
        checks = {
            'contains_topic': 'Legal Tech Compliance' in query,
            'contains_string_gap': 'GDPR compliance' in query,
            'contains_dict_keyword': 'automation' in query,
        }

        all_passed = all(checks.values())
        results.add_result(
            "Mixed formats handled correctly",
            all_passed,
            f"Query: {query[:100]}..." if all_passed else "Some components missing",
            {'full_query': query, 'total_length': len(query)}
        )

    except Exception as e:
        results.add_result(
            "Mixed formats handler",
            False,
            str(e),
            {'error_type': type(e).__name__}
        )

    return results


# ============================================================================
# TEST 4: _build_query with Empty/None Values
# ============================================================================

def test_build_query_empty_values():
    """Test _build_query handles empty and None values gracefully"""
    print("\n" + "=" * 70)
    print("TEST 4: _build_query with Empty/None Values")
    print("=" * 70)

    results = TestResults()
    researcher = DeepResearcher()

    config = {'domain': 'SaaS'}

    try:
        # Test with all None
        query1 = researcher._build_query(
            topic="Test Topic",
            config=config,
            competitor_gaps=None,
            keywords=None
        )

        results.add_result(
            "Handles None gaps and keywords",
            isinstance(query1, str) and len(query1) > 0,
            f"Query: {query1}",
            {}
        )

        # Test with empty lists
        query2 = researcher._build_query(
            topic="Test Topic",
            config=config,
            competitor_gaps=[],
            keywords=[]
        )

        results.add_result(
            "Handles empty lists",
            isinstance(query2, str) and len(query2) > 0,
            f"Query: {query2}",
            {}
        )

        # Test with partial config
        query3 = researcher._build_query(
            topic="Test Topic",
            config={},
            competitor_gaps=None,
            keywords=None
        )

        results.add_result(
            "Handles empty config",
            isinstance(query3, str) and query3 == "Test Topic",
            f"Query: {query3}",
            {}
        )

    except Exception as e:
        results.add_result(
            "Empty values handler",
            False,
            str(e),
            {'error_type': type(e).__name__}
        )

    return results


# ============================================================================
# TEST 5: _build_query Limits to First 3 Items
# ============================================================================

def test_build_query_limits_items():
    """Test _build_query limits to first 3 gaps and keywords"""
    print("\n" + "=" * 70)
    print("TEST 5: _build_query Limits to First 3 Items")
    print("=" * 70)

    results = TestResults()
    researcher = DeepResearcher()

    # More than 3 gaps
    competitor_gaps = [
        "Gap 1",
        "Gap 2",
        "Gap 3",
        "Gap 4 (should be ignored)",
        "Gap 5 (should be ignored)"
    ]

    # More than 3 keywords
    keywords = [
        {'keyword': 'kw1'},
        {'keyword': 'kw2'},
        {'keyword': 'kw3'},
        {'keyword': 'kw4 (should be ignored)'},
        {'keyword': 'kw5 (should be ignored)'}
    ]

    config = {}

    try:
        query = researcher._build_query(
            topic="Test",
            config=config,
            competitor_gaps=competitor_gaps,
            keywords=keywords
        )

        # Verify only first 3 are included
        checks = {
            'has_gap_1': 'Gap 1' in query,
            'has_gap_2': 'Gap 2' in query,
            'has_gap_3': 'Gap 3' in query,
            'missing_gap_4': 'Gap 4' not in query,
            'missing_gap_5': 'Gap 5' not in query,
            'has_kw1': 'kw1' in query,
            'has_kw2': 'kw2' in query,
            'has_kw3': 'kw3' in query,
            'missing_kw4': 'kw4' not in query,
            'missing_kw5': 'kw5' not in query,
        }

        all_passed = all(checks.values())
        results.add_result(
            "Limits to first 3 items",
            all_passed,
            f"Query: {query}" if all_passed else f"Failed checks: {[k for k, v in checks.items() if not v]}",
            {'full_query': query}
        )

    except Exception as e:
        results.add_result(
            "Limit items handler",
            False,
            str(e),
            {'error_type': type(e).__name__}
        )

    return results


# ============================================================================
# TEST 6: research_topic Method Validation
# ============================================================================

async def test_research_topic_validation():
    """Test research_topic method validates inputs"""
    print("\n" + "=" * 70)
    print("TEST 6: research_topic Validation")
    print("=" * 70)

    results = TestResults()
    researcher = DeepResearcher()

    # Test empty topic
    try:
        await researcher.research_topic("", {})
        results.add_result(
            "Rejects empty topic",
            False,
            "Should have raised DeepResearchError",
            {}
        )
    except DeepResearchError as e:
        results.add_result(
            "Rejects empty topic",
            True,
            "Correctly raised DeepResearchError",
            {'error': str(e)}
        )
    except Exception as e:
        results.add_result(
            "Rejects empty topic",
            False,
            f"Unexpected error: {str(e)}",
            {'error_type': type(e).__name__}
        )

    # Test whitespace-only topic
    try:
        await researcher.research_topic("   ", {})
        results.add_result(
            "Rejects whitespace-only topic",
            False,
            "Should have raised DeepResearchError",
            {}
        )
    except DeepResearchError as e:
        results.add_result(
            "Rejects whitespace-only topic",
            True,
            "Correctly raised DeepResearchError",
            {'error': str(e)}
        )
    except Exception as e:
        results.add_result(
            "Rejects whitespace-only topic",
            False,
            f"Unexpected error: {str(e)}",
            {'error_type': type(e).__name__}
            )

    return results


# ============================================================================
# TEST 7: research_topic with Mock gpt-researcher
# ============================================================================

async def test_research_topic_mock():
    """Test research_topic method with mocked gpt-researcher"""
    print("\n" + "=" * 70)
    print("TEST 7: research_topic with Mock gpt-researcher")
    print("=" * 70)

    from unittest.mock import AsyncMock, patch

    results = TestResults()

    # Mock gpt-researcher
    with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt_class:
        mock_instance = AsyncMock()
        mock_gpt_class.return_value = mock_instance

        # Mock the research methods
        mock_instance.conduct_research = AsyncMock()
        mock_instance.write_report = AsyncMock(return_value="# Test Report\n\nThis is a test report.")
        mock_instance.get_source_urls = AsyncMock(return_value=[
            'https://example.com/1',
            'https://example.com/2'
        ])

        researcher = DeepResearcher()

        try:
            result = await researcher.research_topic(
                topic="Test Topic",
                config={'domain': 'SaaS', 'market': 'US'},
                competitor_gaps=['gap1', 'gap2'],
                keywords=[
                    {'keyword': 'kw1'},
                    {'keyword': 'kw2'}
                ]
            )

            # Verify result structure
            checks = {
                'has_topic': 'topic' in result,
                'has_report': 'report' in result,
                'has_sources': 'sources' in result,
                'has_word_count': 'word_count' in result,
                'has_timestamp': 'researched_at' in result,
                'correct_topic': result.get('topic') == 'Test Topic',
                'sources_found': len(result.get('sources', [])) == 2,
            }

            all_passed = all(checks.values())
            results.add_result(
                "research_topic returns correct structure",
                all_passed,
                f"Result keys: {list(result.keys())}" if all_passed else f"Missing: {[k for k, v in checks.items() if not v]}",
                {
                    'topic': result.get('topic'),
                    'word_count': result.get('word_count'),
                    'num_sources': len(result.get('sources', []))
                }
            )

            # Verify statistics updated
            stats = researcher.get_statistics()
            results.add_result(
                "Statistics tracked correctly",
                stats['total_research'] == 1 and stats['failed_research'] == 0,
                f"Total: {stats['total_research']}, Failed: {stats['failed_research']}",
                stats
            )

        except Exception as e:
            results.add_result(
                "research_topic with mock",
                False,
                str(e),
                {'error_type': type(e).__name__}
            )

    return results


# ============================================================================
# TEST 8: Check gpt-researcher Installation
# ============================================================================

def test_gpt_researcher_installation():
    """Check if gpt-researcher is installed"""
    print("\n" + "=" * 70)
    print("TEST 8: gpt-researcher Installation Check")
    print("=" * 70)

    results = TestResults()

    try:
        import gpt_researcher
        results.add_result(
            "gpt-researcher installed",
            True,
            f"Version: {gpt_researcher.__version__ if hasattr(gpt_researcher, '__version__') else 'unknown'}",
            {'module': str(gpt_researcher)}
        )
    except ImportError as e:
        results.add_result(
            "gpt-researcher installed",
            False,
            f"Not installed: {str(e)}",
            {'error': str(e)}
        )

    # Check for google_genai provider
    try:
        from gpt_researcher.llm.google_genai import GoogleGenAILLM
        results.add_result(
            "Gemini 2.0 Flash provider available",
            True,
            "GoogleGenAILLM found",
            {}
        )
    except ImportError:
        results.add_result(
            "Gemini 2.0 Flash provider available",
            False,
            "GoogleGenAILLM not found",
            {}
        )

    return results


# ============================================================================
# TEST 9: Real gpt-researcher Call (if installed and API key available)
# ============================================================================

async def test_real_research():
    """Test with real gpt-researcher call (requires API key)"""
    print("\n" + "=" * 70)
    print("TEST 9: Real gpt-researcher Call (with Gemini 2.0 Flash)")
    print("=" * 70)

    results = TestResults()

    import os

    # Check for API key
    has_api_key = bool(os.getenv('GOOGLE_API_KEY'))

    if not has_api_key:
        results.add_result(
            "API key available",
            False,
            "GOOGLE_API_KEY not set. Skipping real API test.",
            {'note': 'Set GOOGLE_API_KEY to test real gpt-researcher'}
        )
        return results

    try:
        researcher = DeepResearcher(
            llm_provider="google_genai",
            llm_model="gemini-2.0-flash-exp"
        )

        config = {
            'domain': 'SaaS',
            'market': 'Global',
            'language': 'en',
            'vertical': 'AI'
        }

        # Simple, quick topic
        result = await researcher.research_topic(
            topic="Artificial Intelligence Trends 2025",
            config=config,
            competitor_gaps=['Model Efficiency'],
            keywords=[{'keyword': 'AI safety'}, {'keyword': 'multimodal'}]
        )

        # Verify result
        checks = {
            'has_report': bool(result.get('report')),
            'has_sources': len(result.get('sources', [])) > 0,
            'word_count_reasonable': result.get('word_count', 0) > 100,
            'has_timestamp': bool(result.get('researched_at')),
        }

        all_passed = all(checks.values())
        results.add_result(
            "Real gpt-researcher call successful",
            all_passed,
            f"Generated {result.get('word_count')} word report with {len(result.get('sources', []))} sources",
            {
                'word_count': result.get('word_count'),
                'num_sources': len(result.get('sources', [])),
                'report_preview': result.get('report', '')[:200] + '...' if result.get('report') else 'N/A'
            }
        )

        # Quality assessment
        has_good_quality = (
            result.get('word_count', 0) >= 500 and
            len(result.get('sources', [])) >= 3
        )
        results.add_result(
            "Report quality assessment",
            has_good_quality,
            f"Acceptable report: {result.get('word_count')} words, {len(result.get('sources', []))} sources",
            {
                'word_count': result.get('word_count'),
                'num_sources': len(result.get('sources', [])),
                'quality': 'Good' if has_good_quality else 'Poor'
            }
        )

    except Exception as e:
        results.add_result(
            "Real gpt-researcher call successful",
            False,
            str(e),
            {'error_type': type(e).__name__, 'details': str(e)[:200]}
        )

    return results


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

async def main():
    """Run all tests"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "DEEPRESEARCHER INTEGRATION TEST SUITE".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")

    all_results = []

    # Run tests (sync tests first, then async)
    all_results.append(("Test 1: String Gaps", test_build_query_string_gaps()))
    all_results.append(("Test 2: Dict Keywords", test_build_query_dict_keywords()))
    all_results.append(("Test 3: Mixed Formats", test_build_query_mixed_formats()))
    all_results.append(("Test 4: Empty Values", test_build_query_empty_values()))
    all_results.append(("Test 5: Item Limits", test_build_query_limits_items()))
    all_results.append(("Test 6: Validation", await test_research_topic_validation()))
    all_results.append(("Test 7: Mock research_topic", await test_research_topic_mock()))
    all_results.append(("Test 8: Installation", test_gpt_researcher_installation()))
    all_results.append(("Test 9: Real Call", await test_real_research()))

    # Aggregate results
    total_passed = sum(r[1].passed for r in all_results)
    total_failed = sum(r[1].failed for r in all_results)
    total_tests = total_passed + total_failed

    # Final summary
    print("\n\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + "FINAL TEST SUMMARY".center(68) + "║")
    print("║" + "═" * 68 + "║")
    print(f"║  Total Tests: {total_tests:>58}║")
    print(f"║  Passed:      {total_passed:>58}║")
    print(f"║  Failed:      {total_failed:>58}║")
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    print(f"║  Success Rate: {success_rate:.1f}%{' ' * 50}║")
    print("╚" + "═" * 68 + "╝")

    # Generate JSON report
    report = {
        'summary': {
            'total_tests': total_tests,
            'passed': total_passed,
            'failed': total_failed,
            'success_rate': success_rate
        },
        'test_groups': [
            {
                'group': name,
                'results': test_results.summary()
            }
            for name, test_results in all_results
        ]
    }

    # Save report
    report_path = Path(__file__).parent / "test_deep_researcher_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nDetailed report saved to: {report_path}")

    return total_failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

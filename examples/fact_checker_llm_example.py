"""
Example: LLM-Powered FactCheckerAgent with Web Research

Demonstrates the new FactCheckerAgent capabilities:
1. LLM extracts factual claims from blog posts
2. HTTP validation checks if URLs exist
3. Web research (Gemini CLI) verifies claims
4. Comprehensive fact-check reports
5. Thoroughness levels (basic, medium, thorough)

Usage:
    python examples/fact_checker_llm_example.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.fact_checker_agent import FactCheckerAgent


# Sample blog post with hallucinations
BLOG_POST_WITH_HALLUCINATIONS = """# KI-gestützte Predictive Maintenance in der Immobilienwirtschaft

## Einleitung

Künstliche Intelligenz revolutioniert die Gebäudeverwaltung. Laut einer aktuellen
[Studie von Siemens 2023](https://www.siemens.com/studie-predictive-maintenance-2023)
können Gebäudebetreiber durch KI-gestützte Wartung ihre Wartungskosten um bis zu 30% senken.

Das [Bundesministerium für Wirtschaft und Klimaschutz](https://www.bmwk.de/gebaeudeenergiegesetz-2023)
hat neue Richtlinien für energieeffiziente Gebäude veröffentlicht, die ab 2024 in Kraft treten.

## Hauptteil

Eine echte Quelle: Laut [McKinsey Research](https://www.mckinsey.com/industries/manufacturing)
kann KI die Effizienz in der Industrie um 25% steigern.

## Quellen

1. https://www.siemens.com/studie-predictive-maintenance-2023 (FAKE URL)
2. https://www.bmwk.de/gebaeudeenergiegesetz-2023 (FAKE URL)
3. https://www.mckinsey.com/industries/manufacturing (REAL URL)
"""


# Sample blog post with all real URLs
BLOG_POST_ALL_REAL = """# Manufacturing Industry Trends

## AI in Manufacturing

According to [McKinsey research](https://www.mckinsey.com/industries/manufacturing),
artificial intelligence is transforming the manufacturing sector. Companies implementing
AI-powered systems report efficiency gains of 20-30%.

## Sources

1. https://www.mckinsey.com/industries/manufacturing
"""


def example_basic_fact_check():
    """Example 1: Basic fact-checking (URLs only)"""
    print("=" * 80)
    print("Example 1: Basic Fact-Checking (URLs Only)")
    print("=" * 80)

    # Initialize agent
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        return

    agent = FactCheckerAgent(api_key=api_key)

    # Run basic fact-check (URLs only, no claim verification)
    result = agent.verify_content(
        content=BLOG_POST_WITH_HALLUCINATIONS,
        thoroughness="basic"
    )

    # Print results
    print(f"\nValid: {result['valid']}")
    print(f"URLs Checked: {result['urls_checked']}")
    print(f"Real URLs: {result['urls_real']}")
    print(f"Fake URLs: {len(result['urls_fake'])}")
    print(f"Cost: ${result['cost']:.4f}")

    print("\n" + result['report'])


def example_medium_fact_check():
    """Example 2: Medium thoroughness (URLs + top 5 claims)"""
    print("\n\n")
    print("=" * 80)
    print("Example 2: Medium Thoroughness (URLs + Top 5 Claims)")
    print("=" * 80)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        return

    agent = FactCheckerAgent(api_key=api_key)

    # Run medium fact-check (URLs + top 5 claims)
    result = agent.verify_content(
        content=BLOG_POST_WITH_HALLUCINATIONS,
        thoroughness="medium"
    )

    # Print results
    print(f"\nValid: {result['valid']}")
    print(f"Claims Checked: {result['claims_checked']}")
    print(f"Claims Verified: {result['claims_verified']}")
    print(f"Claims Failed: {len(result['claims_failed'])}")
    print(f"Hallucinations: {len(result['hallucinations'])}")
    print(f"Cost: ${result['cost']:.4f}")

    print("\n" + result['report'])

    # Show hallucinations details
    if result['hallucinations']:
        print("\nHallucination Details:")
        for i, h in enumerate(result['hallucinations'], 1):
            print(f"\n{i}. Type: {h['type']}")
            if h['type'] == 'fake_url':
                print(f"   URL: {h['url']}")
                print(f"   Evidence: {h['evidence']}")
            elif h['type'] == 'false_claim':
                print(f"   Claim: {h['claim']}")
                print(f"   Evidence: {h['evidence']}")
                print(f"   Confidence: {h['confidence']:.2f}")


def example_thorough_fact_check():
    """Example 3: Thorough fact-checking (all claims verified)"""
    print("\n\n")
    print("=" * 80)
    print("Example 3: Thorough Fact-Checking (All Claims)")
    print("=" * 80)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        return

    agent = FactCheckerAgent(api_key=api_key)

    # Run thorough fact-check (all claims)
    # NOTE: This is expensive - verify ALL claims via web research
    result = agent.verify_content(
        content=BLOG_POST_ALL_REAL,  # Use simpler post for demo
        thoroughness="thorough"
    )

    # Print results
    print(f"\nValid: {result['valid']}")
    print(f"Claims Checked: {result['claims_checked']}")
    print(f"Claims Verified: {result['claims_verified']}")
    print(f"Hallucinations: {len(result['hallucinations'])}")
    print(f"Cost: ${result['cost']:.4f}")

    print("\n" + result['report'])


def example_cost_comparison():
    """Example 4: Compare costs across thoroughness levels"""
    print("\n\n")
    print("=" * 80)
    print("Example 4: Cost Comparison Across Thoroughness Levels")
    print("=" * 80)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        return

    agent = FactCheckerAgent(api_key=api_key)

    # Test all three levels
    levels = ["basic", "medium", "thorough"]
    costs = {}

    for level in levels:
        print(f"\nTesting {level.upper()} mode...")
        result = agent.verify_content(
            content=BLOG_POST_WITH_HALLUCINATIONS,
            thoroughness=level
        )
        costs[level] = result['cost']
        print(f"  Claims checked: {result['claims_checked']}")
        print(f"  Cost: ${result['cost']:.4f}")

    # Summary
    print("\n" + "=" * 60)
    print("Cost Summary:")
    print("=" * 60)
    for level in levels:
        print(f"{level.capitalize():12} : ${costs[level]:.4f}")

    print("\nRecommendation:")
    print("- Basic (URLs only): Fast, free (HTTP requests only)")
    print("- Medium (top 5): Balanced, ~$0.05-0.08/post")
    print("- Thorough (all): Comprehensive, ~$0.10-0.15/post")


def main():
    """Run all examples"""
    print("LLM-Powered FactCheckerAgent Examples\n")

    # Check API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY environment variable not set")
        print("\nPlease set it:")
        print("  export OPENROUTER_API_KEY='your-key-here'")
        return

    # Run examples
    try:
        # Example 1: Basic (URLs only)
        example_basic_fact_check()

        # Example 2: Medium (URLs + top 5 claims)
        # NOTE: Commented out by default to avoid API costs
        # Uncomment to test claim verification via web research
        # example_medium_fact_check()

        # Example 3: Thorough (all claims)
        # NOTE: Commented out by default (most expensive)
        # example_thorough_fact_check()

        # Example 4: Cost comparison
        # NOTE: Commented out by default to avoid API costs
        # example_cost_comparison()

        print("\n\n" + "=" * 80)
        print("Examples completed successfully!")
        print("=" * 80)

        print("\nTo enable more examples (with API costs):")
        print("1. Uncomment example_medium_fact_check() for claim verification demo")
        print("2. Uncomment example_thorough_fact_check() for full verification")
        print("3. Uncomment example_cost_comparison() for cost analysis")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

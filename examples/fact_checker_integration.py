"""
FactCheckerAgent Integration Example

Demonstrates how to integrate FactCheckerAgent into the content generation pipeline.

Usage:
    python examples/fact_checker_integration.py
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.research_agent import ResearchAgent
from src.agents.writing_agent import WritingAgent
from src.agents.fact_checker_agent import FactCheckerAgent


def example_basic_validation():
    """Example 1: Basic fact-checking workflow"""
    print("=" * 80)
    print("Example 1: Basic Fact-Checking Workflow")
    print("=" * 80)

    # Initialize agents
    api_key = os.getenv("OPENROUTER_API_KEY", "test-key")

    # Simulate research data
    research_data = {
        'sources': [
            {
                'url': 'https://www.mckinsey.com/industries/manufacturing',
                'title': 'Manufacturing Industry Report',
                'snippet': 'AI is transforming manufacturing...'
            },
            {
                'url': 'https://www.fraunhofer.de/research',
                'title': 'Fraunhofer Research',
                'snippet': 'Research on Industry 4.0...'
            }
        ],
        'keywords': ['KI', 'Predictive Maintenance', 'Industrie 4.0'],
        'summary': 'Research on AI-powered predictive maintenance in manufacturing.'
    }

    # Simulate generated content with mix of real and fake URLs
    content = """# KI-gestützte Predictive Maintenance

## Einleitung

Künstliche Intelligenz revolutioniert die industrielle Wartung. Laut einer
[McKinsey Studie](https://www.mckinsey.com/industries/manufacturing) können
Unternehmen ihre Wartungskosten um bis zu 30% senken.

Die [Fraunhofer Gesellschaft](https://www.fraunhofer.de/research) hat mehrere
Forschungsprojekte zu diesem Thema durchgeführt.

## Hauptteil

Eine [aktuelle Analyse von Siemens](https://www.siemens.com/fake-study-2024)
zeigt die Vorteile von KI-gestützter Wartung.

Das [BMWK](https://www.bmwk.de/fake-report) fördert entsprechende Projekte.

## Quellen

1. https://www.mckinsey.com/industries/manufacturing (REAL)
2. https://www.fraunhofer.de/research (REAL)
3. https://www.siemens.com/fake-study-2024 (FAKE)
4. https://www.bmwk.de/fake-report (FAKE)
"""

    # Initialize FactCheckerAgent
    fact_checker = FactCheckerAgent(api_key=api_key)

    # Verify content (strict mode)
    print("\nRunning fact-check (strict mode)...")
    result = fact_checker.verify_content(
        content=content,
        research_data=research_data,
        strict_mode=True
    )

    # Display results
    print(f"\nValidation Result: {'✅ PASSED' if result['valid'] else '❌ FAILED'}")
    print(f"URLs Checked: {result['urls_checked']}")
    print(f"Valid URLs: {result['urls_valid']}")
    print(f"Invalid URLs: {len(result['urls_invalid'])}")

    if result['urls_invalid']:
        print("\nHallucinated URLs:")
        for url in result['urls_invalid']:
            print(f"  - {url}")

    # Display full report
    print("\n" + result['report'])

    # Show corrected content preview
    if not result['valid']:
        print("\n" + "=" * 80)
        print("Corrected Content (first 500 chars):")
        print("=" * 80)
        print(result['corrected_content'][:500] + "...")


def example_non_strict_mode():
    """Example 2: Non-strict mode (warns but allows)"""
    print("\n\n" + "=" * 80)
    print("Example 2: Non-Strict Mode (Warnings Only)")
    print("=" * 80)

    api_key = os.getenv("OPENROUTER_API_KEY", "test-key")

    research_data = {
        'sources': [
            {'url': 'https://example.com/real', 'title': 'Real', 'snippet': 'Real content'}
        ],
        'keywords': [],
        'summary': 'Test research'
    }

    content = """# Test Article

Valid source: [Real Article](https://example.com/real)

Fake source: [Fake Article](https://fake.com/article)
"""

    fact_checker = FactCheckerAgent(api_key=api_key)

    # Verify in non-strict mode
    print("\nRunning fact-check (non-strict mode)...")
    result = fact_checker.verify_content(
        content=content,
        research_data=research_data,
        strict_mode=False
    )

    print(f"\nValidation Result: {'✅ PASSED' if result['valid'] else '❌ FAILED'}")
    print(f"Errors: {len(result['errors'])}")
    print(f"Warnings: {len(result['warnings'])}")

    if result['warnings']:
        print("\nWarnings:")
        for warning in result['warnings']:
            print(f"  - {warning}")

    print("\nNote: Non-strict mode allows publication with warnings.")


def example_pipeline_integration():
    """Example 3: Full pipeline integration"""
    print("\n\n" + "=" * 80)
    print("Example 3: Full Pipeline Integration")
    print("=" * 80)

    api_key = os.getenv("OPENROUTER_API_KEY", "test-key")

    # This is how you would integrate into the actual pipeline
    print("\nPipeline Steps:")
    print("1. Research → ResearchAgent")
    print("2. Writing → WritingAgent")
    print("3. Fact-Check → FactCheckerAgent ← NEW STEP")
    print("4. Cache → CacheManager")
    print("5. Publish → PublishingAgent")

    print("\nPseudo-code for integration:")
    print("""
# In src/ui/pages/generate.py

from src.agents.fact_checker_agent import FactCheckerAgent

# Step 1: Research
research_result = research_agent.research(topic, language='de')

# Step 2: Writing
writing_result = writing_agent.write_blog(
    topic=topic,
    research_data=research_result,
    brand_voice=brand_voice
)

# Step 3: Fact-Check (NEW)
fact_checker = FactCheckerAgent(api_key=api_key)
validation = fact_checker.verify_content(
    content=writing_result['content'],
    research_data=research_result,
    strict_mode=True  # Configurable in settings
)

if not validation['valid']:
    # Show errors to user
    st.error(f"Fact-check failed: {len(validation['errors'])} issues found")

    # Display report
    st.text(validation['report'])

    # Option to use corrected content
    if st.button("Use Corrected Content"):
        writing_result['content'] = validation['corrected_content']
    else:
        st.stop()  # Don't proceed to caching

# Step 4: Cache (only if validation passed)
cache_result = cache_manager.save_blog_post(...)

# Step 5: Publish
publishing_result = publishing_agent.publish(...)
""")


def example_realistic_scenario():
    """Example 4: Realistic scenario with actual hallucination patterns"""
    print("\n\n" + "=" * 80)
    print("Example 4: Realistic Hallucination Detection")
    print("=" * 80)

    api_key = os.getenv("OPENROUTER_API_KEY", "test-key")

    # Realistic research data
    research_data = {
        'sources': [
            {
                'url': 'https://www.mckinsey.com/capabilities/operations/our-insights/predictive-maintenance',
                'title': 'Predictive Maintenance and the Smart Factory',
                'snippet': 'How predictive maintenance powered by AI and IoT...'
            },
            {
                'url': 'https://www.bmwk.de/Redaktion/DE/Artikel/Digitale-Welt/kuenstliche-intelligenz.html',
                'title': 'Künstliche Intelligenz in der Wirtschaft',
                'snippet': 'Das Bundesministerium für Wirtschaft...'
            }
        ],
        'keywords': ['Predictive Maintenance', 'KI', 'Industrie 4.0'],
        'summary': 'Predictive Maintenance reduces costs through AI-powered forecasting.'
    }

    # Content with common hallucination patterns
    content = """# Predictive Maintenance: Die Zukunft der Industrie

## Einleitung

Laut [McKinsey](https://www.mckinsey.com/capabilities/operations/our-insights/predictive-maintenance)
können Unternehmen bis zu 30% ihrer Wartungskosten sparen.

## Technologie

Die [Siemens Studie 2024](https://www.siemens.com/de/de/unternehmen/themenfelder/kuenstliche-intelligenz/predictive-maintenance-studie.html)
zeigt, dass 85% der Unternehmen bereits KI einsetzen. [FAKE URL - Siemens hat diese Studie nie veröffentlicht]

## Förderung

Das [BMWK fördert KI-Projekte](https://www.bmwk.de/Redaktion/DE/Artikel/Digitale-Welt/kuenstliche-intelligenz.html)
in der deutschen Industrie.

Eine [Umfrage des VDI](https://www.vdi.de/technik/fachthemen/industrie-4-0/predictive-maintenance-2024)
bestätigt den Trend. [FAKE URL - VDI hat diese Umfrage nicht veröffentlicht]

## Quellen

1. https://www.mckinsey.com/capabilities/operations/our-insights/predictive-maintenance
2. https://www.siemens.com/de/de/unternehmen/themenfelder/kuenstliche-intelligenz/predictive-maintenance-studie.html (FAKE)
3. https://www.bmwk.de/Redaktion/DE/Artikel/Digitale-Welt/kuenstliche-intelligenz.html
4. https://www.vdi.de/technik/fachthemen/industrie-4-0/predictive-maintenance-2024 (FAKE)
"""

    fact_checker = FactCheckerAgent(api_key=api_key)

    print("\nChecking content with common hallucination patterns...")
    result = fact_checker.verify_content(
        content=content,
        research_data=research_data,
        strict_mode=True
    )

    print(f"\nValidation Result: {'✅ PASSED' if result['valid'] else '❌ FAILED'}")
    print(f"URLs Checked: {result['urls_checked']}")
    print(f"Hallucinations Detected: {len(result['urls_invalid'])}")

    print("\n" + result['report'])

    print("\nCommon Hallucination Patterns Detected:")
    print("1. Plausible-looking URLs that don't exist")
    print("2. Real domains with fake paths/studies")
    print("3. Current year references (2024) to create false authority")
    print("4. Mix of real and fake sources to appear credible")


if __name__ == "__main__":
    # Run all examples
    example_basic_validation()
    example_non_strict_mode()
    example_pipeline_integration()
    example_realistic_scenario()

    print("\n\n" + "=" * 80)
    print("Integration Complete!")
    print("=" * 80)
    print("\nNext Steps:")
    print("1. Add FactCheckerAgent to src/ui/pages/generate.py")
    print("2. Add fact-checking settings to src/ui/pages/settings.py")
    print("3. Update content generation workflow")
    print("4. Test with real WritingAgent output")
    print("=" * 80)

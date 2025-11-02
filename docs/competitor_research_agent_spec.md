# CompetitorResearchAgent Specification

## Purpose
Analyze competitors in the user's niche to identify content gaps, strategies, and opportunities.

## Inputs
- **topic**: str - The niche or topic (e.g., "KI Content Marketing", "Cloud Computing")
- **language**: str - Content language (default: "de")
- **max_competitors**: int - Maximum competitors to analyze (default: 5)
- **include_content_analysis**: bool - Analyze their content strategy (default: True)

## Outputs
Returns `Dict[str, Any]` with:

```python
{
    "competitors": [
        {
            "name": str,                    # Company/brand name
            "website": str,                 # Main website URL
            "description": str,             # Brief description
            "social_handles": {             # Social media presence
                "linkedin": str,
                "twitter": str,
                "facebook": str,
                "instagram": str
            },
            "content_strategy": {           # Content insights
                "topics": List[str],        # Main topics they cover
                "posting_frequency": str,   # e.g., "2-3 posts/week"
                "content_types": List[str], # e.g., ["blog", "video", "infographic"]
                "strengths": List[str],     # What they do well
                "weaknesses": List[str]     # Content gaps/weaknesses
            }
        }
    ],
    "content_gaps": List[str],              # Opportunities not covered by competitors
    "trending_topics": List[str],           # Popular topics in the niche
    "recommendation": str                   # Strategic recommendation
}
```

## Implementation Details

### Data Sources
1. **Gemini CLI** (primary, FREE)
   - Web search for competitors in niche
   - Social media presence lookup
   - Content analysis via web scraping hints

2. **Gemini API** (fallback, also FREE via OpenRouter)
   - Same capabilities as CLI

### Caching Strategy
- Cache competitor data in `cache/research/competitors_{slug}.json`
- TTL: 7 days (competitors don't change frequently)
- Update on explicit request

### Error Handling
- If no competitors found: Return empty list with recommendation
- If social handles unavailable: Set to empty strings
- If content analysis fails: Return basic competitor info only

### Integration Points
- Called before `ResearchAgent` in generation pipeline
- Results passed to `WritingAgent` for differentiation strategy
- Stored in Notion "Competitors" database

## Usage Example

```python
agent = CompetitorResearchAgent(api_key="sk-xxx")

result = agent.research_competitors(
    topic="Cloud Computing für KMU",
    language="de",
    max_competitors=5
)

print(result['competitors'])  # List of 5 competitors
print(result['content_gaps'])  # Opportunities
```

## Test Coverage Requirements
- 80%+ coverage
- Test CLI success and API fallback
- Test empty results handling
- Test malformed JSON responses
- Test caching behavior
- Test competitor data normalization

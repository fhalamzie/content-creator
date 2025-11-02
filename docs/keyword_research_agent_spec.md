# KeywordResearchAgent Specification

## Purpose
Perform SEO keyword research to identify high-value keywords for content optimization.

## Inputs
- **topic**: str - Content topic (e.g., "KI Content Marketing")
- **language**: str - Content language (default: "de")
- **target_audience**: str - Audience description (for keyword intent)
- **keyword_count**: int - Number of keywords to return (default: 10)

## Outputs
Returns `Dict[str, Any]` with:

```python
{
    "primary_keyword": {
        "keyword": str,                     # Main keyword phrase
        "search_volume": str,               # e.g., "1K-10K", "10K-100K"
        "competition": str,                 # "Low", "Medium", "High"
        "difficulty": int,                  # 0-100 scale
        "intent": str                       # "Informational", "Commercial", "Navigational"
    },
    "secondary_keywords": [
        {
            "keyword": str,
            "search_volume": str,
            "competition": str,
            "difficulty": int,
            "relevance": float              # 0.0-1.0 (relevance to primary)
        }
    ],
    "long_tail_keywords": [
        {
            "keyword": str,                 # Longer, specific phrases (3-5 words)
            "search_volume": str,
            "competition": str,
            "difficulty": int
        }
    ],
    "related_questions": List[str],         # "People also ask" style questions
    "search_trends": {
        "trending_up": List[str],           # Growing keywords
        "trending_down": List[str],         # Declining keywords
        "seasonal": bool                    # Is topic seasonal?
    },
    "recommendation": str                   # Strategic keyword recommendation
}
```

## Implementation Details

### Data Sources
1. **Gemini CLI** (primary, FREE)
   - Web search for keyword data
   - Google Trends integration
   - Search volume estimates
   - Related searches analysis

2. **Gemini API** (fallback, also FREE via OpenRouter)
   - Same capabilities as CLI

### Keyword Selection Strategy
1. **Primary Keyword**:
   - Highest relevance to topic
   - Moderate-to-high search volume
   - Achievable difficulty (not too competitive)

2. **Secondary Keywords**:
   - Related to primary (semantic similarity)
   - Mix of volumes (some high, some low)
   - Lower difficulty preferred

3. **Long-Tail Keywords**:
   - Specific phrases (3-5 words)
   - Lower competition
   - Higher conversion potential
   - Include question formats

### Caching Strategy
- Cache keyword data in `cache/research/keywords_{slug}.json`
- TTL: 30 days (keyword data relatively stable)
- Update on explicit request

### Error Handling
- If search volume unavailable: Use relative indicators ("Low", "Medium", "High")
- If difficulty score unavailable: Set to 50 (medium)
- If no keywords found: Return topic as primary keyword

### Integration Points
- Called before `WritingAgent` in generation pipeline
- Results passed to `WritingAgent` for SEO optimization
- Primary keyword used in title and headings
- Secondary keywords distributed throughout content
- Long-tail keywords used in subheadings

## Usage Example

```python
agent = KeywordResearchAgent(api_key="sk-xxx")

result = agent.research_keywords(
    topic="Cloud Computing für KMU",
    language="de",
    target_audience="German small business owners",
    keyword_count=10
)

print(result['primary_keyword'])      # Best keyword to target
print(result['secondary_keywords'])   # Supporting keywords
print(result['long_tail_keywords'])   # Specific phrases
```

## Test Coverage Requirements
- 80%+ coverage
- Test CLI success and API fallback
- Test keyword ranking logic (primary vs secondary)
- Test malformed JSON responses
- Test caching behavior
- Test different languages (de, en)
- Test empty results handling
- Test difficulty score calculation

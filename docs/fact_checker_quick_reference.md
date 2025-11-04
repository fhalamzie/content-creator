# FactCheckerAgent - Quick Reference Guide

## Installation

No installation needed - part of the core agents.

## Basic Usage

```python
from src.agents.fact_checker_agent import FactCheckerAgent

# Initialize
agent = FactCheckerAgent(api_key="your-api-key")

# Verify content
result = agent.verify_content(
    content=blog_post_markdown,
    research_data=research_results,
    strict_mode=True
)

# Check result
if result['valid']:
    print("✅ All URLs valid")
else:
    print(f"❌ Found {len(result['urls_invalid'])} hallucinated URLs")
    print(result['report'])
```

## Return Value

```python
{
    'valid': bool,                # True = all checks pass
    'urls_checked': int,          # Total URLs found
    'urls_valid': int,            # Valid URLs
    'urls_invalid': List[str],    # Hallucinated URLs
    'warnings': List[str],        # Non-critical issues
    'errors': List[str],          # Critical issues
    'report': str,                # Human-readable report
    'corrected_content': str      # Content with fakes removed
}
```

## Modes

### Strict Mode (Recommended)
```python
# Fails validation on ANY hallucinated URL
result = agent.verify_content(..., strict_mode=True)
```

### Non-Strict Mode
```python
# Warns but allows publication
result = agent.verify_content(..., strict_mode=False)
```

## Integration Example

```python
# Step 1: Research
research_result = research_agent.research(topic, language='de')

# Step 2: Writing
writing_result = writing_agent.write_blog(
    topic=topic,
    research_data=research_result
)

# Step 3: Fact-Check (NEW)
fact_checker = FactCheckerAgent(api_key=api_key)
validation = fact_checker.verify_content(
    content=writing_result['content'],
    research_data=research_result,
    strict_mode=True
)

# Step 4: Handle result
if not validation['valid']:
    # Show errors
    print(validation['report'])

    # Use corrected content
    content = validation['corrected_content']
else:
    content = writing_result['content']

# Step 5: Cache and publish
cache_manager.save_blog_post(content, ...)
```

## Common Use Cases

### 1. Validate before caching
```python
if validation['valid']:
    cache_manager.save_blog_post(...)
else:
    print("Fix hallucinations before caching")
```

### 2. Get corrected content
```python
if not validation['valid']:
    # Use corrected content (fakes removed)
    content = validation['corrected_content']
```

### 3. Display report to user
```python
if not validation['valid']:
    st.error("Hallucinations detected!")
    st.text(validation['report'])
```

## Error Handling

```python
from src.agents.fact_checker_agent import FactCheckError

try:
    result = agent.verify_content(content, research_data)
except FactCheckError as e:
    print(f"Validation error: {e}")
```

## Performance

- **Speed**: <1 second per validation
- **Cost**: $0.00 (no API calls)
- **Scalability**: Handles 5000+ word blog posts

## Testing

```bash
# Run tests
pytest tests/test_agents/test_fact_checker_agent.py -v

# Check coverage
pytest tests/test_agents/test_fact_checker_agent.py \
    --cov=src.agents.fact_checker_agent
```

## Configuration (models.yaml)

```yaml
agents:
  fact_checker:
    model: "qwen/qwen3-235b-a22b"
    temperature: 0.3
    max_tokens: 2000
    description: "URL validation and hallucination detection"
```

## Common Patterns

### Pattern 1: Fail-fast
```python
result = agent.verify_content(..., strict_mode=True)
if not result['valid']:
    raise Exception("Hallucinations detected - aborting")
```

### Pattern 2: Warn and continue
```python
result = agent.verify_content(..., strict_mode=False)
if result['warnings']:
    log.warning(f"Found issues: {result['warnings']}")
# Continue with original or corrected content
```

### Pattern 3: Manual review
```python
result = agent.verify_content(...)
if not result['valid']:
    # Show user the issues
    display_report(result['report'])
    # Let user decide
    if user_confirms():
        use_corrected = True
```

## Troubleshooting

### Issue: All URLs flagged as invalid
**Cause**: Research data incomplete or empty
**Solution**: Verify `research_data['sources']` contains URLs

### Issue: Valid URLs flagged as invalid
**Cause**: URL variant mismatch (e.g., trailing slash, query params)
**Solution**: Check URL normalization, use non-strict mode

### Issue: False negatives (fake URLs not detected)
**Cause**: Fake URL happens to match research source
**Solution**: Improve research quality, add web verification

## See Also

- Full documentation: `docs/fact_checker_implementation.md`
- Integration examples: `examples/fact_checker_integration.py`
- Tests: `tests/test_agents/test_fact_checker_agent.py`
- Source code: `src/agents/fact_checker_agent.py`

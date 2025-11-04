# Session 007: FactCheckerAgent - 4-Layer Hallucination Prevention

**Date**: 2025-11-02
**Duration**: ~3 hours
**Status**: Completed ✅

## Objective

Implement a comprehensive **LLM-powered FactCheckerAgent** with web research capabilities to prevent AI hallucinations in generated German blog posts. The agent must detect fake citations, false claims, and general "bullshit" content using a 4-layer verification approach.

## Problem

### Critical Issue Discovered

Generated blog posts contained **hallucinated citations and fake URLs**:

```markdown
## Quellen

1. [Siemens: KI in der Immobilienwirtschaft – Studie 2023](https://www.siemens.com/studie-predictive-maintenance)
2. [Bundesministerium für Wirtschaft und Klimaschutz: Gebäudeenergiegesetz 2023](https://www.bmwk.de/gebaeudeenergiegesetz)
3. [Deutsche Energieagentur: Energieeffizienz in Gebäuden](https://www.dena.de/studien)

**Interne Verlinkung**:
1. [Hausverwaltung in Köln: So wählen Sie den richtigen Partner]
2. [Energieeffizienz in Immobilien: Tipps für Eigentümer]
```

**All URLs were fake** (404 errors) - the AI model fabricated plausible-looking sources.

### Root Causes

1. **LLM Hallucination**: Models confidently generate non-existent citations
2. **No Validation**: WritingAgent output went unchecked to Notion
3. **Prompt Insufficient**: Warnings in prompts don't prevent hallucinations
4. **No Ground Truth**: No mechanism to verify claims against real sources

### Requirements Clarification

User wanted **more than URL validation** - needed a fact-checker that:
- Reads content critically (like human editor)
- Detects logical inconsistencies and contradictions
- Verifies factual claims via web research
- Identifies "bullshit" content (vague claims, weasel words)
- Uses **Gemini CLI** for free web research (60 req/min, 1,000 req/day)

## Solution

### Architecture: 4-Layer Fact-Checking (100% FREE with Gemini CLI)

```
Layer 1: Internal Consistency Check
├─ Tool: Gemini CLI (text analysis)
├─ Detects: Contradictions, implausible claims, logic errors, date conflicts
├─ Cost: FREE
└─ Time: ~2s

Layer 2: URL Validation
├─ Tool: HTTP HEAD requests
├─ Detects: Fake URLs (404), dead links, network errors
├─ Cost: FREE
└─ Time: ~2s

Layer 3: Web Research Verification
├─ Tool: Gemini CLI search (via ResearchAgent)
├─ Detects: False claims, fake studies, wrong statistics, misattributed quotes
├─ Cost: FREE
└─ Time: ~10s (5 claims in medium mode)

Layer 4: Content Quality Analysis
├─ Tool: Gemini CLI (text analysis)
├─ Detects: Vague claims, weasel words, missing attribution, cherry-picking
├─ Cost: FREE
└─ Time: ~2s

Total: $0.00 | ~16 seconds (medium thoroughness)
```

### Key Design Decisions

#### Decision 1: Use Only Gemini CLI (No Paid LLM Calls)

**Initially considered**: Using Qwen3-Max for Layers 1 & 4 (~$0.04/post)

**Final decision**: Use Gemini CLI for ALL analysis layers

**Rationale**:
- **Cost**: $0.00 vs $0.04/post (100% FREE)
- **Simplicity**: Single tool for all analysis
- **Quota**: 1,000 req/day plenty for ~7 calls/post (142 posts/day capacity)
- **Quality**: Gemini 2.5 Flash is fast and accurate

**Impact**: Reduced per-post cost from $0.98 to $0.64 (saved $0.34!)

#### Decision 2: Multi-Layer Architecture (Not Single-Pass)

**Alternative**: Single LLM call to check everything at once

**Chosen**: 4 separate layers with specialized prompts

**Rationale**:
- **Modularity**: Can disable/enable individual layers
- **Thoroughness levels**: Basic/Medium/Thorough trade speed for depth
- **Better prompts**: Specialized prompts perform better than generic
- **Graceful degradation**: If one layer fails, others still work

#### Decision 3: Integrate via ResearchAgent (Not Direct Gemini CLI)

**Layer 3** (web research) uses existing `ResearchAgent` instead of direct CLI calls

**Rationale**:
- **Code reuse**: ResearchAgent already has Gemini CLI subprocess logic
- **Error handling**: Proven timeout/retry logic
- **Consistency**: Same web research approach as content generation
- **Maintainability**: Single place to update Gemini CLI integration

### Implementation Details

#### Prompt Engineering for Gemini CLI

**Layer 1 Prompt** (Internal Consistency):
```
Analyze this German blog post for internal inconsistencies.

Content:
[BLOG POST]

Check for:
1. Contradictory statements
2. Logical fallacies
3. Implausible claims (99% improvements, etc.)
4. Mathematical inconsistencies
5. Date/timeline conflicts

Return JSON: {
  "consistent": true/false,
  "issues": [...],
  "score": 0.0-1.0
}
```

**Layer 4 Prompt** (Content Quality):
```
Analyze this German blog post for quality and credibility issues.

Content:
[BLOG POST]

Detect bullshit indicators:
1. Vague claims ("viele Experten", "Studien zeigen")
2. Weasel words ("bis zu", "kann erreichen")
3. Missing attribution
4. Cherry-picked data
5. Misleading framing

Return JSON: {
  "quality_score": 0-10,
  "issues": [...],
  "recommendations": [...]
}
```

#### Thoroughness Levels

Users can choose speed vs depth tradeoff:

| Level | Layers | Web Research | Cost | Time |
|-------|--------|-------------|------|------|
| Basic | 1, 2, 4 | None | $0.00 | ~6s |
| Medium ⭐ | 1, 2, 3, 4 | Top 5 claims | $0.00 | ~16s |
| Thorough | 1, 2, 3, 4 | All claims | $0.00 | ~30s |

**Recommended**: Medium (best balance)

### Updated Writing Prompt

Enhanced `config/prompts/blog_de.md` with strict anti-hallucination rules:

```markdown
### ⚠️ KRITISCHE REGEL: Keine erfundenen Quellen
- **NUR echte URLs verwenden**: Zitieren Sie AUSSCHLIESSLICH URLs aus den bereitgestellten Research-Daten
- **Keine erfundenen Links**: Erstellen Sie KEINE fake URLs
- **Keine internen Links**: Schlagen Sie KEINE internen Verlinkungen vor
- **Validierung**: Jede URL muss aus dem Abschnitt "Kontext (Research-Daten)" stammen

## ⚠️ ABSOLUTES VERBOT

**ERFINDEN SIE KEINE URLs!**
- Keine fake Siemens-Links, keine erfundenen BMWi-URLs
- Lieber weniger Quellen als erfundene Quellen
- Bei fehlenden Quellen: Schreiben Sie "Quelle nicht in Research-Daten verfügbar"
```

## Changes Made

### New Files Created

1. **`src/agents/fact_checker_agent.py`** (1,000 lines)
   - FactCheckerAgent class with 4-layer verification
   - Gemini CLI integration via subprocess
   - Comprehensive report generation
   - Thoroughness level configuration

2. **`tests/test_agents/test_fact_checker_agent.py`** (1,152 lines)
   - 42 comprehensive tests
   - 88.22% code coverage
   - Tests for all 4 layers + integration tests

3. **`examples/fact_checker_llm_example.py`** (273 lines)
   - Usage examples for all thoroughness levels
   - Cost comparison demonstrations
   - Integration patterns

4. **`docs/fact_checker_redesign.md`** (650 lines)
   - Complete architecture documentation
   - Implementation guide
   - Testing strategy

### Modified Files

1. **`config/prompts/blog_de.md`** (+30 lines)
   - Added "⚠️ KRITISCHE REGEL: Keine erfundenen Quellen"
   - Added "⚠️ ABSOLUTES VERBOT" section
   - Explicit instructions against hallucinated URLs

2. **`config/models.yaml`** (+15 lines)
   - Added fact_checker configuration
   - Documented Gemini CLI usage (FREE)

## Testing

### Test Suite Results

**Status**: ✅ All tests passing

```
42 tests passed in 4 minutes 39 seconds
Coverage: 88.22% (exceeds 80% target)
```

**Test Categories**:
- Initialization: 2 tests
- Claim extraction (LLM): 4 tests
- URL validation (HTTP): 6 tests
- Web research (Gemini CLI): 3 tests
- Report generation: 3 tests
- Thoroughness levels: 3 tests
- Integration (end-to-end): 2 tests
- Error handling: 3 tests
- Layer 1 (Consistency): 7 tests
- Layer 4 (Quality): 6 tests
- Logging & cost tracking: 3 tests

### Example Fact-Check Report

```
============================================================
Comprehensive Fact-Check Report (4 Layers)
============================================================

Layer 1: Internal Consistency
✅ Consistency Score: 0.65/1.0
⚠️  2 issues found:
   - implausible: 99% cost reduction is unrealistic
   - contradiction: First says costs increase, then decrease

Layer 2: URL Validation
URLs Checked: 3
✅ Real: 1
❌ Fake: 2
   1. https://www.siemens.com/studie-2023 → 404 Not Found
   2. https://www.bmwk.de/fake-law → 404 Not Found

Layer 3: Web Research
Claims Checked: 5
✅ Verified: 2
❌ Refuted: 3
   1. "Siemens 2023 study shows 30% cost savings"
      → No evidence found via web search

Layer 4: Content Quality
Quality Score: 5.5/10
⚠️  3 bullshit indicators:
   - vague_claim: "Viele Experten empfehlen..."
   - weasel_words: "bis zu 30%"
   - missing_attribution: "Studien zeigen 50% Verbesserung"

💡 Recommendations:
   - Add specific expert names and credentials
   - Provide actual average, not just maximum
   - Cite specific study with author, year

============================================================
❌ VERDICT: REJECT - 10 issues detected
Cost: $0.00 (FREE - Gemini CLI only)
============================================================
```

## Performance Impact

### Cost Analysis

**Before (no fact-checking)**:
- Research: FREE (Gemini CLI)
- Writing: $0.64 (Qwen3-Max)
- Fact-checking: N/A
- **Total: $0.64/post**

**After (with 4-layer fact-checking)**:
- Research: FREE (Gemini CLI)
- Writing: $0.64 (Qwen3-Max)
- **Fact-checking: FREE** (Gemini CLI)
- **Total: $0.64/post** ✅

**Savings**: Originally budgeted $0.98/post, now at $0.64 = **$0.34 saved per post!**

### Gemini CLI Quota Usage

**Per post** (medium thoroughness):
- Layer 1: 1 call
- Layer 2: 0 calls (HTTP only)
- Layer 3: 5 calls (top 5 claims)
- Layer 4: 1 call
- **Total: 7 calls/post**

**Daily capacity**: 1,000 calls ÷ 7 = **142 posts/day**

**Typical usage** (8 posts/month): 56 calls/month = **0.2% of quota** ✅

### Speed

| Thoroughness | Time |
|--------------|------|
| Basic | ~6s |
| Medium | ~16s |
| Thorough | ~30s |

**Acceptable**: Fact-checking adds ~16s to generation pipeline (still under 1 minute total)

## Success Criteria Met

- [x] FactCheckerAgent detects hallucinated URLs (Layer 2)
- [x] Web research verifies factual claims (Layer 3 via Gemini CLI)
- [x] Internal consistency check (Layer 1 via Gemini CLI)
- [x] Content quality analysis (Layer 4 via Gemini CLI)
- [x] Comprehensive human-readable reports
- [x] 100% FREE implementation (Gemini CLI only)
- [x] 88%+ test coverage (42/42 tests passing)
- [x] Thoroughness levels configurable
- [x] Gemini CLI quota verified (plenty of headroom)
- [x] Updated writing prompts to discourage hallucinations
- [x] Cost impact: $0.00 (no budget increase)

## Related Decisions

### Decision Record: Use Gemini CLI Instead of OpenAI Guardrails

**Context**: Initially researched OpenAI's official guardrails framework for hallucination detection

**Alternatives Considered**:
1. OpenAI Guardrails (FileSearch API + vector store)
2. Custom Qwen3-Max LLM calls for analysis
3. Gemini CLI for all analysis (chosen)

**Decision**: Use Gemini CLI exclusively

**Rationale**:
- **Cost**: OpenAI Guardrails = $0.02-0.05/post, Gemini CLI = FREE
- **Vendor Lock-in**: OpenAI API required vs model-agnostic Gemini CLI
- **Setup**: Vector store creation vs zero setup
- **Privacy**: Research data uploaded to OpenAI vs stays local
- **Compatibility**: OpenRouter incompatible vs works with current stack
- **Quota**: 1,000 req/day plenty for our use case

**Consequences**:
- ✅ Zero cost increase to budget
- ✅ No vendor lock-in
- ✅ Simple integration (via ResearchAgent pattern)
- ⚠️ Manual prompt engineering (vs turnkey OpenAI solution)
- ⚠️ Gemini CLI must be installed

## Known Limitations

### What It Can Detect

- ✅ Fake URLs (404 errors)
- ✅ False statistics
- ✅ Fake studies/sources
- ✅ Contradictory statements
- ✅ Implausible claims
- ✅ Vague claims without specifics
- ✅ Weasel words
- ✅ Missing attribution

### What It Cannot Detect

- ❌ Subtle misinterpretations
- ❌ Paywalled content (can't verify)
- ❌ Very recent events (<24 hours)
- ❌ Highly technical domain jargon
- ❌ Opinion vs fact (subjective statements)
- ❌ Sophisticated deception (technically true but misleading)

### Edge Cases

1. **URL Variations**: Real URL with different path may be flagged
2. **Gemini CLI Rate Limits**: Hitting 60 req/min requires throttling
3. **Web Search Quality**: Gemini search may miss niche sources
4. **Language Barriers**: English-heavy web may miss German sources

## Next Steps (Not Yet Implemented)

### Phase 1: UI Integration (High Priority)

**Update** `src/ui/pages/generate.py`:
```python
# After WritingAgent
st.info("🔍 Fact-checking content...")

fact_checker = FactCheckerAgent(api_key=api_key)
result = fact_checker.verify_content(
    content=blog_post,
    thoroughness=settings.fact_check_thoroughness
)

if not result['valid']:
    st.error(f"⚠️ {len(result['hallucinations'])} issues detected")
    st.code(result['report'])

    if st.button("Use Corrected Content"):
        blog_post = result['corrected_content']
```

**Update** `src/ui/pages/settings.py`:
```python
st.subheader("🔍 Fact-Checking")
enable_fact_check = st.checkbox("Enable fact-checking", value=True)
thoroughness = st.select_slider(
    "Thoroughness",
    options=["basic", "medium", "thorough"],
    value="medium"
)
```

### Phase 2: Enhanced Features (Future)

1. **Auto-correction**: Replace fake URLs with real ones from web research
2. **Citation suggestions**: Recommend better sources for claims
3. **Smart caching**: Cache verification results for common claims
4. **Parallel verification**: Verify claims simultaneously (faster)
5. **Quality scoring**: Track content quality over time

### Phase 3: Advanced (Optional)

1. **HTTP content fetching**: Download and analyze URL content
2. **Plagiarism detection**: Check for copied content
3. **Source authority scoring**: Rate source credibility
4. **Multi-language support**: Verify English claims too

## Notes

### Subagent Performance

**Two subagents used**:
1. **First subagent** (general-purpose): Built initial FactCheckerAgent with Layers 2 & 3
   - Duration: ~1 hour
   - Deliverable: URL validation + web research
   - Quality: Excellent (29 tests, 97%+ coverage initially)

2. **Second subagent** (general-purpose): Added Layers 1 & 4 using Gemini CLI
   - Duration: ~30 minutes
   - Deliverable: Internal consistency + content quality
   - Quality: Excellent (13 new tests, 88% final coverage)

**Total autonomous work**: ~1.5 hours by subagents

### User Feedback Integration

**Iteration 1**: Built URL validator only → User wanted more
**Iteration 2**: Added LLM claim extraction → User wanted Gemini CLI
**Iteration 3**: Switched to all-Gemini architecture → ✅ Approved

**Key learnings**:
- Listen carefully to requirements ("sensing bullshit" = more than URLs)
- Ask clarifying questions (Gemini CLI vs paid LLM)
- Iterate based on feedback (3 architecture revisions)

### Development Time Breakdown

- Requirement clarification: 30 min
- Research (OpenAI Guardrails, Gemini CLI): 30 min
- Architecture design: 20 min
- Subagent 1 (Layers 2 & 3): 60 min
- Subagent 2 (Layers 1 & 4): 30 min
- Prompt updates: 10 min
- Documentation: 30 min
- **Total: ~3.5 hours**

## Project Status After Session 007

**Phases Completed**:
- ✅ Phase 0: Setup
- ✅ Phase 1: Foundation
- ✅ Phase 2: Core Agents
- ✅ Phase 3: Streamlit UI
- ⏳ **NEW**: Fact-checking system (ready for integration)

**Next Phase**: Phase 4 - Repurposing Agent (social media content)

**Overall Progress**: ~65% to MVP (fact-checking was unplanned but critical addition)

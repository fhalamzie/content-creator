# Streamlit UI Refactoring Plan

**Status**: Approved - Ready for Implementation
**Date**: 2025-11-15
**Session**: 050
**AI Expert Review**: Codex (GPT-5) + Gemini (2.5 Flash)

---

## Problem Statement

**Current Issues**:
- ❌ 7 pages with unclear purposes
- ❌ 3 overlapping generation methods (Generate, Pipeline, Research)
- ❌ Checkbox overload (6+ options, users don't understand what they do)
- ❌ No clear onboarding path for new users
- ❌ Configuration split across Setup + Settings pages
- ❌ No "why" explanations for features

**User Feedback**: "Too many checkboxes, don't know what they do or why I need them"

---

## Proposed Solution

**New Structure (5-6 pages)**:

```
1. Dashboard       → Overview + guided routing ("What do you want to do?")
2. Quick Create    → Simplified single-topic (uses saved defaults)
3. Automation      → 3-step wizard (website → topics → articles)
4. Research Lab    → Analysis tabs (Topic/Competitor/Keywords)
5. Settings        → Unified config (Brand + API + Models + Advanced)
6. Library         → Browse/manage content (keep as-is)
```

**3 User Paths**:
1. **Business Owner** → Full Automation (hands-off)
2. **Content Creator** → Quick Create (manual, fast)
3. **SEO/Marketer** → Research Lab (analysis-first)

---

## AI Expert Recommendations (Consensus)

**Codex (GPT-5) + Gemini (2.5 Flash) Agreement**:

✅ **Structure is correct** (5-6 pages, 3 paths)
✅ **Refactor Quick Create FIRST** (highest impact)
✅ **Keep Research Lab separate** (but surface insights inline)
✅ **Add onboarding wizard** (step-zero routing on Dashboard)
✅ **Merge Setup + Settings** (one unified configuration page)
✅ **Progressive disclosure** (hide advanced options by default)
✅ **Show cost/time estimates** (before every action)
✅ **Explain every feature** (what it does + why it exists)

**Skipped for Prototype**:
- ❌ Multi-brand profiles (agency feature)
- ❌ Performance metrics in Library
- ❌ Visual polish (colors, animations)
- Focus: **User flow clarity only**

---

## Design Pattern: Progressive Help

**3-Tier Help System**:

1. **Inline hints** (always visible) - Brief "what"
   - Example: `ℹ️ What you want to write about`

2. **Tooltips** (hover/click ℹ️) - Detailed "why"
   - Example: `↳ Why: Visual content increases engagement by 94%`

3. **Expandable help** (optional) - Full context
   - Example: `[❓ What happens next?] ← EXPANDABLE`

---

## Phase 1: Quick Create (START HERE) - Week 1

### Goal
Make single-topic generation dead simple with clear explanations.

### Changes

**Before** (Current):
```
Topic: [_____]
Language: [de ▼]
[✓] Generate images
[✓] Competitor research
[✓] Keyword research
[✓] Fact-check
[✓] Auto-sync
Target words: [1500]
[Generate]
```

**After** (Refactored):
```
Topic: [_____] ℹ️ What you want to write about
Language: [de ▼] ℹ️ Article language

✅ Using your saved settings:
   • Brand Voice: Professional ℹ️ How formal/casual
   • Generate images (3 Flux + 2 AI) ℹ️ 5 photorealistic images
     Why? Visual content increases engagement by 94%
   • Fact-check content (FREE) ℹ️ Verifies claims and URLs
     Why? Prevents publishing false information
   • Auto-sync to Notion ℹ️ Saves for editorial review
     Why? Review before publishing

   [⚙️ Advanced Options] ← COLLAPSED

💰 Cost: $0.07-$0.20
⏱️ Time: 2-3 minutes

[🚀 Generate Article]

[❓ What happens next?] ← EXPANDABLE HELP
```

**Advanced Options** (when expanded):
```
🔬 Extra Research (Optional):
[ ] Competitor analysis (+10s, FREE) ℹ️
    ↳ What: Finds competitor content
    ↳ Why: Identifies content gaps
    ↳ When: Strategic planning

[ ] Keyword research (+8s, FREE) ℹ️
    ↳ What: Finds SEO keywords
    ↳ Why: Helps rank in Google
    ↳ When: SEO-focused content

🖼️ Image Settings:
[✓] Generate images ℹ️
    ↳ Cost breakdown:
      • Flux 1.1 Pro Ultra (hero): $0.06
      • Flux Dev (2 supporting): $0.006
      • JuggernautXL (Chutes): $0.025
      • qwen-image (Chutes): $0.105
    ↳ Why 5 images?
      1 hero (attracts readers)
      2 supporting (breaks up text)
      2 comparison (test AI styles)

📝 Content Options:
[✓] Fact-check (FREE, +15s) ℹ️
    ↳ What: 4-layer verification
    ↳ Why: Prevents misinformation

Target words: [1500 ▼] ℹ️
    ↳ Recommended: 1500 (8-10 min read)
    ↳ Why: Ideal for SEO + engagement
```

**"What happens next?" Expandable**:
```
📖 Generation Process:

1️⃣ Research (30s)
   → Searches 5+ sources
   → Why? Ensures factual content

2️⃣ Writing (90s)
   → AI writes 1500-word article
   → Uses your brand voice
   → Why? Consistent with brand

3️⃣ Image Generation (45s)
   → Creates 5 photorealistic images
   → Why? Visual variety + comparison

4️⃣ Fact-Check (15s, optional)
   → Verifies claims and URLs
   → Why? Prevents misinformation

5️⃣ Save & Sync (5s)
   → Local cache + Notion
   → Why? Review before publishing

✅ Result: Ready article in Library
```

### Implementation Files
- `src/ui/pages/quick_create.py` (new file, replace `generate.py`)
- `src/ui/components/help.py` (new file, reusable help components)

### Success Criteria
- [ ] No checkboxes in main view (all collapsed in Advanced)
- [ ] Every option has ℹ️ tooltip explaining "what" and "why"
- [ ] Cost/time estimates shown before generation
- [ ] "What happens next?" expandable with full process
- [ ] Uses Settings defaults (no manual configuration required)

---

## Phase 2: Settings Consolidation - Week 1

### Goal
Merge Setup + Settings into one unified page with clear explanations.

### Changes

**Unified Settings (4 tabs)**:

**Tab 1: Brand Setup** (merge from old Setup page)
```
Brand Name: [_____] ℹ️
↳ Your company name
↳ Used in: Author attribution

Website: [_____] ℹ️
↳ Your business URL
↳ Used in: Automation (website analysis)
↳ Optional but recommended

Brand Voice: [Professional ▼] ℹ️
↳ How formal or casual
↳ Options:
  • Professional - Business, formal (B2B)
  • Casual - Friendly (B2C)
  • Technical - Industry expert
  • Creative - Engaging, storytelling

[ℹ️ See examples of each voice] ← EXPANDABLE

Target Audience: [_____] ℹ️
↳ Who reads your content? Be specific.
↳ Good: "German SMB owners aged 35-50 in PropTech"
↳ Bad: "Everyone"
↳ Why important: AI tailors language complexity

Primary Keywords: [_____] ℹ️
↳ Topics you want to rank for
↳ Example: "Cloud computing, AI, Digital transformation"
↳ Used in: SEO optimization, topic suggestions

ℹ️ These defaults are used in Quick Create

[💾 Save Brand Settings]
```

**Tab 2: API Keys** (from old Settings)
```
Notion Integration Token: [_____] ℹ️
↳ What: Saves articles to Notion
↳ Why: Editorial workflow
↳ Get it: https://notion.so/my-integrations
↳ Required? Optional (saves to cache without it)

OpenRouter API Key: [_____] ℹ️
↳ What: AI writing service (Qwen3-Max)
↳ Why: Generates blog posts
↳ Get it: https://openrouter.ai/keys
↳ Required? Yes (core functionality)

Gemini API Key: [_____] ℹ️
↳ What: Free research and fact-checking
↳ Why: Finds topics, verifies facts (saves $$)
↳ Get it: https://aistudio.google.com/app/apikey
↳ Required? No (but recommended - FREE)

[🧪 Test All Connections]

[❓ Why do I need these?] ← EXPANDABLE
```

**Tab 3: AI Models** (keep from old Settings)
**Tab 4: Advanced** (keep from old Settings)

### Implementation Files
- Refactor `src/ui/pages/settings.py` (add Brand tab, merge Setup)
- Delete `src/ui/pages/setup.py` (merged into Settings)

### Success Criteria
- [ ] One unified Settings page (not two separate pages)
- [ ] Brand config is Tab 1 (primary importance)
- [ ] Every API key explains "what", "why", "required?"
- [ ] First-time setup wizard (guides through tabs)

---

## Phase 3: Dashboard Routing - Week 1

### Goal
Help users understand what each page does and guide them to the right path.

### Changes

**"What do you want to do?" Routing**:
```
┌─────────────────────────────────────┐
│ 🚀 Create 1 Article Now             │
│ ℹ️ Quick & simple single-topic      │
│ When: You have a specific topic     │
│ Time: 2-3 minutes                   │
│ Cost: $0.07-$0.20                   │
│ [→ Go to Quick Create]              │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 🎯 Automate My Website              │
│ ℹ️ Analyze site → Generate articles │
│ When: You need bulk content         │
│ Process:                             │
│  1. Analyzes website (FREE)         │
│  2. Finds competitors (FREE)        │
│  3. Discovers 50+ ideas (FREE)      │
│  4. You select 5-20 topics          │
│  5. Generates articles ($0.01 each) │
│ Time: 10-15 minutes                 │
│ Cost: ~$0.10 (for 10 articles)      │
│ [→ Go to Automation]                │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 🔬 Research Topics First            │
│ ℹ️ Deep analysis before writing     │
│ When: Planning content strategy     │
│ What you get:                        │
│  • 5-source deep research           │
│  • Competitor gap analysis          │
│  • Keyword difficulty scores        │
│  • Topic recommendations            │
│ Time: 5-10 minutes                  │
│ Cost: Mostly FREE (Gemini API)      │
│ [→ Go to Research Lab]              │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 📚 View My Content Library          │
│ ℹ️ Browse and manage content        │
│ [→ Go to Library]                   │
└─────────────────────────────────────┘

[❓ New to content generation? Start here]
```

**"Start here" Expandable**:
```
🎓 Getting Started Guide

Step 1: Configure Your Brand (5 min)
→ Settings → Brand Setup tab
→ Fill: Name, voice, audience, keywords
→ These make Quick Create super fast

Step 2: Add API Keys (5 min)
→ Settings → API Keys tab
→ Add: OpenRouter (required), Gemini (recommended)
→ Test connections

Step 3: Generate First Article (3 min)
→ Quick Create
→ Enter topic: "Benefits of cloud computing"
→ Click "Generate Article"
→ Review in Library or Notion

🎉 Done! You're ready to create at scale.

[✅ I've completed setup] [❓ Get help]
```

### Implementation Files
- Refactor `src/ui/pages/dashboard.py` (add routing cards)

### Success Criteria
- [ ] 4 clear routing cards with "When to use"
- [ ] Time and cost estimates for each path
- [ ] "Getting Started" guide for new users
- [ ] Visual separation between cards

---

## Phase 4: Automation Wizard - Week 2

### Goal
Show progress, reduce anxiety, explain each step.

### Changes

**3-Step Wizard with Progress**:

**Step 1: Website Analysis**
```
Progress: [████░░░░░░] 1/3

Website URL: [_____]

ℹ️ What we'll do:
1. Extract keywords from your site (FREE)
2. Find competitor topics (FREE)
3. Discover 50+ article ideas (FREE)
4. Score & validate topics (FREE)

Estimated time: 30 seconds

[🔍 Analyze Website]
```

**Step 2: Select Topics**
```
Progress: [████████░░] 2/3

✅ Found 50 topics → Validated 20 best

Select topics to research ($0.01 each):
[✓] Topic 1 (Score: 0.85) ℹ️ High relevance
[✓] Topic 2 (Score: 0.82)
[ ] Topic 3 (Score: 0.76)
...

Selected: 5 → Cost: $0.05

ℹ️ Why scoring? Filters low-quality topics
   before expensive research operations.
   Saves 60% cost.

[🚀 Generate 5 Articles]
```

**Step 3: Review Results**
```
Progress: [██████████] 3/3 ✅

✅ 5 articles generated
✅ All synced to Notion
💰 Total cost: $0.05

[📚 View in Library] [🔄 Start New]
```

### Implementation Files
- Refactor `src/ui/pages/pipeline_automation.py` (add progress indicators)

### Success Criteria
- [ ] Visual progress bar (1/3, 2/3, 3/3)
- [ ] Each step explains "what we'll do"
- [ ] Cost shown before generation (not after)
- [ ] Clear completion state with next actions

---

## Phase 5: Research Lab - Week 2

### Goal
Clarify purpose of each research type.

### Changes

**3 Tabs with Clear Use Cases**:

**Tab 1: Topic Research**
```
ℹ️ Deep research on a specific topic

When to use:
• You want to understand a topic deeply
• You need well-researched content
• You want 5-source fact-checked info

What you get:
• 2000-word research report
• 5+ sources with citations
• Reranked for quality (BM25 → Voyage)

Topic: [_____]
[🔬 Research]
```

**Tab 2: Competitor Analysis**
```
ℹ️ Find what competitors write about

When to use:
• You want to identify content gaps
• You need competitor insights
• You're planning content strategy

What you get:
• Top 5 competitors
• Content gap analysis
• Trending topics in your niche

Website: [_____]
[🔍 Analyze Competitors]
```

**Tab 3: Keyword Research**
```
ℹ️ Find SEO keywords for your topic

When to use:
• You want to rank in Google
• You need search volume data
• You're optimizing for SEO

What you get:
• Primary keyword suggestions
• Search volume estimates
• Difficulty scores
• Related questions

Topic: [_____]
[🎯 Research Keywords]
```

**Each tab has**:
→ "Use this in Quick Create" button (export topic)

### Implementation Files
- Refactor `src/ui/pages/topic_research.py` (add 3 tabs with clear purposes)

### Success Criteria
- [ ] 3 separate tabs (not one mixed page)
- [ ] Each tab explains "when to use"
- [ ] "What you get" clearly listed
- [ ] Export to Quick Create button

---

## Reusable Components

### Help Components (`src/ui/components/help.py`)

```python
import streamlit as st

def info_inline(text: str, help_text: str):
    """Inline info with ℹ️ icon"""
    st.markdown(f"{text} ℹ️")
    st.caption(f"↳ {help_text}")

def expandable_help(title: str, content: str):
    """Collapsible help section"""
    with st.expander(f"❓ {title}"):
        st.markdown(content)

def cost_breakdown(items: dict):
    """Show cost with explanations"""
    st.caption("💰 Cost Breakdown:")
    total = 0
    for item, cost in items.items():
        st.caption(f"• {item}: ${cost:.4f}")
        total += cost
    st.caption("─" * 30)
    st.caption(f"**Total: ${total:.2f}**")

def why_section(feature: str, what: str, why: str, when: str = None):
    """Explain feature with what/why/when"""
    st.caption(f"**{feature}**")
    st.caption(f"ℹ️ What: {what}")
    st.caption(f"ℹ️ Why: {why}")
    if when:
        st.caption(f"📌 When: {when}")

def time_estimate(seconds: int):
    """Show time estimate"""
    if seconds < 60:
        st.caption(f"⏱️ Time: ~{seconds}s")
    else:
        minutes = seconds // 60
        st.caption(f"⏱️ Time: ~{minutes} min")
```

---

## Implementation Timeline

### Week 1 (High Impact, Quick Wins)
- **Day 1-2**: Quick Create refactoring
  - Simplified form with defaults
  - Collapse advanced options
  - Add inline help and tooltips
  - Cost/time estimates
  - "What happens next?" expandable

- **Day 3**: Settings consolidation
  - Merge Setup → Settings Tab 1
  - Add explanations to all fields
  - "Why do I need this?" expandables

- **Day 4-5**: Dashboard routing
  - Add routing cards with descriptions
  - Add "Getting Started" guide
  - Visual improvements

### Week 2 (Polish & Enhancement)
- **Day 6-7**: Automation wizard
  - Add progress indicators
  - Explain each step
  - Cost estimates before generation

- **Day 8-9**: Research Lab tabs
  - Split into 3 tabs
  - Add "when to use" for each
  - Export to Quick Create

- **Day 10**: Testing & refinement
  - User flow testing
  - Cost estimate verification
  - Help text clarity

---

## Success Metrics

### User Understanding
- [ ] Users can explain what each page does
- [ ] Users understand when to use each path
- [ ] Users know why features exist (not just what they do)

### Reduced Confusion
- [ ] Zero questions about "what does this checkbox do?"
- [ ] Clear cost expectations before generation
- [ ] No accidental expensive operations

### Improved Onboarding
- [ ] New users complete first article in <10 minutes
- [ ] Setup completion rate >90%
- [ ] Users can navigate without external documentation

---

## References

- **AI Expert Review**: Codex (GPT-5) + Gemini (2.5 Flash)
- **Current UI**: `src/ui/pages/*.py`
- **Target Architecture**: `TARGET_ARCHITECTURE.md` (FastAPI + React for production)
- **Session**: 050 (2025-11-15)

---

**Next Steps**: Start Phase 1 (Quick Create refactoring)

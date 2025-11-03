# Session 008: Universal Topic Research Agent - Week 1 Foundation

**Date**: 2025-11-04
**Duration**: 3 hours
**Status**: Completed - 3/7 Components (42.9%)

## Objective

Implement the foundational infrastructure (Week 1) for the Universal Topic Research Agent using strict TDD methodology. Focus on core components that enable all future collectors and processors.

## Context

Started implementation of the Universal Topic Research Agent as documented in `docs/IMPLEMENTATION_PLAN.md` (1,600 lines). This agent will automatically discover SEO-optimized topics for ANY domain/market/language using intelligent feed discovery, LLM-based processing, and competitor/keyword research.

**Target**: 7 foundation components for Week 1
**Achieved**: 3 components (42.9% complete)

## Components Implemented

### Component 1: Central Logging System ✅

**Files**:
- `src/utils/logger.py` (9 statements, 100% coverage)
- `tests/unit/test_logger.py` (20 tests)

**Features**:
- structlog-based structured logging with ISO timestamps
- Log level filtering (DEBUG, INFO, WARNING, ERROR)
- Metrics tracking hooks (WAL size, API usage, error rates, cache stats)
- Context variables support for correlation IDs
- Pattern: `logger.info("event", key="value")` → structured JSON output

**Usage Example**:
```python
from src.utils.logger import setup_logging, get_logger

setup_logging(log_level="INFO")  # Once in main.py
logger = get_logger(__name__)
logger.info("rss_collection_started", feed_count=20)
```

**Test Coverage**: 20/20 tests passing, 100% coverage

---

### Component 2: Document Model ✅

**Files**:
- `src/models/document.py` (31 statements, 100% coverage)
- `tests/unit/test_document.py` (20 tests)

**Features**:
- Universal data model for ALL collectors (RSS, Reddit, Trends, SERP, Autocomplete)
- 20+ fields organized into sections:
  - Identity: `id`, `source`, `source_url`
  - Content: `title`, `content`, `summary`
  - Classification: `language`, `domain`, `market`, `vertical`
  - Deduplication: `content_hash`, `canonical_url`
  - Metadata: `published_at`, `fetched_at`, `author`
  - Enrichment: `entities`, `keywords` (added by LLM processor)
  - Provenance: `reliability_score`, `paywall`
  - Status: `status` (new, processed, rejected)
- Pydantic V2 validation with ConfigDict
- Helper methods: `is_processed()`, `has_entities()`, `has_keywords()`
- Serialization: `model_dump()`, `model_dump_json()`, `**dict` deserialization

**Usage Example**:
```python
from src.models.document import Document
from datetime import datetime

doc = Document(
    id="rss_heise_123",
    source="rss_heise",
    source_url="https://heise.de/article/123",
    title="PropTech Trends 2025",
    content="...",
    language="de",
    domain="SaaS",
    market="Germany",
    vertical="Proptech",
    content_hash="abc123",
    canonical_url="https://heise.de/article/123",
    published_at=datetime.now(),
    fetched_at=datetime.now()
)

if doc.is_processed() and doc.has_entities():
    print(f"Entities: {doc.entities}")
```

**Test Coverage**: 20/20 tests passing, 100% coverage

---

### Component 3: Configuration System ✅

**Files**:
- `src/utils/config_loader.py` (66 statements, 93.94% coverage)
- `tests/unit/test_config_loader.py` (20 tests)
- `config/markets/proptech_de.yaml` (example config - German PropTech)
- `config/markets/fashion_fr.yaml` (example config - French Fashion)
- `config/markets/README.md` (documentation)

**Features**:
- YAML-based market configurations with Pydantic validation
- Three config sections:
  - **MarketConfig**: `domain`, `market`, `language`, `vertical`, `seed_keywords`, `competitor_urls`, `target_audience`
  - **CollectorConfig**: Enable/disable collectors, custom RSS feeds, Reddit subreddits
  - **SchedulingConfig**: Collection time, Notion sync day, lookback days
- Default values for optional fields (all collectors enabled by default)
- Multi-config support (German PropTech + French Fashion in parallel)
- Per-config isolation (no language mixing, no topic bleeding)

**Usage Example**:
```python
from src.utils.config_loader import ConfigLoader

loader = ConfigLoader()
config = loader.load("proptech_de")

# Access config values
print(config.market.domain)           # "SaaS"
print(config.market.language)         # "de"
print(config.market.seed_keywords)    # ["PropTech", "Smart Building", ...]

# Use in collectors
if config.collectors.rss_enabled:
    feeds = config.collectors.custom_feeds  # 7 German tech feeds
if config.collectors.reddit_enabled:
    subreddits = config.collectors.reddit_subreddits  # ["de", "Finanzen", ...]
```

**Example Configurations**:
1. **proptech_de.yaml**: German PropTech / SaaS
   - 7 seed keywords (PropTech, Smart Building, DSGVO, etc.)
   - 7 custom RSS feeds (Heise, t3n, Golem, German tech news)
   - 4 Reddit subreddits (de, Finanzen, PropTech, realestate_de)
   - 4 competitors (ImmobilienScout24, Propstack, Casavi, Haufe)

2. **fashion_fr.yaml**: French Fashion / E-commerce
   - 7 seed keywords (Mode, Fashion Tech, Shopping en ligne, etc.)
   - 5 custom RSS feeds (Vogue, Elle, Madmoizelle, French fashion media)
   - 4 Reddit subreddits (france, FrenchFashion, fashion advice)
   - Custom scheduling (03:00 collection, Wednesday sync, 14-day lookback)

**Test Coverage**: 20/20 tests passing, 93.94% coverage

---

## Testing Methodology

**Strict TDD Approach** (100% compliance):
1. ✅ Write failing tests first
2. ✅ Implement minimum code to pass
3. ✅ Refactor
4. ✅ Repeat

**Test Organization**:
- `tests/unit/` - Fast, isolated, mocked dependencies (60 tests)
- `tests/integration/` - Real operations (planned for Components 4-7)

**Coverage Targets**:
- Critical paths (logger, document): 100% ✅
- Configuration system: 93.94% ✅
- Overall: 96.23% ✅ (target: 80%+)

---

## Performance Metrics

### Test Execution
- **Total Tests**: 60 (all passing)
- **Execution Time**: 0.48 seconds (all 60 tests)
- **Coverage**: 96.23% (106 statements, 4 missed)

### Component Breakdown
| Component | Tests | Coverage | Lines | Status |
|-----------|-------|----------|-------|--------|
| Logger | 20 | 100% | 9 | ✅ |
| Document | 20 | 100% | 31 | ✅ |
| Config | 20 | 93.94% | 66 | ✅ |
| **Total** | **60** | **96.23%** | **106** | **✅** |

---

## Configuration Validation

Created and validated 2 production-ready market configs:

**Validation Results**:
```
✓ Market config valid (domain=SaaS, language=de, keywords=7)
✓ Collectors config valid (custom_feeds=7, subreddits=4)
✓ Scheduling config valid (collection_time=02:00, sync_day=monday)
✅ proptech_de.yaml VALID

✓ Market config valid (domain=E-commerce, language=fr, keywords=7)
✓ Collectors config valid (custom_feeds=5, subreddits=4)
✓ Scheduling config valid (collection_time=03:00, sync_day=wednesday)
✅ fashion_fr.yaml VALID
```

---

## Architectural Patterns Established

### 1. Dependency Injection
No global state - all dependencies passed explicitly:
```python
# ✅ GOOD
class RSSCollector:
    def __init__(self, db: DatabaseManager, llm: LLMProcessor, logger):
        self.db = db
        self.llm = llm
        self.logger = logger
```

### 2. Layered Architecture
Clear dependency direction (bottom-up only):
```
main.py (Entry Point)
    ↓
agents/ (Orchestration)
    ↓
collectors/ processors/ research/
    ↓
database/ tasks/
    ↓
models/ utils/ config/ (Foundation) ← WE ARE HERE
```

### 3. Central Logging
Single logger setup, used everywhere:
```python
# In main.py (once)
from src.utils.logger import setup_logging
setup_logging(log_level="INFO")

# In any module
from src.utils.logger import get_logger
logger = get_logger(__name__)
logger.info("event", key="value")
```

### 4. Configuration-Driven Design
One config file per market/domain/language:
```
config/markets/
├── proptech_de.yaml     # German PropTech
├── fashion_fr.yaml      # French Fashion
└── [your_niche].yaml    # Add more easily
```

---

## Files Created

```
src/
├── models/
│   └── document.py                    # Universal document model (31 lines)
├── utils/
│   ├── logger.py                      # Central logging (9 lines)
│   └── config_loader.py               # Config system (66 lines)

tests/unit/
├── test_logger.py                     # Logger tests (20 tests)
├── test_document.py                   # Document tests (20 tests)
└── test_config_loader.py              # Config tests (20 tests)

config/markets/
├── proptech_de.yaml                   # German PropTech config (90 lines)
├── fashion_fr.yaml                    # French Fashion config (71 lines)
└── README.md                          # Config documentation (160 lines)
```

**Total**: 7 new files, 106 statements, 60 tests

---

## Remaining Work (Week 1)

### Component 4: Optimized SQLite (pending)
- SQLite with WAL mode (`wal_autocheckpoint=1000`)
- Database schema: documents, topics, FTS
- WAL size monitoring (alert if >10MB, force checkpoint)
- Single writer pattern (thread-safe)
- Health checks

### Component 5: LLM Processor (pending)
- qwen-turbo integration via OpenRouter
- 30-day caching (minimize costs: $0.003/month target)
- Language detection, topic clustering, entity extraction
- Circuit breaker + retry logic (3 attempts, exponential backoff)
- Pydantic validation (NOT Instructor library)

### Component 6: Deduplicator (pending)
- MinHash/LSH for near-duplicate detection (threshold=0.7)
- Canonical URL normalization (remove tracking, www, lowercase)
- Persistent bloom filter (survives restarts)
- Target: <5% duplicate rate

### Component 7: Huey Task Queue (pending)
- SQLite-backed queue (no Redis for MVP)
- DLQ (dead-letter queue) for failed jobs
- Scheduled tasks (daily collection at 2 AM)
- Retry logic with exponential backoff
- Job timeout (prevent runaway tasks)

---

## Integration Points

**How completed components enable future work**:

✅ **Logger** → Used by all future components for structured logging
✅ **Document Model** → Used by all collectors to standardize data
✅ **Config System** → Drives collector initialization, LLM language detection, scheduling

**Next Components Will Use**:
- Component 4 (SQLite) uses `config.market.domain/market/language` for table partitioning
- Component 5 (LLM) uses `config.market.language` for language detection caching
- Component 6 (Dedup) uses Document model's `content_hash` and `canonical_url`
- Component 7 (Huey) uses `config.scheduling` for cron setup

---

## Success Criteria Met

✅ **TDD Compliance**: 100% (all tests written before implementation)
✅ **Coverage Target**: 96.23% (exceeds 80% requirement)
✅ **Import Circles**: None (dependency flow validated)
✅ **Test Execution**: <1 second for 60 tests
✅ **Documentation**: Complete (code examples, usage patterns, README)
✅ **Multi-Config Support**: Validated with 2 real-world configs

---

## Next Session Goals

**Week 1 Completion** (4 remaining components):
1. Implement Component 4 (Optimized SQLite)
2. Implement Component 5 (LLM Processor)
3. Implement Component 6 (Deduplicator)
4. Implement Component 7 (Huey Task Queue)

**Estimated**: 1-2 additional sessions to complete Week 1 Foundation

**Week 2 Preview** (after Week 1 complete):
- Feed Discovery Pipeline (2-stage: OPML + SerpAPI)
- RSS Collector (feedparser + trafilatura)
- Simple TF-IDF Clustering
- Deep Research Integration (gpt-researcher wrapper)

---

## Notes

- Established pattern for TDD workflow (3 components with 100% test-first)
- Configuration system validates multi-market support (German + French working)
- Foundation ready for intelligent feed discovery (seed keywords → SERP → feeds)
- All components use Pydantic V2 (no deprecation warnings)
- Structured logging provides excellent observability from day 1

**Cost Optimization Validated**:
- LLM-first strategy replaces 5GB of NLP dependencies
- qwen-turbo target: $0.003/month for MVP
- Gemini CLI: FREE (competitor + keyword research)
- Total agent cost target: ~$1/month

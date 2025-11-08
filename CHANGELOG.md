# Changelog

Recent development sessions (last 3 sessions, <100 lines).

## Session 040: Duplicate Rate Reduction - Autocomplete & Feed Filtering (2025-11-08)

**73% Improvement**: Reduced duplicate rate from 75.63% → 20.63% by fixing autocomplete noise and Wikipedia feed filtering.

**Root Causes Fixed**:
- Autocomplete noise: 304 low-value queries (alphabet a-z patterns) + template-based content (90% identical → false duplicates)
- Wikipedia feeds: 80 noisy docs from general encyclopedia (not PropTech-specific)

**3 Key Fixes**:
- Autocomplete default: ALL expansion types → QUESTIONS only (304 → 18 queries, 94% reduction)
- Autocomplete content: Template format → plain suggestion (prevents MinHash false positives)
- Feed discovery: Added Wikipedia domain blacklist (skips 4 noisy feeds)

**Results**: 143 → 63 total docs (56% reduction), 108 → 13 duplicates (88% reduction), 35 → 50 unique docs (43% increase)

**Test Results**: ✅ E2E test passing (20.63% < 30% target), ✅ 23/23 autocomplete unit tests passing

**See**: [Full details](docs/sessions/040-duplicate-rate-reduction.md)

---

## Session 039: RSS Collection Integration - Dual-Source Config Support (2025-11-07)

**RSS Collection Integrated**: Fixed RSS feed collection in UniversalTopicAgent with dual-source configuration support. Supports feeds from `market.rss_feeds` (HttpUrl), `collectors.custom_feeds` (strings), and discovered feeds.

**3 Key Fixes**:
- Fixed type mismatch: `market.rss_feeds` (HttpUrl) → string conversion, `collectors.custom_feeds` (strings) used as-is
- Added None checks: Both config sources can be optional without errors
- Enhanced ConfigLoader: Now parses 7 missing MarketConfig fields (rss_feeds, opml_file, reddit_subreddits, excluded_keywords, research settings)

**Configuration**:
- Updated `proptech_de.yaml` with 2 PropTech-specific RSS feeds
- Total feeds: 9 (2 market + 7 custom + discovered feeds)

**Test Results**: ✅ 6/6 new RSS integration tests passing, ✅ 20/20 config loader tests passing (no regressions)

**Architecture**: Three-source RSS system (discovered + market + custom) merges seamlessly, providing flexibility for industry-specific and general feeds.

**See**: [Full details](docs/sessions/039-rss-collection-integration.md)

---

## Session 038: FullConfig Standardization & Config System Consolidation (2025-11-07)

**Config System Unified**: Consolidated dual config systems into single source of truth (`src/utils/config_loader.py`). Eliminated 2-system confusion, added type safety, and automated enforcement via pre-commit hooks.

**10-Phase Consolidation**:
- Merged `models/config.py` (2 files) + `utils/config_loader.py` (26 files) → single canonical source
- Enriched MarketConfig with 7 missing fields (rss_feeds, opml_file, research settings)
- Added 4 new config classes (LLMConfig, SearchConfig, DatabaseConfig, NotionConfig)
- Renamed CollectorConfig → CollectorsConfig across 26 files for consistency
- Extended FullConfig to include all 7 sections (market, collectors, scheduling, llm, search, database, notion)

**Type Safety & Enforcement**:
- Updated ContentPipeline + UniversalTopicAgent to use `config: FullConfig` type hints (11 changes)
- Created pre-commit hook preventing MarketConfig parameters (`.pre-commit-config.yaml`)
- Fixed test fixture bug (MarketConfig → FullConfig wrapper)

**Test Results**: ✅ 169/169 config-related unit tests passing (5 unrelated external API failures)

**See**: [Full details](docs/sessions/038-fullconfig-standardization-consolidation.md)

---

*Older sessions archived in `docs/sessions/` directory*

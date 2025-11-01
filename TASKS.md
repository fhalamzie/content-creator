# Tasks

## High Priority (Phase 3: Streamlit UI)

- [ ] Create `streamlit_app.py` (main entry point, page routing)
- [ ] Setup page (brand voice, target audience, keywords configuration)
- [ ] Generate content page (topic input, progress bar, ETA display)
- [ ] Content browser (view cached posts, Notion database viewer)
- [ ] Settings page (API keys management, rate limits, model selection)
- [ ] Dashboard (stats, cost tracking, recent posts)

## Completed

**Phase 2 - Core Agents** ✅:
- [x] Create German prompts (blog_de.md, social_de.md) - 2 comprehensive templates
- [x] Write tests + implement `src/agents/base_agent.py` (100% coverage, 25 tests)
- [x] Write tests + implement `src/agents/research_agent.py` (97.06% coverage, 23 tests)
- [x] Write tests + implement `src/agents/writing_agent.py` (97.70% coverage, 22 tests)
- [x] Write tests + implement `src/notion_integration/sync_manager.py` (93.20% coverage, 22 tests)
- [x] Integration tests (11 tests) - Complete pipeline validation
- [x] Enhanced CacheManager (get_cached_blog_posts, get_cached_social_posts, save_blog_post)

**Phase 1 - Foundation** ✅:
- [x] Write tests + implement `src/cache_manager.py` (100% coverage, 24 tests)
- [x] Write tests + implement `src/notion_integration/rate_limiter.py` (100% coverage, 21 tests)
- [x] Write tests + implement `src/notion_integration/notion_client.py` (93.67% coverage, 23 tests)
- [x] Create `config/notion_schemas.py` (5 database schemas, 52 properties)
- [x] Create `config/settings.py` (environment validation, secret masking)
- [x] Implement `setup_notion.py` (5 Notion databases created successfully)
- [x] Test infrastructure (pytest.ini, .coveragerc, 97.70% overall coverage)

## Backlog

**Phase 4 - Repurposing Agent**:
- [ ] Repurposing agent (4 platforms: LinkedIn, Facebook, TikTok, Instagram)
- [ ] Social post templates integration (use social_de.md)
- [ ] Hashtag generation (platform-specific)
- [ ] Media suggestions (image descriptions for DALL-E 3)

**Phase 5 - Publishing Automation**:
- [ ] Platform publishers (LinkedIn, Facebook APIs)
- [ ] Publishing agent + background service (APScheduler)
- [ ] Publisher deployment (PM2 or Streamlit thread)
- [ ] Scheduled posting (calendar integration)

**Phase 6 - Enhancements**:
- [ ] Media creator (DALL-E 3 hero images)
- [ ] Analytics dashboard (performance tracking)
- [ ] Plagiarism checker integration
- [ ] Competitor monitoring
- [ ] A/B testing for social posts
- [ ] Multi-language support (add blog_en.md)

## Known Issues

- Notion API limitation: Relation properties require manual configuration in UI
  - Blog Posts → Project (relation)
  - Social Posts → Blog Post (relation)
  - Research Data → Blog Post (relation)

## Technical Debt

- [ ] Add disk space monitoring for cache directory
- [ ] Test Notion client with pagination (large result sets, >100 pages)
- [ ] Verify Gemini CLI integration stability (long-term monitoring)
- [ ] Test German content quality with native speakers
- [ ] Add secret rotation mechanism for API keys
- [ ] Consider cache cleanup strategy (auto-delete old posts)
- [ ] Add retry logic to cache operations (handle disk full errors)

## Success Criteria

**Phase 1** ✅: All tasks complete, cache system working (100% coverage), Notion connection (rate-limited, 93.67% coverage), 5 databases created, test infrastructure (97.70% coverage)

**Phase 2** ✅: German prompts created (2 templates), base agent working (100% coverage), research agent (Gemini CLI, 97.06% coverage), writing agent (Qwen3-Max, 97.70% coverage), sync manager (cache → Notion, 93.20% coverage), integration tests passing (11 tests), 171 total tests, 94.87% overall coverage

**Phase 3**: Streamlit UI functional (setup, generate, browse pages), progress tracking working, ETA display accurate, cost tracking visible, Notion integration seamless

**MVP**: Generate 10 German blog posts via UI, cache sync to Notion, edit in Notion, 4 social posts per blog (repurposing agent), cost target achieved (~$0.98/bundle), basic publishing working

**Production**: 100 posts generated/published, logging in place, documentation complete, publisher stable, German quality validated by native speakers, rate limiting working, analytics dashboard functional

## Notes

- **TDD**: Write tests before implementation
- **Coverage**: 80% minimum, 100% for critical paths
- **Cost Target**: ~$0.98/bundle

**Detailed info**: See [PLAN.md](PLAN.md) for comprehensive implementation plan

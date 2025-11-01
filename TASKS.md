# Tasks

## High Priority (Phase 2: Core Agents)

- [ ] Create German prompts (`config/prompts/blog_de.md`, `config/prompts/social_de.md`)
- [ ] Write tests + implement `src/agents/base_agent.py` (OpenRouter integration)
- [ ] Write tests + implement `src/agents/research_agent.py` (Gemini CLI integration)
- [ ] Write tests + implement `src/agents/writing_agent.py` (Qwen3-Max, German content)
- [ ] Write tests + implement `src/notion_integration/sync_manager.py` (cache → Notion sync)
- [ ] Integration test: Research → Writing → Cache → Notion workflow
- [ ] Create `streamlit_app.py` (setup page, progress tracking with ETA)

## Completed

**Phase 1 - Foundation** ✅:
- [x] Write tests + implement `src/cache_manager.py` (100% coverage, 24 tests)
- [x] Write tests + implement `src/notion_integration/rate_limiter.py` (100% coverage, 21 tests)
- [x] Write tests + implement `src/notion_integration/notion_client.py` (93.67% coverage, 23 tests)
- [x] Create `config/notion_schemas.py` (5 database schemas, 52 properties)
- [x] Create `config/settings.py` (environment validation, secret masking)
- [x] Implement `setup_notion.py` (5 Notion databases created successfully)
- [x] Test infrastructure (pytest.ini, .coveragerc, 97.70% overall coverage)

## Backlog

**Phase 3 - Repurposing**:
- [ ] Repurposing agent (4 platforms: LinkedIn, Facebook, TikTok, Instagram)
- [ ] Media creator (DALL-E 3, optional)
- [ ] End-to-end pipeline test

**Phase 4 - Publishing**:
- [ ] Platform publishers (LinkedIn, Facebook APIs)
- [ ] Publishing agent + background service (APScheduler)
- [ ] Publisher deployment (PM2 or Streamlit thread)

**Phase 5 - UI Enhancement**:
- [ ] Dashboard page (stats, upcoming/recent posts)
- [ ] Generate content page (project selector, topic input, progress bar)
- [ ] Settings page (API keys, rate limits, model selection)
- [ ] Error handling & logging
- [ ] User documentation

## Known Issues

- Notion API limitation: Relation properties require manual configuration in UI
  - Blog Posts → Project (relation)
  - Social Posts → Blog Post (relation)
  - Research Data → Blog Post (relation)

## Technical Debt

- [ ] Add integration test for full workflow (cache → Notion sync)
- [ ] Consider adding retry logic to cache operations (disk failures)
- [ ] Add disk space monitoring for cache directory
- [ ] Test Notion client with pagination (large result sets)
- [ ] Verify Gemini CLI integration stability (consider MCP fallback)
- [ ] Test German content quality with native speakers (post-Phase 2)
- [ ] Add secret rotation mechanism for API keys

## Success Criteria

**Phase 1** ✅: All tasks complete, cache system working (100% coverage), Notion connection (rate-limited, 93.67% coverage), 5 databases created, test infrastructure (97.70% coverage)

**Phase 2**: German prompts created, base agent working, research agent (Gemini CLI), writing agent (Qwen3-Max), sync manager (cache → Notion), integration test passing, Streamlit UI functional

**MVP**: Streamlit form, generate 10 German blog posts, cache sync to Notion, edit in Notion, 4 social posts per blog, background publisher working, cost target achieved (~$0.98/bundle)

**Production**: 100 posts generated/published, logging in place, documentation complete, publisher stable, German quality validated, rate limiting working

## Notes

- **TDD**: Write tests before implementation
- **Coverage**: 80% minimum, 100% for critical paths
- **Cost Target**: ~$0.98/bundle

**Detailed info**: See [PLAN.md](PLAN.md) for comprehensive implementation plan

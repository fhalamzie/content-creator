# Project-Specific Guidelines - Content Creator

This project follows the global development guidelines from `~/.claude/CLAUDE.md` with the following additions and overrides.

---

## Architecture Documentation

**Current MVP Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- Streamlit UI + Disk Cache + Notion integration
- 23k lines of Python, battle-tested
- $0.07-$0.10 per content bundle with images

**Target Production Architecture**: See [TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md)
- Modular Monolith with 4 domains (auth, research, content, publishing)
- FastAPI + React + Postgres + psycopg3
- Multi-tenant SaaS, JWT auth, role-based access
- Timeline: 4-6 weeks to MVP

---

## Project-Specific Tech Stack

### Current MVP
- Python 3.12+, Streamlit, Notion SDK
- OpenRouter (Qwen3-Max), Gemini CLI
- Huey (background jobs), pytest

### Target Production
- Backend: FastAPI 0.115, SQLAlchemy 2.0.35, Alembic 1.13.3, psycopg3
- Frontend: React 18.3.1, TypeScript 5.6.3, Vite 5.4.11, shadcn/ui
- Database: Postgres 16.6 (no Redis initially)
- Observability: structlog + Sentry + Prometheus

---

## Development Workflow

### Current Session Context
Use `/init` to load:
1. README.md - Project overview
2. ARCHITECTURE.md - Current MVP architecture
3. CHANGELOG.md - Recent work
4. TASKS.md - Current priorities

**Optional**: TARGET_ARCHITECTURE.md - Production SaaS plan (read only when planning migration)

### Migration Strategy
- Keep existing agents (research, writing, image generation)
- Wrap in FastAPI services (no logic rewrite)
- Build React frontend alongside Streamlit (dual-UI during transition)
- Dual-write to Postgres + disk cache (2 weeks validation)

---

## Cost Optimization Targets

**Current**: $0.07-$0.076 per topic with images
**Target**: Maintain <$0.10 per topic in production

**Infrastructure**: ~$40/month (up to 100 users)
- Postgres: $15, Compute: $20, S3: $2, Domain: $2

---

## Key Decisions (Session 050)

1. **Boilerplate**: Hybrid approach (tiangolo/full-stack-fastapi-template + custom frontend)
2. **Redis**: Start without, add at >100 concurrent users
3. **Multi-tenancy**: 1:1 user:org initially, role field ready for team expansion
4. **Domain structure**: 4 domains from start (auth, research, content, publishing)
5. **Observability**: structlog (JSON logs) + Sentry (errors) + Prometheus (metrics)

---

For global development standards (TDD, naming conventions, security, etc.), refer to `~/.claude/CLAUDE.md`.

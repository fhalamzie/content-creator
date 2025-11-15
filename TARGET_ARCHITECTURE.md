# Target Architecture - Production SaaS

**Status**: Planning (Session 050)
**Goal**: Transform MVP to production multi-tenant SaaS
**Timeline**: 4-6 weeks to MVP
**Approach**: Modular Monolith with Domain-Driven Design

---

## Architecture Overview

### Pattern: Modular Monolith
Single deployable application with clear domain boundaries. Can extract to microservices later if needed.

**Benefits**:
- Fast development (single codebase, simple deployment)
- Clear boundaries (each domain is isolated)
- Easy to extract (domains can become services later)
- Single DB transaction (simpler consistency)
- Claude Code friendly (manageable complexity)

**NOT Microservices Because**:
- Over-engineering for <1000 users
- Complex deployment overhead
- Harder to develop with single AI assistant
- Data consistency challenges

---

## Tech Stack (Latest Versions)

### Backend
| Component | Version | Purpose |
|-----------|---------|---------|
| **FastAPI** | 0.115.0 | Web framework, async, OpenAPI docs |
| **SQLAlchemy** | 2.0.35 | ORM with async support |
| **Alembic** | 1.13.3 | Database migrations |
| **Pydantic** | 2.9.2 | Data validation |
| **psycopg3** | 3.2.3 | Postgres driver (async, 30% faster) |
| **FastAPI-Users** | 13.0.0 | Auth + JWT + user management |
| **Huey** | 2.5.2 | Background jobs (keep existing) |
| **structlog** | 24.4.0 | Structured JSON logging |
| **Sentry-SDK** | 2.16.0 | Error tracking + APM |

### Frontend
| Component | Version | Purpose |
|-----------|---------|---------|
| **React** | 18.3.1 | UI framework |
| **TypeScript** | 5.6.3 | Type safety |
| **Vite** | 5.4.11 | Build tool (10x faster than Webpack) |
| **TanStack Query** | 5.59.20 | Server state management |
| **TanStack Router** | 1.77.0 | Type-safe routing |
| **shadcn/ui** | Latest | Accessible component library |
| **Tailwind CSS** | 3.4.15 | Utility-first CSS |
| **React Hook Form** | 7.53.2 | Form management |
| **Zod** | 3.23.8 | Client-side validation |

### Database & Infrastructure
| Component | Version | Purpose |
|-----------|---------|---------|
| **Postgres** | 16.6 | Primary database, pgvector built-in |
| **Redis** | - | NOT used initially (add at >100 users) |
| **Docker** | Latest | Containerization |
| **Docker Compose** | Latest | Local development |

---

## Domain Structure (4 Domains)

```
backend/
├── app/
│   ├── domains/
│   │   ├── auth/              # Authentication & Authorization
│   │   │   ├── models.py      # User, Organization
│   │   │   ├── schemas.py     # Pydantic models
│   │   │   ├── service.py     # Business logic
│   │   │   ├── router.py      # API routes
│   │   │   └── dependencies.py # get_current_user()
│   │   │
│   │   ├── research/          # Topic Discovery & Research
│   │   │   ├── models.py      # Topic, Research, Source
│   │   │   ├── schemas.py
│   │   │   ├── service.py     # Wrap orchestrator
│   │   │   ├── router.py
│   │   │   └── agents/        # Existing code
│   │   │       ├── orchestrator.py
│   │   │       ├── collectors/
│   │   │       ├── reranker/
│   │   │       └── synthesizer/
│   │   │
│   │   ├── content/           # Writing, Images, Blog Posts
│   │   │   ├── models.py      # BlogPost, Image
│   │   │   ├── schemas.py
│   │   │   ├── service.py     # Wrap agents
│   │   │   ├── router.py
│   │   │   └── agents/
│   │   │       ├── writing_agent.py
│   │   │       └── image_generator.py
│   │   │
│   │   └── publishing/        # Social Posts, Scheduling, Platforms
│   │       ├── models.py      # SocialPost, Schedule, PublishLog
│   │       ├── schemas.py
│   │       ├── service.py     # Publishing logic
│   │       ├── router.py
│   │       └── publishers/
│   │           ├── linkedin.py
│   │           └── facebook.py
│   │
│   ├── core/                  # Shared Infrastructure
│   │   ├── config.py          # Settings (Pydantic BaseSettings)
│   │   ├── database.py        # SQLAlchemy engine, sessions
│   │   ├── security.py        # JWT, password hashing
│   │   ├── logging.py         # structlog configuration
│   │   ├── exceptions.py      # Custom exceptions
│   │   └── dependencies.py    # Global FastAPI deps
│   │
│   └── main.py                # FastAPI app entry point
│
├── alembic/                   # Database migrations
├── tests/
│   ├── domains/               # Mirror domain structure
│   └── conftest.py
└── docker-compose.yml

frontend/
├── src/
│   ├── components/            # shadcn/ui + custom components
│   ├── pages/                 # Route pages
│   ├── lib/                   # API client, utils
│   ├── hooks/                 # Custom React hooks
│   └── main.tsx
├── package.json
└── vite.config.ts
```

### Domain Communication Rules
1. **No direct imports between domains** - Use service interfaces
2. **Each domain owns its data** - No cross-domain DB queries
3. **Services coordinate domains** - Higher-level orchestration
4. **Shared code in core/** - Common utilities only

---

## Database Schema

### Multi-Tenancy (1:1 User:Org, Expandable)

```sql
-- Phase 1: Simple 1:1
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'owner',  -- owner, admin, member (ready for expansion)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Phase 2: Team expansion (future)
-- CREATE TABLE org_members (
--     id UUID PRIMARY KEY,
--     org_id UUID REFERENCES organizations(id),
--     user_id UUID REFERENCES users(id),
--     role VARCHAR(50),
--     permissions JSONB,
--     UNIQUE(org_id, user_id)
-- );
```

### Research Domain

```sql
CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    keywords JSONB,               -- Flexible keyword storage
    research_data JSONB,          -- Full research results
    status VARCHAR(50) DEFAULT 'discovered',  -- discovered, researched, written
    score FLOAT,                  -- Topic validation score
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_topics_org_status ON topics(org_id, status);
CREATE INDEX idx_topics_created_at ON topics(created_at DESC);

CREATE TABLE research_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    url VARCHAR(1000) NOT NULL,
    title VARCHAR(500),
    content TEXT,
    backend VARCHAR(50),          -- tavily, searxng, gemini, rss, news
    relevance_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sources_topic ON research_sources(topic_id);
```

### Content Domain

```sql
CREATE TABLE blog_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    topic_id UUID REFERENCES topics(id) ON DELETE SET NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT,                 -- Markdown content
    excerpt VARCHAR(1000),
    hero_image_url VARCHAR(1000),
    metadata JSONB,               -- SEO, keywords, word_count, etc.
    status VARCHAR(50) DEFAULT 'draft',  -- draft, ready, scheduled, published
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_blog_posts_org_status ON blog_posts(org_id, status);
CREATE INDEX idx_blog_posts_published ON blog_posts(published_at DESC) WHERE published_at IS NOT NULL;

CREATE TABLE images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blog_post_id UUID REFERENCES blog_posts(id) ON DELETE CASCADE,
    url VARCHAR(1000) NOT NULL,
    type VARCHAR(50),             -- hero, supporting
    model VARCHAR(100),           -- flux-ultra, flux-dev, juggernaut-xl
    prompt TEXT,
    cost_usd DECIMAL(10, 6),
    metadata JSONB,               -- width, height, aspect, etc.
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_images_blog_post ON images(blog_post_id);
```

### Publishing Domain

```sql
CREATE TABLE social_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    blog_post_id UUID REFERENCES blog_posts(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    platform VARCHAR(50) NOT NULL,  -- linkedin, facebook, twitter, instagram
    content TEXT NOT NULL,
    media_urls JSONB,               -- Array of image URLs
    hashtags JSONB,                 -- Array of hashtags
    status VARCHAR(50) DEFAULT 'draft',  -- draft, scheduled, published, failed
    scheduled_for TIMESTAMP,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_social_posts_org_platform ON social_posts(org_id, platform);
CREATE INDEX idx_social_posts_scheduled ON social_posts(scheduled_for) WHERE status = 'scheduled';

CREATE TABLE publish_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    social_post_id UUID REFERENCES social_posts(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    platform_post_id VARCHAR(255),  -- External platform ID
    metadata JSONB,                 -- Platform-specific response data
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_publish_logs_post ON publish_logs(social_post_id);
CREATE INDEX idx_publish_logs_created ON publish_logs(created_at DESC);
```

### Usage & Analytics (Optional Phase 3)

```sql
CREATE TABLE api_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    endpoint VARCHAR(255),
    method VARCHAR(10),
    status_code INT,
    duration_ms INT,
    cost_usd DECIMAL(10, 6),      -- AI API costs
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_api_usage_org_created ON api_usage(org_id, created_at DESC);
```

---

## Logging & Observability

### 3-Tier Strategy

**Tier 1: Structured Logging (Built-in)**
- Library: `structlog` with JSON output
- Every request: `request_id`, `user_id`, `org_id`, `endpoint`, `duration_ms`, `status_code`
- Every error: `error_type`, `stack_trace`, `context`
- AI API calls: `model`, `tokens`, `cost_usd`, `latency_ms`
- Background jobs: `job_id`, `task_name`, `status`, `duration_ms`

**Tier 2: Error Tracking (Sentry)**
- Free tier: 5k events/month
- Automatic error capture
- Performance monitoring (transaction traces)
- User context attached (user_id, org_id)
- Release tracking

**Tier 3: Metrics (Prometheus + Grafana)**
- Self-hosted (free)
- Track: API latency (P50, P95, P99), error rate, queue depth, DB connections
- Dashboards: System health, cost tracking, user activity
- Alerts: Error rate >1%, API latency >500ms

### Implementation Checklist
- ✅ Request ID in all logs (UUID per request)
- ✅ User context in errors (who, what, when)
- ✅ Cost tracking per request (AI API costs)
- ✅ Performance spans (identify slow operations)
- ✅ Health check endpoints (`/health`, `/ready`)

---

## Boilerplate Strategy: Hybrid Approach

### Starting Point
**Template**: [tiangolo/full-stack-fastapi-template](https://github.com/tiangolo/full-stack-fastapi-template)

### What to Keep
- ✅ Backend core: Auth, DB setup, migrations, Docker
- ✅ Security: CORS, headers, JWT implementation
- ✅ Database: SQLAlchemy 2.0 + Alembic configuration
- ✅ Testing: pytest setup, fixtures

### What to Replace
- ❌ Frontend: Delete React app, build custom with Vite + shadcn/ui
- ❌ Celery: Swap for Huey (existing background jobs)
- ❌ Traefik: Use nginx later (simpler)
- ❌ pgAdmin: Use TablePlus/DBeaver locally

### What to Add
- ➕ Domain structure: 4 domains (auth, research, content, publishing)
- ➕ Existing agents: Wrap in services
- ➕ structlog: Replace basic logging
- ➕ Sentry: Error tracking
- ➕ Cost tracking: AI API usage

### Migration Steps
1. Clone template → Understand structure (1 day)
2. Replace frontend → Vite + shadcn/ui (1 day)
3. Swap Celery → Huey (1 day)
4. Add domain structure (1 day)
5. Wrap existing agents (2-3 days)

**Total Setup**: 1 week to working foundation

---

## Migration from Current MVP

### Phase 1: Dual-Write Strategy
**Goal**: Zero data loss during transition

1. **Setup Postgres + Alembic** - Create all tables
2. **Dual-write agents** - Save to both disk cache AND database
3. **Validate for 2 weeks** - Compare disk vs DB results
4. **Switch reads to DB** - Start querying Postgres
5. **Remove disk writes** - Keep only as backup
6. **Archive disk cache** - Keep for 6 months, then delete

### Phase 2: API Migration
**Goal**: Decouple UI from business logic

1. **Wrap existing agents in services** - No logic changes
2. **Create FastAPI endpoints** - Call services
3. **Build React pages one-by-one** - Replace Streamlit pages
4. **Keep Streamlit as admin panel** - Internal tools
5. **Deprecate Streamlit after 6 months** - Full React migration

### Data Migration Script
```python
# Example: Migrate disk cache topics to Postgres
async def migrate_topics_from_disk():
    cache_dir = Path("cache/research/")
    for file in cache_dir.glob("*_research.json"):
        data = json.loads(file.read_text())
        topic = Topic(
            org_id=default_org_id,
            title=data["title"],
            keywords=data["keywords"],
            research_data=data
        )
        db.add(topic)
    await db.commit()
```

---

## Infrastructure Decisions

### No Redis (Initially)
**Why Not:**
- Sessions: JWT stateless (no storage needed)
- Cache: Postgres JSONB + Python in-memory
- Queue: Huey with SQLite backend (works for <100 concurrent jobs)

**Add Redis When:**
- >100 concurrent users (session cache beneficial)
- >1000 background jobs/day (Redis queue faster)
- Real-time features (WebSockets, pub/sub)

### psycopg3 vs psycopg2
**Choice**: psycopg3
- 30% faster than psycopg2
- Native async support (required for SQLAlchemy 2.0 async)
- Better type hints
- Modern API

```python
# SQLAlchemy async engine with psycopg3
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+psycopg://user:pass@localhost/db",
    echo=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)
```

### Background Jobs: Keep Huey
**Why:**
- Already integrated (2 AM daily, Monday sync)
- Simple API (decorators, no boilerplate)
- SQLite backend (no Redis needed)
- Good for <1000 jobs/day

**Huey Setup:**
```python
# config/huey.py
from huey import SqliteHuey

huey = SqliteHuey(filename='huey.db')

@huey.task()
async def discover_topics_task(org_id: str, config: dict):
    service = ResearchService()
    return await service.discover_topics(org_id, config)
```

---

## Development Timeline

### Week 1: Foundation
- **Day 1-2**: Setup boilerplate, understand structure
- **Day 3**: Replace frontend (Vite + shadcn/ui skeleton)
- **Day 4**: Swap Celery → Huey
- **Day 5**: Add domain structure folders

**Deliverable**: Dev environment running, auth working (login/register)

### Week 2-3: Research Domain
- **Day 6-7**: Research models + schemas + repository
- **Day 8-9**: Wrap HybridResearchOrchestrator in service
- **Day 10-11**: Research API endpoints + tests
- **Day 12-13**: React pages (topic discovery, list, detail)

**Deliverable**: Users can discover and view topics via API

### Week 4-5: Content Domain
- **Day 14-15**: Content models + schemas
- **Day 16-17**: Wrap WritingAgent, ImageGenerator in service
- **Day 18-19**: Content API + tests
- **Day 20-21**: React pages (generate, edit, preview)

**Deliverable**: Users can generate blog posts with images

### Week 6: Publishing + Polish
- **Day 22-23**: Publishing models + social post generation
- **Day 24**: LinkedIn/Facebook publishers (basic)
- **Day 25**: React publishing page (schedule, calendar)
- **Day 26-28**: Docker production setup, deployment, testing

**Deliverable**: MVP deployed, users can publish content

---

## Security Checklist

### Application Security
- ✅ Password hashing: bcrypt (built into FastAPI-Users)
- ✅ JWT tokens: Short expiry (15 min access, 7 day refresh)
- ✅ CORS: Whitelist frontend domain only
- ✅ Rate limiting: Per user/org (10 req/sec)
- ✅ Input validation: Pydantic on all endpoints
- ✅ SQL injection: Parameterized queries (SQLAlchemy ORM)
- ✅ XSS prevention: Sanitize markdown output

### Infrastructure Security
- ✅ Secrets: Environment variables (never commit)
- ✅ HTTPS: TLS 1.3 minimum
- ✅ Database: Encrypted at rest (RDS default)
- ✅ API keys: Rotate monthly
- ✅ Logs: No sensitive data (mask passwords, tokens)

### OWASP Top 10 Compliance
- A01:2021 – Broken Access Control: ✅ RBAC, org_id checks
- A02:2021 – Cryptographic Failures: ✅ bcrypt, HTTPS, encrypted DB
- A03:2021 – Injection: ✅ ORM, Pydantic validation
- A07:2021 – Identification/Authentication Failures: ✅ FastAPI-Users, JWT

---

## Cost Analysis

### Development (Claude Code Hours)
- **Phase 1 (Foundation)**: 40-60 hours
- **Phase 2 (Research)**: 40-60 hours
- **Phase 3 (Content)**: 40-60 hours
- **Phase 4 (Publishing)**: 40-60 hours
- **Total**: 160-240 hours (~4-6 weeks full-time)

### Infrastructure (Monthly)
- **Postgres** (AWS RDS t4g.micro): $15
- **Compute** (AWS ECS Fargate 0.5 vCPU): $20
- **S3 Storage** (100 GB): $2
- **Sentry** (Free tier): $0
- **Domain + SSL**: $2
- **Total**: ~$40/month (up to 100 users)

### AI API Costs (No Change)
- Research: FREE (Gemini) or $0.02 (Tavily fallback)
- Writing: $0.01 (Qwen3-Max)
- Images: $0.06-$0.076 (Flux Ultra + Dev)
- **Per bundle**: $0.07-$0.10 (same as current)

---

## Success Metrics

### Technical KPIs
- **API Response Time**: <200ms (P95)
- **Error Rate**: <1%
- **Test Coverage**: >80%
- **Database Query Time**: <50ms (P95)
- **Background Job Success**: >99%

### Business KPIs
- **User Onboarding**: <5 min to first topic
- **Content Generation**: <3 min per article
- **Publishing Success**: >95%
- **System Uptime**: >99.5%
- **Cost per User**: <$50/month (infra + AI)

---

## Future Enhancements (Post-MVP)

### Phase 5: Team Collaboration
- Invite team members
- Role-based permissions (admin, member, viewer)
- Approval workflows
- Comments on posts

### Phase 6: Advanced Features
- Billing (Stripe integration)
- Usage-based pricing
- API rate limiting per plan
- Analytics dashboard
- Content calendar
- Multi-language support

### Phase 7: Scale
- Microservices extraction (if >1000 users)
- Kubernetes deployment
- Multi-region (global latency)
- CDN for images (CloudFront)
- Redis cluster (caching + queue)

---

## References

- **FastAPI**: https://fastapi.tiangolo.com/
- **SQLAlchemy 2.0**: https://docs.sqlalchemy.org/en/20/
- **Alembic**: https://alembic.sqlalchemy.org/
- **FastAPI-Users**: https://fastapi-users.github.io/fastapi-users/
- **TanStack Query**: https://tanstack.com/query/latest
- **shadcn/ui**: https://ui.shadcn.com/
- **structlog**: https://www.structlog.org/
- **Sentry**: https://sentry.io/
- **Boilerplate**: https://github.com/tiangolo/full-stack-fastapi-template

---

**Document Version**: 1.0
**Last Updated**: 2025-11-15 (Session 050)
**Status**: Approved - Ready for Implementation

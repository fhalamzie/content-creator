# Notion Database Schema Migrations

**Purpose:** Document all changes to Notion database schemas over time

---

## Migration Log

### Initial Schema - 2025-11-01

**Created by:** System Setup
**Notion Databases:** 5 databases created

#### 1. Projects Database

Properties:
- Name (title)
- SaaS URL (url)
- Description (text)
- Target Audience (multi-select)
- Problems Solved (rich text)
- Brand Voice (select)
- Primary Keywords (multi-select)
- Competitors (relation → Competitors DB)
- Content Volume (number)
- Platforms (multi-select)
- Status (select)
- Created Date (created time)
- Last Generated (date)

**Rationale:** Store project/brand configurations for multi-project support

---

#### 2. Blog Posts Database

Properties:
- Title (title) ⭐
- Status (select) ⭐ - Draft, Ready, Scheduled, Published
- Content (page content) - German blog posts
- Excerpt (text) - Meta description (150-160 chars)
- Project (relation → Projects DB)
- Keywords (multi-select)
- Hero Image (file)
- Scheduled Date (date)
- Published Date (date)
- SEO Score (number)
- Word Count (number)
- Reading Time (number)
- Authoritative Sources (rich text)
- Internal Links (multi-select)
- CTA Links (url)
- Category (select) - Top/Middle/Bottom funnel
- Research Data (relation → Research DB)
- Platform URL (url) - Published URL
- Created (created time)
- Updated (last edited time)

**Rationale:** Primary content editing interface for blog posts

---

#### 3. Social Posts Database

Properties:
- Title (title)
- Platform (select) ⭐ - LinkedIn, Facebook, TikTok, Instagram
- Content (page content) - German social media content
- Blog Post (relation → Blog Posts DB)
- Project (relation → Projects DB)
- Media (files)
- Hashtags (multi-select)
- Status (select) - Draft, Ready, Scheduled, Published
- Scheduled Date (date)
- Published Date (date)
- Platform URL (url) - Published post URL
- Engagement (number) - Likes/shares
- Created (created time)

**Rationale:** Social media content management (4 platforms per blog post)

---

#### 4. Research Data Database

Properties:
- Topic (title)
- Keywords (multi-select)
- Sources (rich text) - URLs, articles, studies
- Competitor Gap Analysis (rich text)
- Trending Insights (rich text)
- Search Volume (number)
- Competition Level (select) - Low, Medium, High
- Recommended Angle (text)
- Created Date (created time)
- Used In (relation → Blog Posts DB)

**Rationale:** SEO research and keyword strategy tracking

---

#### 5. Competitors Database

Properties:
- Company Name (title)
- Website (url)
- Blog URL (url)
- Facebook Page (url)
- LinkedIn Page (url)
- Instagram Handle (text)
- TikTok Handle (text)
- Project (relation → Projects DB)
- Target Audience (multi-select)
- Content Strategy (rich text)
- Content Frequency (number)
- Top Performing Topics (multi-select)
- Last Analyzed (date)
- Status (select) - Active, Archived

**Rationale:** Competitor tracking and content gap analysis

---

## Future Migrations

Document all schema changes here:

### Template:

```markdown
### Migration [Number] - [Date]

**Changed by:** [Name/System]
**Database:** [Database Name]
**Type:** [Added Property / Removed Property / Modified Property / New Database]

**Changes:**
- [Description of changes]

**Rationale:**
[Why this change was made]

**Backward Compatibility:**
[How to handle existing data]

**Migration Script:**
[Python script or manual steps if needed]
```

---

## Schema Versioning

**Current Version:** v1.0.0
**Last Updated:** 2025-11-01

### Version History:
- **v1.0.0** (2025-11-01) - Initial schema creation

---

## Notes

- Always test schema changes in a development Notion workspace first
- Document all property type changes (may affect existing data)
- Relation changes require updating both databases
- Consider data migration scripts for breaking changes

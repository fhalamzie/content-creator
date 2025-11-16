# Hub + Spoke Content Strategy

Complete guide to implementing topical authority clusters for SEO dominance.

---

## Overview

The Hub + Spoke strategy organizes content into topical clusters to establish authority and boost SEO rankings.

**Structure**:
- **1 Hub Article**: Comprehensive pillar content (3000 words)
- **7 Spoke Articles**: Specific angles (1500-2500 words each)
- **Internal Linking**: Bidirectional links (hub ↔ spokes)

**Benefits**:
- **Topical Authority**: Own a niche, dominate search rankings
- **Internal Linking Boost**: 30% SEO improvement
- **Organic Traffic**: 2-5x increase within 6 months
- **Lower Competition**: Unique cross-topic insights

**Timeline**: 1 hour planning + 8 weeks execution (2 articles/week)

**Cost**: Same as current ($0.072-$0.082/article)

---

## How It Works

### 1. Cluster Planning (Week 0)

Define your cluster topic and create a content plan.

**Example Cluster: "PropTech Automation 2025"**
```
Cluster ID: proptech-automation-2025
Target Keywords: PropTech automation, AI real estate, property management technology
Description: Comprehensive coverage of automation in property technology for 2025
```

**Hub Article** (Week 1, 3000 words):
- Title: "Complete Guide to PropTech Automation in 2025"
- Comprehensive pillar content covering all aspects
- Links to all 7 spoke articles

**Spoke Articles** (Weeks 2-8, 1500-2500 words each):
1. "AI-Powered Property Valuation: Tools and Techniques"
2. "Smart Building Management Systems: ROI Analysis"
3. "Automated Tenant Screening: Best Practices"
4. "PropTech CRM Integration Strategies"
5. "Predictive Maintenance with IoT Sensors"
6. "Virtual Property Tours: Technology Stack"
7. "Blockchain in Real Estate Transactions"

### 2. Create Cluster Plan

Use the `ClusterManager` to create a plan:

```python
from src.synthesis.cluster_manager import ClusterManager, ClusterPlan
from src.database.sqlite_manager import SQLiteManager

# Initialize
db = SQLiteManager("data/topics.db")
cluster_mgr = ClusterManager(db)

# Create cluster plan
plan = cluster_mgr.create_cluster_plan(
    cluster_id="proptech-automation-2025",
    hub_topic="Complete Guide to PropTech Automation in 2025",
    spoke_topics=[
        "AI-Powered Property Valuation: Tools and Techniques",
        "Smart Building Management Systems: ROI Analysis",
        "Automated Tenant Screening: Best Practices",
        "PropTech CRM Integration Strategies",
        "Predictive Maintenance with IoT Sensors",
        "Virtual Property Tours: Technology Stack",
        "Blockchain in Real Estate Transactions"
    ],
    target_keywords=[
        "PropTech automation",
        "AI real estate",
        "property management technology",
        "smart building systems",
        "real estate automation"
    ],
    description="Comprehensive coverage of automation in property technology for 2025"
)

# Save plan (optional - for reference)
import json
with open("docs/clusters/proptech-automation-2025.json", "w") as f:
    json.dump(plan.to_dict(), f, indent=2)
```

### 3. Generate Hub Article (Week 1)

Generate the hub article with cluster context:

```python
from src.agents.writing_agent import WritingAgent

# Initialize agent
agent = WritingAgent(
    api_key="your-api-key",
    language="de",
    db_path="data/topics.db"
)

# Generate hub article
result = agent.write_blog(
    topic="Complete Guide to PropTech Automation in 2025",
    research_data=research_results,  # From ResearchAgent
    topic_id="proptech-automation-2025-hub",
    cluster_id="proptech-automation-2025",
    cluster_role="Hub",
    brand_voice="Professional",
    target_audience="Property managers and real estate professionals"
)

# Result includes internal link suggestions
print(f"Content: {result['content']}")
print(f"Internal Links: {result['internal_link_suggestions']}")
```

### 4. Generate Spoke Articles (Weeks 2-8)

Generate each spoke article with automatic linking to hub:

```python
# Week 2: Spoke 1
result = agent.write_blog(
    topic="AI-Powered Property Valuation: Tools and Techniques",
    research_data=research_results,
    topic_id="ai-property-valuation",
    cluster_id="proptech-automation-2025",
    cluster_role="Spoke",
    brand_voice="Professional",
    target_audience="Property managers and real estate professionals"
)

# Automatic internal linking:
# - Links to hub article
# - Links to related spokes (if available)
# - Suggestions in result['internal_link_suggestions']
```

### 5. Track Cluster Progress

Monitor cluster completion:

```python
# Get cluster statistics
stats = cluster_mgr.get_cluster_stats("proptech-automation-2025")

print(f"Hub exists: {stats['has_hub']}")
print(f"Spokes completed: {stats['spoke_count']}/7")
print(f"Total articles: {stats['total_articles']}/8")
print(f"Completion: {stats['completion_percentage']:.0f}%")
```

---

## Notion Integration

### Adding Cluster Fields to Blog Posts Database

The cluster fields are automatically added to your Notion Blog Posts database:

1. **Cluster ID** (Text): Unique cluster identifier
2. **Cluster Role** (Select): Hub | Spoke | Standalone
3. **Internal Links** (Text): JSON array of suggested links

**Syncing to Notion**:
```python
# Cluster metadata is automatically included in Notion sync
# Fields are populated from WritingAgent result metadata
```

---

## Internal Linking Best Practices

### Automatic Suggestions

The `ClusterManager` generates internal link suggestions:

```python
# Get suggestions for an article
suggestions = cluster_mgr.suggest_internal_links(
    topic_id="ai-property-valuation",
    cluster_id="proptech-automation-2025",
    max_links=5
)

for link in suggestions:
    print(f"Link to: {link.title}")
    print(f"Anchor text: {link.anchor_text}")
    print(f"Context: {link.context}")
    print(f"URL: /blog/{link.slug}")
    print("---")
```

### Linking Strategy

**Hub to Spokes**:
- Link to ALL 7 spoke articles
- Use descriptive anchor text: "AI-powered property valuation"
- Place links naturally in relevant sections

**Spokes to Hub**:
- ALWAYS link to hub article
- Anchor text: "comprehensive guide to PropTech automation"
- Early in article (within first 300 words)

**Spokes to Spokes**:
- Link to 2-3 related spokes
- Use natural anchor text from related topics
- Place in contextually relevant sections

---

## SEO Impact

### Topical Authority Signals

**Google Ranking Factors**:
1. **Comprehensive Coverage**: Hub article shows expertise
2. **Internal Linking**: Signals topic relationships
3. **Fresh Content**: Regular spoke articles (2/week)
4. **Unique Insights**: Cross-topic synthesis differentiates from competitors

### Expected Results

**Timeline**:
- **Weeks 1-4**: Hub article ranks for long-tail keywords
- **Weeks 5-12**: Spoke articles start ranking
- **Months 3-6**: Cluster dominates niche searches
- **Months 6-12**: Top 3 rankings for target keywords

**Traffic Growth**:
- **Month 1**: Baseline (hub only)
- **Month 2**: +50% (3-4 spokes published)
- **Month 3**: +150% (all 8 articles published)
- **Month 6**: +300-500% (rankings improve, backlinks accumulate)

---

## Advanced: Multiple Clusters

### Planning Multiple Clusters

Run 2-3 clusters simultaneously for faster growth:

**Example: 3 Clusters in Parallel**
```
Cluster 1: PropTech Automation (Weeks 1-8)
Cluster 2: Remote Work Technology (Weeks 3-10)
Cluster 3: AI Content Marketing (Weeks 5-12)
```

**Publishing Schedule** (3 articles/week):
- Week 1: Hub 1
- Week 2: Spoke 1.1, Spoke 1.2
- Week 3: Hub 2, Spoke 1.3
- Week 4: Spoke 2.1, Spoke 1.4
- ... and so on

### Cluster Selection Criteria

**Choose Niches Where**:
1. **Low Competition**: Keyword difficulty < 40
2. **High Intent**: Commercial or transactional keywords
3. **Your Expertise**: Existing research or knowledge
4. **Audience Fit**: Target audience searches for these topics

**Tools**:
- Use Hybrid Research Orchestrator to discover cluster topics
- Analyze Topic Validation scores (Phase 4.5)
- Check search volume and competition

---

## Examples

### Example 1: SaaS Marketing Cluster

```
Cluster ID: saas-marketing-2025
Hub: "Complete SaaS Marketing Guide for 2025"
Spokes:
  1. "SaaS SEO: On-Page Optimization Strategies"
  2. "Product-Led Growth: Implementation Framework"
  3. "SaaS Email Marketing Automation"
  4. "Pricing Page Optimization for SaaS"
  5. "SaaS Customer Onboarding Best Practices"
  6. "Content Marketing for Early-Stage SaaS"
  7. "SaaS Analytics: Metrics That Matter"
```

### Example 2: Remote Work Cluster

```
Cluster ID: remote-work-tech-2025
Hub: "Remote Work Technology Stack: Complete Guide"
Spokes:
  1. "Best Video Conferencing Tools Comparison"
  2. "Project Management Software for Remote Teams"
  3. "Remote Team Communication Strategies"
  4. "Cybersecurity for Distributed Workforces"
  5. "Time Zone Management Tools and Techniques"
  6. "Virtual Team Building Activities"
  7. "Remote Work Performance Monitoring Tools"
```

---

## Troubleshooting

### Common Issues

**Issue: Spoke articles don't link to hub**
- Solution: Ensure `cluster_id` is provided in `write_blog()` call
- Check that hub article exists in database with same `cluster_id`

**Issue: No internal link suggestions**
- Solution: Ensure `topic_id` is provided (required for link generation)
- Verify cluster articles exist in database

**Issue: Cluster stats show 0 articles**
- Solution: Check `cluster_id` spelling is consistent
- Verify articles are saved to database with correct cluster metadata

---

## API Reference

### ClusterPlan

Create a cluster plan:
```python
plan = ClusterPlan(
    cluster_id="unique-id",
    hub_topic="Hub Article Title",
    spoke_topics=["Spoke 1", "Spoke 2", ..., "Spoke 7"],  # Exactly 7
    target_keywords=["keyword1", "keyword2"],
    description="Optional description"
)
```

### ClusterManager

Main cluster operations:

```python
# Initialize
cluster_mgr = ClusterManager(db_manager)

# Create plan
plan = cluster_mgr.create_cluster_plan(...)

# Get cluster articles
articles = cluster_mgr.get_cluster_articles(cluster_id)

# Suggest internal links
links = cluster_mgr.suggest_internal_links(topic_id, cluster_id)

# Get statistics
stats = cluster_mgr.get_cluster_stats(cluster_id)
```

### WritingAgent with Clusters

Generate clustered content:

```python
agent = WritingAgent(api_key="...", db_path="data/topics.db")

result = agent.write_blog(
    topic="Article Title",
    topic_id="unique-topic-id",
    cluster_id="cluster-id",  # Optional
    cluster_role="Hub" | "Spoke" | "Standalone",  # Optional
    # ... other parameters
)

# Access cluster data
print(result['metadata']['cluster_id'])
print(result['metadata']['cluster_role'])
print(result['internal_link_suggestions'])
```

---

## Next Steps

1. **Plan Your First Cluster**: Choose a niche to dominate
2. **Create Cluster Plan**: Define hub + 7 spokes
3. **Generate Hub Article**: Week 1 (comprehensive pillar)
4. **Generate Spoke Articles**: Weeks 2-8 (2/week, 1500-2500 words)
5. **Track Progress**: Monitor cluster completion
6. **Measure Results**: Track rankings and traffic (6-month horizon)

---

## Resources

- [Cross-Topic Synthesis](../src/synthesis/cross_topic_synthesizer.py) - Find related topics
- [Cluster Manager](../src/synthesis/cluster_manager.py) - Cluster operations
- [Writing Agent](../src/agents/writing_agent.py) - Content generation with clustering
- [Notion Schemas](../config/notion_schemas.py) - Database fields

---

**Last Updated**: Session 069 (2025-11-16)

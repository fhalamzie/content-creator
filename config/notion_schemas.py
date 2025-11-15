"""
Notion Database Schemas

Defines the property schemas for all 5 Notion databases.
These schemas are used by setup_notion.py to create databases.

Notion Property Types:
- title: Database title (required, one per database)
- rich_text: Long text fields
- select: Single-select dropdown
- multi_select: Multi-select dropdown
- number: Numeric fields
- date: Date/datetime fields
- url: URL fields
- relation: Links to other databases
- status: Status with workflow

Reference: https://developers.notion.com/reference/property-object
"""

# ==================== 1. Projects Database ====================

PROJECTS_SCHEMA = {
    "title": "Projects",
    "properties": {
        "Name": {
            "title": {}  # Database title (project name)
        },
        "SaaS URL": {
            "url": {}
        },
        "Target Audience": {
            "rich_text": {}
        },
        "Brand Voice": {
            "select": {
                "options": [
                    {"name": "Professional", "color": "blue"},
                    {"name": "Casual", "color": "green"},
                    {"name": "Technical", "color": "purple"},
                    {"name": "Friendly", "color": "yellow"}
                ]
            }
        },
        "Keywords": {
            "multi_select": {
                "options": []  # Dynamically added
            }
        },
        "Content Volume": {
            "select": {
                "options": [
                    {"name": "2 posts/week", "color": "gray"},
                    {"name": "4 posts/week", "color": "green"},
                    {"name": "Daily", "color": "blue"}
                ]
            }
        },
        "Description": {
            "rich_text": {}
        },
        "Created": {
            "date": {}
        }
    }
}

# ==================== 2. Blog Posts Database ====================

BLOG_POSTS_SCHEMA = {
    "title": "Blog Posts",
    "properties": {
        "Title": {
            "title": {}  # Post title
        },
        "Status": {
            "select": {
                "options": [
                    {"name": "Draft", "color": "gray"},
                    {"name": "Ready", "color": "green"},
                    {"name": "Scheduled", "color": "yellow"},
                    {"name": "Published", "color": "blue"}
                ]
            }
        },
        "Project": {
            "relation": {
                "database_id": None,  # Set dynamically to Projects DB
                "type": "single_property"
            }
        },
        "Content": {
            "rich_text": {}  # Full blog post content (markdown)
        },
        "Excerpt": {
            "rich_text": {}  # Short summary (150-200 chars)
        },
        "Keywords": {
            "multi_select": {
                "options": []  # Dynamically added
            }
        },
        "Hero Image URL": {
            "url": {}
        },
        "Scheduled Date": {
            "date": {}
        },
        "Published Date": {
            "date": {}
        },
        "SEO Score": {
            "number": {
                "format": "number"
            }
        },
        "Word Count": {
            "number": {
                "format": "number"
            }
        },
        "Citations": {
            "rich_text": {}  # JSON array of sources
        },
        "Slug": {
            "rich_text": {}  # URL-friendly slug
        },
        "Created": {
            "date": {}
        }
    }
}

# ==================== 3. Social Posts Database ====================

SOCIAL_POSTS_SCHEMA = {
    "title": "Social Posts",
    "properties": {
        "Title": {
            "title": {}  # Auto-generated: "{Blog Title} - {Platform}"
        },
        "Platform": {
            "select": {
                "options": [
                    {"name": "LinkedIn", "color": "blue"},
                    {"name": "Facebook", "color": "blue"},
                    {"name": "Instagram", "color": "purple"},
                    {"name": "TikTok", "color": "red"}
                ]
            }
        },
        "Blog Post": {
            "relation": {
                "database_id": None,  # Set dynamically to Blog Posts DB
                "type": "single_property"
            }
        },
        "Content": {
            "rich_text": {}  # Platform-optimized content
        },
        "Media URL": {
            "url": {}  # Image/video URL
        },
        "Hashtags": {
            "multi_select": {
                "options": []  # Dynamically added
            }
        },
        "Status": {
            "select": {
                "options": [
                    {"name": "Draft", "color": "gray"},
                    {"name": "Ready", "color": "green"},
                    {"name": "Scheduled", "color": "yellow"},
                    {"name": "Published", "color": "blue"}
                ]
            }
        },
        "Scheduled Date": {
            "date": {}
        },
        "Published Date": {
            "date": {}
        },
        "Character Count": {
            "number": {
                "format": "number"
            }
        },
        "Created": {
            "date": {}
        }
    }
}

# ==================== 4. Research Data Database ====================

RESEARCH_DATA_SCHEMA = {
    "title": "Research Data",
    "properties": {
        "Topic": {
            "title": {}  # Research topic
        },
        "Keywords": {
            "multi_select": {
                "options": []  # Dynamically added
            }
        },
        "Sources": {
            "rich_text": {}  # JSON array of sources (title, url, snippet)
        },
        "Competitor Gaps": {
            "rich_text": {}  # Identified content gaps
        },
        "Search Volume": {
            "number": {
                "format": "number"
            }
        },
        "Competition Level": {
            "select": {
                "options": [
                    {"name": "Low", "color": "green"},
                    {"name": "Medium", "color": "yellow"},
                    {"name": "High", "color": "red"}
                ]
            }
        },
        "Blog Post": {
            "relation": {
                "database_id": None,  # Set dynamically to Blog Posts DB
                "type": "single_property"
            }
        },
        "Research Date": {
            "date": {}
        },
        "Created": {
            "date": {}
        }
    }
}

# ==================== 5. Competitors Database ====================

COMPETITORS_SCHEMA = {
    "title": "Competitors",
    "properties": {
        "Company Name": {
            "title": {}  # Competitor name
        },
        "Website": {
            "url": {}
        },
        "LinkedIn URL": {
            "url": {}
        },
        "Facebook URL": {
            "url": {}
        },
        "Instagram Handle": {
            "rich_text": {}
        },
        "TikTok Handle": {
            "rich_text": {}
        },
        "Content Strategy": {
            "rich_text": {}  # Notes on their content approach
        },
        "Posting Frequency": {
            "select": {
                "options": [
                    {"name": "Daily", "color": "red"},
                    {"name": "3-4x/week", "color": "yellow"},
                    {"name": "1-2x/week", "color": "green"},
                    {"name": "Occasional", "color": "gray"}
                ]
            }
        },
        "Content Quality": {
            "select": {
                "options": [
                    {"name": "Excellent", "color": "green"},
                    {"name": "Good", "color": "blue"},
                    {"name": "Average", "color": "yellow"},
                    {"name": "Poor", "color": "red"}
                ]
            }
        },
        "Last Analyzed": {
            "date": {}
        },
        "Created": {
            "date": {}
        }
    }
}

# ==================== 6. Topics Database ====================

TOPICS_SCHEMA = {
    "title": "Topics",
    "properties": {
        "Title": {
            "title": {}  # Topic title
        },
        "Status": {
            "select": {
                "options": [
                    {"name": "discovered", "color": "gray"},
                    {"name": "validated", "color": "yellow"},
                    {"name": "researched", "color": "blue"},
                    {"name": "drafted", "color": "purple"},
                    {"name": "published", "color": "green"},
                    {"name": "archived", "color": "red"}
                ]
            }
        },
        "Priority": {
            "number": {
                "format": "number"
            }
        },
        "Domain": {
            "select": {
                "options": []  # Dynamically added (e.g., "proptech", "fashion")
            }
        },
        "Market": {
            "select": {
                "options": []  # Dynamically added (e.g., "de", "fr", "us")
            }
        },
        "Language": {
            "select": {
                "options": [
                    {"name": "de", "color": "blue"},
                    {"name": "en", "color": "green"},
                    {"name": "fr", "color": "purple"},
                    {"name": "es", "color": "yellow"}
                ]
            }
        },
        "Source": {
            "select": {
                "options": [
                    {"name": "rss", "color": "blue"},
                    {"name": "reddit", "color": "orange"},
                    {"name": "trends", "color": "red"},
                    {"name": "autocomplete", "color": "green"},
                    {"name": "competitor", "color": "purple"},
                    {"name": "manual", "color": "gray"}
                ]
            }
        },
        "Description": {
            "rich_text": {}
        },
        "Source URL": {
            "url": {}
        },
        "Intent": {
            "select": {
                "options": [
                    {"name": "informational", "color": "blue"},
                    {"name": "commercial", "color": "yellow"},
                    {"name": "transactional", "color": "green"},
                    {"name": "navigational", "color": "purple"}
                ]
            }
        },
        "Engagement Score": {
            "number": {
                "format": "number"
            }
        },
        "Trending Score": {
            "number": {
                "format": "number"
            }
        },
        "Research Report": {
            "rich_text": {}  # Truncated to 2000 chars
        },
        "Word Count": {
            "number": {
                "format": "number"
            }
        },
        "Content Score": {
            "number": {
                "format": "number"
            }
        },
        "Hero Image URL": {
            "url": {}  # Generated hero image (1792x1024 HD)
        },
        "Supporting Images": {
            "rich_text": {}  # JSON array of supporting images [{url, alt, size, quality}]
        },
        "Discovered At": {
            "date": {}
        },
        "Updated At": {
            "date": {}
        },
        "Published At": {
            "date": {}
        },
        "Created": {
            "date": {}
        }
    }
}

# ==================== 7. Keywords Database ====================

KEYWORDS_SCHEMA = {
    "title": "Keywords",
    "properties": {
        "Keyword": {
            "title": {}  # The keyword/phrase
        },
        "Search Volume": {
            "rich_text": {}  # Volume estimate (e.g., "10K-100K/month")
        },
        "Competition": {
            "select": {
                "options": [
                    {"name": "Low", "color": "green"},
                    {"name": "Medium", "color": "yellow"},
                    {"name": "High", "color": "red"}
                ]
            }
        },
        "Difficulty": {
            "number": {
                "format": "number"  # 0-100 scale
            }
        },
        "Intent": {
            "select": {
                "options": [
                    {"name": "Informational", "color": "blue"},
                    {"name": "Commercial", "color": "yellow"},
                    {"name": "Transactional", "color": "green"},
                    {"name": "Navigational", "color": "purple"}
                ]
            }
        },
        "Relevance": {
            "number": {
                "format": "number"  # 0-1 scale
            }
        },
        "Source Topic": {
            "rich_text": {}  # The topic this keyword came from
        },
        "Opportunity Score": {
            "number": {
                "format": "number"  # 0-100 scale (AI-calculated)
            }
        },
        "Keyword Type": {
            "select": {
                "options": [
                    {"name": "Primary", "color": "blue"},
                    {"name": "Secondary", "color": "green"},
                    {"name": "Long-tail", "color": "purple"},
                    {"name": "Question", "color": "yellow"}
                ]
            }
        },
        "Research Date": {
            "date": {}
        },
        "Created": {
            "date": {}
        }
    }
}

# ==================== Schema Registry ====================

ALL_SCHEMAS = {
    "projects": PROJECTS_SCHEMA,
    "blog_posts": BLOG_POSTS_SCHEMA,
    "social_posts": SOCIAL_POSTS_SCHEMA,
    "research_data": RESEARCH_DATA_SCHEMA,
    "competitors": COMPETITORS_SCHEMA,
    "topics": TOPICS_SCHEMA,
    "keywords": KEYWORDS_SCHEMA
}


def get_schema(database_name: str) -> dict:
    """
    Get schema for a specific database.

    Args:
        database_name: Database name (projects, blog_posts, social_posts, research_data, competitors, topics, keywords)

    Returns:
        Schema dict with 'title' and 'properties'

    Raises:
        ValueError: If database_name is invalid
    """
    if database_name not in ALL_SCHEMAS:
        raise ValueError(
            f"Invalid database name: {database_name}. "
            f"Must be one of: {list(ALL_SCHEMAS.keys())}"
        )
    return ALL_SCHEMAS[database_name]


def set_relation_database_id(schema: dict, property_name: str, database_id: str) -> dict:
    """
    Set the database_id for a relation property.

    Args:
        schema: Database schema dict
        property_name: Property name with relation type
        database_id: Target database ID

    Returns:
        Updated schema dict
    """
    if property_name in schema["properties"]:
        if "relation" in schema["properties"][property_name]:
            schema["properties"][property_name]["relation"]["database_id"] = database_id
    return schema

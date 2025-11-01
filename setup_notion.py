#!/usr/bin/env python3
"""
Notion Database Setup Script

Creates the 5 required Notion databases in the specified parent page.

Usage:
    python setup_notion.py

Databases created:
    1. Projects - Brand configurations
    2. Blog Posts - Primary editorial interface
    3. Social Posts - Platform-specific content
    4. Research Data - SEO research
    5. Competitors - Competitor tracking

Prerequisites:
    - .env file with NOTION_TOKEN and NOTION_PAGE_ID
    - Notion integration must have access to parent page
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings, setup_logging, SettingsError
from config.notion_schemas import (
    ALL_SCHEMAS,
    set_relation_database_id
)
from src.notion_integration.notion_client import NotionClient, NotionError

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def create_database(
    client: NotionClient,
    parent_page_id: str,
    schema: dict
) -> dict:
    """
    Create a Notion database.

    Args:
        client: NotionClient instance
        parent_page_id: Parent page ID
        schema: Database schema (title + properties)

    Returns:
        Created database object with 'id' and 'title'

    Raises:
        NotionError: On API errors
    """
    title = schema["title"]
    properties = schema["properties"]

    logger.info(f"Creating database: {title}")

    try:
        database = client.create_database(
            parent_page_id=parent_page_id,
            title=title,
            properties=properties,
            retry=True,
            max_retries=3
        )

        db_id = database["id"]
        logger.info(f"✅ Created database '{title}' (ID: {db_id})")

        return database

    except NotionError as e:
        logger.error(f"❌ Failed to create database '{title}': {e}")
        raise


def setup_relations(
    client: NotionClient,
    database_ids: dict
) -> None:
    """
    Update databases with relation properties.

    Relations must be set after all databases are created
    because they reference other database IDs.

    Args:
        client: NotionClient instance
        database_ids: Dict mapping database names to IDs
    """
    logger.info("Setting up database relations...")

    # Blog Posts → Projects relation
    # (This would require updating the database schema, which Notion API doesn't fully support yet)
    # Instead, we note this limitation and create databases without pre-configured relations

    logger.warning(
        "⚠️  Note: Notion API doesn't support updating database schemas after creation. "
        "Relation properties have been created, but you'll need to manually configure "
        "the target databases in Notion UI if they weren't set correctly."
    )


def save_database_ids(database_ids: dict, output_file: str = "cache/database_ids.json") -> None:
    """
    Save database IDs to file for later use.

    Args:
        database_ids: Dict mapping database names to IDs
        output_file: Output file path
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True, parents=True)

    data = {
        "created_at": datetime.now().isoformat(),
        "databases": database_ids
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"💾 Saved database IDs to: {output_path}")


def main():
    """Main setup function"""
    logger.info("=" * 60)
    logger.info("Notion Database Setup")
    logger.info("=" * 60)

    # Validate settings
    try:
        settings.validate_all()
    except SettingsError as e:
        logger.error(f"❌ Configuration error:\n{e}")
        sys.exit(1)

    logger.info("✅ Configuration valid")
    logger.info(f"Parent page ID: {settings.NOTION_PAGE_ID}")
    logger.info(f"Rate limit: {settings.NOTION_RATE_LIMIT} req/sec")

    # Initialize Notion client
    try:
        client = NotionClient(
            token=settings.NOTION_TOKEN,
            rate_limit=settings.NOTION_RATE_LIMIT
        )
        logger.info("✅ Notion client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Notion client: {e}")
        sys.exit(1)

    # Create databases
    database_ids = {}
    database_order = [
        ("projects", "Projects"),
        ("blog_posts", "Blog Posts"),
        ("social_posts", "Social Posts"),
        ("research_data", "Research Data"),
        ("competitors", "Competitors")
    ]

    logger.info(f"\nCreating {len(database_order)} databases...")

    for key, name in database_order:
        try:
            schema = ALL_SCHEMAS[key].copy()

            # For databases with relations, we'll create them without relations first
            # (Notion API limitation: can't update database schema after creation)

            database = create_database(
                client=client,
                parent_page_id=settings.NOTION_PAGE_ID,
                schema=schema
            )

            database_ids[key] = database["id"]

        except NotionError as e:
            logger.error(f"❌ Failed to create database '{name}'. Aborting.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"❌ Unexpected error creating database '{name}': {e}")
            sys.exit(1)

    # Save database IDs
    save_database_ids(database_ids)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("✅ Setup Complete!")
    logger.info("=" * 60)
    logger.info("\nCreated databases:")
    for key, name in database_order:
        db_id = database_ids[key]
        logger.info(f"  - {name}: {db_id}")

    logger.info("\n📝 Next steps:")
    logger.info("  1. Open Notion and verify databases were created")
    logger.info("  2. Grant your integration access to the parent page (if not already)")
    logger.info("  3. Manually configure relation properties:")
    logger.info("     - Blog Posts → Project (relation)")
    logger.info("     - Social Posts → Blog Post (relation)")
    logger.info("     - Research Data → Blog Post (relation)")
    logger.info("  4. Run test: python test_notion_connection.py")

    logger.info("\n💾 Database IDs saved to: cache/database_ids.json")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n❌ Setup cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)

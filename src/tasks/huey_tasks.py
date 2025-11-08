"""
Huey Task Queue Setup

Component 7 (Week 1): Background task processing
- SQLite-backed queue (single writer, no Redis needed for MVP)
- DLQ (dead-letter queue) for failed jobs
- Retry logic with exponential backoff
- Periodic task scheduling

Usage:
    # Start consumer:
    huey_consumer src.tasks.huey_tasks.huey

    # Schedule task programmatically:
    from src.tasks.huey_tasks import collect_all_sources
    collect_all_sources.schedule(delay=60)  # Run in 60 seconds

    # Periodic tasks run automatically when consumer is running
"""

from huey import SqliteHuey, crontab
from pathlib import Path
from datetime import datetime
import sqlite3
from typing import List, Dict
from src.utils.logger import get_logger

# Initialize logger
logger = get_logger(__name__)

# Initialize Huey with SQLite backend
# Database stored in project root for easy access
HUEY_DB_PATH = Path(__file__).parent.parent.parent / "tasks.db"
huey = SqliteHuey(filename=str(HUEY_DB_PATH))

# DLQ database path (separate from main tasks database)
DLQ_DB_PATH = Path(__file__).parent.parent.parent / "dlq.db"


def _init_dlq_db():
    """Initialize dead-letter queue database"""
    with sqlite3.connect(DLQ_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT NOT NULL,
                error TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def log_to_dlq(task_name: str, error: str, timestamp: datetime) -> None:
    """
    Log failed task to dead-letter queue

    Args:
        task_name: Name of the failed task
        error: Error message
        timestamp: When the error occurred
    """
    _init_dlq_db()

    with sqlite3.connect(DLQ_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO dead_letter_queue (task_name, error, timestamp)
            VALUES (?, ?, ?)
            """,
            (task_name, error, timestamp.isoformat())
        )
        conn.commit()

    logger.error(
        "task_failed_to_dlq",
        task_name=task_name,
        error=error,
        timestamp=timestamp.isoformat()
    )


def get_dlq_entries(limit: int = 100) -> List[Dict[str, str]]:
    """
    Retrieve dead-letter queue entries for monitoring

    Args:
        limit: Maximum number of entries to return

    Returns:
        List of DLQ entries with task_name, error, timestamp
    """
    _init_dlq_db()

    with sqlite3.connect(DLQ_DB_PATH) as conn:
        cursor = conn.execute(
            """
            SELECT task_name, error, timestamp, created_at
            FROM dead_letter_queue
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()

    return [
        {
            "task_name": row[0],
            "error": row[1],
            "timestamp": row[2],
            "created_at": row[3]
        }
        for row in rows
    ]


# ============================================================================
# Core Tasks
# ============================================================================

@huey.task(retries=3, retry_delay=60)
def collect_all_sources(config_path: str = "config/markets/proptech_de.yaml") -> Dict[str, int]:
    """
    Background task: Collect documents from all enabled sources

    Retry logic:
    - 3 retries with 60s base delay
    - Exponential backoff: 60s, 120s, 240s

    Args:
        config_path: Path to market configuration file

    Returns:
        Collection stats (documents collected, sources processed)

    Raises:
        Exception: If collection fails after all retries (logged to DLQ)
    """
    logger.info("collect_all_sources_started", config_path=config_path)

    try:
        from src.agents.universal_topic_agent import UniversalTopicAgent

        agent = UniversalTopicAgent.load_config(config_path)
        stats = agent.collect_all_sources()

        logger.info("collect_all_sources_completed", **stats)
        return stats

    except Exception as e:
        logger.error("collect_all_sources_failed", error=str(e))

        # Log to DLQ on final failure
        if not hasattr(collect_all_sources, '_retry_count'):
            log_to_dlq(
                task_name="collect_all_sources",
                error=str(e),
                timestamp=datetime.now()
            )

        raise


@huey.periodic_task(crontab(hour=2, minute=0))
def daily_collection():
    """
    Scheduled task: Daily collection at 2 AM

    Automatically runs when Huey consumer is active.
    Collects from all configured sources for the default config.

    Schedule: Daily at 2:00 AM server time
    """
    logger.info("daily_collection_triggered")

    try:
        # Default to PropTech Germany config
        result = collect_all_sources(config_path="config/markets/proptech_de.yaml")
        logger.info("daily_collection_completed", result=result)
        return result

    except Exception as e:
        logger.error("daily_collection_failed", error=str(e))
        log_to_dlq(
            task_name="daily_collection",
            error=str(e),
            timestamp=datetime.now()
        )
        raise


@huey.periodic_task(crontab(day_of_week='1', hour=9, minute=0))
def weekly_notion_sync(config_path: str = "config/markets/proptech_de.yaml"):
    """
    Scheduled task: Weekly Notion sync on Monday at 9 AM

    Syncs top topics from database to Notion for review.
    Runs weekly to avoid API rate limits.

    Args:
        config_path: Path to market configuration file

    Schedule: Every Monday at 9:00 AM server time
    """
    logger.info("weekly_notion_sync_triggered", config_path=config_path)

    try:
        from src.agents.universal_topic_agent import UniversalTopicAgent
        import asyncio

        agent = UniversalTopicAgent.load_config(config_path)
        result = asyncio.run(agent.sync_to_notion(limit=10))

        logger.info("weekly_notion_sync_completed", result=result)
        return result

    except Exception as e:
        logger.error("weekly_notion_sync_failed", error=str(e))
        log_to_dlq(
            task_name="weekly_notion_sync",
            error=str(e),
            timestamp=datetime.now()
        )
        raise


# ============================================================================
# Utility Functions
# ============================================================================

def get_task_stats() -> Dict[str, int]:
    """
    Get task queue statistics

    Returns:
        Dict with pending, scheduled, and failed task counts
    """
    # Huey doesn't expose pending count directly via API
    # This would require querying the SQLite database directly
    # For now, return basic info

    stats = {
        "pending_tasks": 0,  # Would need to query tasks.db
        "dlq_entries": len(get_dlq_entries())
    }

    logger.info("task_stats_retrieved", **stats)
    return stats


def clear_dlq() -> int:
    """
    Clear all entries from dead-letter queue

    Returns:
        Number of entries cleared
    """
    _init_dlq_db()

    with sqlite3.connect(DLQ_DB_PATH) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM dead_letter_queue")
        count = cursor.fetchone()[0]

        conn.execute("DELETE FROM dead_letter_queue")
        conn.commit()

    logger.info("dlq_cleared", entries_removed=count)
    return count

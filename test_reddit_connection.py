#!/usr/bin/env python3
"""
Quick verification script for Reddit API (PRAW) connection.
Tests authentication and basic API access.
"""

import os
from dotenv import load_dotenv
import praw

def test_reddit_connection():
    """Test Reddit API connection with PRAW"""
    print("🔍 Testing Reddit API Connection...")
    print("-" * 50)

    # Load environment variables
    load_dotenv()

    # Get credentials
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")

    # Verify credentials exist
    if not all([client_id, client_secret, user_agent]):
        print("❌ FAILED: Missing Reddit credentials in .env")
        print(f"   REDDIT_CLIENT_ID: {'✓' if client_id else '✗'}")
        print(f"   REDDIT_CLIENT_SECRET: {'✓' if client_secret else '✗'}")
        print(f"   REDDIT_USER_AGENT: {'✓' if user_agent else '✗'}")
        return False

    print(f"✓ Credentials loaded from .env")
    print(f"  Client ID: {client_id[:10]}...")
    print(f"  User Agent: {user_agent}")
    print()

    try:
        # Initialize Reddit client
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )

        print("✓ PRAW client initialized")
        print()

        # Test read-only access (get subreddit info)
        print("Testing subreddit access (r/de)...")
        subreddit = reddit.subreddit("de")

        # Get subreddit details
        print(f"  Name: r/{subreddit.display_name}")
        print(f"  Subscribers: {subreddit.subscribers:,}")
        print(f"  Description: {subreddit.public_description[:100]}...")
        print()

        # Get recent posts (limit to 3 for quick test)
        print("Fetching recent posts from r/de (limit 3)...")
        posts = list(subreddit.new(limit=3))

        for i, post in enumerate(posts, 1):
            print(f"  {i}. {post.title[:60]}...")
            print(f"     Author: u/{post.author}")
            print(f"     Score: {post.score}")
            print()

        print("✅ SUCCESS: Reddit API connection working!")
        print("   - Authentication successful")
        print("   - Subreddit access working")
        print("   - Post fetching working")
        print()
        print("Ready to implement Reddit Collector (Phase 6)")
        return True

    except praw.exceptions.PRAWException as e:
        print(f"❌ FAILED: PRAW error - {e}")
        return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error - {e}")
        return False

if __name__ == "__main__":
    success = test_reddit_connection()
    exit(0 if success else 1)

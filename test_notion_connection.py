#!/usr/bin/env python3
"""
Quick test to verify Notion SDK connection
"""
import os
from dotenv import load_dotenv
from notion_client import Client

# Load environment variables
load_dotenv()

# Get Notion token
notion_token = os.getenv("NOTION_TOKEN")

if not notion_token:
    print("❌ NOTION_TOKEN not found in .env file")
    exit(1)

print("🔍 Testing Notion SDK connection...")
print(f"   Token: {notion_token[:20]}...")

try:
    # Initialize Notion client
    notion = Client(auth=notion_token)

    # Test connection by listing users (simple API call)
    users = notion.users.list()

    print("✅ Notion SDK connection successful!")
    print(f"   Workspace: {os.getenv('NOTION_WORKSPACE')}")
    print(f"   Found {len(users['results'])} users in workspace")

    # Try to get the content automation page
    page_id = os.getenv("NOTION_PAGE_ID")
    if page_id:
        try:
            page = notion.pages.retrieve(page_id=page_id)
            print(f"✅ Content Automation page accessible")
            print(f"   Page ID: {page_id}")
        except Exception as e:
            print(f"⚠️  Could not access Content Automation page: {e}")

except Exception as e:
    print(f"❌ Notion SDK connection failed: {e}")
    exit(1)

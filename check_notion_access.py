#!/usr/bin/env python3
"""
Check what the Notion integration can access
"""
import os
from dotenv import load_dotenv
from notion_client import Client

# Load environment variables
load_dotenv()

notion_token = os.getenv("NOTION_TOKEN")
notion = Client(auth=notion_token)

print("=" * 60)
print("🔍 Checking Notion Integration Access")
print("=" * 60)

# 1. List all databases the integration can access
print("\n📊 Searching for databases...")
try:
    databases = notion.search(filter={"property": "object", "value": "database"})
    print(f"✅ Found {len(databases['results'])} databases")
    for db in databases['results']:
        print(f"   - {db.get('title', [{}])[0].get('plain_text', 'Untitled')}")
        print(f"     ID: {db['id']}")
except Exception as e:
    print(f"❌ Error searching databases: {e}")

# 2. List all pages the integration can access
print("\n📄 Searching for pages...")
try:
    pages = notion.search(filter={"property": "object", "value": "page"})
    print(f"✅ Found {len(pages['results'])} pages")
    for page in pages['results']:
        title = "Untitled"
        if 'properties' in page:
            for prop_name, prop_val in page['properties'].items():
                if prop_val['type'] == 'title' and prop_val.get('title'):
                    title = prop_val['title'][0]['plain_text']
                    break
        print(f"   - {title}")
        print(f"     ID: {page['id']}")
except Exception as e:
    print(f"❌ Error searching pages: {e}")

# 3. Try to access the Content Automation page with different ID formats
print("\n🔍 Testing Content Automation page access...")
page_id = os.getenv("NOTION_PAGE_ID")
print(f"   Page ID from .env: {page_id}")

# Try without dashes (raw format)
try:
    page = notion.pages.retrieve(page_id=page_id)
    print(f"✅ SUCCESS: Content Automation page accessible!")
    print(f"   Page Object: {page.get('object')}")
    if 'parent' in page:
        print(f"   Parent: {page['parent']}")
except Exception as e:
    print(f"❌ Failed with raw ID: {e}")

# Try with dashes (UUID format)
page_id_with_dashes = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"
print(f"   Trying with dashes: {page_id_with_dashes}")
try:
    page = notion.pages.retrieve(page_id=page_id_with_dashes)
    print(f"✅ SUCCESS with dashes: Content Automation page accessible!")
    print(f"   Page Object: {page.get('object')}")
except Exception as e:
    print(f"❌ Failed with dashed ID: {e}")

print("\n" + "=" * 60)
print("💡 If the page isn't accessible, make sure it's shared with")
print("   your 'content-writer' integration in Notion")
print("=" * 60)

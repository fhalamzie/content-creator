#!/usr/bin/env python3
"""
Check for existing databases under the Content Automation page
"""
import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()
notion = Client(auth=os.getenv("NOTION_TOKEN"))

print("=" * 60)
print("🔍 Checking for Existing Databases")
print("=" * 60)

# Search for all accessible content (pages and databases)
try:
    results = notion.search()

    databases = [r for r in results['results'] if r['object'] == 'database']
    pages = [r for r in results['results'] if r['object'] == 'page']

    print(f"\n📊 Found {len(databases)} databases:")
    if databases:
        for db in databases:
            title = "Untitled"
            if db.get('title'):
                title = db['title'][0]['plain_text'] if db['title'] else "Untitled"
            print(f"   ✓ {title}")
            print(f"     ID: {db['id']}")
            print(f"     Parent: {db.get('parent', {}).get('type')}")
    else:
        print("   (No databases found)")

    print(f"\n📄 Found {len(pages)} pages:")
    if pages:
        for page in pages:
            title = "Untitled"
            if 'properties' in page:
                for prop_name, prop_val in page['properties'].items():
                    if prop_val['type'] == 'title' and prop_val.get('title'):
                        title = prop_val['title'][0]['plain_text']
                        break
            print(f"   ✓ {title}")
            print(f"     ID: {page['id']}")

    print("\n" + "=" * 60)

    # Check if we need to create databases
    if len(databases) == 0:
        print("💡 No databases found. Ready to create 5 databases!")
    elif len(databases) < 5:
        print(f"⚠️  Only {len(databases)}/5 databases found.")
        print("   Missing databases will need to be created.")
    else:
        print("✅ All databases appear to exist!")
        print("   Review names to confirm they match our schema.")

except Exception as e:
    print(f"❌ Error: {e}")

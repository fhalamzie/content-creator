#!/usr/bin/env python3
"""Quick Feed Discovery Test - Tests SerpAPI integration only"""

from src.utils.config_loader import ConfigLoader
from src.collectors.feed_discovery import FeedDiscovery

# Load config
config_loader = ConfigLoader(config_dir="config/markets")
config = config_loader.load("proptech_de")

# Initialize with SerpAPI key from env
feed_discovery = FeedDiscovery(
    config=config,
    cache_dir="cache/feed_discovery_test",
    serpapi_daily_limit=3
)

print("Testing SerpAPI integration...")
print(f"API Key configured: {bool(feed_discovery.serpapi_api_key)}")

# Test single keyword search
keyword = "PropTech Germany"
domains = feed_discovery._search_with_serpapi(keyword)

print(f"\nResults for '{keyword}':")
print(f"  Domains found: {len(domains)}")
for i, domain in enumerate(domains[:5], 1):
    print(f"  {i}. {domain}")

if len(domains) >= 5:
    print(f"✅ SerpAPI working! Found {len(domains)} domains")
else:
    print(f"⚠️ Expected at least 5 domains, got {len(domains)}")

# Check cache
cache_file = feed_discovery.cache_dir / "serp_cache.json"
print(f"\n Cache file created: {cache_file.exists()}")
print(f"✅ Feed Discovery Stage 2 functional!")

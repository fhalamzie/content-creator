#!/bin/bash
# Monitor topic discovery events in real-time

echo "=== Monitoring Topic Discovery Events ==="
echo "Watching: streamlit_clean.log"
echo ""

tail -f streamlit_clean.log | grep --line-buffered -E "(stage[0-9]_|discovering_sources|llm_topic|reddit_collection|news_collection|autocomplete_collection|trends_collection|topic_discovery|Stage [0-9]/6)" | while read line; do
    echo "[$(date '+%H:%M:%S')] $line"
done

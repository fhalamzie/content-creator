#!/bin/bash
# Check recent topic discovery events

echo "=== Recent Topic Discovery Events ==="
echo ""

grep -E "(stage[0-9]_|discovering_sources|llm_topic|reddit_collection|news_collection|autocomplete_collection|trends_collection|Stage [0-9]/6)" streamlit_clean.log | tail -50

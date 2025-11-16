#!/usr/bin/env python3
"""
Test script for async Gemini API fix (Stage 2 pipeline hang)

This script tests the new generate_async() method to verify it works
without deadlocking in an async context.

Usage:
    python test_async_gemini.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.gemini_agent import GeminiAgent
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_async_gemini():
    """Test the async Gemini API method"""
    print("=" * 60)
    print("Testing Gemini generate_async() method")
    print("=" * 60)

    # Create agent with grounding
    print("\n1. Creating GeminiAgent with grounding enabled...")
    agent = GeminiAgent(
        model="gemini-2.5-flash",
        api_key=os.getenv("GEMINI_API_KEY"),
        enable_grounding=True,
        temperature=0.3,
        max_tokens=4000
    )
    print("   ✓ Agent created")

    # Test simple prompt (no grounding, no JSON schema)
    print("\n2. Testing simple prompt (no grounding, no JSON)...")
    try:
        result = await agent.generate_async(
            prompt="What is 2+2? Answer in one word.",
            enable_grounding=False
        )
        print(f"   ✓ Response: {result['content'][:100]}")
        print(f"   ✓ Tokens: {result['tokens']['total']}")
        print(f"   ✓ Cost: ${result['cost']:.4f}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test with grounding + JSON schema (the problematic case)
    print("\n3. Testing grounding + JSON schema (Stage 2 case)...")
    response_schema = {
        "type": "object",
        "properties": {
            "competitors": {
                "type": "array",
                "items": {"type": "string"}
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["competitors", "keywords"]
    }

    try:
        result = await agent.generate_async(
            prompt="Find 3 competitors in the PropTech industry and list 5 related keywords.",
            response_schema=response_schema,
            enable_grounding=True
        )
        print(f"   ✓ Response received")
        print(f"   ✓ Content keys: {list(result.keys())}")
        print(f"   ✓ Tokens: {result['tokens']['total']}")
        print(f"   ✓ Cost: ${result['cost']:.4f}")

        if 'grounding_metadata' in result:
            print(f"   ✓ Grounding sources: {len(result['grounding_metadata'].get('sources', []))}")

        # Parse content
        import json
        content_data = json.loads(result['content'])
        print(f"   ✓ Competitors found: {len(content_data.get('competitors', []))}")
        print(f"   ✓ Keywords found: {len(content_data.get('keywords', []))}")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test with asyncio timeout (simulating pipeline timeout)
    print("\n4. Testing with 10s timeout (simulating pipeline)...")
    try:
        result = await asyncio.wait_for(
            agent.generate_async(
                prompt="List 3 competitors in real estate tech.",
                response_schema=response_schema,
                enable_grounding=True
            ),
            timeout=10.0
        )
        print(f"   ✓ Completed within timeout")
        print(f"   ✓ Response received successfully")
    except asyncio.TimeoutError:
        print(f"   ✗ Timeout after 10s - STILL HAS ISSUES!")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Async fix working correctly!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    print("\nAsync Gemini API Test")
    print("This tests the fix for Stage 2 pipeline hang")
    print()

    # Run async test
    success = asyncio.run(test_async_gemini())

    if success:
        print("\n✅ Fix verified - Pipeline Stage 2 should now work!")
        sys.exit(0)
    else:
        print("\n❌ Fix failed - More debugging needed")
        sys.exit(1)

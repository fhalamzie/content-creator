#!/usr/bin/env python3
"""
E2E Test Script for Content Generation

Tests the actual generate_content function from the Streamlit UI
without requiring browser automation.

Run with: python test_generate_e2e.py
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the actual generate_content function
from src.ui.pages.generate import generate_content


def test_generate_content_mocked_apis():
    """Test generate_content with mocked external APIs"""

    # Mock project config
    project_config = {
        "brand_voice": "Professional",
        "target_audience": "Business professionals",
        "keywords": "KI, Marketing, Automatisierung"
    }

    # Mock placeholders
    progress_placeholder = Mock()
    status_placeholder = Mock()

    # Mock research data
    mock_research_data = {
        'sources': [
            {'url': 'https://example.com', 'title': 'Test Source', 'snippet': 'Test data'}
        ],
        'keywords': ['KI', 'Marketing'],
        'summary': 'AI marketing summary'
    }

    # Mock blog result
    mock_blog_result = {
        'content': '# Test Blog Post\n\nThis is a test German blog post about KI Marketing.\n\n' * 100,  # ~1500 words
        'metadata': {
            'topic': 'KI Marketing',
            'word_count': 1500,
            'language': 'de',
            'created_at': '2025-11-01'
        },
        'seo': {
            'meta_description': 'Test meta description',
            'alt_texts': ['Image 1 alt text'],
            'internal_links': ['Link 1']
        },
        'cost': 0.65
    }

    # Mock Notion sync result
    mock_sync_result = {
        'success': True,
        'page_id': 'test-page-123',
        'url': 'https://notion.so/test-page-123'
    }

    # Patch all external dependencies
    with patch('src.ui.pages.generate.ResearchAgent') as mock_research_class, \
         patch('src.ui.pages.generate.WritingAgent') as mock_writing_class, \
         patch('src.ui.pages.generate.SyncManager') as mock_sync_class, \
         patch('src.notion_integration.notion_client.NotionClient'):

        # Setup mocks
        mock_research = Mock()
        mock_research.research.return_value = mock_research_data
        mock_research_class.return_value = mock_research

        mock_writing = Mock()
        mock_writing.write_blog.return_value = mock_blog_result
        mock_writing_class.return_value = mock_writing

        mock_sync = Mock()
        mock_sync.sync_blog_post.return_value = mock_sync_result
        mock_sync_class.return_value = mock_sync

        # Call the actual generate_content function
        result = generate_content(
            topic="KI Marketing Automatisierung",
            project_config=project_config,
            progress_placeholder=progress_placeholder,
            status_placeholder=status_placeholder
        )

        # Verify result
        print("\n" + "=" * 60)
        print("E2E TEST RESULTS")
        print("=" * 60)

        assert result['success'] == True, f"Generation failed: {result.get('error')}"
        assert 'blog_data' in result
        assert 'stats' in result

        print(f"✅ Generation successful")
        print(f"✅ Word count: {result['stats']['word_count']}")
        print(f"✅ Research sources: {result['stats']['research_sources']}")
        print(f"✅ Cost: ${result['stats']['cost']:.2f}")

        # Verify all stages were called
        assert progress_placeholder.progress.called, "Progress not updated"
        assert status_placeholder.info.called or status_placeholder.success.called, "Status not updated"

        # Verify pipeline stages
        mock_research.research.assert_called_once()
        mock_writing.write_blog.assert_called_once()
        mock_sync.sync_blog_post.assert_called_once()

        print(f"✅ Research stage called")
        print(f"✅ Writing stage called")
        print(f"✅ Sync stage called")

        # Verify slug parameter (Bug #1 fix)
        sync_call_kwargs = mock_sync.sync_blog_post.call_args.kwargs
        assert 'slug' in sync_call_kwargs, "Bug #1: sync_blog_post not called with slug parameter"
        print(f"✅ Bug #1 fix verified: sync_blog_post called with slug={sync_call_kwargs['slug']}")

        print("\n" + "=" * 60)
        print("ALL E2E TESTS PASSED ✅")
        print("=" * 60)

        return result


def test_generate_content_with_sync_failure():
    """Test generate_content handles sync failures gracefully"""

    project_config = {
        "brand_voice": "Professional",
        "target_audience": "Developers",
        "keywords": "testing"
    }

    progress_placeholder = Mock()
    status_placeholder = Mock()

    mock_research_data = {'sources': [], 'keywords': ['test'], 'summary': 'Test'}
    mock_blog_result = {
        'content': '# Test\n\nContent' * 50,
        'metadata': {'topic': 'Test', 'word_count': 500},
        'seo': {},
        'cost': 0.25
    }

    # Sync fails
    mock_sync_result = {'success': False, 'error': 'Notion API unavailable'}

    with patch('src.ui.pages.generate.ResearchAgent') as mock_research_class, \
         patch('src.ui.pages.generate.WritingAgent') as mock_writing_class, \
         patch('src.ui.pages.generate.SyncManager') as mock_sync_class, \
         patch('src.notion_integration.notion_client.NotionClient'):

        mock_research = Mock()
        mock_research.research.return_value = mock_research_data
        mock_research_class.return_value = mock_research

        mock_writing = Mock()
        mock_writing.write_blog.return_value = mock_blog_result
        mock_writing_class.return_value = mock_writing

        mock_sync = Mock()
        mock_sync.sync_blog_post.return_value = mock_sync_result
        mock_sync_class.return_value = mock_sync

        result = generate_content(
            topic="Test Topic",
            project_config=project_config,
            progress_placeholder=progress_placeholder,
            status_placeholder=status_placeholder
        )

        # Should still succeed even if sync fails (content is cached)
        assert result['success'] == True, "Should succeed despite sync failure"
        assert 'blog_data' in result
        assert result['notion_url'] is None, "Notion URL should be None when sync fails"

        print(f"\n✅ Graceful sync failure handling verified")


if __name__ == "__main__":
    print("\nRunning E2E Tests for Content Generation...")
    print("=" * 60)

    try:
        # Test 1: Normal flow
        test_generate_content_mocked_apis()

        # Test 2: Sync failure handling
        test_generate_content_with_sync_failure()

        print("\n🎉 ALL E2E TESTS PASSED!")
        sys.exit(0)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

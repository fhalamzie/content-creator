"""
SyncManager - Cache to Notion Sync with Rate Limiting

Syncs cached content to Notion databases with rate limiting and progress tracking.

Design Principles:
- Batch operations with progress callbacks
- Rate limiting (2.5 req/sec for Notion API)
- ETA calculation for UI
- Retry logic with exponential backoff
- Comprehensive error handling
- Detailed logging
"""

import logging
import time
from typing import Dict, Any, List, Optional, Callable

from src.cache_manager import CacheManager
from src.notion_integration.notion_client import NotionClient
from src.notion_integration.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class SyncError(Exception):
    """Base exception for sync errors"""
    pass


class SyncManager:
    """
    Manages syncing cached content to Notion databases.

    Features:
    - Batch blog post sync
    - Batch social posts sync
    - Rate limiting (configurable)
    - Progress callbacks with ETA
    - Retry logic
    - Error handling

    Usage:
        sync_manager = SyncManager()

        # Sync all blog posts with progress
        def progress(data):
            print(f"Progress: {data['current']}/{data['total']} (ETA: {data['eta_seconds']}s)")

        results = sync_manager.sync_all_blog_posts(progress_callback=progress)
        print(f"Synced {results['successful']}/{results['total']} posts")
    """

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        notion_client: Optional[NotionClient] = None,
        rate_limiter: Optional[RateLimiter] = None,
        max_retries: int = 3
    ):
        """
        Initialize SyncManager.

        Args:
            cache_manager: Optional CacheManager instance
            notion_client: Optional NotionClient instance
            rate_limiter: Optional RateLimiter instance
            max_retries: Maximum retry attempts (default: 3)
        """
        self.cache_manager = cache_manager or CacheManager()

        # Create NotionClient from environment if not provided
        if notion_client is None:
            import os
            from dotenv import load_dotenv
            load_dotenv()
            token = os.getenv("NOTION_TOKEN")
            if not token:
                raise ValueError("NOTION_TOKEN environment variable required")
            notion_client = NotionClient(token=token)

        self.notion_client = notion_client
        self.rate_limiter = rate_limiter or RateLimiter()
        self.max_retries = max_retries

        logger.info(
            f"SyncManager initialized: "
            f"rate_limit={self.rate_limiter.rate} req/sec, "
            f"max_retries={max_retries}"
        )

    def sync_blog_post(
        self,
        slug: str,
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync single blog post to Notion.

        Args:
            slug: Blog post slug (loaded from cache)
            progress_callback: Optional progress callback(current, total, eta_seconds)

        Returns:
            Dict with:
                - success: bool
                - page_id: Notion page ID (if successful)
                - url: Notion page URL (if successful)
                - error: Error message (if failed)

        Raises:
            SyncError: If sync fails after retries
        """
        logger.info(f"Syncing blog post: {slug}")

        # Load blog data from cache
        try:
            post_data = self.cache_manager.read_blog_post(slug)
            blog_data = {
                'slug': slug,
                'content': post_data['content'],
                'metadata': post_data['metadata']
            }
        except Exception as e:
            error_msg = f"Blog post '{slug}' not found in cache: {e}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Call progress callback (start)
        if progress_callback:
            progress_callback(0, 1, self.calculate_eta(1))

        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Acquire rate limit token
                self.rate_limiter.acquire()

                # Create Notion page with content
                properties = self._build_blog_properties(blog_data)
                children = self._markdown_to_blocks(blog_data.get('content', ''))

                # Insert images into content blocks
                children = self._insert_images_into_blocks(children, blog_data.get('metadata', {}))

                # Notion API limit: 100 blocks per request
                # If more than 100 blocks, create page with first 100, then append rest
                NOTION_BLOCK_LIMIT = 100

                if len(children) <= NOTION_BLOCK_LIMIT:
                    # Simple case: all blocks fit in one request
                    page = self.notion_client.create_page(
                        parent_database_id=self.notion_client.database_ids['blog_posts'],
                        properties=properties,
                        children=children
                    )
                else:
                    # Complex case: need to chunk blocks
                    logger.info(f"Blog post has {len(children)} blocks, splitting into chunks")

                    # Create page with first 100 blocks
                    first_chunk = children[:NOTION_BLOCK_LIMIT]
                    page = self.notion_client.create_page(
                        parent_database_id=self.notion_client.database_ids['blog_posts'],
                        properties=properties,
                        children=first_chunk
                    )

                    # Append remaining blocks in chunks
                    remaining_blocks = children[NOTION_BLOCK_LIMIT:]
                    for i in range(0, len(remaining_blocks), NOTION_BLOCK_LIMIT):
                        chunk = remaining_blocks[i:i + NOTION_BLOCK_LIMIT]
                        logger.info(f"Appending chunk {i//NOTION_BLOCK_LIMIT + 1}: {len(chunk)} blocks")
                        self.notion_client.append_blocks(
                            block_id=page['id'],
                            children=chunk,
                            retry=True
                        )
                        # Rate limit between chunks
                        self.rate_limiter.acquire()

                logger.info(f"Synced blog post successfully: {slug} → {page['id']}")

                # Call progress callback (complete)
                if progress_callback:
                    progress_callback(1, 1, 0)

                return {
                    'success': True,
                    'page_id': page['id'],
                    'url': page['url']
                }

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.max_retries} "
                        f"after {backoff}s: {e}"
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"Failed to sync blog post after {self.max_retries} retries: {e}")

        # All retries exhausted
        raise SyncError(
            f"Failed to sync blog post '{slug}' after {self.max_retries} retries: {last_error}"
        ) from last_error

    def sync_all_blog_posts(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync all cached blog posts to Notion.

        Args:
            progress_callback: Optional progress callback

        Returns:
            Dict with:
                - total: Total posts processed
                - successful: Number of successful syncs
                - failed: Number of failed syncs
                - errors: List of error messages
        """
        logger.info("Starting batch blog post sync")

        # Get cached blog posts
        cached_posts = self.cache_manager.get_cached_blog_posts()
        total = len(cached_posts)

        if total == 0:
            logger.info("No cached blog posts to sync")
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }

        logger.info(f"Found {total} cached blog posts to sync")

        # Sync each post
        successful = 0
        failed = 0
        errors = []

        for idx, post_data in enumerate(cached_posts):
            current = idx + 1
            remaining = total - current
            eta = self.calculate_eta(remaining)

            # Call progress callback
            if progress_callback:
                progress_callback({
                    'current': current,
                    'total': total,
                    'eta_seconds': eta,
                    'message': f"Syncing {post_data.get('slug', 'unknown')} ({current}/{total})"
                })

            try:
                self.sync_blog_post(post_data['slug'], progress_callback=None)  # Don't double-call callback
                successful += 1
            except SyncError as e:
                failed += 1
                errors.append(str(e))
                logger.error(f"Failed to sync post: {e}")

        logger.info(
            f"Batch blog post sync complete: "
            f"{successful} successful, {failed} failed"
        )

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'errors': errors
        }

    def sync_all_social_posts(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync all cached social posts to Notion.

        Args:
            progress_callback: Optional progress callback

        Returns:
            Dict with:
                - total: Total posts processed
                - successful: Number of successful syncs
                - failed: Number of failed syncs
                - errors: List of error messages
        """
        logger.info("Starting batch social post sync")

        # Get cached social posts
        cached_posts = self.cache_manager.get_cached_social_posts()
        total = len(cached_posts)

        if total == 0:
            logger.info("No cached social posts to sync")
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }

        logger.info(f"Found {total} cached social posts to sync")

        # Sync each post
        successful = 0
        failed = 0
        errors = []

        for idx, post_data in enumerate(cached_posts):
            current = idx + 1
            remaining = total - current
            eta = self.calculate_eta(remaining)

            # Call progress callback
            if progress_callback:
                progress_callback({
                    'current': current,
                    'total': total,
                    'eta_seconds': eta,
                    'message': f"Syncing {post_data.get('platform', 'unknown')} post ({current}/{total})"
                })

            try:
                # Acquire rate limit token
                self.rate_limiter.acquire()

                # Create Notion page
                properties = self._build_social_properties(post_data)
                page = self.notion_client.create_page(
                    parent_database_id=self.notion_client.database_ids['social_posts'],
                    properties=properties
                )

                successful += 1
                logger.info(f"Synced social post: {post_data.get('platform')} → {page['id']}")

            except Exception as e:
                failed += 1
                errors.append(str(e))
                logger.error(f"Failed to sync social post: {e}")

        logger.info(
            f"Batch social post sync complete: "
            f"{successful} successful, {failed} failed"
        )

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'errors': errors
        }

    def calculate_eta(self, num_items: int) -> float:
        """
        Calculate estimated time to sync items.

        Args:
            num_items: Number of items to sync

        Returns:
            Estimated time in seconds
        """
        if num_items == 0:
            return 0.0

        # ETA = num_items / rate (req/sec)
        return num_items / self.rate_limiter.rate

    def _build_blog_properties(self, blog_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Notion properties for blog post.

        Args:
            blog_data: Blog post data

        Returns:
            Dict of Notion properties
        """
        metadata = blog_data.get('metadata', {})
        content = blog_data.get('content', '')

        # Extract title from content or use topic
        title = metadata.get('topic', 'Untitled')
        if content and content.startswith('#'):
            first_line = content.split('\n')[0]
            title = first_line.lstrip('#').strip()

        # Use only "Name" property which exists in all Notion databases by default
        return {
            'Name': {
                'title': [
                    {
                        'text': {
                            'content': title[:2000]  # Notion title limit
                        }
                    }
                ]
            }
        }

    def _markdown_to_blocks(self, markdown: str) -> List[Dict[str, Any]]:
        """
        Convert markdown content to Notion blocks using mistletoe parser.

        Args:
            markdown: Markdown content

        Returns:
            List of Notion block objects compatible with notion-client
        """
        from mistletoe import Document
        from mistletoe.base_renderer import BaseRenderer

        class NotionClientRenderer(BaseRenderer):
            """Render mistletoe AST to notion-client blocks."""

            def __init__(self):
                super().__init__()
                self.blocks = []

            def render_document(self, token):
                """Render the root document."""
                for child in token.children:
                    self.render(child)
                return self.blocks[:100]  # Notion 100 block limit

            def render_heading(self, token):
                """Render headings (#, ##, ###)."""
                level = token.level
                if level > 3:
                    level = 3  # Notion only supports 3 levels

                heading_type = f'heading_{level}'
                self.blocks.append({
                    'object': 'block',
                    'type': heading_type,
                    heading_type: {
                        'rich_text': self._render_rich_text(token.children)
                    }
                })

            def render_paragraph(self, token):
                """Render paragraphs."""
                self.blocks.append({
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': self._render_rich_text(token.children)
                    }
                })

            def render_block_code(self, token):
                """Render code blocks."""
                language = token.language or 'plain text'
                content = token.children[0].content if token.children else ''
                self.blocks.append({
                    'object': 'block',
                    'type': 'code',
                    'code': {
                        'rich_text': [{'type': 'text', 'text': {'content': content[:2000]}}],
                        'language': language
                    }
                })

            def render_list(self, token):
                """Render lists (bulleted or numbered)."""
                for item in token.children:
                    self.render(item)

            def render_list_item(self, token):
                """Render list items."""
                # Determine if bulleted or numbered based on parent
                is_ordered = hasattr(token, 'leader') or (
                    hasattr(token, 'loose') and str(token.loose).isdigit()
                )

                list_type = 'numbered_list_item' if is_ordered else 'bulleted_list_item'
                self.blocks.append({
                    'object': 'block',
                    'type': list_type,
                    list_type: {
                        'rich_text': self._render_rich_text(token.children)
                    }
                })

            def render_quote(self, token):
                """Render blockquotes."""
                self.blocks.append({
                    'object': 'block',
                    'type': 'quote',
                    'quote': {
                        'rich_text': self._render_rich_text(token.children)
                    }
                })

            def render_thematic_break(self, token):
                """Render horizontal rules."""
                self.blocks.append({
                    'object': 'block',
                    'type': 'divider',
                    'divider': {}
                })

            def _render_rich_text(self, tokens) -> List[Dict[str, Any]]:
                """Convert span tokens to Notion rich text format."""
                rich_text = []

                for token in tokens:
                    rich_text.extend(self._render_span(token))

                if not rich_text:
                    rich_text = [{'type': 'text', 'text': {'content': ''}}]

                return rich_text

            def _render_span(self, token) -> List[Dict[str, Any]]:
                """Render a single span token with formatting."""
                from mistletoe.span_token import RawText, Strong, Emphasis, InlineCode, Link, LineBreak

                if isinstance(token, RawText):
                    content = token.content[:2000]  # Notion limit
                    if content:
                        return [{'type': 'text', 'text': {'content': content}}]
                    return []

                elif isinstance(token, Strong):
                    # Bold
                    inner_text = self._get_text_content(token.children)
                    if inner_text:
                        return [{
                            'type': 'text',
                            'text': {'content': inner_text[:2000]},
                            'annotations': {'bold': True}
                        }]
                    return []

                elif isinstance(token, Emphasis):
                    # Italic
                    inner_text = self._get_text_content(token.children)
                    if inner_text:
                        return [{
                            'type': 'text',
                            'text': {'content': inner_text[:2000]},
                            'annotations': {'italic': True}
                        }]
                    return []

                elif isinstance(token, InlineCode):
                    content = token.children[0].content if token.children else ''
                    if content:
                        return [{
                            'type': 'text',
                            'text': {'content': content[:2000]},
                            'annotations': {'code': True}
                        }]
                    return []

                elif isinstance(token, Link):
                    inner_text = self._get_text_content(token.children)
                    if inner_text:
                        return [{
                            'type': 'text',
                            'text': {
                                'content': inner_text[:2000],
                                'link': {'url': token.target}
                            }
                        }]
                    return []

                elif isinstance(token, LineBreak):
                    return [{'type': 'text', 'text': {'content': '\n'}}]

                else:
                    # Fallback for unknown tokens
                    if hasattr(token, 'children'):
                        result = []
                        for child in token.children:
                            result.extend(self._render_span(child))
                        return result
                    return []

            def _get_text_content(self, tokens) -> str:
                """Extract plain text from token children."""
                text_parts = []
                for token in tokens:
                    if hasattr(token, 'content'):
                        text_parts.append(token.content)
                    elif hasattr(token, 'children'):
                        text_parts.append(self._get_text_content(token.children))
                return ''.join(text_parts)

        # Strip markdown code fence if present (```markdown...```)
        markdown = markdown.strip()
        if markdown.startswith('```markdown'):
            # Remove opening fence
            markdown = markdown[len('```markdown'):].lstrip('\n')
            # Remove closing fence if present
            if markdown.endswith('```'):
                markdown = markdown[:-3].rstrip('\n')
        elif markdown.startswith('```'):
            # Remove generic code fence
            first_newline = markdown.find('\n')
            if first_newline > 0:
                markdown = markdown[first_newline + 1:].lstrip('\n')
            if markdown.endswith('```'):
                markdown = markdown[:-3].rstrip('\n')

        # Parse markdown and render to Notion blocks
        try:
            doc = Document(markdown)
            renderer = NotionClientRenderer()
            return renderer.render(doc)
        except Exception as e:
            # Fallback to simple paragraph if parsing fails
            self.logger.warning(f"Markdown parsing failed: {e}, using fallback")
            return [{
                'object': 'block',
                'type': 'paragraph',
                'paragraph': {
                    'rich_text': [{'type': 'text', 'text': {'content': markdown[:2000]}}]
                }
            }]

    def _build_social_properties(self, social_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Notion properties for social post.

        Args:
            social_data: Social post data

        Returns:
            Dict of Notion properties
        """
        return {
            'Name': {
                'title': [
                    {
                        'text': {
                            'content': f"{social_data.get('platform', 'Social').capitalize()} Post"[:2000]
                        }
                    }
                ]
            }
        }

    def _insert_images_into_blocks(
        self,
        blocks: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Insert hero and supporting images into Notion blocks.

        Args:
            blocks: List of Notion block objects
            metadata: Blog post metadata containing image URLs

        Returns:
            Updated list of blocks with images inserted

        Strategy:
            - Hero image: Insert after first heading (or at beginning if no heading)
            - Supporting images: Distribute evenly throughout content
        """
        images = metadata.get('images', {})
        hero_url = images.get('hero_url')
        supporting = images.get('supporting', [])

        # If no images, return original blocks
        if not hero_url and not supporting:
            return blocks

        result_blocks = []
        hero_inserted = False

        # Find first heading index
        first_heading_idx = -1
        for idx, block in enumerate(blocks):
            block_type = block.get('type', '')
            if block_type.startswith('heading_'):
                first_heading_idx = idx
                break

        # Calculate supporting image insertion points
        # Insert supporting images every N blocks (excluding headings)
        supporting_interval = max(3, len(blocks) // max(len(supporting), 1)) if supporting else 0
        next_supporting_idx = 0
        supporting_insert_counter = 0

        for idx, block in enumerate(blocks):
            # Add current block
            result_blocks.append(block)

            # Insert hero image after first heading
            if not hero_inserted and hero_url:
                if first_heading_idx >= 0 and idx == first_heading_idx:
                    # Insert after first heading
                    result_blocks.append(self._create_image_block(hero_url))
                    hero_inserted = True
                elif first_heading_idx < 0 and idx == 0:
                    # No heading found, insert at beginning (after first block)
                    result_blocks.append(self._create_image_block(hero_url))
                    hero_inserted = True

            # Insert supporting images at intervals
            if supporting and next_supporting_idx < len(supporting):
                supporting_insert_counter += 1
                if supporting_insert_counter >= supporting_interval:
                    supporting_img = supporting[next_supporting_idx]
                    result_blocks.append(self._create_image_block(
                        supporting_img.get('url'),
                        supporting_img.get('alt')
                    ))
                    next_supporting_idx += 1
                    supporting_insert_counter = 0

        # If hero image wasn't inserted yet, add it at the beginning
        if not hero_inserted and hero_url:
            result_blocks.insert(0, self._create_image_block(hero_url))

        # Add any remaining supporting images at the end
        while next_supporting_idx < len(supporting):
            supporting_img = supporting[next_supporting_idx]
            result_blocks.append(self._create_image_block(
                supporting_img.get('url'),
                supporting_img.get('alt')
            ))
            next_supporting_idx += 1

        logger.info(
            f"Images inserted: hero={bool(hero_url)}, "
            f"supporting={len(supporting)}, "
            f"total_blocks={len(result_blocks)}"
        )

        return result_blocks

    def _create_image_block(self, url: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a Notion image block.

        Args:
            url: Image URL
            caption: Optional image caption

        Returns:
            Notion image block object
        """
        block = {
            'object': 'block',
            'type': 'image',
            'image': {
                'type': 'external',
                'external': {
                    'url': url
                }
            }
        }

        # Add caption if provided
        if caption:
            block['image']['caption'] = [
                {
                    'type': 'text',
                    'text': {
                        'content': caption[:2000]  # Notion limit
                    }
                }
            ]

        return block

"""
WritingAgent - German Blog Post Generation

Generates SEO-optimized German blog posts using Qwen3-Max via OpenRouter.

Design Principles:
- Template-based prompting (from config/prompts/blog_de.md)
- Brand voice support (Professional, Casual, Technical, Friendly)
- Research data integration
- SEO metadata extraction
- Cache integration
- Comprehensive logging
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent, AgentError
from src.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class WritingError(Exception):
    """Base exception for writing errors"""
    pass


class WritingAgent(BaseAgent):
    """
    German blog post writing agent.

    Features:
    - Template-based German prompts
    - Brand voice configuration
    - Research data integration
    - SEO metadata extraction
    - Word count calculation
    - Cache integration

    Usage:
        agent = WritingAgent(api_key="sk-xxx")
        result = agent.write_blog(
            topic="KI Content Marketing",
            research_data=research_results,
            brand_voice="Professional",
            target_audience="Marketing Managers"
        )
        print(result['content'])
        print(result['metadata'])
        print(result['seo'])
    """

    def __init__(
        self,
        api_key: str,
        language: str = "de",
        cache_dir: Optional[str] = None
    ):
        """
        Initialize WritingAgent.

        Args:
            api_key: OpenRouter API key
            language: Content language (default: de)
            cache_dir: Optional cache directory

        Raises:
            WritingError: If initialization fails
        """
        # Initialize base agent with writing config
        super().__init__(agent_type="writing", api_key=api_key)

        self.language = language

        # Initialize cache manager if cache_dir provided
        self.cache_manager = None
        if cache_dir:
            self.cache_manager = CacheManager(cache_dir=cache_dir)

        # Load prompt template
        self.prompt_template = self._load_prompt_template()

        logger.info(
            f"WritingAgent initialized: language={language}, "
            f"cache_enabled={cache_dir is not None}"
        )

    def _load_prompt_template(self) -> str:
        """
        Load prompt template from config/prompts/blog_de.md.

        Returns:
            Prompt template string

        Raises:
            WritingError: If template file not found
        """
        template_path = Path(__file__).parent.parent.parent / "config" / "prompts" / f"blog_{self.language}.md"

        if not template_path.exists():
            raise WritingError(
                f"Prompt template not found: {template_path}"
            )

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            logger.info(f"Loaded prompt template: {template_path}")
            return template
        except Exception as e:
            raise WritingError(f"Failed to load prompt template: {e}") from e

    def write_blog(
        self,
        topic: str,
        research_data: Optional[Dict[str, Any]] = None,
        brand_voice: str = "Professional",
        target_audience: str = "Business professionals",
        primary_keyword: Optional[str] = None,
        secondary_keywords: Optional[List[str]] = None,
        save_to_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Generate German blog post.

        Args:
            topic: Blog post topic
            research_data: Optional research data from ResearchAgent
            brand_voice: Brand voice (Professional, Casual, Technical, Friendly)
            target_audience: Target audience description
            primary_keyword: Primary SEO keyword
            secondary_keywords: Secondary SEO keywords
            save_to_cache: Save to cache (default: False)

        Returns:
            Dict with:
                - content: Generated blog post markdown
                - metadata: Dict with topic, brand_voice, language, word_count
                - seo: Dict with meta_description, alt_texts, internal_links
                - tokens: Token usage stats
                - cost: Estimated cost
                - cache_path: (if save_to_cache=True)

        Raises:
            WritingError: If generation fails
        """
        # Validate input
        if not topic or not topic.strip():
            raise WritingError("Topic is required")

        topic = topic.strip()

        logger.info(
            f"Writing blog post: topic='{topic}', "
            f"brand_voice={brand_voice}, language={self.language}"
        )

        # Prepare prompt variables
        research_summary = ""
        keywords_str = ""

        if research_data:
            research_summary = research_data.get('summary', '')
            keywords_list = research_data.get('keywords', [])
            keywords_str = ", ".join(keywords_list)

        # Override with explicit keywords if provided
        if primary_keyword:
            primary_kw = primary_keyword
        else:
            primary_kw = research_data.get('keywords', [''])[0] if research_data and research_data.get('keywords') else topic

        if secondary_keywords:
            secondary_kw = ", ".join(secondary_keywords)
        else:
            secondary_kw = keywords_str

        # Format prompt template
        prompt = self.prompt_template.format(
            topic=topic,
            research_data=research_summary,
            primary_keyword=primary_kw,
            secondary_keywords=secondary_kw,
            brand_voice=brand_voice,
            target_audience=target_audience
        )

        # Generate blog post
        try:
            result = self.generate(prompt=prompt)
        except AgentError as e:
            logger.error(f"Failed to generate blog post: {e}")
            raise WritingError(f"Failed to generate blog post: {e}") from e

        content = result['content']

        # Extract SEO metadata
        seo_data = self._extract_seo_metadata(content)

        # Calculate word count
        word_count = self._calculate_word_count(content)

        # Build response
        response = {
            'content': content,
            'metadata': {
                'topic': topic,
                'brand_voice': brand_voice,
                'target_audience': target_audience,
                'language': self.language,
                'word_count': word_count
            },
            'seo': seo_data,
            'tokens': result['tokens'],
            'cost': result['cost']
        }

        # Save to cache if requested
        if save_to_cache and self.cache_manager:
            try:
                cache_path = self.cache_manager.save_blog_post(
                    content=content,
                    metadata=response['metadata'],
                    topic=topic
                )
                response['cache_path'] = cache_path
                logger.info(f"Saved to cache: {cache_path}")
            except Exception as e:
                logger.error(f"Failed to save to cache: {e}")
                # Don't fail the whole operation if cache fails

        logger.info(
            f"Blog post generated successfully: "
            f"words={word_count}, cost=${result['cost']:.4f}"
        )

        return response

    def _extract_seo_metadata(self, content: str) -> Dict[str, Any]:
        """
        Extract SEO metadata from generated content.

        Args:
            content: Generated blog post markdown

        Returns:
            Dict with meta_description, alt_texts, internal_links
        """
        seo_data = {
            'meta_description': '',
            'alt_texts': [],
            'internal_links': []
        }

        # Extract meta description
        meta_match = re.search(
            r'\*\*Meta-Description\*\*:\s*(.+?)(?:\n|$)',
            content,
            re.IGNORECASE
        )
        if meta_match:
            seo_data['meta_description'] = meta_match.group(1).strip()

        # Extract alt texts
        alt_text_pattern = r'-\s*Bild\s*\d+:\s*(.+?)(?:\n|$)'
        alt_texts = re.findall(alt_text_pattern, content, re.IGNORECASE)
        seo_data['alt_texts'] = [alt.strip() for alt in alt_texts]

        # Extract internal links
        link_pattern = r'-\s*\[([^\]]+)\]|^-\s*([^\n]+?)(?:\n|$)'
        # Look in "Interne Verlinkung" section
        internal_section_match = re.search(
            r'\*\*Interne Verlinkung\*\*:(.+?)(?=\n##|\n\*\*|$)',
            content,
            re.IGNORECASE | re.DOTALL
        )
        if internal_section_match:
            section = internal_section_match.group(1)
            links = re.findall(r'-\s*(.+?)(?:\n|$)', section)
            seo_data['internal_links'] = [link.strip() for link in links if link.strip()]

        return seo_data

    def _calculate_word_count(self, content: str) -> int:
        """
        Calculate word count of blog post.

        Args:
            content: Blog post markdown

        Returns:
            Word count (int)
        """
        # Remove markdown headers, links, formatting
        text = re.sub(r'#+ ', '', content)  # Remove headers
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Remove links, keep text
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)  # Remove bold
        text = re.sub(r'\_([^\_]+)\_', r'\1', text)  # Remove italic

        # Count words
        words = text.split()
        return len(words)

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
from src.synthesis.cross_topic_synthesizer import CrossTopicSynthesizer
from src.synthesis.cluster_manager import ClusterManager
from src.database.sqlite_manager import SQLiteManager

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
        cache_dir: Optional[str] = None,
        db_path: str = "data/topics.db",
        enable_synthesis: bool = True
    ):
        """
        Initialize WritingAgent.

        Args:
            api_key: OpenRouter API key
            language: Content language (default: de)
            cache_dir: Optional cache directory
            db_path: Path to SQLite database (default: data/topics.db)
            enable_synthesis: Enable cross-topic synthesis (default: True)

        Raises:
            WritingError: If initialization fails
        """
        # Initialize base agent with writing config
        super().__init__(agent_type="writing", api_key=api_key)

        self.language = language
        self.enable_synthesis = enable_synthesis
        self.db_path = db_path

        # Initialize cache manager if cache_dir provided
        self.cache_manager = None
        if cache_dir:
            self.cache_manager = CacheManager(cache_dir=cache_dir)

        # Initialize SQLite manager for cluster operations
        self.db_manager = None
        try:
            self.db_manager = SQLiteManager(db_path=db_path)
            logger.info("sqlite_manager_initialized", db_path=db_path)
        except Exception as e:
            logger.warning(f"failed_to_initialize_db_manager: {e}")
            self.db_manager = None

        # Initialize cross-topic synthesizer
        self.synthesizer = None
        if enable_synthesis and self.db_manager:
            try:
                self.synthesizer = CrossTopicSynthesizer(self.db_manager)
                logger.info("cross_topic_synthesis_enabled")
            except Exception as e:
                logger.warning(f"failed_to_initialize_synthesizer: {e}, synthesis disabled")
                self.synthesizer = None

        # Initialize cluster manager
        self.cluster_manager = None
        if self.db_manager:
            try:
                self.cluster_manager = ClusterManager(self.db_manager)
                logger.info("cluster_manager_enabled")
            except Exception as e:
                logger.warning(f"failed_to_initialize_cluster_manager: {e}, clustering disabled")
                self.cluster_manager = None

        # Load prompt template
        self.prompt_template = self._load_prompt_template()

        logger.info(
            f"WritingAgent initialized: language={language}, "
            f"cache_enabled={cache_dir is not None}, "
            f"synthesis_enabled={self.synthesizer is not None}, "
            f"cluster_enabled={self.cluster_manager is not None}"
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
        save_to_cache: bool = False,
        topic_id: Optional[str] = None,
        enable_synthesis: Optional[bool] = None,
        cluster_id: Optional[str] = None,
        cluster_role: Optional[str] = None
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
            topic_id: Optional topic ID for synthesis lookup (default: None)
            enable_synthesis: Override synthesis setting for this call (default: None, uses instance setting)
            cluster_id: Optional cluster ID for Hub + Spoke strategy (default: None)
            cluster_role: Optional cluster role: "Hub", "Spoke", or "Standalone" (default: None)

        Returns:
            Dict with:
                - content: Generated blog post markdown
                - metadata: Dict with topic, brand_voice, language, word_count, cluster_id, cluster_role
                - seo: Dict with meta_description, alt_texts, internal_links
                - tokens: Token usage stats
                - cost: Estimated cost
                - cache_path: (if save_to_cache=True)
                - synthesis: (if synthesis enabled) Dict with related topics and unique angles
                - internal_link_suggestions: (if cluster enabled) List of suggested internal links

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
        synthesis_result = None

        if research_data:
            # Check if deep research article is available (from cache)
            deep_article = research_data.get('article', '')

            if deep_article:
                # Use deep research article as context (2000+ words with citations)
                # Extract first 1500 chars for summary (keep manageable)
                research_summary = deep_article[:1500] + "\n\n[Deep research available - use inline citations]"
                logger.info("using_deep_research_article", article_length=len(deep_article))
            else:
                # Use simple research summary
                research_summary = research_data.get('summary', '')
                logger.info("using_simple_research_summary")

            keywords_list = research_data.get('keywords', [])
            keywords_str = ", ".join(keywords_list)

        # Add cross-topic synthesis if enabled
        use_synthesis = enable_synthesis if enable_synthesis is not None else self.enable_synthesis
        if use_synthesis and self.synthesizer and topic_id:
            try:
                logger.info("fetching_cross_topic_synthesis", topic_id=topic_id)
                related_context = self.synthesizer.get_related_context_for_writing(
                    topic_id=topic_id,
                    max_related=3
                )

                if related_context:
                    # Append synthesis to research summary
                    research_summary += f"\n\n---\n\n{related_context}"
                    logger.info("cross_topic_synthesis_added", topic_id=topic_id)

                    # Get full synthesis for metadata
                    synthesis_result = self.synthesizer.synthesize_related_topics(
                        topic=topic,
                        topic_id=topic_id,
                        max_related=3
                    )
                else:
                    logger.info("no_related_topics_for_synthesis", topic_id=topic_id)

            except Exception as e:
                logger.warning(f"synthesis_failed: {e}, continuing without synthesis")
                synthesis_result = None

        # Add cluster context if enabled
        internal_link_suggestions = []
        if cluster_id and self.cluster_manager:
            try:
                logger.info("fetching_cluster_context", cluster_id=cluster_id, cluster_role=cluster_role)

                # Get cluster articles
                cluster_articles = self.cluster_manager.get_cluster_articles(cluster_id)

                # Build cluster context
                cluster_context = f"\n\n--- CLUSTER CONTEXT (Hub + Spoke SEO Strategy) ---\n\n"
                cluster_context += f"This article is part of the '{cluster_id}' content cluster.\n"
                cluster_context += f"Role: {cluster_role or 'Standalone'}\n\n"

                if cluster_articles["hub"]:
                    hub = cluster_articles["hub"]
                    cluster_context += f"Hub Article: {hub['title']}\n"

                if cluster_articles["spokes"]:
                    cluster_context += f"\nRelated Spoke Articles ({len(cluster_articles['spokes'])}):\n"
                    for spoke in cluster_articles["spokes"]:
                        cluster_context += f"- {spoke['title']}\n"

                cluster_context += "\nInternal Linking Instructions:\n"
                cluster_context += "- Link naturally to related articles in the cluster\n"
                cluster_context += "- Use descriptive anchor text (not 'click here')\n"
                cluster_context += "- Spokes should link to the Hub article\n"
                cluster_context += "- Hub should link to all Spoke articles\n"

                # Append to research summary
                research_summary += cluster_context
                logger.info("cluster_context_added", cluster_id=cluster_id)

                # Generate internal link suggestions
                if topic_id:
                    internal_link_suggestions = self.cluster_manager.suggest_internal_links(
                        topic_id=topic_id,
                        cluster_id=cluster_id,
                        max_links=5
                    )
                    logger.info("internal_links_suggested", count=len(internal_link_suggestions))

            except Exception as e:
                logger.warning(f"cluster_context_failed: {e}, continuing without cluster context")

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
                'word_count': word_count,
                'cluster_id': cluster_id,
                'cluster_role': cluster_role
            },
            'seo': seo_data,
            'tokens': result['tokens'],
            'cost': result['cost']
        }

        # Add synthesis if available
        if synthesis_result:
            response['synthesis'] = synthesis_result

        # Add internal link suggestions if available
        if internal_link_suggestions:
            response['internal_link_suggestions'] = [
                link.to_dict() for link in internal_link_suggestions
            ]

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

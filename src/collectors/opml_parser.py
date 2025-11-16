"""
OPML Parser

Parses OPML (Outline Processor Markup Language) files to extract RSS feed URLs.

OPML is a standard XML format for RSS feed lists, commonly used by feed readers
and aggregators like Feedly, Inoreader, and AllTop.

Typical OPML structure:
    <opml>
      <body>
        <outline text="Category">
          <outline type="rss" text="Feed Name" xmlUrl="https://example.com/feed"/>
        </outline>
      </body>
    </opml>
"""

import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OPMLFeed:
    """
    RSS feed extracted from OPML file.
    """
    url: str  # Feed URL (xmlUrl in OPML)
    title: str  # Feed title
    website_url: Optional[str] = None  # Website URL (htmlUrl in OPML)
    category: Optional[str] = None  # Category from parent outline
    description: Optional[str] = None  # Feed description

    def __repr__(self) -> str:
        return f"OPMLFeed(title='{self.title[:50]}...', url='{self.url[:50]}...')"


class OPMLParser:
    """
    Parse OPML files to extract RSS feeds.

    Usage:
        parser = OPMLParser()
        feeds = parser.parse_file("feeds.opml")

        for feed in feeds:
            print(f"{feed.title}: {feed.url}")
    """

    def __init__(self):
        """Initialize OPML parser."""
        self.feeds_found = 0
        self.errors = 0

    def parse_file(self, file_path: str) -> List[OPMLFeed]:
        """
        Parse OPML file and extract feeds.

        Args:
            file_path: Path to OPML file

        Returns:
            List of OPMLFeed objects
        """
        try:
            logger.info("opml_parse_started", file=file_path)

            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Use BeautifulSoup with xml parser (more lenient than ET)
            soup = BeautifulSoup(content, 'xml')

            # Find body element
            body = soup.find('body')
            if not body:
                logger.warning("opml_no_body", file=file_path)
                return []

            # Extract feeds from outline elements
            feeds = []
            for outline in body.find_all('outline'):
                xml_url = outline.get('xmlUrl')
                if xml_url:  # This is a feed
                    feed = OPMLFeed(
                        url=xml_url.strip(),
                        title=(outline.get('title') or outline.get('text') or "Untitled").strip(),
                        website_url=outline.get('htmlUrl', '').strip() or None,
                        category=self._get_parent_category(outline),
                        description=outline.get('description', '').strip() or None
                    )
                    feeds.append(feed)
                    self.feeds_found += 1

            # Remove duplicates
            unique_feeds = self._deduplicate_feeds(feeds)

            logger.info(
                "opml_parse_complete",
                file=file_path,
                total_feeds=len(feeds),
                unique_feeds=len(unique_feeds)
            )

            return unique_feeds

        except Exception as e:
            logger.error(
                "opml_parse_failed",
                file=file_path,
                error=str(e)
            )
            self.errors += 1
            return []

    def _get_parent_category(self, element) -> Optional[str]:
        """
        Get category from parent outline element.

        Args:
            element: BeautifulSoup element

        Returns:
            Category name or None
        """
        parent = element.parent
        while parent:
            if parent.name == 'outline' and not parent.get('xmlUrl'):
                # Parent is a category (no xmlUrl)
                return parent.get('title') or parent.get('text')
            parent = parent.parent
        return None

    def parse_string(self, opml_content: str) -> List[OPMLFeed]:
        """
        Parse OPML from string content.

        Args:
            opml_content: OPML XML content as string

        Returns:
            List of OPMLFeed objects
        """
        try:
            logger.info("opml_string_parse_started")

            # Parse XML from string
            root = ET.fromstring(opml_content)

            # Extract feeds from <body> section
            body = root.find('body')
            if body is None:
                logger.warning("opml_no_body")
                return []

            # Recursively extract feeds
            feeds = self._extract_feeds(body)

            # Remove duplicates
            unique_feeds = self._deduplicate_feeds(feeds)

            logger.info(
                "opml_string_parse_complete",
                total_feeds=len(feeds),
                unique_feeds=len(unique_feeds)
            )

            return unique_feeds

        except ET.ParseError as e:
            logger.error("opml_string_parse_error", error=str(e))
            self.errors += 1
            return []

        except Exception as e:
            logger.error("opml_string_parse_failed", error=str(e))
            self.errors += 1
            return []

    def _extract_feeds(
        self,
        element: ET.Element,
        category: Optional[str] = None
    ) -> List[OPMLFeed]:
        """
        Recursively extract feeds from outline elements.

        Args:
            element: XML element to process
            category: Current category name (from parent outline)

        Returns:
            List of OPMLFeed objects
        """
        feeds = []

        # Process all <outline> children
        for outline in element.findall('outline'):
            # Get attributes
            outline_type = outline.get('type', '').lower()
            xml_url = outline.get('xmlUrl')
            html_url = outline.get('htmlUrl')
            text = outline.get('text', '')
            title = outline.get('title', text)
            description = outline.get('description')

            # Check if this is a feed or a category
            if xml_url:
                # This is a feed
                feed = OPMLFeed(
                    url=xml_url.strip(),
                    title=title.strip() if title else "Untitled Feed",
                    website_url=html_url.strip() if html_url else None,
                    category=category,
                    description=description.strip() if description else None
                )
                feeds.append(feed)
                self.feeds_found += 1

            else:
                # This is a category - use text/title as category name
                new_category = title or text or category

                # Recursively process children
                child_feeds = self._extract_feeds(outline, category=new_category)
                feeds.extend(child_feeds)

        return feeds

    def _deduplicate_feeds(self, feeds: List[OPMLFeed]) -> List[OPMLFeed]:
        """
        Remove duplicate feeds (same URL).

        Args:
            feeds: List of feeds

        Returns:
            List of unique feeds
        """
        seen_urls = set()
        unique_feeds = []

        for feed in feeds:
            # Normalize URL (lowercase, strip trailing /)
            normalized_url = feed.url.lower().rstrip('/')

            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_feeds.append(feed)

        duplicates_removed = len(feeds) - len(unique_feeds)
        if duplicates_removed > 0:
            logger.info(
                "opml_duplicates_removed",
                count=duplicates_removed
            )

        return unique_feeds

    def parse_directory(
        self,
        directory: str,
        pattern: str = "*.opml"
    ) -> Dict[str, List[OPMLFeed]]:
        """
        Parse all OPML files in a directory.

        Args:
            directory: Directory path
            pattern: File pattern to match (default: *.opml)

        Returns:
            Dictionary mapping filename -> list of feeds
        """
        logger.info(
            "opml_directory_parse_started",
            directory=directory,
            pattern=pattern
        )

        results = {}
        directory_path = Path(directory)

        # Find all matching files
        opml_files = list(directory_path.glob(pattern))

        logger.info(
            "opml_files_found",
            count=len(opml_files)
        )

        # Parse each file
        for file_path in opml_files:
            feeds = self.parse_file(str(file_path))
            results[file_path.name] = feeds

        total_feeds = sum(len(feeds) for feeds in results.values())

        logger.info(
            "opml_directory_parse_complete",
            files_processed=len(results),
            total_feeds=total_feeds,
            errors=self.errors
        )

        return results

    def get_statistics(self) -> Dict:
        """
        Get parsing statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "feeds_found": self.feeds_found,
            "errors": self.errors
        }

    def categorize_feeds(
        self,
        feeds: List[OPMLFeed]
    ) -> Dict[str, List[OPMLFeed]]:
        """
        Group feeds by category.

        Args:
            feeds: List of feeds

        Returns:
            Dictionary mapping category -> list of feeds
        """
        categorized = {}

        for feed in feeds:
            category = feed.category or "Uncategorized"

            if category not in categorized:
                categorized[category] = []

            categorized[category].append(feed)

        logger.info(
            "feeds_categorized",
            categories=len(categorized),
            total_feeds=len(feeds)
        )

        return categorized

    def export_to_list(
        self,
        feeds: List[OPMLFeed],
        format: str = "urls"
    ) -> List[str]:
        """
        Export feeds as list of URLs or titles.

        Args:
            feeds: List of feeds
            format: "urls", "titles", or "both"

        Returns:
            List of strings
        """
        if format == "urls":
            return [feed.url for feed in feeds]
        elif format == "titles":
            return [feed.title for feed in feeds]
        elif format == "both":
            return [f"{feed.title}: {feed.url}" for feed in feeds]
        else:
            raise ValueError(f"Invalid format: {format}")

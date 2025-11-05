"""
Deduplicator

MinHash/LSH-based near-duplicate detection with canonical URL normalization.

Target: <5% deduplication rate
Uses: datasketch library for efficient similarity search
"""

from typing import Dict, Set, List
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from datasketch import MinHash, MinHashLSH

from src.models.document import Document
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Deduplicator:
    """
    Near-duplicate detection using MinHash and LSH

    Features:
    - Content-based deduplication (MinHash/LSH)
    - Canonical URL normalization
    - Statistics tracking
    - Configurable similarity threshold
    """

    # Common tracking parameters to remove
    TRACKING_PARAMS = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'ref', 'source', 'fbclid', 'gclid', 'msclkid',
        '_ga', '_gl', 'mc_cid', 'mc_eid'
    }

    def __init__(self, threshold: float = 0.7, num_perm: int = 128):
        """
        Initialize deduplicator

        Args:
            threshold: Jaccard similarity threshold (0.7 = 70% similar)
            num_perm: Number of permutations for MinHash (higher = more accurate, slower)
        """
        self.threshold = threshold
        self.num_perm = num_perm

        # LSH index for fast similarity search
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)

        # Track seen canonical URLs
        self.seen_urls: Set[str] = set()

        # Statistics
        self.total_documents = 0
        self.duplicates_found = 0

        logger.info("deduplicator_initialized", threshold=threshold, num_perm=num_perm)

    def is_duplicate(self, doc: Document) -> bool:
        """
        Check if document is a duplicate (content or URL)

        Args:
            doc: Document to check

        Returns:
            True if document is duplicate, False otherwise
        """
        self.total_documents += 1

        # Check canonical URL first (fast)
        if doc.canonical_url in self.seen_urls:
            logger.info("duplicate_detected_url", doc_id=doc.id, url=doc.canonical_url)
            self.duplicates_found += 1
            return True

        # Check content similarity (MinHash/LSH)
        minhash = self.compute_minhash(doc.content)
        duplicates = self.lsh.query(minhash)

        if len(duplicates) > 0:
            logger.info("duplicate_detected_content", doc_id=doc.id, similar_to=duplicates)
            self.duplicates_found += 1
            return True

        return False

    def add(self, doc: Document) -> None:
        """
        Add document to deduplication index

        Args:
            doc: Document to add
        """
        # Add canonical URL
        self.seen_urls.add(doc.canonical_url)

        # Add content hash to LSH
        minhash = self.compute_minhash(doc.content)
        self.lsh.insert(doc.id, minhash)

        logger.info("document_added_to_index", doc_id=doc.id)

    def deduplicate(self, documents: List[Document]) -> List[Document]:
        """
        Deduplicate a list of documents.

        Args:
            documents: List of documents to deduplicate

        Returns:
            List of unique documents (duplicates removed)
        """
        unique_docs = []

        for doc in documents:
            if not self.is_duplicate(doc):
                self.add(doc)
                unique_docs.append(doc)

        logger.info(
            "deduplication_completed",
            total=len(documents),
            unique=len(unique_docs),
            duplicates=len(documents) - len(unique_docs),
            duplicate_rate=f"{(len(documents) - len(unique_docs)) / len(documents) * 100:.2f}%" if documents else "0%"
        )

        return unique_docs

    def is_canonical_duplicate(self, doc1: Document, doc2: Document) -> bool:
        """
        Check if two documents have the same canonical URL

        Args:
            doc1: First document
            doc2: Second document

        Returns:
            True if canonical URLs match, False otherwise
        """
        return doc1.canonical_url == doc2.canonical_url

    def compute_minhash(self, content: str) -> MinHash:
        """
        Compute MinHash signature for content

        Args:
            content: Text content to hash

        Returns:
            MinHash object
        """
        minhash = MinHash(num_perm=self.num_perm)

        # Tokenize by whitespace and add to MinHash
        words = content.lower().split()
        for word in words:
            minhash.update(word.encode('utf-8'))

        return minhash

    def normalize_url(self, url: str) -> str:
        """
        Normalize URL to canonical form

        Removes:
        - www prefix
        - Tracking parameters
        - Trailing slash
        - URL fragments
        - Converts to lowercase

        Args:
            url: URL to normalize

        Returns:
            Normalized canonical URL
        """
        # Parse URL
        parsed = urlparse(url.lower())

        # Remove www prefix from hostname
        hostname = parsed.netloc
        if hostname.startswith('www.'):
            hostname = hostname[4:]

        # Filter out tracking parameters
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            # Remove tracking params
            clean_params = {k: v for k, v in params.items() if k not in self.TRACKING_PARAMS}

            # Rebuild query string (sorted for consistency)
            query_string = urlencode(sorted(clean_params.items()), doseq=True)
        else:
            query_string = ''

        # Remove trailing slash from path
        path = parsed.path.rstrip('/')

        # Reconstruct URL without fragment (hash)
        normalized = urlunparse((
            parsed.scheme,
            hostname,
            path,
            parsed.params,
            query_string,
            ''  # Remove fragment
        ))

        return normalized

    def mark_duplicate(self, doc: Document) -> None:
        """
        Mark document as duplicate (for statistics tracking)

        Args:
            doc: Document that was determined to be duplicate
        """
        # This is called externally when a duplicate is confirmed
        # (Already counted in is_duplicate, but this can be used
        # for additional bookkeeping if needed)
        logger.info("duplicate_marked", doc_id=doc.id)

    def get_stats(self) -> Dict[str, float]:
        """
        Get deduplication statistics

        Returns:
            Dictionary with statistics:
            - total_documents: Total documents checked
            - duplicates_found: Number of duplicates detected
            - deduplication_rate: Percentage of duplicates (0-100)
        """
        if self.total_documents == 0:
            rate = 0.0
        else:
            rate = (self.duplicates_found / self.total_documents) * 100

        return {
            'total_documents': self.total_documents,
            'duplicates_found': self.duplicates_found,
            'deduplication_rate': round(rate, 2)
        }

    def reset_stats(self) -> None:
        """Reset statistics counters"""
        self.total_documents = 0
        self.duplicates_found = 0
        logger.info("stats_reset")

    def clear(self) -> None:
        """Clear all stored data (URLs and LSH index)"""
        self.seen_urls.clear()
        self.lsh = MinHashLSH(threshold=self.threshold, num_perm=self.num_perm)
        self.reset_stats()
        logger.info("deduplicator_cleared")

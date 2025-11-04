"""
Entity Extractor

Extracts named entities and keywords from Document objects using LLMProcessor.
Updates Document with enrichment data (entities, keywords, status).

Example:
    from src.processors.entity_extractor import EntityExtractor
    from src.models.document import Document

    extractor = EntityExtractor()

    # Process single document
    document = extractor.process(doc)
    print(f"Entities: {document.entities}")
    print(f"Keywords: {document.keywords}")

    # Batch process
    documents = extractor.process_batch(docs, skip_errors=True)
    print(extractor.get_statistics())
"""

from typing import List, Dict
from src.models.document import Document
from src.processors.llm_processor import LLMProcessor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EntityExtractionError(Exception):
    """Raised when entity extraction fails"""
    pass


class EntityExtractor:
    """
    Extract entities and keywords from documents using LLM

    Features:
    - Processes Document objects
    - Uses LLMProcessor for extraction
    - Updates document status to 'processed'
    - Tracks statistics (success/failure rates)
    - Supports batch processing
    - Graceful error handling
    """

    def __init__(self, model: str = "qwen/qwen-2.5-7b-instruct"):
        """
        Initialize entity extractor

        Args:
            model: OpenRouter model ID for LLM processing

        Raises:
            ValueError: If OPENROUTER_API_KEY not set
        """
        self.llm_processor = LLMProcessor(model=model)

        # Statistics
        self.total_documents = 0
        self.processed_documents = 0
        self.failed_documents = 0

        logger.info("entity_extractor_initialized", model=model)

    def process(self, doc: Document, force: bool = False) -> Document:
        """
        Extract entities and keywords from a document

        Args:
            doc: Document to process
            force: If True, reprocess even if already processed

        Returns:
            Updated Document with entities and keywords

        Raises:
            EntityExtractionError: If extraction fails
        """
        # Skip if already processed (unless force=True)
        if not force and doc.has_entities() and doc.has_keywords():
            logger.info("document_already_processed", doc_id=doc.id)
            return doc

        # Validate document has content
        if not doc.content or len(doc.content.strip()) == 0:
            self.failed_documents += 1
            logger.error("document_empty_content", doc_id=doc.id)
            raise EntityExtractionError(f"Document has empty content: {doc.id}")

        self.total_documents += 1

        try:
            # Extract entities and keywords using LLM
            result = self.llm_processor.extract_entities_keywords(
                content=doc.content,
                language=doc.language
            )

            # Update document
            doc.entities = result.entities
            doc.keywords = result.keywords
            doc.status = "processed"

            self.processed_documents += 1

            logger.info(
                "entities_extracted",
                doc_id=doc.id,
                num_entities=len(result.entities),
                num_keywords=len(result.keywords)
            )

            return doc

        except Exception as e:
            self.failed_documents += 1
            logger.error("extraction_failed", doc_id=doc.id, error=str(e))
            raise EntityExtractionError(f"Failed to extract entities from {doc.id}: {e}")

    def process_batch(self, docs: List[Document], skip_errors: bool = False) -> List[Document]:
        """
        Process multiple documents in batch

        Args:
            docs: List of documents to process
            skip_errors: If True, skip failed documents instead of raising

        Returns:
            List of successfully processed documents

        Raises:
            EntityExtractionError: If skip_errors=False and any document fails
        """
        if not docs:
            logger.info("process_batch_empty")
            return []

        processed = []

        for doc in docs:
            try:
                result = self.process(doc)
                processed.append(result)
            except EntityExtractionError as e:
                if not skip_errors:
                    raise
                logger.warning("batch_document_skipped", doc_id=doc.id, error=str(e))

        logger.info(
            "batch_processing_complete",
            total=len(docs),
            processed=len(processed),
            failed=len(docs) - len(processed)
        )

        return processed

    def get_statistics(self) -> Dict[str, float]:
        """
        Get processing statistics

        Returns:
            Dictionary with statistics:
            - total_documents: Total documents processed
            - processed_documents: Successfully processed
            - failed_documents: Failed to process
            - success_rate: Ratio of successful to total (0-1)
            - failure_rate: Ratio of failed to total (0-1)
        """
        success_rate = (
            self.processed_documents / self.total_documents
            if self.total_documents > 0
            else 0.0
        )
        failure_rate = (
            self.failed_documents / self.total_documents
            if self.total_documents > 0
            else 0.0
        )

        return {
            'total_documents': self.total_documents,
            'processed_documents': self.processed_documents,
            'failed_documents': self.failed_documents,
            'success_rate': success_rate,
            'failure_rate': failure_rate
        }

    def reset_statistics(self) -> None:
        """Reset all statistics to zero"""
        self.total_documents = 0
        self.processed_documents = 0
        self.failed_documents = 0
        logger.info("statistics_reset")

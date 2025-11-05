"""Content synthesis module for generating articles from research sources"""

from src.research.synthesizer.content_synthesizer import (
    ContentSynthesizer,
    PassageExtractionStrategy,
    SynthesisError
)

__all__ = ['ContentSynthesizer', 'PassageExtractionStrategy', 'SynthesisError']

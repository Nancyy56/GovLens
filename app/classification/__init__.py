"""Document classification package.

Provides deterministic, rule-based classification of government documents
into typed categories without ML, LLM, or embedding dependencies.
"""

from app.classification.classifier import RuleBasedDocumentClassifier
from app.classification.interfaces import DocumentClassifier

__all__ = [
    "DocumentClassifier",
    "RuleBasedDocumentClassifier",
]

"""
Data access layer repositories.

Repositories provide abstraction over database operations,
implementing the Repository pattern for clean data access.
Handles all CRUD operations and complex queries on models.
"""

from app.repositories.documents import (
    DocumentChunkRepository,
    DocumentRelationshipRepository,
    DocumentRepository,
)

__all__ = [
    "DocumentChunkRepository",
    "DocumentRelationshipRepository",
    "DocumentRepository",
]

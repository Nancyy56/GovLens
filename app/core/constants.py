"""
Application constants and configuration values.

Define immutable constants used across the application such as
API versions, default values, and configuration parameters.
"""

# API Configuration
API_V1_STR = "/api/v1"
PROJECT_NAME = "GovLens"
PROJECT_DESCRIPTION = "Government Document Lens: A comprehensive platform for analyzing government documents"

# Database Configuration
DB_POOL_SIZE = 5
DB_MAX_OVERFLOW = 10
DB_POOL_TIMEOUT = 30
DB_POOL_RECYCLE = 3600

# Qdrant Configuration
QDRANT_COLLECTION_DEFAULT_SIZE = 384  # Default vector size placeholder

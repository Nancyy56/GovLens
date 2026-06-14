# Docker Notes

This directory contains Docker-related documentation only. The main application Dockerfile is in the project root.

## Services in `docker-compose.yml`

- `postgres`: PostgreSQL 16 for document metadata, chunk text, and supersession relationships
- `qdrant`: Qdrant vector database for embeddings and retrieval payloads
- `ollama`: Ollama service for local LLM generation
- `app`: FastAPI application that runs Alembic migrations and starts Uvicorn

## Current Scope

Docker Compose is used for local service orchestration. The compose file does not implement production hardening such as authentication, TLS termination, monitoring, backups, or deployment strategy.

## Useful Commands

```bash
docker compose up --build -d
docker compose ps
docker compose exec ollama ollama pull qwen3:8b
docker compose exec ollama ollama list
curl http://localhost:6333/health
curl http://localhost:8000/api/v1/health
```

## Notes

- The Dockerfile installs Tesseract and Poppler utilities for OCR support.
- The app service mounts the repository into `/app` for development.
- The app service runs `alembic -c alembic/alembic.ini upgrade head` before starting Uvicorn.
- Ollama and HuggingFace model availability may require network access during setup.

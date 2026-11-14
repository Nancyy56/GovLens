"""Query routes: a complete answer, or the answer streamed as it is written."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_query_service
from app.api.schemas import QueryRequest
from app.services.query import QueryService
from app.retrieval.schemas import RetrievedChunk
from app.services.schemas import QueryResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResult)
def query_documents(
    request: QueryRequest,
    service: QueryService = Depends(get_query_service),
):
    return service.query(
        query=request.query,
        top_k=request.top_k,
        document_numbers=request.document_numbers,
    )


@router.post("/search", response_model=list[RetrievedChunk])
def search_documents(
    request: QueryRequest,
    service: QueryService = Depends(get_query_service),
):
    """Return the ranked chunks hybrid retrieval finds, without asking the LLM.

    Fast, so it suits retrieval debugging and evaluation.
    """

    return service.search(
        query=request.query,
        top_k=request.top_k,
        document_numbers=request.document_numbers,
    )


@router.post(
    "/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Server-sent events"}},
)
def stream_query(
    request: QueryRequest,
    service: QueryService = Depends(get_query_service),
):
    """Stream the answer as server-sent events.

    Events, in order: one ``retrieval`` (counts and supersession warnings),
    many ``token`` (``{"text": ...}`` pieces of the answer), then one ``done``
    with the full result, including only the citations the answer used. An
    ``error`` event is sent if generation fails part-way.
    """

    events = service.stream(
        query=request.query,
        top_k=request.top_k,
        document_numbers=request.document_numbers,
    )
    return StreamingResponse(
        _to_sse(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _to_sse(events: Iterator[dict]) -> Iterator[str]:
    try:
        for event in events:
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
    except Exception as exc:
        logger.exception("Streaming query failed")
        yield f"event: error\ndata: {json.dumps({'detail': str(exc) or exc.__class__.__name__})}\n\n"

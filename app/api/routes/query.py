"""Query routes: a complete answer, or the answer streamed as it is written."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_query_service
from app.api.schemas import QueryRequest
from app.api.security import Principal, require_viewer
from app.services import history
from app.services.query import QueryService
from app.retrieval.schemas import RetrievedChunk
from app.services.schemas import QueryResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResult)
def query_documents(
    request: QueryRequest,
    principal: Principal = Depends(require_viewer),
    service: QueryService = Depends(get_query_service),
):
    started = time.perf_counter()
    result = service.query(
        query=request.query,
        top_k=request.top_k,
        document_numbers=request.document_numbers,
    )
    history.record_query(
        user_id=principal.user_id,
        username=principal.username,
        result=result,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    return result


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
    principal: Principal = Depends(require_viewer),
    service: QueryService = Depends(get_query_service),
):
    """Stream the answer as server-sent events.

    Events, in order: one ``retrieval`` (counts and supersession warnings),
    many ``token`` (``{"text": ...}`` pieces of the answer), then one ``done``
    with the full result, including only the citations the answer used. An
    ``error`` event is sent if generation fails part-way. After ``done``, a
    ``saved`` event carries the history id (``{"id": ...}``) used to rate the answer.
    """

    events = service.stream(
        query=request.query,
        top_k=request.top_k,
        document_numbers=request.document_numbers,
    )
    return StreamingResponse(
        _to_sse(events, principal),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _record(data: dict, principal: Principal, started: float):
    """Save a finished answer to the user's history. Never raises: logging must not break an answer."""

    try:
        return history.record_query(
            user_id=principal.user_id,
            username=principal.username,
            result=QueryResult.model_validate(data),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception:
        logger.warning("Skipping history for an answer that could not be recorded", exc_info=True)
        return None


def _to_sse(events: Iterator[dict], principal: Principal | None = None) -> Iterator[str]:
    started = time.perf_counter()
    try:
        for event in events:
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
            if event["event"] == "done" and principal is not None:
                log_id = _record(event["data"], principal, started)
                if log_id is not None:
                    yield f"event: saved\ndata: {json.dumps({'id': str(log_id)})}\n\n"
    except Exception as exc:
        logger.exception("Streaming query failed")
        yield f"event: error\ndata: {json.dumps({'detail': str(exc) or exc.__class__.__name__})}\n\n"

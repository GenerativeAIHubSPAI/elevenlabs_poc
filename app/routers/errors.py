"""HTTP mappings for service errors shared by several routers."""

from fastapi import HTTPException, status

from app.services.static_kb_jobs import (
    LOADING_RETRY_AFTER_SECONDS,
    KnowledgeSourceNotReadyError,
)


def knowledge_source_http_error(exc: KnowledgeSourceNotReadyError) -> HTTPException:
    """503 for a topic that cannot answer, with Retry-After while it loads.

    503 rather than 4xx: the request is valid, the server just cannot serve that
    topic right now.
    """
    headers = (
        {"Retry-After": str(LOADING_RETRY_AFTER_SECONDS)}
        if exc.status == "loading"
        else None
    )

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=exc.to_detail(),
        headers=headers,
    )

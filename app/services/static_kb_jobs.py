"""Static knowledge-base loading state.

Tracks the startup discovery of static topics in S3 and every per-namespace load
(queued, running, succeeded, failed), and turns that into one readiness answer
per topic: "ready", "loading" or "unavailable".

Routes ask for that answer before calling the LLM. Without it, a topic that
failed or was still loading had no context, and the model -- told not to mention
internal limitations -- answered vaguely with a 200, hiding the failure.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Lock, Thread
from typing import Any, Literal

from app.core.knowledge_sources import (
    STATIC_BUSINESS_EXAMPLES,
    list_knowledge_source_options,
)
from app.services.kb import kb_store
from app.services.static_kb_loader import (
    StaticKBLoaderError,
    list_static_namespaces,
    load_static_namespace,
)

logger = logging.getLogger(__name__)

ReadinessStatus = Literal["ready", "loading", "unavailable"]

# Seconds a client should wait before retrying a topic that is still loading.
LOADING_RETRY_AFTER_SECONDS = 5

_STATIC_NAMESPACES = frozenset(
    example["namespace"] for example in STATIC_BUSINESS_EXAMPLES.values()
)

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = Lock()

# Startup discovery. "not_started" until the app lifespan runs it, so a process
# that never preloads (tests, scripts) reports topics as unavailable rather than
# as loading forever.
_preload: dict[str, Any] = {"status": "not_started", "error": None, "missing": []}
_preload_lock = Lock()


class KnowledgeSourceNotReadyError(Exception):
    """Raised when a static topic is asked for before it can answer."""

    def __init__(self, namespace: str, status: ReadinessStatus, reason: str):
        self.namespace = namespace
        self.status = status
        self.reason = reason
        super().__init__(f"Knowledge source '{namespace}' is {status}: {reason}")

    @property
    def code(self) -> str:
        if self.status == "loading":
            return "knowledge_source_loading"

        return "knowledge_source_unavailable"

    def to_detail(self) -> dict[str, str]:
        """Error body in the {code, message} shape the API already uses."""
        return {
            "code": self.code,
            "knowledge_source": self.namespace,
            "message": self.reason,
        }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _set_job(namespace: str, payload: dict[str, Any]) -> None:
    with _jobs_lock:
        _jobs[namespace] = {
            **_jobs.get(namespace, {}),
            **payload,
            "updated_at": _now_iso(),
        }


def get_static_kb_job(namespace: str) -> dict[str, Any] | None:
    with _jobs_lock:
        job = _jobs.get(namespace)

        return dict(job) if job is not None else None


def list_static_kb_jobs() -> list[dict[str, Any]]:
    with _jobs_lock:
        return [dict(job) for job in _jobs.values()]


def _run_load(namespace: str) -> None:
    _set_job(namespace, {"status": "running", "started_at": _now_iso()})

    try:
        result = load_static_namespace(namespace)

    except Exception as exc:
        # StaticKBLoaderError carries an actionable message; anything else is a
        # bug or an infrastructure failure, so keep the traceback for both.
        logger.exception("Static KB load failed namespace=%s", namespace)

        _set_job(
            namespace,
            {
                "status": "failed",
                "finished_at": _now_iso(),
                "result": None,
                "error": str(exc),
            },
        )
        return

    logger.info("Static KB load succeeded namespace=%s result=%s", namespace, result)

    _set_job(
        namespace,
        {
            "status": "succeeded",
            "finished_at": _now_iso(),
            "result": result,
            "error": None,
        },
    )


def queue_static_kb_load(namespace: str) -> dict[str, Any] | None:
    """Start loading a static KB namespace unless a load is already in flight."""
    with _jobs_lock:
        existing = _jobs.get(namespace)

        if existing and existing.get("status") in {"queued", "running"}:
            return dict(existing)

        _jobs[namespace] = {
            "namespace": namespace,
            "status": "queued",
            "queued_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
            "updated_at": _now_iso(),
        }

    Thread(
        target=_run_load,
        args=(namespace,),
        name=f"kb-load-{namespace}",
        daemon=True,
    ).start()

    return get_static_kb_job(namespace)


def _set_preload(**fields: Any) -> None:
    with _preload_lock:
        _preload.update(fields)


def _discover_and_queue() -> None:
    try:
        discovered = {source["value"] for source in list_static_namespaces()}

    except StaticKBLoaderError as exc:
        logger.exception("Static KB discovery failed.")
        _set_preload(status="failed", error=str(exc))
        return

    selectable = [option["value"] for option in list_knowledge_source_options()]
    missing = [namespace for namespace in selectable if namespace not in discovered]

    if missing:
        logger.warning("Static KB topics with no content in S3: %s", missing)

    # Queue before publishing "done": a topic must never read as unavailable in
    # the gap between discovery and its job being created.
    for namespace in selectable:
        if namespace in discovered:
            queue_static_kb_load(namespace)

    _set_preload(status="done", missing=missing)


def start_static_kb_preload(enabled: bool) -> None:
    """Discover and load every selectable topic in the background.

    Called from the app lifespan. The state flips to "discovering" before the
    thread starts, so no request can observe a not-yet-started preload.
    """
    if not enabled:
        logger.warning("Static KB autoload disabled; saved topics are unavailable.")
        _set_preload(status="disabled")
        return

    _set_preload(status="discovering", error=None, missing=[])

    Thread(target=_discover_and_queue, name="kb-preload", daemon=True).start()


def is_static_namespace(namespace: str) -> bool:
    return namespace in _STATIC_NAMESPACES


def get_static_kb_status(namespace: str) -> dict[str, Any]:
    """Readiness of one static topic, with the reason when it is not ready."""
    job = get_static_kb_job(namespace)

    if job is not None:
        if job["status"] == "succeeded":
            return {"namespace": namespace, "status": "ready", "error": None}

        if job["status"] in {"queued", "running"}:
            return {
                "namespace": namespace,
                "status": "loading",
                "error": "This topic is still loading. Try again in a few seconds.",
            }

        return {
            "namespace": namespace,
            "status": "unavailable",
            "error": f"This topic failed to load: {job.get('error')}",
        }

    # Content ingested by other means (e.g. /kb/ingest-text) is usable as is.
    if kb_store.get(namespace):
        return {"namespace": namespace, "status": "ready", "error": None}

    with _preload_lock:
        preload = dict(_preload)

    if preload["status"] == "discovering":
        return {
            "namespace": namespace,
            "status": "loading",
            "error": "Saved topics are still being discovered. Try again in a few seconds.",
        }

    reasons = {
        "disabled": "Saved topics are disabled on this server (KB_AUTOLOAD_STATIC).",
        "failed": f"Saved topics could not be listed from S3: {preload['error']}",
        "not_started": "Saved topics have not been loaded on this server.",
    }

    if preload["status"] in reasons:
        reason = reasons[preload["status"]]
    elif namespace in preload["missing"]:
        reason = "This topic has no content in S3."
    else:
        reason = "This topic is not loaded."

    return {"namespace": namespace, "status": "unavailable", "error": reason}


def ensure_static_kbs_ready(namespaces: list[str]) -> None:
    """Raise KnowledgeSourceNotReadyError if any static topic cannot answer yet.

    Only registry topics are checked: uploaded-PDF namespaces start empty by
    design and are not a failure.
    """
    for namespace in namespaces:
        if not is_static_namespace(namespace):
            continue

        status = get_static_kb_status(namespace)

        if status["status"] != "ready":
            raise KnowledgeSourceNotReadyError(
                namespace=namespace,
                status=status["status"],
                reason=status["error"],
            )


def static_kb_health() -> dict[str, Any]:
    """Overall static-KB state for /health: "ok", "loading" or "degraded"."""
    namespaces = {
        option["value"]: get_static_kb_status(option["value"])
        for option in list_knowledge_source_options()
    }

    statuses = {status["status"] for status in namespaces.values()}

    if "unavailable" in statuses:
        overall = "degraded"
    elif "loading" in statuses:
        overall = "loading"
    else:
        overall = "ok"

    with _preload_lock:
        preload = dict(_preload)

    return {
        "status": overall,
        "preload": preload,
        "namespaces": namespaces,
    }

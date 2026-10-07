"""In-memory semantic knowledge-base service.

This module stores knowledge-base chunks by namespace and retrieves relevant
chunks for user questions using text embeddings and cosine similarity.

The service supports plain-text and PDF-derived ingestion through shared chunking
logic. Each chunk keeps metadata such as title, source type, source name, page,
and chunk index. Embeddings are generated at ingestion time and stored in memory
with each chunk. Search embeds the user query, compares it against stored chunk
vectors, and returns the highest-scoring matches.

The storage is intentionally temporary and resets when the server restarts. Use a
persistent database or vector store before deploying this service in production.
"""

from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any

import boto3
import numpy as np
import logging

from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from app.core.aws import aws_client_config
from app.core.config import get_settings

settings = get_settings()

kb_store: dict[str, list[dict[str, Any]]] = {}

# Full (unchunked) text of every ingested page, so small knowledge bases such as
# a single guide can be passed to the LLM in full instead of as retrieved chunks.
kb_documents: dict[str, list[dict[str, Any]]] = {}

# Ingestion runs in worker threads (uploads and the static preload at the same
# time), so writes to the two stores above are serialized.
_kb_write_lock = Lock()

# One pool for the whole process caps concurrent Bedrock calls across every
# ingestion, instead of each upload opening its own burst of requests.
_embedding_pool = ThreadPoolExecutor(
    max_workers=max(1, settings.KB_EMBEDDING_CONCURRENCY),
    thread_name_prefix="kb-embed",
)

_bedrock_client = None
_bedrock_client_lock = Lock()

logger = logging.getLogger(__name__)


class KnowledgeBaseError(Exception):
    """Base exception for knowledge-base operations."""


class EmbeddingConfigurationError(KnowledgeBaseError):
    """Raised when embedding configuration is missing or invalid."""


class EmbeddingProviderError(KnowledgeBaseError):
    """Raised when the embedding provider request fails."""

def _get_bedrock_client():
    """Return the shared Bedrock Runtime client, creating it on first use.

    boto3 clients are thread-safe once built but creating one is not, and
    building a fresh client for every chunk made ingestion needlessly slow.
    """
    global _bedrock_client

    if _bedrock_client is not None:
        return _bedrock_client

    with _bedrock_client_lock:
        if _bedrock_client is None:
            _bedrock_client = _create_bedrock_client()

    return _bedrock_client


def _create_bedrock_client():
    if not settings.BEDROCK_EMBEDDING_MODEL_ID:
        raise EmbeddingConfigurationError(
            "BEDROCK_EMBEDDING_MODEL_ID is not configured."
        )

    if not settings.AWS_REGION:
        raise EmbeddingConfigurationError(
            "AWS_REGION is not configured."
        )

    if settings.AWS_BEARER_TOKEN_BEDROCK:
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = (
            settings.AWS_BEARER_TOKEN_BEDROCK
        )

    try:
        return boto3.client(
            service_name="bedrock-runtime",
            region_name=settings.AWS_REGION,
            config=aws_client_config(
                max_pool_connections=max(10, settings.KB_EMBEDDING_CONCURRENCY),
            ),
        )
    except Exception as exc:
        logger.exception("Failed to create Bedrock Runtime client.")

        raise EmbeddingConfigurationError(
            f"Failed to create Bedrock Runtime client: {exc}"
        ) from exc

def chunk_text(
    text: str,
    chunk_size: int = 280,
    overlap: int = 60,
    min_words: int = 10,
) -> list[str]:
    words = text.split()

    if len(words) < min_words:
        return []

    chunks = []
    step = max(1, chunk_size - overlap)

    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_size]).strip()

        if chunk:
            chunks.append(chunk)

    return chunks


def _normalize_vector(vector: list[float]) -> list[float]:
    arr = np.array(vector, dtype=np.float32)
    norm = np.linalg.norm(arr)

    if norm == 0:
        return arr.tolist()

    return (arr / norm).tolist()


def embed_text(text: str) -> list[float]:
    client = _get_bedrock_client()

    payload = {
        "inputText": text,
        "dimensions": settings.BEDROCK_EMBEDDING_DIMENSIONS,
        "normalize": True,
    }

    try:
        response = client.invoke_model(
            modelId=settings.BEDROCK_EMBEDDING_MODEL_ID,
            body=json.dumps(payload),
            accept="application/json",
            contentType="application/json",
        )

        body = json.loads(response["body"].read())

    except NoCredentialsError as exc:
        logger.exception("Bedrock credentials are missing.")

        raise EmbeddingProviderError(
            "Bedrock credentials are missing or unavailable."
        ) from exc

    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "Unknown")
        message = error.get("Message", str(exc))

        logger.exception(
            "Bedrock embedding request failed. code=%s message=%s",
            code,
            message,
        )

        raise EmbeddingProviderError(
            f"Bedrock embedding request failed: {code}. {message}"
        ) from exc

    except BotoCoreError as exc:
        logger.exception("Bedrock client error.")

        raise EmbeddingProviderError(
            f"Bedrock client error: {exc}"
        ) from exc

    except json.JSONDecodeError as exc:
        logger.exception("Bedrock returned invalid JSON.")

        raise EmbeddingProviderError(
            "Bedrock returned an invalid JSON response."
        ) from exc

    except Exception as exc:
        logger.exception("Unexpected embedding provider error.")

        raise EmbeddingProviderError(
            f"Unexpected embedding provider error: {exc}"
        ) from exc

    embedding = body.get("embedding")

    if not embedding:
        logger.error("Bedrock response did not contain an embedding: %s", body)

        raise EmbeddingProviderError(
            "Bedrock response did not contain an embedding."
        )

    return _normalize_vector(embedding)

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)

    denom = np.linalg.norm(a) * np.linalg.norm(b)

    if denom == 0:
        return 0.0

    return float(np.dot(a, b) / denom)


def _build_embedding_text(item: dict[str, Any]) -> str:
    metadata = []

    if item.get("title"):
        metadata.append(f"Title: {item['title']}")

    if item.get("source_name"):
        metadata.append(f"Source: {item['source_name']}")

    if item.get("page"):
        metadata.append(f"Page: {item['page']}")

    metadata.append(f"Content: {item['text']}")

    return "\n".join(metadata)


def kb_ingest_pages(
    title: str,
    pages: list[dict[str, Any]],
    namespace: str,
    source_type: str = "text",
    source_name: str | None = None,
):
    """Chunk, embed and store a whole document.

    `pages` holds dicts with "text" and an optional "page" number. Embeddings run
    in parallel on the shared pool, and the document is added to the store only
    once every chunk is embedded: searches never see half a document, and a
    failed embedding leaves nothing behind.
    """
    documents = []
    items = []

    for page in pages:
        text = page["text"]
        page_number = page.get("page")

        documents.append(
            {
                "title": title,
                "source_name": source_name,
                "page": page_number,
                "text": text,
            }
        )

        for chunk_index, chunk in enumerate(chunk_text(text)):
            items.append(
                {
                    "chunk_id": str(uuid.uuid4()),
                    "title": title,
                    "text": chunk,
                    "namespace": namespace,
                    "source_type": source_type,
                    "source_name": source_name,
                    "page": page_number,
                    "chunk_index": chunk_index,
                }
            )

    embeddings = _embedding_pool.map(
        embed_text,
        [_build_embedding_text(item) for item in items],
    )

    for item, embedding in zip(items, embeddings):
        item["embedding"] = embedding

    with _kb_write_lock:
        kb_documents.setdefault(namespace, []).extend(documents)
        kb_store.setdefault(namespace, []).extend(items)

    return [
        {
            key: value
            for key, value in item.items()
            if key != "embedding"
        }
        for item in items
    ]


def kb_ingest_text(
    title: str,
    text: str,
    namespace: str,
    source_type: str = "text",
    source_name: str | None = None,
    page: int | None = None,
):
    return kb_ingest_pages(
        title=title,
        pages=[{"text": text, "page": page}],
        namespace=namespace,
        source_type=source_type,
        source_name=source_name,
    )


def kb_search(query: str, namespace: str, top_k: int = 4):
    chunks = kb_store.get(namespace, [])

    if not chunks:
        return []

    query_embedding = embed_text(query)

    results = []

    for item in chunks:
        score = cosine_similarity(query_embedding, item["embedding"])

        result = {
            key: value
            for key, value in item.items()
            if key != "embedding"
        }

        result["score"] = round(score, 4)
        results.append(result)

    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:top_k]

def kb_search_many(
    query: str,
    namespaces: list[str],
    top_k: int = 4,
):
    results = []

    for namespace in namespaces:
        namespace_results = kb_search(
            query=query,
            namespace=namespace,
            top_k=top_k,
        )
        results.extend(namespace_results)

    results.sort(key=lambda item: item["score"], reverse=True)

    return results[:top_k]

def kb_full_text(namespaces: list[str]) -> str | None:
    """Return the full text of the namespaces if it fits KB_FULL_CONTEXT_MAX_CHARS.

    Returns None when full-context mode is disabled, the namespaces are empty, or
    the content is too large; callers then fall back to chunk retrieval.
    """
    max_chars = settings.KB_FULL_CONTEXT_MAX_CHARS

    if max_chars <= 0:
        return None

    sections: list[str] = []
    current_title = None

    for namespace in namespaces:
        for page in kb_documents.get(namespace, []):
            text = (page.get("text") or "").strip()
            if not text:
                continue

            if page["title"] != current_title:
                current_title = page["title"]
                sections.append(f"=== Documento: {current_title} ===")

            if page.get("page"):
                sections.append(f"[Página {page['page']}]")

            sections.append(text)

    full_text = "\n\n".join(sections)

    if not full_text or len(full_text) > max_chars:
        return None

    return full_text


def kb_list(namespace: str, limit: int = 20):
    chunks = kb_store.get(namespace, [])[:limit]

    return [
        {
            key: value
            for key, value in item.items()
            if key != "embedding"
        }
        for item in chunks
    ]


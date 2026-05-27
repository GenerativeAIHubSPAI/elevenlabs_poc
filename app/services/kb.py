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
from typing import Any

import boto3
import numpy as np

from app.core.config import get_settings

settings = get_settings()

kb_store: dict[str, list[dict[str, Any]]] = {}


def _get_bedrock_client():
    if settings.AWS_BEARER_TOKEN_BEDROCK:
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.AWS_BEARER_TOKEN_BEDROCK

    return boto3.client(
        service_name="bedrock-runtime",
        region_name=settings.AWS_REGION,
    )


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

    response = client.invoke_model(
        modelId=settings.BEDROCK_EMBEDDING_MODEL_ID,
        body=json.dumps(payload),
        accept="application/json",
        contentType="application/json",
    )

    body = json.loads(response["body"].read())

    embedding = body.get("embedding")

    if not embedding:
        raise RuntimeError(f"No embedding returned by Bedrock: {body}")

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


def kb_ingest_text(
    title: str,
    text: str,
    namespace: str,
    source_type: str = "text",
    source_name: str | None = None,
    page: int | None = None,
):
    if namespace not in kb_store:
        kb_store[namespace] = []

    chunks = chunk_text(text)
    saved = []

    for chunk_index, chunk in enumerate(chunks):
        item = {
            "chunk_id": str(uuid.uuid4()),
            "title": title,
            "text": chunk,
            "namespace": namespace,
            "source_type": source_type,
            "source_name": source_name,
            "page": page,
            "chunk_index": chunk_index,
        }

        embedding_input = _build_embedding_text(item)
        item["embedding"] = embed_text(embedding_input)

        kb_store[namespace].append(item)

        saved.append(
            {
                key: value
                for key, value in item.items()
                if key != "embedding"
            }
        )

    return saved


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
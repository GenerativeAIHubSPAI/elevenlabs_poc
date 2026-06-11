"""Static knowledge-base loader.

This module loads static business-example documents from S3 into the existing
in-memory knowledge base. It reads one manifest per namespace, downloads the
listed PDF documents, extracts text page by page, and ingests the content using
the current KB embedding pipeline.
"""

from __future__ import annotations

import json

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from app.core.config import get_settings

from app.services.kb import kb_ingest_text
from app.services.pdf_parser import extract_pdf_pages

settings = get_settings()

class StaticKBLoaderError(Exception):
    """Raised when static KB loading fails."""


def _get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
    )


def _get_static_bucket() -> str:
    if not settings.KB_STATIC_BUCKET:
        raise StaticKBLoaderError("KB_STATIC_BUCKET is not configured.")

    return settings.KB_STATIC_BUCKET


def _get_static_prefix() -> str:
    return settings.KB_STATIC_PREFIX.strip("/")


def _get_static_namespaces() -> list[str]:
    return [
        namespace.strip()
        for namespace in settings.KB_STATIC_NAMESPACES.split(",")
        if namespace.strip()
    ]



def _read_s3_json(bucket: str, key: str) -> dict[str, Any]:
    s3 = _get_s3_client()

    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)

    except ClientError as exc:
        raise StaticKBLoaderError(
            f"Could not read S3 JSON object s3://{bucket}/{key}: {exc}"
        ) from exc

    except json.JSONDecodeError as exc:
        raise StaticKBLoaderError(
            f"Invalid JSON in s3://{bucket}/{key}: {exc}"
        ) from exc


def _read_s3_bytes(bucket: str, key: str) -> bytes:
    s3 = _get_s3_client()

    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    except (ClientError, BotoCoreError) as exc:
        raise StaticKBLoaderError(
            f"Could not read S3 object s3://{bucket}/{key}: {exc}"
        ) from exc


def load_static_namespace(namespace: str) -> dict[str, Any]:
    """Load one static namespace from its S3 manifest."""

    bucket = _get_static_bucket()
    prefix = _get_static_prefix()

    manifest_key = f"{prefix}/{namespace}/manifest.json"

    manifest = _read_s3_json(
        bucket=bucket,
        key=manifest_key,
    )

    manifest_namespace = manifest.get("namespace")

    if manifest_namespace != namespace:
        raise StaticKBLoaderError(
            f"Manifest namespace mismatch. Expected '{namespace}', got '{manifest_namespace}'."
        )

    documents = manifest.get("documents", [])

    if not documents:
        return {
            "namespace": namespace,
            "documents_loaded": 0,
            "chunks_ingested": 0,
            "message": "Manifest contains no documents.",
        }

    total_chunks = 0
    loaded_documents = []

    for document in documents:
        title = document.get("title") or "Untitled static document"
        source_type = document.get("source_type", "pdf")
        s3_key = document.get("s3_key")

        if not s3_key:
            raise StaticKBLoaderError(
                f"Document in namespace '{namespace}' is missing s3_key."
            )

        if source_type != "pdf":
            raise StaticKBLoaderError(
                f"Unsupported source_type '{source_type}' for {s3_key}. Only 'pdf' is supported for now."
            )

        file_bytes = _read_s3_bytes(
            bucket=bucket,
            key=s3_key,
        )

        pages = extract_pdf_pages(file_bytes)

        document_chunks = 0

        for page in pages:
            saved = kb_ingest_text(
                title=title,
                text=page["text"],
                namespace=namespace,
                source_type="pdf",
                source_name=s3_key,
                page=page["page"],
            )

            document_chunks += len(saved)

        total_chunks += document_chunks

        loaded_documents.append(
            {
                "title": title,
                "s3_key": s3_key,
                "pages_processed": len(pages),
                "chunks_ingested": document_chunks,
            }
        )

    return {
        "namespace": namespace,
        "documents_loaded": len(loaded_documents),
        "chunks_ingested": total_chunks,
        "documents": loaded_documents,
    }


def load_all_static_namespaces() -> dict[str, Any]:
    """Load all configured static namespaces from S3."""

    namespaces = [source["value"] for source in list_static_namespaces()]
    
    results = []
    total_chunks = 0

    for namespace in namespaces:
        result = load_static_namespace(namespace)
        results.append(result)
        total_chunks += result.get("chunks_ingested", 0)

    return {
        "namespaces": namespaces,
        "namespaces_loaded": len(results),
        "chunks_ingested": total_chunks,
        "results": results,
    }

def list_static_namespaces() -> list[dict[str, str]]:
    """List available static KB namespaces from S3 folder prefixes."""
    bucket = _get_static_bucket()
    prefix = _get_static_prefix()

    s3 = _get_s3_client()

    try:
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=f"{prefix}/",
            Delimiter="/",
        )

    except (ClientError, BotoCoreError) as exc:
        raise StaticKBLoaderError(
            f"Failed to list static KB namespaces under s3://{bucket}/{prefix}/: {exc}"
        ) from exc

    sources: list[dict[str, str]] = []

    for item in response.get("CommonPrefixes", []):
        folder_prefix = item.get("Prefix", "")
        namespace = folder_prefix.replace(f"{prefix}/", "").strip("/")

        if namespace:
            sources.append(
                {
                    "value": namespace,
                    "label": namespace.replace("_", " ").title(),
                }
            )

    sources.sort(key=lambda source: source["label"])

    return sources
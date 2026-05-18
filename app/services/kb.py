import re
import uuid
from typing import Any

kb_store: dict[str, list[dict[str, Any]]] = {}


def normalize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(1, chunk_size - overlap)

    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def kb_ingest_text(title: str, text: str, namespace: str):
    if namespace not in kb_store:
        kb_store[namespace] = []

    chunks = chunk_text(text)
    saved = []

    for chunk in chunks:
        item = {
            "chunk_id": str(uuid.uuid4()),
            "title": title,
            "text": chunk,
            "namespace": namespace,
        }
        kb_store[namespace].append(item)
        saved.append(item)

    return saved


def kb_search(query: str, namespace: str, top_k: int = 4):
    q_tokens = set(normalize(query))
    results = []

    for item in kb_store.get(namespace, []):
        c_tokens = set(normalize(item["text"]))
        overlap = len(q_tokens & c_tokens)
        if overlap == 0:
            continue

        score = overlap / max(len(q_tokens), 1)
        results.append({**item, "score": round(score, 4)})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
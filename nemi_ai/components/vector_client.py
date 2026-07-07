"""Qdrant vector database client singleton.

Provides a shared connection-pooled Qdrant client and collection helpers.
Mirrors nemi-gpt's vector_client.py pattern.
"""

from __future__ import annotations

import re
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    HnswConfigDiff,
    OptimizersConfigDiff,
)

# ── Default collection names ───────────────────────────────────
DOCUMENTS_COLLECTION = "nemi_documents"
CONFIG_COLLECTION = "nemi_config"
SUGGESTIONS_COLLECTION = "nemi_suggestions"

# Default embedding vector size (sentence-transformers paraphrase-multilingual-MiniLM-L12-v2)
DEFAULT_VECTOR_SIZE = 384

# Connection-pooled client singleton
_client_instance: Optional[QdrantClient] = None


def get_qdrant_client(
    host: str = "localhost",
    port: int = 6333,
    api_key: Optional[str] = None,
) -> QdrantClient:
    """Return the shared Qdrant client, creating one if needed."""
    global _client_instance
    if _client_instance is None:
        kwargs = dict(host=host, port=port, timeout=30)
        if api_key:
            kwargs["api_key"] = api_key
        _client_instance = QdrantClient(**kwargs)
    return _client_instance


def reset_client() -> None:
    """Reset the client singleton (useful for tests or reconnection)."""
    global _client_instance
    if _client_instance is not None:
        _client_instance.close()
        _client_instance = None


def sanitize_collection_name(name: str) -> str:
    """Sanitize an embedder model name to a valid Qdrant collection name."""
    safe = re.sub(r"[^a-zA-Z0-9_\-.]", "_", name)
    safe = re.sub(r"_+", "_", safe)
    return f"nemi_embedding_{safe}"


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int = DEFAULT_VECTOR_SIZE,
    distance: Distance = Distance.COSINE,
) -> bool:
    """Create collection if it doesn't exist. Returns True if created."""
    collections = [c.name for c in client.get_collections().collections]
    if collection_name not in collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=distance,
            ),
            hnsw_config=HnswConfigDiff(
                m=16,
                ef_construct=100,
            ),
            optimizers_config=OptimizersConfigDiff(
                default_segment_number=2,
            ),
        )
        return True
    return False


def ensure_documents_collection(client: QdrantClient) -> str:
    """Ensure documents collection exists, return name."""
    ensure_collection(client, DOCUMENTS_COLLECTION, vector_size=0)
    return DOCUMENTS_COLLECTION


def ensure_config_collection(client: QdrantClient) -> str:
    """Ensure config collection exists, return name."""
    ensure_collection(client, CONFIG_COLLECTION, vector_size=0)
    return CONFIG_COLLECTION


def ensure_suggestions_collection(client: QdrantClient) -> str:
    """Ensure suggestions collection exists, return name."""
    ensure_collection(client, SUGGESTIONS_COLLECTION, vector_size=0)
    return SUGGESTIONS_COLLECTION


def ensure_embedding_collection(
    client: QdrantClient,
    embedder_name: str,
    vector_size: int = DEFAULT_VECTOR_SIZE,
) -> str:
    """Ensure embedding collection for a given embedder, return sanitized name."""
    col = sanitize_collection_name(embedder_name)
    ensure_collection(client, col, vector_size=vector_size)
    return col

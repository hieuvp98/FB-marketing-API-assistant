"""Qdrant-based storage manager replacing WeaviateManager.

Handles all vector DB operations: documents, chunks, config, suggestions.
Uses synchronous QdrantClient wrapped in run_in_executor for async call sites.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import uuid
from datetime import datetime
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchText,
    MatchValue,
    PointIdsList,
    PointStruct,
    SearchParams,
    ScoredPoint,
)
from sklearn.decomposition import PCA
from wasabi import msg

from nemi_ai.components.document import Document
from nemi_ai.components.vector_client import (
    get_qdrant_client,
    ensure_collection,
    ensure_documents_collection,
    ensure_config_collection,
    ensure_suggestions_collection,
    ensure_embedding_collection,
    sanitize_collection_name,
    DOCUMENTS_COLLECTION,
    CONFIG_COLLECTION,
    SUGGESTIONS_COLLECTION,
)


def _run_sync(fn, *args, **kwargs):
    """Run a synchronous function in a thread executor."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: fn(*args, **kwargs))


class QdrantManager:
    """Manages all Qdrant vector DB operations.

    Mirrors the WeaviateManager interface to minimize changes in calling code.
    """

    document_collection_name = DOCUMENTS_COLLECTION
    config_collection_name = CONFIG_COLLECTION
    suggestion_collection_name = SUGGESTIONS_COLLECTION

    def __init__(self):
        self.embedding_table: dict[str, str] = {}  # embedder_name → collection name
        self._client: Optional[QdrantClient] = None

    # ─────────────────────────── Connection ───────────────────────────

    async def connect(
        self,
        host: str = "localhost",
        port: int = 6333,
        api_key: Optional[str] = None,
    ) -> QdrantClient:
        """Connect to Qdrant (sync client, wrapped for async)."""
        try:
            client = get_qdrant_client(host=host, port=port, api_key=api_key)
            # Quick health check
            await _run_sync(client.get_collections)
            self._client = client
            msg.good("Successfully connected to Qdrant")
            return client
        except Exception as e:
            msg.fail(f"Couldn't connect to Qdrant: {e}")
            raise

    async def disconnect(self, client: QdrantClient) -> bool:
        """Close the Qdrant connection."""
        try:
            client.close()
            self._client = None
            return True
        except Exception as e:
            msg.fail(f"Couldn't disconnect Qdrant: {e}")
            return False

    def _get_client(self, client: Optional[QdrantClient] = None) -> QdrantClient:
        return client or self._client or get_qdrant_client()

    # ─────────────────────────── Collections ─────────────────────────

    def _embedding_collection(self, embedder: str) -> str:
        """Get or create mapping for embedder → collection name."""
        if embedder not in self.embedding_table:
            self.embedding_table[embedder] = sanitize_collection_name(embedder)
        return self.embedding_table[embedder]

    def _get_or_create_documents(self, client: QdrantClient) -> str:
        return ensure_documents_collection(client)

    def _get_or_create_config(self, client: QdrantClient) -> str:
        return ensure_config_collection(client)

    def _get_or_create_suggestions(self, client: QdrantClient) -> str:
        return ensure_suggestions_collection(client)

    def _get_or_create_embedding(
        self, client: QdrantClient, embedder: str, vector_size: int = 384
    ) -> str:
        col = self._embedding_collection(embedder)
        ensure_collection(client, col, vector_size=vector_size)
        return col

    # ─────────────────────────── Config CRUD ─────────────────────────

    async def get_config(self, client: QdrantClient, uuid: str) -> Optional[dict]:
        """Get a config object by UUID."""
        client = self._get_client(client)
        col = self._get_or_create_config(client)
        try:
            points = await _run_sync(
                client.retrieve, collection_name=col, ids=[uuid]
            )
            if points:
                return json.loads(points[0].payload.get("config", "{}"))
        except Exception:
            pass
        return None

    async def set_config(self, client: QdrantClient, uuid: str, config: dict):
        """Upsert a config object."""
        client = self._get_client(client)
        col = self._get_or_create_config(client)
        await _run_sync(
            client.upsert,
            collection_name=col,
            points=[
                PointStruct(
                    id=uuid,
                    vector=[0.0] * 4,  # dummy vector for non-vector collection
                    payload={"config": json.dumps(config)},
                )
            ],
        )

    async def reset_config(self, client: QdrantClient, uuid: str):
        """Delete a config by UUID."""
        client = self._get_client(client)
        col = self._get_or_create_config(client)
        await _run_sync(client.delete, collection_name=col, points_selector=PointIdsList(ids=[uuid]))

    async def delete_all_configs(self, client: QdrantClient):
        """Delete all configs."""
        client = self._get_client(client)
        col = self._get_or_create_config(client)
        await _run_sync(client.delete_collection, collection_name=col)
        ensure_config_collection(client)

    # ─────────────────────────── Document CRUD ───────────────────────

    async def import_document(
        self, client: QdrantClient, document: Document, embedder: str
    ):
        """Import a document with its chunks into Qdrant."""
        client = self._get_client(client)
        doc_col = self._get_or_create_documents(client)
        emb_col = self._get_or_create_embedding(client, embedder)

        # Determine vector size from first chunk
        vector_size = None
        if document.chunks and document.chunks[0].vector:
            vector_size = len(document.chunks[0].vector)
        if vector_size:
            self._get_or_create_embedding(client, embedder, vector_size=vector_size)

        # Generate document UUID client-side
        doc_uuid = str(uuid.uuid4())

        # Import document
        doc_obj = Document.to_json(document)
        await _run_sync(
            client.upsert,
            collection_name=doc_col,
            points=[
                PointStruct(
                    id=doc_uuid,
                    vector=[0.0] * 4,
                    payload=doc_obj,
                )
            ],
        )

        try:
            # Prepare chunk points with client-side UUIDs
            chunk_points = []
            chunk_uuids = []
            for chunk in document.chunks:
                chunk.doc_uuid = doc_uuid
                chunk.labels = document.labels
                chunk.title = document.title
                cid = str(uuid.uuid4())
                chunk_uuids.append(cid)
                chunk_points.append(
                    PointStruct(
                        id=cid,
                        vector=chunk.vector or [0.0] * (vector_size or 384),
                        payload=chunk.to_json(),
                    )
                )

            await _run_sync(
                client.upsert,
                collection_name=emb_col,
                points=chunk_points,
            )

            # Verify count
            count = await _run_sync(
                lambda: client.count(
                    collection_name=emb_col,
                    exact=True,
                ).count
            )
            if len(chunk_uuids) != len(document.chunks):
                if doc_uuid:
                    await self.delete_document(client, doc_uuid)
                raise Exception(
                    f"Chunk mismatch: imported {len(chunk_uuids)} vs expected {len(document.chunks)}"
                )

        except Exception as e:
            if doc_uuid:
                await self.delete_document(client, doc_uuid)
            raise Exception(f"Chunk import failed: {e}")

    async def exist_document_name(
        self, client: QdrantClient, name: str
    ) -> Optional[str]:
        """Check if a document with the given title exists."""
        client = self._get_client(client)
        col = self._get_or_create_documents(client)
        try:
            points = await _run_sync(
                client.scroll,
                collection_name=col,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="title",
                            match=MatchText(text=name),
                        )
                    ]
                ),
                limit=1,
                with_payload=False,
            )
            if points and points[0]:
                return points[0][0].id
        except Exception:
            pass
        return None

    async def delete_document(self, client: QdrantClient, uuid: str):
        """Delete a document and its chunks."""
        client = self._get_client(client)
        doc_col = self._get_or_create_documents(client)

        # Get document to find embedder info
        doc = await self.get_document(client, uuid, properties=["meta"])
        if not doc:
            return

        # Delete from documents collection
        await _run_sync(
            client.delete,
            collection_name=doc_col,
            points_selector=PointIdsList(ids=[uuid]),
        )

        # Delete chunks from embedding collections
        meta_str = doc.get("meta", "{}")
        if meta_str:
            try:
                meta = json.loads(meta_str)
                embedder = meta.get("Embedder", {}).get("config", {}).get("Model", {}).get("value", "")
                if embedder:
                    emb_col = self._embedding_collection(embedder)
                    # Check if collection exists
                    collections = [c.name for c in client.get_collections().collections]
                    if emb_col in collections:
                        await _run_sync(
                            client.delete,
                            collection_name=emb_col,
                            points_selector=Filter(
                                must=[
                                    FieldCondition(
                                        key="doc_uuid",
                                        match=MatchText(text=str(uuid)),
                                    )
                                ]
                            ),
                        )
            except Exception as e:
                msg.warn(f"Failed to delete chunks for {uuid}: {e}")

    async def delete_all_documents(self, client: QdrantClient):
        """Delete all documents and their embedding collections."""
        await self.delete_all(client)

    async def get_documents(
        self,
        client: QdrantClient,
        query: str,
        pageSize: int,
        page: int,
        labels: list[str],
        properties: Optional[list[str]] = None,
    ) -> tuple[list[dict], int]:
        """List/search documents with pagination."""
        client = self._get_client(client)
        col = self._get_or_create_documents(client)
        offset = pageSize * (page - 1)

        # Build filter
        filter_conditions = []
        if labels:
            filter_conditions.append(
                FieldCondition(
                    key="labels",
                    match=MatchText(text=" ".join(labels)),
                )
            )
        doc_filter = Filter(must=filter_conditions) if filter_conditions else None

        # Get total count
        count_result = await _run_sync(
            lambda: client.count(
                collection_name=col,
                exact=True,
                count_filter=doc_filter,
            )
        )
        total_count = count_result.count
        if total_count == 0:
            return [], 0

        if not query:
            # Fetch with pagination
            result = await _run_sync(
                client.scroll,
                collection_name=col,
                limit=pageSize,
                offset=offset,
                with_payload=True,
            )
            points = result[0] if result else []
        else:
            # Simple text search via payload filter
            filter_conditions.append(
                FieldCondition(
                    key="title",
                    match=MatchText(text=query),
                )
            )
            search_filter = Filter(must=filter_conditions)
            result = await _run_sync(
                client.scroll,
                collection_name=col,
                scroll_filter=search_filter,
                limit=pageSize,
                offset=offset,
                with_payload=True,
            )
            points = result[0] if result else []

        return [
            {
                "title": p.payload.get("title", ""),
                "uuid": str(p.id),
                "labels": p.payload.get("labels", []),
            }
            for p in points
            if p.payload
        ], total_count

    async def get_document(
        self,
        client: QdrantClient,
        uuid: str,
        properties: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """Get a single document by UUID."""
        client = self._get_client(client)
        col = self._get_or_create_documents(client)
        try:
            points = await _run_sync(
                client.retrieve,
                collection_name=col,
                ids=[uuid],
                with_payload=True,
            )
            if points:
                payload = points[0].payload
                if properties:
                    return {k: payload.get(k) for k in properties if k in payload}
                return dict(payload)
        except Exception:
            pass
        return None

    async def get_labels(self, client: QdrantClient) -> list[str]:
        """Get all unique labels from documents."""
        client = self._get_client(client)
        col = self._get_or_create_documents(client)
        all_labels: set[str] = set()
        try:
            result = await _run_sync(
                client.scroll,
                collection_name=col,
                limit=10000,
                with_payload=True,
                with_vectors=False,
            )
            for point in result[0]:
                labels = point.payload.get("labels", [])
                if labels:
                    all_labels.update(labels)
        except Exception:
            pass
        return sorted(all_labels)

    # ─────────────────────────── Chunk Operations ────────────────────

    async def hybrid_chunks(
        self,
        client: QdrantClient,
        embedder: str,
        query: str,
        vector: list[float],
        limit_mode: str,
        limit: int,
        labels: list[str],
        document_uuids: list[str],
    ) -> list[ScoredPoint]:
        """Search chunks by vector similarity with optional filters."""
        client = self._get_client(client)
        emb_col = self._get_or_create_embedding(client, embedder)

        # Build filter
        filter_conditions = []
        if labels:
            filter_conditions.append(
                FieldCondition(
                    key="labels",
                    match=MatchText(text=" ".join(labels)),
                )
            )
        if document_uuids:
            filter_conditions.append(
                FieldCondition(
                    key="doc_uuid",
                    match=MatchText(text=" ".join(document_uuids)),
                )
            )

        search_filter = Filter(must=filter_conditions) if filter_conditions else None

        # Determine limit
        search_limit = limit
        if limit_mode == "Autocut":
            search_limit = limit * 50  # generous initial pool for autocut

        results = await _run_sync(
            client.search,
            collection_name=emb_col,
            query_vector=vector,
            query_filter=search_filter,
            limit=search_limit,
            with_payload=True,
            score_threshold=0.0,
        )

        # Simple autocut: find the "elbow" where scores drop sharply
        if limit_mode == "Autocut" and len(results) > limit:
            scores = [r.score for r in results]
            if len(scores) > 2:
                # Find the biggest relative drop
                drops = [
                    (scores[i] - scores[i + 1]) / max(scores[i], 0.001)
                    for i in range(len(scores) - 1)
                ]
                if drops:
                    cut_idx = max(1, drops.index(max(drops)) + 1)
                    cut_idx = min(cut_idx, limit * 10)
                    results = results[:max(cut_idx, limit)]

        return results

    async def get_chunk(
        self, client: QdrantClient, uuid: str, embedder: str
    ) -> Optional[dict]:
        """Get a single chunk by UUID."""
        client = self._get_client(client)
        emb_col = self._embedding_collection(embedder)
        collections = [c.name for c in client.get_collections().collections]
        if emb_col not in collections:
            return None
        try:
            points = await _run_sync(
                client.retrieve,
                collection_name=emb_col,
                ids=[uuid],
                with_payload=True,
            )
            if points:
                props = dict(points[0].payload)
                props["doc_uuid"] = str(props.get("doc_uuid", ""))
                return props
        except Exception:
            pass
        return None

    async def get_chunks(
        self, client: QdrantClient, uuid: str, page: int, pageSize: int
    ) -> list[dict]:
        """Get chunks for a document with pagination."""
        client = self._get_client(client)
        doc = await self.get_document(client, uuid, properties=["meta"])
        if not doc:
            return []

        meta_str = doc.get("meta", "{}")
        if not meta_str:
            return []
        try:
            meta = json.loads(meta_str)
            embedder = meta.get("Embedder", {}).get("config", {}).get("Model", {}).get("value", "")
        except (json.JSONDecodeError, AttributeError):
            return []

        if not embedder:
            return []

        emb_col = self._embedding_collection(embedder)
        collections = [c.name for c in client.get_collections().collections]
        if emb_col not in collections:
            return []

        offset = pageSize * (page - 1)
        result = await _run_sync(
            client.scroll,
            collection_name=emb_col,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="doc_uuid",
                        match=MatchText(text=str(uuid)),
                    )
                ]
            ),
            limit=pageSize,
            offset=offset,
            with_payload=True,
        )
        chunks = []
        for point in result[0]:
            props = dict(point.payload)
            props["doc_uuid"] = str(props.get("doc_uuid", ""))
            chunks.append(props)
        return chunks

    async def get_chunk_by_ids(
        self,
        client: QdrantClient,
        embedder: str,
        doc_uuid: str,
        ids: list[int],
    ) -> list:
        """Get multiple chunks by their chunk_id values."""
        client = self._get_client(client)
        emb_col = self._embedding_collection(embedder)
        collections = [c.name for c in client.get_collections().collections]
        if emb_col not in collections:
            return []

        try:
            # Fetch all chunks for this document and filter by chunk_id
            result = await _run_sync(
                client.scroll,
                collection_name=emb_col,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="doc_uuid",
                            match=MatchText(text=str(doc_uuid)),
                        )
                    ]
                ),
                limit=10000,
                with_payload=True,
            )
            id_set = set(ids)
            matched = []
            for point in result[0]:
                cid = point.payload.get("chunk_id")
                if cid is not None and int(cid) in id_set:
                    matched.append(point)

            # Sort by chunk_id
            matched.sort(key=lambda p: int(p.payload.get("chunk_id", 0)))
            return matched
        except Exception as e:
            msg.fail(f"Failed to fetch chunks by IDs: {e}")
            return []

    async def get_vectors(
        self, client: QdrantClient, uuid: str, showAll: bool
    ) -> Optional[dict]:
        """Get PCA-reduced vectors for 3D visualization."""
        client = self._get_client(client)
        doc = await self.get_document(client, uuid, properties=["meta", "title"])
        if not doc:
            return None

        meta_str = doc.get("meta", "{}")
        if not meta_str:
            return None
        try:
            meta = json.loads(meta_str)
            embedder = meta.get("Embedder", {}).get("config", {}).get("Model", {}).get("value", "")
        except (json.JSONDecodeError, AttributeError):
            return None

        if not embedder:
            return None

        emb_col = self._embedding_collection(embedder)
        collections = [c.name for c in client.get_collections().collections]
        if emb_col not in collections:
            return None

        # Fetch all chunks for this document, with vectors
        result = await _run_sync(
            client.scroll,
            collection_name=emb_col,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="doc_uuid",
                        match=MatchText(text=str(uuid)),
                    )
                ]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=True,
        )

        points = result[0]
        if not points:
            return None

        vector_dim = len(points[0].vector) if points[0].vector else 0

        if not showAll:
            chunks = []
            for p in points:
                payload = p.payload
                if payload.get("pca"):
                    pca_val = payload["pca"]
                    chunks.append({
                        "vector": {"x": pca_val[0], "y": pca_val[1], "z": pca_val[2]},
                        "uuid": str(p.id),
                        "chunk_id": payload.get("chunk_id"),
                    })
            return {
                "embedder": embedder,
                "dimensions": vector_dim,
                "groups": [{"name": doc.get("title", ""), "chunks": chunks}],
            }
        else:
            # PCA all vectors
            vector_list = []
            vector_ids = []
            all_uuids = []
            all_cids = []
            for p in points:
                if p.vector:
                    vector_list.append(p.vector)
                    vector_ids.append(str(p.payload.get("doc_uuid", "")))
                    all_uuids.append(str(p.id))
                    all_cids.append(p.payload.get("chunk_id"))

            if len(vector_list) < 3:
                return {
                    "embedder": embedder,
                    "dimensions": vector_dim,
                    "groups": [],
                }

            pca = PCA(n_components=3)
            pca_result = pca.fit_transform(vector_list)

            vector_map: dict[str, dict] = {}
            for pca_val, vid, cuuid, cid in zip(pca_result, vector_ids, all_uuids, all_cids):
                if vid not in vector_map:
                    vector_map[vid] = {"name": doc.get("title", ""), "chunks": []}
                vector_map[vid]["chunks"].append({
                    "vector": {"x": float(pca_val[0]), "y": float(pca_val[1]), "z": float(pca_val[2])},
                    "uuid": cuuid,
                    "chunk_id": cid,
                })

            return {
                "embedder": embedder,
                "dimensions": vector_dim,
                "groups": list(vector_map.values()),
            }

    # ─────────────────────────── Chunk Metadata ──────────────────────

    async def get_chunk_count(
        self, client: QdrantClient, embedder: str, doc_uuid: str
    ) -> int:
        """Count chunks for a document."""
        client = self._get_client(client)
        emb_col = self._embedding_collection(embedder)
        collections = [c.name for c in client.get_collections().collections]
        if emb_col not in collections:
            return 0
        try:
            count_result = await _run_sync(
                lambda: client.count(
                    collection_name=emb_col,
                    exact=True,
                    count_filter=Filter(
                        must=[
                            FieldCondition(
                                key="doc_uuid",
                                match=MatchText(text=str(doc_uuid)),
                            )
                        ]
                    ),
                )
            )
            return count_result.count
        except Exception:
            return 0

    async def get_datacount(
        self,
        client: QdrantClient,
        embedder: str,
        document_uuids: list[str],
    ) -> int:
        """Count unique documents that have chunks in an embedding collection."""
        client = self._get_client(client)
        emb_col = self._embedding_collection(embedder)
        collections = [c.name for c in client.get_collections().collections]
        if emb_col not in collections:
            return 0
        try:
            # Get all doc_uuids from the embedding collection
            result = await _run_sync(
                client.scroll,
                collection_name=emb_col,
                limit=10000,
                with_payload=True,
                with_vectors=False,
            )
            doc_uuids = set()
            for p in result[0]:
                du = p.payload.get("doc_uuid")
                if du:
                    if document_uuids and str(du) in document_uuids:
                        doc_uuids.add(str(du))
                    elif not document_uuids:
                        doc_uuids.add(str(du))
            return len(doc_uuids)
        except Exception:
            return 0

    # ─────────────────────────── Suggestions ─────────────────────────

    async def add_suggestion(self, client: QdrantClient, query: str):
        """Record a user query as a suggestion."""
        client = self._get_client(client)
        col = self._get_or_create_suggestions(client)

        # Check if exists
        try:
            result = await _run_sync(
                client.scroll,
                collection_name=col,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="query",
                            match=MatchText(text=query),
                        )
                    ]
                ),
                limit=1,
                with_payload=False,
            )
            if result and result[0]:
                return  # already exists
        except Exception:
            pass

        await _run_sync(
            client.upsert,
            collection_name=col,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=[0.0] * 4,
                    payload={
                        "query": query,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            ],
        )

    async def retrieve_suggestions(
        self, client: QdrantClient, query: str, limit: int
    ) -> list[dict]:
        """Search suggestions by query text match."""
        client = self._get_client(client)
        col = self._get_or_create_suggestions(client)
        try:
            result = await _run_sync(
                client.scroll,
                collection_name=col,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="query",
                            match=MatchText(text=query),
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
            )
            return [
                {
                    "query": p.payload.get("query", ""),
                    "timestamp": p.payload.get("timestamp", ""),
                    "uuid": str(p.id),
                }
                for p in result[0]
                if p.payload
            ]
        except Exception:
            return []

    async def retrieve_all_suggestions(
        self, client: QdrantClient, page: int, pageSize: int
    ) -> tuple[list[dict], int]:
        """List all suggestions with pagination."""
        client = self._get_client(client)
        col = self._get_or_create_suggestions(client)
        offset = pageSize * (page - 1)
        try:
            count_result = await _run_sync(
                lambda: client.count(collection_name=col, exact=True)
            )
            total = count_result.count

            result = await _run_sync(
                client.scroll,
                collection_name=col,
                limit=pageSize,
                offset=offset,
                with_payload=True,
            )
            suggestions = [
                {
                    "query": p.payload.get("query", ""),
                    "timestamp": p.payload.get("timestamp", ""),
                    "uuid": str(p.id),
                }
                for p in result[0]
                if p.payload
            ]
            return suggestions, total
        except Exception:
            return [], 0

    async def delete_suggestions(self, client: QdrantClient, uuid: str):
        """Delete a suggestion by UUID."""
        client = self._get_client(client)
        col = self._get_or_create_suggestions(client)
        try:
            await _run_sync(
                client.delete,
                collection_name=col,
                points_selector=PointIdsList(ids=[uuid]),
            )
        except Exception:
            pass

    async def delete_all_suggestions(self, client: QdrantClient):
        """Delete all suggestions."""
        client = self._get_client(client)
        col = self._get_or_create_suggestions(client)
        try:
            await _run_sync(client.delete_collection, collection_name=col)
        except Exception:
            pass
        ensure_suggestions_collection(client)

    # ─────────────────────────── Bulk Operations ─────────────────────

    async def delete_all(self, client: QdrantClient):
        """Delete everything: documents, configs, suggestions, embedding collections."""
        client = self._get_client(client)
        # Get all collections
        collections = [c.name for c in client.get_collections().collections]
        for col in collections:
            if col.startswith("nemi_"):
                await _run_sync(client.delete_collection, collection_name=col)
        # Recreate base collections
        ensure_documents_collection(client)
        ensure_config_collection(client)
        ensure_suggestions_collection(client)

    async def get_metadata(self, client: QdrantClient) -> tuple[dict, dict]:
        """Get Qdrant cluster metadata (analogous to Weaviate get_metadata)."""
        client = self._get_client(client)
        try:
            collections = client.get_collections().collections
        except Exception:
            return {}, {}

        node_payload = {
            "node_count": 1,
            "qdrant_version": "unknown",
            "nodes": [{"status": "healthy", "shards": len(collections), "version": "?", "name": "qdrant"}],
        }

        collection_list = []
        for col in collections:
            try:
                count = client.count(collection_name=col.name, exact=True).count
            except Exception:
                count = 0
            collection_list.append({"name": col.name, "count": count})
        collection_list.sort(key=lambda x: x["count"], reverse=True)

        return node_payload, {
            "collection_count": len(collections),
            "collections": collection_list,
        }

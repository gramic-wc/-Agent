"""Qdrant 封装：默认嵌入式本地模式（免 Docker），设了 QDRANT_URL 就切服务端。"""

from __future__ import annotations

import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from .. import llm
from ..config import settings
from ..schema import Chunk

log = logging.getLogger(__name__)

UPSERT_BATCH = 32


def get_client() -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url)
    settings.qdrant_path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(settings.qdrant_path))


def recreate_collection(client: QdrantClient) -> None:
    if client.collection_exists(settings.collection):
        client.delete_collection(settings.collection)
    client.create_collection(
        collection_name=settings.collection,
        vectors_config=VectorParams(size=settings.embed_dim, distance=Distance.COSINE),
    )


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def build_filter(device_model: str | None = None, block_types: list[str] | None = None):
    must = []
    if device_model:
        must.append(FieldCondition(key="device_model", match=MatchValue(value=device_model)))
    if block_types:
        must.append(FieldCondition(key="block_type", match=MatchAny(any=list(block_types))))
    return Filter(must=must) if must else None


def upsert_chunks(client: QdrantClient, chunks: list[Chunk]) -> None:
    for i in range(0, len(chunks), UPSERT_BATCH):
        batch = chunks[i : i + UPSERT_BATCH]
        vectors = llm.embed([c.embed_text() for c in batch])
        points = [
            PointStruct(id=point_id(c.chunk_id), vector=v, payload={**c.payload(), "text": c.text})
            for c, v in zip(batch, vectors, strict=True)
        ]
        client.upsert(collection_name=settings.collection, points=points)
        log.info("upsert %d/%d", min(i + UPSERT_BATCH, len(chunks)), len(chunks))


def query(client: QdrantClient, vector: list[float], top_k: int, flt=None) -> list:
    """兼容 qdrant-client 新旧 API（1.12+ 用 query_points）。"""
    if hasattr(client, "query_points"):
        res = client.query_points(
            collection_name=settings.collection,
            query=vector,
            limit=top_k,
            query_filter=flt,
            with_payload=True,
        )
        return list(res.points)
    return list(
        client.search(
            collection_name=settings.collection,
            query_vector=vector,
            limit=top_k,
            query_filter=flt,
            with_payload=True,
        )
    )

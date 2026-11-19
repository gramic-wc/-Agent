"""混合检索：语义 + BM25，RRF 融合，再重排。

为什么必须加 BM25：型号（GA55）、故障码（E-204）、备件编码（P-1023）这类字符串，
纯向量检索命中率很差，而工单里到处是它们。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

from .. import llm
from ..config import settings
from . import index as vindex

log = logging.getLogger(__name__)

RRF_K = 60
DENSE_K = 30
SPARSE_K = 30
RERANK_K = 30


@dataclass
class Hit:
    chunk_id: str
    text: str
    payload: dict = field(default_factory=dict)
    score: float = 0.0
    source: str = ""

    @property
    def page(self) -> int:
        return int(self.payload.get("page") or 0)

    @property
    def doc_title(self) -> str:
        return self.payload.get("doc_title") or self.payload.get("doc_id") or ""

    def as_evidence(self, label: str) -> dict:
        return {
            "id": label,
            "chunk_id": self.chunk_id,
            "doc_id": self.payload.get("doc_id", ""),
            "doc_title": self.doc_title,
            "page": self.page,
            "block_type": self.payload.get("block_type", ""),
            "figure_no": self.payload.get("figure_no", ""),
            "text": self.text,
        }


def _tokens(text: str) -> list[str]:
    return [t for t in jieba.lcut((text or "").lower()) if t.strip()]


class Retriever:
    def __init__(self, chunks_path: Path | None = None):
        path = Path(chunks_path or settings.index_dir / "chunks.jsonl")
        if not path.exists():
            raise RuntimeError(
                f"缺少索引文件 {path}，先跑入库：uv run eq-ingest --no-vlm"
            )
        self.by_id: dict[str, dict] = {}
        corpus: list[list[str]] = []
        self.ids: list[str] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                self.by_id[row["chunk_id"]] = row
                self.ids.append(row["chunk_id"])
                corpus.append(
                    _tokens(
                        f"{row.get('doc_title','')} {row.get('device_model','')} "
                        f"{row.get('section_path','')} {row.get('text','')}"
                    )
                )
        self.bm25 = BM25Okapi(corpus) if corpus else None
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = vindex.get_client()
        return self._client

    # ------------------------------------------------------------ 两路召回
    def _dense(self, query: str, top_k: int, device_model: str | None, block_types):
        flt = vindex.build_filter(device_model, block_types)
        points = vindex.query(self.client, llm.embed([query])[0], top_k, flt)
        out = []
        for p in points:
            payload = p.payload or {}
            cid = self._match_id(payload)
            if cid:
                out.append(Hit(cid, payload.get("text", ""), payload, float(p.score), "dense"))
        return out

    def _match_id(self, payload: dict) -> str | None:
        for key in ("chunk_id",):
            cid = payload.get(key)
            if cid in self.by_id:
                return cid
        return None

    def _sparse(self, query: str, top_k: int, device_model: str | None, block_types):
        if self.bm25 is None:
            return []
        scores = self.bm25.get_scores(_tokens(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[: top_k * 4]
        out = []
        for i in order:
            if scores[i] <= 0:
                break
            cid = self.ids[i]
            row = self.by_id[cid]
            if device_model and row.get("device_model") != device_model:
                continue
            if block_types and row.get("block_type") not in block_types:
                continue
            out.append(Hit(cid, row.get("text", ""), row, float(scores[i]), "sparse"))
            if len(out) >= top_k:
                break
        return out

    # ------------------------------------------------------------ 对外
    def search(
        self,
        query: str,
        top_k: int = 6,
        device_model: str | None = None,
        block_types: list[str] | None = None,
    ) -> list[Hit]:
        dense = self._dense(query, DENSE_K, device_model, block_types)
        sparse = self._sparse(query, SPARSE_K, device_model, block_types)

        fused: dict[str, float] = {}
        pool: dict[str, Hit] = {}
        for hits in (dense, sparse):
            for rank, hit in enumerate(hits):
                fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
                pool.setdefault(hit.chunk_id, hit)
        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:RERANK_K]
        cands = [pool[cid] for cid, _ in ranked]

        reranked = llm.rerank(query, [h.text[:800] for h in cands], top_n=min(top_k, len(cands)))
        if reranked:
            out = []
            for idx, score in reranked:
                hit = cands[idx]
                hit.score, hit.source = score, f"{hit.source}+rerank"
                out.append(hit)
            return out[:top_k]

        for hit in cands:
            hit.score = fused[hit.chunk_id]
        return cands[:top_k]


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()

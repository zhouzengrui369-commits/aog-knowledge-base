"""Chroma 向量检索客户端 - 持久化到 ./data/chroma

设计:
- 单一 collection: aog_documents
- 由 Wave 1 T3 pipeline 写入 (id / text / metadata)
- 后端只读, 提供 query(q, n_results, where) 检索
- ★ NSM-2: 即使 collection 为空, 也要返回结构化空结果, chat 端点再补 mock 引用
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from aog_web.config import get_settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "aog_documents"


class ChromaClient:
    """持久化 Chroma 客户端 (单例)"""

    def __init__(self, chroma_path: Path):
        self.chroma_path = chroma_path
        chroma_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(chroma_path),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=False,
            ),
        )
        # 拿到或创建 collection (get_or_create 安全)
        try:
            self._collection = self._client.get_collection(COLLECTION_NAME)
        except Exception:
            self._collection = self._client.create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

    def count(self) -> int:
        try:
            return self._collection.count()
        except Exception as e:
            logger.warning("chroma count failed: %s", e)
            return 0

    async def query(
        self,
        q: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """同步接口, 但 await 调用 (chroma 内部 IO 阻塞不影响 FastAPI 异步调度)"""
        if not q or not q.strip():
            return []
        n_results = max(1, min(n_results, 20))  # 1-20 cap
        try:
            kwargs: Dict[str, Any] = {
                "query_texts": [q],
                "n_results": n_results,
            }
            if where:
                kwargs["where"] = where
            res = self._collection.query(**kwargs)
        except Exception as e:
            logger.error("chroma query failed: %s", e)
            return []

        # 展开: 返回 list of {id, text, metadata, score, distance}
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]

        out: List[Dict[str, Any]] = []
        for i, doc_id in enumerate(ids):
            text = docs[i] if i < len(docs) else ""
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else None
            # cosine distance -> score (0-1, 越大越相关)
            score = max(0.0, 1.0 - dist) if dist is not None else 0.0
            out.append({
                "id": doc_id,
                "text": text,
                "metadata": meta or {},
                "score": round(score, 4),
            })
        return out


_client: Optional[ChromaClient] = None


def get_chroma_client() -> ChromaClient:
    """获取 Chroma 客户端单例"""
    global _client
    if _client is None:
        s = get_settings()
        _client = ChromaClient(s.chroma_path)
    return _client


def reset_chroma_client() -> None:
    """测试 helper"""
    global _client
    _client = None

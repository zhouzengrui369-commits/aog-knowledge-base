"""Embedding: 本地 bge-m3。

支持两种 backend:
- Ollama (默认): 通过本地 ollama HTTP API 调用 bge-m3
  - 优点: 启动快, 已有模型缓存, 无需下载
  - 缺点: 单次请求略慢 (~0.1-0.3s), 批量需要并发
- SentenceTransformers: 直接加载模型
  - 优点: 批量 GPU 推理快
  - 缺点: 首次需下载模型 (~2.3GB), 加载慢

默认用 ollama, 因为任务环境已预装 bge-m3。
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Sequence

DEFAULT_MODEL = "bge-m3"
DEFAULT_BATCH = 8
DEFAULT_BACKEND = "ollama"  # 'ollama' | 'sentence-transformers'
DEFAULT_OLLAMA_URL = "http://localhost:11434"


class Embedder:
    """Embedding wrapper。优先用 ollama (已缓存 bge-m3), 失败回退 sentence-transformers。"""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
        batch_size: int = DEFAULT_BATCH,
        backend: str = DEFAULT_BACKEND,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        ollama_concurrency: int = 4,
    ):
        self.model_name = model_name
        self.device = device or "cpu"
        self.batch_size = batch_size
        self.backend = backend
        self.ollama_url = ollama_url
        self.ollama_concurrency = ollama_concurrency
        self._st_model = None
        self._dim: int | None = None

    # ---------- ollama backend ----------

    def _ollama_embed_one(self, text: str) -> list[float]:
        import urllib.request
        import json

        body = json.dumps({"model": self.model_name, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.ollama_url}/api/embeddings",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["embedding"]

    def _ollama_available(self) -> bool:
        """检查 ollama 服务是否可用 + 模型存在。"""
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                import json

                data = json.loads(resp.read())
            models = {m["name"].split(":")[0] for m in data.get("models", [])}
            return self.model_name in models
        except Exception:
            return False

    def _ollama_embed_batch(self, texts: Sequence[str], show_progress: bool = False) -> list[list[float]]:
        """并发调用 ollama。"""
        from tqdm import tqdm

        out: list[list[float] | None] = [None] * len(texts)
        with ThreadPoolExecutor(max_workers=self.ollama_concurrency) as ex:
            futures = {ex.submit(self._ollama_embed_one, t): i for i, t in enumerate(texts)}
            iterator = as_completed(futures)
            if show_progress:
                iterator = tqdm(iterator, total=len(texts), desc="embed")
            for f in iterator:
                i = futures[f]
                try:
                    out[i] = f.result()
                except Exception as e:
                    raise RuntimeError(f"ollama embed failed at index {i}: {e}") from e
        return out  # type: ignore

    # ---------- sentence-transformers backend ----------

    def _st_available(self) -> bool:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_st_model(self) -> None:
        if self._st_model is not None:
            return
        from sentence_transformers import SentenceTransformer

        os.environ.setdefault("TQDM_DISABLE", "1")
        device = self._pick_st_device()
        self._st_model = SentenceTransformer(self.model_name, device=device)
        self.device = device

    @staticmethod
    def _pick_st_device() -> str:
        try:
            import torch

            if torch.backends.mps.is_available() and torch.backends.mps.is_built():
                return "mps"
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"

    # ---------- public ----------

    def embed(self, texts: Sequence[str], show_progress: bool = False) -> list[list[float]]:
        """文本序列 → 向量列表。"""
        if not texts:
            return []
        # 选择 backend
        backend = self.backend
        if backend == "ollama" and not self._ollama_available():
            if self._st_available():
                print(f"[embed] ollama 不可用, 回退到 sentence-transformers")
                backend = "sentence-transformers"
            else:
                raise RuntimeError(
                    f"ollama 不可用且 sentence-transformers 未安装, 无法 embedding"
                )
        if backend == "ollama":
            return self._ollama_embed_batch(texts, show_progress=show_progress)
        # sentence-transformers
        self._ensure_st_model()
        vecs = self._st_model.encode(
            list(texts),
            batch_size=self.batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return [v.tolist() for v in vecs]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def dimension(self) -> int:
        """返回向量维度, bge-m3 = 1024。"""
        if self._dim is None:
            v = self.embed_one("dim probe")
            self._dim = len(v)
        return self._dim

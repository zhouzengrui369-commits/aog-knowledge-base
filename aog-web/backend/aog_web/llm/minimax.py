"""MiniMax M3 LLM 真实调用 - httpx async client"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)


class MiniMaxM3Client:
    """MiniMax M3 真实实现 - 通过 httpx async client 调 HTTPS API

    失败模式:
    - API key 缺失: 由 get_llm() 在工厂层改派 Mock, 此 client 假设 key 存在
    - 网络错误: 抛出 httpx.HTTPError, 上层 chat 端点转为 502
    - 5xx: 同上
    """

    def __init__(self, api_key: str, base_url: str = "https://api.MiniMax.chat/v1", model: str = "minimax-m3"):
        if not api_key or not api_key.strip():
            raise ValueError("MINIMAX_API_KEY required for MiniMaxM3Client (use MockMiniMax if missing)")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """OpenAI 兼容 chat completions 调用

        messages: [{"role": "system|user|assistant", "content": "..."}]
        返回: 纯文本回答
        """
        client = await self._get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        try:
            resp = await client.post("/chat/completions", json=payload)
        except httpx.HTTPError as e:
            logger.error("MiniMax M3 network error: %s", e)
            raise

        if resp.status_code >= 500:
            logger.error("MiniMax M3 5xx: status=%d body=%s", resp.status_code, resp.text[:200])
            raise httpx.HTTPStatusError(
                f"upstream 5xx: {resp.status_code}",
                request=resp.request,
                response=resp,
            )

        if resp.status_code != 200:
            logger.error("MiniMax M3 4xx: status=%d body=%s", resp.status_code, resp.text[:200])
            resp.raise_for_status()

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error("MiniMax M3 unexpected payload: %s", data)
            raise ValueError(f"unexpected LLM payload: {e}") from e

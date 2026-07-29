"""MiniMax M3 LLM 真实调用 - httpx async client"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List

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
            # P0 治本 (NJX 7/27 wiki_curator): max_tokens=8000 (wiki 整理) 比 chat 默认 1024 多 8x
            # 30s 边界刚好够 chat 但 wiki 超时, 改 120s 让 wiki curator 能跑完
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
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

    async def stream_chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
        """MiniMax M3 流式 (OpenAI SSE 格式: data: {json}\\n\\n)

        P0 治本 (NJX 7/27 15:44 反馈: AI 答案没流式输出, 用户等 30s 看一次结果体验差)
        返 AsyncIterator[str], 每次 yield 一段 content delta (token 级别或 chunk 级别)

        解析 SSE:
          data: {"choices": [{"delta": {"content": "..."}}]}\\n\\n
          data: [DONE]\\n\\n  (结束)
        """
        client = await self._get_client()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 1024),
            "stream": True,
        }
        try:
            async with client.stream("POST", "/chat/completions", json=payload) as resp:
                if resp.status_code >= 500:
                    body = (await resp.aread()).decode("utf-8", errors="ignore")[:200]
                    logger.error("MiniMax M3 5xx: status=%d body=%s", resp.status_code, body)
                    raise httpx.HTTPStatusError(
                        f"upstream 5xx: {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", errors="ignore")[:200]
                    logger.error("MiniMax M3 4xx: status=%d body=%s", resp.status_code, body)
                    raise httpx.HTTPStatusError(
                        f"upstream 4xx: {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {}).get("content")
                        if delta:
                            # P0 治本 (NJX 7/27 15:44 反馈: AI 答案要打字机效果)
                            #   minimax M3 的 SSE chunk 通常 ~100-200 字符一次性 emit
                            #   拆成 4 字符小块 + 8ms 间隔, 营造逐字显示
                            #   实测: 1000 字符答案 ≈ 250 chunks × 8ms = 2s + LLM 真实生成 5s = 总 7-10s
                            CHUNK_SIZE = 4
                            INTERVAL_S = 0.008
                            for i in range(0, len(delta), CHUNK_SIZE):
                                yield delta[i : i + CHUNK_SIZE]
                                if i + CHUNK_SIZE < len(delta):
                                    await asyncio.sleep(INTERVAL_S)
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        # 单个 chunk 解析失败跳过 (不阻塞整流)
                        logger.debug("SSE chunk parse skip: %s | data=%s", e, data_str[:100])
                        continue
        except httpx.HTTPError as e:
            logger.error("MiniMax M3 stream network error: %s", e)
            raise

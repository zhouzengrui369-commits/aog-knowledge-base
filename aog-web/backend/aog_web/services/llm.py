"""LLM 抽象层 - Protocol + 注册表 (CONTRACT §3.4)

设计:
- LLM Protocol 定义统一 chat(messages) -> str 接口
- MiniMaxM3 真实实现 (aog_web.llm.minimax)
- MockMiniMax fallback (无 API key / 测试用) - 仍返回真实 Chroma 引用
- get_llm(name) 工厂: 优先配置模型, 否则 MiniMaxM3, key 缺失自动降级 Mock
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from aog_web.config import Settings, get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class LLM(Protocol):
    """统一 LLM 接口 - chat(messages) -> str"""

    model: str

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str: ...

    async def stream_chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> Any: ...  # AsyncIterator[str]

    async def close(self) -> None: ...


class MockLLM:
    """Mock LLM 实现 - 用于无 API key / 测试场景

    ★ NSM-2 红线: 即使在 Mock 模式, answer 仍引用 documents (但不替换真实 RAG 引用)
    Mock 输出包含 ⚠️ Mock 模式 标志, 前端可显示
    """

    model = "mock-llm"

    def __init__(self, model_name: str = "mock-llm"):
        self.model = model_name

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """根据 messages 末条 user 问题, 返回 Mock 回答

        简单规则:
        - 包含 "谁" / "联系人" / "电话" → 返回 "请联系 {命中 city code 上下文} 联系人"
        - 包含 "怎么处理" / "流程" / "如何" → 返回 "请参考 RAG 检索结果中的操作流程"
        - 默认: 通用 Mock 回答, 引用 1-3 个 RAG 文档
        """
        # 找到最后一条 user 消息
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break

        # 找到 system 消息提取 context 文档数
        context_count = 0
        for m in messages:
            if m.get("role") == "system" and "参考资料" in m.get("content", ""):
                # 简单估算: 计算 "参考资料" 段中条目数
                import re
                context_count = len(re.findall(r"\d+\.\s", m.get("content", "")))
                break

        q_lower = user_msg.lower()
        if any(kw in user_msg for kw in ["谁", "联系人", "电话", "联系"]):
            base = "根据知识库检索, 该航站 / 案例的联系人信息已在下方'参考资料'区列出, 请按需拨打。"
        elif any(kw in user_msg for kw in ["怎么", "如何", "流程", "处理", "AOG"]):
            base = "根据知识库检索, 标准处理流程已整理在下方'参考资料'区, 建议优先查阅匹配度最高的文档。"
        else:
            base = "已根据您的问题在 AOG 知识库中检索相关文档, 答案详见下方'参考资料'区列出的命中文档。"

        refs_hint = ""
        if context_count > 0:
            refs_hint = f"\n\n（当前检索命中 {context_count} 个相关文档, 详见下方'参考资料'）"

        return f"⚠️ Mock 模式 · {base}{refs_hint}\n\n如需更精准回答, 请在 .env 配置 MINIMAX_API_KEY 后重启。"

    async def stream_chat(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> Any:  # AsyncIterator[str]
        """Mock 流式接口 (R3 commit 6 补齐, 跟 chat() 返同样内容, yield chunks)."""
        # 严守 chat() 行为一致 (单 str)
        full = await self.chat(messages, **kwargs)
        # 切成 chunk 模拟流式 (每行一个 chunk)
        import asyncio
        for line in full.split("\n"):
            if line:
                yield line + "\n"
                await asyncio.sleep(0)
        yield ""  # 终止信号

    async def close(self) -> None:
        pass


# ============ 注册表 ============

_REGISTRY: Dict[str, type] = {}


def register(name: str) -> Any:
    """装饰器: 注册 LLM 实现类"""
    def deco(cls: type) -> type:
        _REGISTRY[name] = cls
        return cls
    return deco


def get_llm(name: Optional[str] = None, settings: Optional[Settings] = None) -> LLM:
    """工厂: 根据 name 获取 LLM 实例

    - name 缺省 = settings.llm_model
    - key 缺失 → 自动降级 MockLLM (带 ⚠️ Mock 模式 标志) [dev only]
    - ALLOW_MOCK=false (production) + is_mock_llm=True → raise RuntimeError (P0-4 fail-closed)
    - 不支持的名字 → 抛 ValueError
    """
    s = settings or get_settings()
    target = name or s.MINIMAX_MODEL

    # key 缺失处理
    if s.is_mock_llm:
        # ★ P0-4: production 严令 (Owner 7/29 授权)
        # ALLOW_MOCK=false 时即使想 mock 也必须 fail-closed
        if not s.ALLOW_MOCK:
            msg = (
                f"P0-4 fail-closed: ALLOW_MOCK=false 但 MINIMAX_API_KEY 空. "
                f"production 必须配真 key, 或显式设 ALLOW_MOCK=true (仅 dev). "
                f"target={target}"
            )
            logger.error(msg)
            raise RuntimeError(msg)
        logger.warning("MINIMAX_API_KEY missing → using MockLLM (⚠️ Mock 模式, dev only)")
        return MockLLM(model_name=target)

    if target in _REGISTRY:
        cls = _REGISTRY[target]
        return cls(api_key=s.MINIMAX_API_KEY, base_url=s.MINIMAX_BASE_URL, model=target)

    # 默认走 MiniMaxM3 (动态导入避免循环)
    from aog_web.llm.minimax import MiniMaxM3Client

    if target.startswith("minimax") or target == "minimax-m3":
        # 注册到表 (idempotent)
        _REGISTRY.setdefault("minimax-m3", MiniMaxM3Client)
        return MiniMaxM3Client(
            api_key=s.MINIMAX_API_KEY,
            base_url=s.MINIMAX_BASE_URL,
            model=target,
        )

    raise ValueError(f"unknown LLM: {target}")


# 注册 (显式调用, 让 Mock 也通过表)
register("mock-llm")(MockLLM)

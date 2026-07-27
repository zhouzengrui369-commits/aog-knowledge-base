"""POST /api/chat - RAG + LLM - CONTRACT §2.7
POST /api/chat/stream - RAG + LLM 流式 (SSE) - NJX 7/27 15:44 反馈 AI 答案要打字机效果

流程:
1. 收到 q → RAG backend 查 top-5 (chroma 或 fts5, 由 settings.rag_backend 决定)
2. 取 1-3 个最相关文档作为 context
3. 构造 system prompt + user q
4. 调 LLM (Mock 或 MiniMax M3 真实)
5. 返回 {answer, references, model, latency_ms}
★ NSM-2: references 强制 ≥ 1 (从 RAG 检索结果填, 不足则用 SQLite 兜底)

流式 (/api/chat/stream):
- 用 FastAPI StreamingResponse + SSE (text/event-stream)
- 先 emit 一行 JSON: {references, model} (前端拿到 references 立刻显示, 不等 LLM)
- 再 emit 多行 content delta (LLM stream_chat yield)
- 最后 emit "data: [DONE]\\n\\n"
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from aog_web.models.chat import ChatRequest, ChatResponse, Reference
# ★ SCF 部署: chromadb 无 Linux wheel, 改成 lazy import
from aog_web.services.fts5_client import get_fts5_client
from aog_web.services.llm import get_llm
from aog_web.services.sqlite_client import get_sqlite_client


def _get_chroma_client_lazy():
    from aog_web.services.chroma_client import get_chroma_client
    return get_chroma_client()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


SYSTEM_PROMPT_TEMPLATE = """你是 AOG（飞机停场维修）应急保障知识库的 AI 助手。
你只能基于下面给出的"参考资料"回答用户问题。如果参考资料没有相关信息，请直接说"暂未找到相关文档"。
回答要简洁，分步骤、给出联系人/件号/流程要点。
回答末尾必须列出引用的参考资料编号（与下面参考资料对应）。

P0 治本 (NJX 7/27 15:44 反馈: AI 答案显示原始 markdown 格式, 没渲染):
- **必须使用标准 markdown 语法** —— 表格行之间用真正的换行 (\\n) 分隔, 不要用空格
- 标题用 ## / ### 单独一行, 不要跟正文连写
- 列表用 - 或 1. 单独一行, 缩进 2 空格
- **bold** 和 `code` 可内联
- 思考过程 (用 <think>...</think> 包裹) 跟正文用 \\n\\n 分隔

参考资料（已按相关度排序）:
{context_block}
"""


def _build_context_block(refs: List[Dict[str, Any]]) -> str:
    """构造 system prompt 中的 context 块"""
    if not refs:
        return "（暂无参考资料）"
    lines: List[str] = []
    for i, r in enumerate(refs, 1):
        title = r.get("title") or r.get("id", "")
        snippet = (r.get("text") or r.get("snippet") or "")[:600]
        lines.append(f"{i}. [{title}] {snippet}")
    return "\n".join(lines)


def _build_references(refs: List[Dict[str, Any]]) -> List[Reference]:
    """从 Chroma 检索结果构造 Reference 列表 (≥ 1)"""
    out: List[Reference] = []
    for r in refs:
        meta = r.get("metadata", {}) or {}
        # 优先 metadata.title / metadata.href
        title = meta.get("title") or r.get("title") or r.get("id", "doc")
        doc_id = r.get("id", "")
        # href: city -> /city/{code}, experience -> /experience/{id}, core -> /core-plan/{id}
        kind = meta.get("kind") or meta.get("type") or ""
        code = meta.get("code") or meta.get("city_code") or ""
        if kind == "city" and code:
            href = f"/city/{code}"
        elif kind == "experience":
            href = f"/experience/{doc_id}"
        elif kind == "core_plan":
            href = f"/core-plan/{doc_id}"
        else:
            # 兜底: 用 doc_id
            href = f"/{doc_id}"

        text = r.get("text", "")
        snippet = text[:200] if text else meta.get("snippet", "")[:200]
        if not snippet:
            snippet = title

        out.append(Reference(
            id=doc_id,
            title=title,
            href=href,
            snippet=snippet,
            score=float(r.get("score", 0.0)),
        ))
    return out


async def _sqlite_fallback_references(q: str, max_n: int = 3) -> List[Reference]:
    """★ NSM-2 兜底: Chroma 空 / 失败时, 用 SQLite 简单关键词搜 cities + experiences

    不保证语义匹配, 但保证 references.length ≥ 1
    """
    import re

    sqlite = get_sqlite_client()
    out: List[Reference] = []

    # token 化: 拆 q 为多个 keyword (中文按字, 英文按词)
    keywords: List[str] = []
    if q:
        # 提取英文/数字 token
        for m in re.finditer(r"[A-Za-z0-9\-]+", q):
            t = m.group(0).lower()
            if len(t) >= 1:
                keywords.append(t)
        # 提取中文片段 (2字+)
        for m in re.finditer(r"[\u4e00-\u9fff]{2,}", q):
            keywords.append(m.group(0))

    def _score(haystack_lower: str) -> int:
        """统计 keyword 命中数"""
        return sum(1 for k in keywords if k in haystack_lower)

    # 1. experiences - 命中 keywords 数
    all_exps = await sqlite.list_experiences()
    scored: List[tuple] = []
    for e in all_exps:
        haystack = (e.get("title", "") + " " + e.get("summary", "") + " " + e.get("content_md", "")).lower()
        s = _score(haystack)
        scored.append((s, e))
    scored.sort(key=lambda x: -x[0])
    for s, e in scored[:max_n]:
        if s == 0 and keywords:
            # 没命中任何 keyword, 跳过
            continue
        out.append(Reference(
            id=e["id"],
            title=e["title"],
            href=f"/experience/{e['id']}",
            snippet=(e.get("summary") or e.get("content_md", ""))[:200],
            score=round(0.5 + min(s, 3) * 0.1, 4),
        ))

    # 2. cities - 命中 keywords 数
    cities = await sqlite.list_cities()
    city_scored: List[tuple] = []
    for c in cities:
        hay = (f"{c.get('name','')} {c.get('code','')} {c.get('iata','')} {c.get('pinyin','')}").lower()
        s = _score(hay)
        city_scored.append((s, c))
    city_scored.sort(key=lambda x: -x[0])
    for s, c in city_scored[:max_n * 2]:
        if s == 0 and keywords:
            continue
        out.append(Reference(
            id=c["code"],
            title=c.get("name") or c["code"],
            href=f"/city/{c['code']}",
            snippet=(c.get("content_md") or f"{c.get('name','')} 航站预案")[:200],
            score=round(0.3 + min(s, 3) * 0.1, 4),
        ))
        if len(out) >= max_n * 2:
            break

    # 3. 没 keyword (q 全是标点) → 兜底给前 3 个 exp + 前 3 个 city
    if not out and not keywords:
        for e in all_exps[:max_n]:
            out.append(Reference(
                id=e["id"],
                title=e["title"],
                href=f"/experience/{e['id']}",
                snippet=(e.get("summary") or e.get("content_md", ""))[:200],
                score=0.3,
            ))
        for c in cities[:max_n]:
            out.append(Reference(
                id=c["code"],
                title=c.get("name") or c["code"],
                href=f"/city/{c['code']}",
                snippet=(c.get("content_md") or f"{c.get('name','')} 航站预案")[:200],
                score=0.2,
            ))

    # ★ NSM-2 强制兜底: 即使全空, 给一个 "no-match" 占位
    if not out:
        out.append(Reference(
            id="__no_match__",
            title="暂未找到相关文档",
            href="#",
            snippet="请尝试更具体的关键词, 或换个角度提问。",
            score=0.0,
        ))

    return out


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """RAG chat - 强制 references ≥ 1 (NSM-2)

    P0 治本 (NJX 7/27): chat() 非流式也调 _retrieve_context (5 段式 wiki > city > contacts > experience > core_plan)
    之前 chat() 走 inline 3 段式代码, 没接 P1-1 wiki 段 — 5 段式只在 chat_stream 生效
    """
    started = time.time()

    settings = request.app.state.settings
    llm = get_llm(settings=settings)

    # 1. RAG 检索 (5 段式 query: P1-1 wiki + D-030 city + contacts + exp + core)
    try:
        rag_hits = await _retrieve_context(request, body)
    except Exception as e:
        logger.error("RAG retrieve failed: %s", e)
        rag_hits = []
    # 用通用名 chroma_hits 保持下游不变
    chroma_hits = rag_hits

    # 2. 取 1-3 个最相关文档作为 context
    top_refs = chroma_hits[:3]

    # 3. ★ NSM-2: 强制 references ≥ 1
    references = _build_references(chroma_hits[:5])
    if not references:
        # Chroma 空 / 没命中 → SQLite 兜底
        references = await _sqlite_fallback_references(body.q, max_n=3)
        logger.info("using sqlite fallback references: %d", len(references))

    # 4. 构造 messages
    context_block = _build_context_block(top_refs)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context_block=context_block)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": body.q},
    ]

    # 5. 调 LLM
    try:
        answer = await llm.chat(messages)
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        await llm.close()
        # 即使 LLM 失败, 也返回 references (NSM-2)
        raise HTTPException(
            status_code=502,
            detail={"error": "upstream LLM error", "message": str(e)[:200]},
        )

    latency_ms = int((time.time() - started) * 1000)
    return ChatResponse(
        answer=answer,
        references=references,
        model=llm.model,
        latency_ms=latency_ms,
    )


# ====== 流式端点 (NJX 7/27 15:44 反馈: AI 答案要打字机效果) ======


def _sse_format(data: str, event: str = "message") -> str:
    """SSE 格式: `event: {event}\\ndata: {data}\\n\\n`"""
    return f"event: {event}\ndata: {data}\n\n"


async def _retrieve_context(request: Request, body: ChatRequest) -> List[Dict[str, Any]]:
    """RAG 检索 (P1-1 5 段式 query) — 跟非流式 /api/chat 共用
    顺序 (按 NJX 拍 🅰️ 双轨方案):
      1) wiki 段 (source_type=wiki) top 5 — 后台 LLM 整理的 wiki 页面, 优先召 (NJX 7/27 14:43 拍)
      2) city 主文档 (source_type=city) top 5 — D-030 治本, 完整城市预案
      3) city_contacts top 3 — 具体电话号码
      4) experience top 3 — 保障经验
      5) core_plan top 2 — 核心预案
    合并去重, 限制 8 个
    """
    settings = request.app.state.settings
    rag_hits: List[Dict[str, Any]] = []
    if settings.rag_backend == "fts5":
        try:
            fts5 = get_fts5_client()
            # 5 段式 query (P1-1: NJX 7/27 14:43 拍 🅰️ 双轨, wiki 优先)
            wiki_hits = await fts5.query(body.q, n_results=5, where={"source_type": "wiki"})
            city_hits = await fts5.query(body.q, n_results=5, where={"source_type": "city"})
            contacts_hits = await fts5.query(body.q, n_results=3, where={"source_type": "city_contacts"})
            experience_hits = await fts5.query(body.q, n_results=3, where={"source_type": "experience"})
            core_plan_hits = await fts5.query(body.q, n_results=2, where={"source_type": "core_plan"})
            # city 主文档 1.5x boost (D-030 治本)
            for h in city_hits:
                h["score"] = min(1.0, float(h.get("score", 0.0)) * 1.5)
            # wiki 段 1.3x boost (P1-1, LLM 整理的更结构化, 优先召)
            for h in wiki_hits:
                h["score"] = min(1.0, float(h.get("score", 0.0)) * 1.3)
            # 合并去重 (按 wiki > city > contacts > experience > core_plan 顺序)
            seen_ids: set = set()
            rag_hits = []
            for h in wiki_hits + city_hits + contacts_hits + experience_hits + core_plan_hits:
                if h.get("id") not in seen_ids:
                    seen_ids.add(h.get("id"))
                    rag_hits.append(h)
                if len(rag_hits) >= 8:
                    break
            logger.info(
                "P1-1 fts5 5 段 hits: %d (wiki=%d city=%d contacts=%d exp=%d core=%d) for q=%r",
                len(rag_hits), len(wiki_hits), len(city_hits), len(contacts_hits),
                len(experience_hits), len(core_plan_hits), body.q[:60],
            )
        except Exception as e:
            logger.warning("fts5 query failed, fallback to chroma: %s", e)
            try:
                chroma = _get_chroma_client_lazy()
                rag_hits = await chroma.query(body.q, n_results=5)
            except Exception as e2:
                logger.error("chroma fallback also failed: %s", e2)
    else:
        chroma = _get_chroma_client_lazy()
        rag_hits = await chroma.query(body.q, n_results=5)
    return rag_hits


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """流式 chat (SSE) - NJX 7/27 15:44 反馈 AI 答案要打字机效果

    SSE 协议:
      1) event: refs\\ndata: {json references + model}\\n\\n     ← 立刻 emit, 不等 LLM
      2) event: token\\ndata: {str content_delta}\\n\\n          ← LLM stream_chat yield 一次 emit 一次
      3) event: done\\ndata: [DONE]\\n\\n                       ← 结束
      4) 出错: event: error\\ndata: {json error}\\n\\n
    """
    started = time.time()
    settings = request.app.state.settings
    llm = get_llm(settings=settings)

    # 1. RAG 检索 (D-030 3 段式 query)
    try:
        rag_hits = await _retrieve_context(request, body)
    except Exception as e:
        logger.error("RAG retrieve failed: %s", e)
        rag_hits = []

    # 2. 构造 references
    references = _build_references(rag_hits[:5])
    if not references:
        references = await _sqlite_fallback_references(body.q, max_n=3)
        logger.info("using sqlite fallback references: %d", len(references))

    # 3. 构造 messages
    top_refs = rag_hits[:3]
    context_block = _build_context_block(top_refs)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context_block=context_block)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": body.q},
    ]

    # 4. SSE generator
    async def event_stream() -> AsyncIterator[str]:
        # 4a. 立刻 emit references (前端先显示, 不等 LLM 30s)
        refs_payload = {
            "references": [r.model_dump() if hasattr(r, "model_dump") else r.dict() for r in references],
            "model": llm.model,
            "latency_ms_partial": int((time.time() - started) * 1000),
        }
        yield _sse_format(json.dumps(refs_payload, ensure_ascii=False), event="refs")

        # 4b. LLM 流式
        try:
            # 优先用 stream_chat, 没有则 fallback chat() 然后整段 emit
            if hasattr(llm, "stream_chat"):
                async for delta in llm.stream_chat(messages):
                    yield _sse_format(delta, event="token")
            else:
                # Mock LLM / 老 LLM 没 stream, 走一次性 emit
                full = await llm.chat(messages)
                # 模拟流式: 按字切 + 间隔 10ms (NJX 看得到打字机效果)
                for ch in full:
                    yield _sse_format(ch, event="token")
                    await asyncio.sleep(0.01)
        except Exception as e:
            logger.error("LLM stream failed: %s", e)
            yield _sse_format(json.dumps({"error": str(e)[:200]}), event="error")

        # 4c. 结束
        latency_ms = int((time.time() - started) * 1000)
        done_payload = {"latency_ms": latency_ms}
        yield _sse_format(json.dumps(done_payload), event="done")
        yield _sse_format("[DONE]", event="message")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 不缓冲
            "Connection": "keep-alive",
        },
    )

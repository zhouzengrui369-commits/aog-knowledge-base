"""POST /api/chat - RAG + LLM - CONTRACT §2.7
POST /api/chat/stream - RAG + LLM 流式 (SSE) - NJX 7/27 15:44 反馈 AI 答案要打字机效果
V30 (NJX 7/27 22:14 拍板 🅰️): LLM 输出结构化 JSON + 前端组件化
  - LLM 输出末尾加 ===JSON_START===...===JSON_END=== sentinel 段, 描述 sections 数组
  - 后端 parser 解析成功 → sections 字段, 前端按 type 渲染 React 组件 (100% 视觉受控)
  - parser 失败 → sections=None, 前端 fallback 到 V29d++ markdown 渲染

流程:
1. 收到 q → RAG backend 查 top-5 (chroma 或 fts5, 由 settings.rag_backend 决定)
2. 取 1-3 个最相关文档作为 context
3. 构造 system prompt + user q
4. 调 LLM (Mock 或 MiniMax M3 真实)
5. 返回 {answer, sections, references, model, latency_ms}
★ NSM-2: references 强制 ≥ 1 (从 RAG 检索结果填, 不足则用 SQLite 兜底)

流式 (/api/chat/stream):
- 用 FastAPI StreamingResponse + SSE (text/event-stream)
- 先 emit refs event: {references, model} (前端拿到 references 立刻显示, 不等 LLM)
- 再 emit token events: 流式 markdown delta (打字机)
- LLM 流完后, parser 解析 sentinel 段, emit sections event: {sections: [...]} (前端用 sections 重渲染)
- 最后 emit done event: {latency_ms}
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from aog_web.models.chat import ChatRequest, ChatResponse, ChatSection, Reference
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

P0 治本 (NJX 7/27 15:44 + 19:37 + 20:34 反馈: AI 答案排版混乱, markdown marker inline 不分行):
- **每个 markdown 元素必须独占一行**:
  - 标题: `## xxx` / `### xxx` 单独一行, 前面必须有 \\n
  - 列表: `- xxx` / `* xxx` / `1. xxx` 单独一行
  - 表格: `| col1 | col2 |` + `|---|---|` + `| data |` 每行换行
  - 段落: 段落之间用空行 \\n\\n 分隔
- **bold** 用 `**xxx**`, **italic** 用 `*xxx*`, **code** 用 `` `xxx` ``
- **绝对不要**把多个 markdown 元素塞在同一行 (例如 `*机场: ...# 二、故障树`)
- **绝对不要**把 markdown 标记紧贴前字符 (例如 `件号:C20649000-` 应该是 `件号: C20649000 -`)
- 思考过程 (用 <think>...</think> 包裹) 跟正文用 \\n\\n 分隔

P0 治本 视觉结构 (NJX 7/27 20:34 反馈"AI 文本输出依然不便于阅读, 改为输出可视化水平高的文本格式"):
- **结构化输出**: 优先用 heading 分章节, 用 list 列步骤, 用 table 列对比/清单
- **重要件号/联系人/电话用 `code` 包裹** (e.g. `` `3-1531-3` ``)
- **关键操作动词用 **bold** 加粗** (e.g. **自我保障** / **求援** / **ADE 保障**)
- **场景分支用三级 heading 切分** (e.g. `### 场景 A: 短停故障` / `### 场景 B: 航后故障`)
- **避免长段落**: 一段不超过 3 行, 多了拆 list
- **引用编号加方括号**: `[1] [2]` 而不是 `1 2`

V30 治本 (NJX 7/27 22:14 拍板 🅰️): 回答末尾必须输出**结构化 JSON** 描述答案结构 (前端用 React 组件渲染, 100% 视觉受控, 不依赖 markdown 解析).

JSON 输出规则 (放在 markdown 答案最后, 用 sentinel 包裹):
===JSON_START===
{{
  "sections": [
    {{"type": "heading", "level": 2, "text": "基本信息"}},
    {{"type": "table", "header": ["项目", "内容"], "rows": [["IATA/ICAO", "HEL/EFHK"], ["机场", "赫尔辛基万塔国际机场"], ["国家/地区", "芬兰"], ["时差", "UTC+2/+3"], ["执飞机型", "B787/A350/A320"]]}},
    {{"type": "heading", "level": 3, "text": "当地服务商与联系人"}},
    {{"type": "table", "header": ["公司", "职责"], "rows": [["AVIATOR", "地服"], ["ASR", "货站清关"]]}},
    {{"type": "list", "items": ["自我保障", "求援", "ADE 保障"]}},
    {{"type": "alert", "variant": "warning", "text": "航材备件需提前 24h 申请"}},
    {{"type": "quote", "text": "短停故障应急流程见 [1]"}}
  ]
}}
===JSON_END===

8 种 section type 说明:
- heading: 一级/二级/三级标题, level=1/2/3
- paragraph: 普通段落, 纯文本
- table: 表格, header=[列名数组], rows=[[cell1, cell2, ...] 行数据]
- list: 无序列表, items=[字符串]
- ordered_list: 有序列表, items=[字符串]
- code: 代码块, text=内容, language=可选 (bash/text/sql)
- alert: 提示框, text=内容, variant=info/warning/danger/success
- quote: 引用块, text=内容

JSON 注意事项:
- 严格按上面 8 种 type 之一, 不要发明新 type
- 每个 section 一个完整结构, 不允许嵌套 (父子关系靠 level 表达)
- JSON 内部不要用 markdown (e.g. 不要 `**bold**` 包裹, 用纯字符串 + 视觉由前端决定)
- 如果某部分没有合适 type, 跳过 (不需要硬塞)
- sentinel 段必须用 ===JSON_START=== / ===JSON_END=== 完整包裹, 不可换行
- JSON 之前的所有内容都当 markdown 处理 (流式打字机)

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


# ====== V30 治本 (NJX 7/27 22:14 拍板 🅰️): LLM 输出结构化 JSON ======

# sentinel 段正则: 找 ===JSON_START=== ... ===JSON_END=== 之间的 JSON
_JSON_SECTION_RE = re.compile(
    r"===JSON_START===\s*([\s\S]+?)\s*===JSON_END===",
    re.MULTILINE,
)
# 合法 section type (校验用)
_VALID_SECTION_TYPES = {
    "heading", "paragraph", "table", "list", "ordered_list", "code", "alert", "quote",
}


def _parse_sections(answer: str) -> Tuple[str, Optional[List[ChatSection]]]:
    """V30 治本: 解析 LLM 输出里的 ===JSON_START===...===JSON_END=== sentinel 段

    返回 (clean_answer, sections):
      - clean_answer: 去掉 sentinel 段后的纯 markdown (sentinel 段不返给前端, 避免双渲染)
      - sections: 解析成功 = List[ChatSection], 失败 = None (前端 fallback markdown 渲染)

    容错 (P0 治本):
      - 没 sentinel 段 → (answer, None) 完整保留
      - JSON parse 失败 → (clean, None) clean 不含 sentinel
      - sections 不是 list / 全部不合法 → (clean, None)
      - 任何 type 非法 / pydantic 校验失败 → skip 这个 section, 其他 section 保留
    """
    if not answer:
        return answer, None
    match = _JSON_SECTION_RE.search(answer)
    if not match:
        return answer, None
    # 构造 clean_answer: 去掉 sentinel 段
    clean_answer = (answer[: match.start()] + answer[match.end() :]).strip()
    # 解析 JSON
    json_str = match.group(1).strip()
    # 兼容: LLM 可能包一层 ```json ... ``` markdown fence, 去之
    json_str = re.sub(r"^```(?:json)?\s*", "", json_str)
    json_str = re.sub(r"\s*```$", "", json_str)
    try:
        data = json.loads(json_str)
    except Exception as e:
        logger.warning("[V30] sections JSON parse failed: %s", e)
        return clean_answer, None
    if not isinstance(data, dict):
        logger.warning("[V30] sections JSON is not a dict: %r", type(data).__name__)
        return clean_answer, None
    raw_sections = data.get("sections")
    if not isinstance(raw_sections, list):
        logger.warning("[V30] sections field is not a list: %r", type(raw_sections).__name__)
        return clean_answer, None
    # 校验 + 构造 ChatSection
    sections: List[ChatSection] = []
    skipped = 0
    for raw in raw_sections:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        t = raw.get("type")
        if t not in _VALID_SECTION_TYPES:
            logger.debug("[V30] skip section: invalid type=%r", t)
            skipped += 1
            continue
        try:
            sections.append(ChatSection(**raw))
        except Exception as e:
            logger.debug("[V30] skip section %s: pydantic error %s", t, e)
            skipped += 1
            continue
    if not sections:
        return clean_answer, None
    logger.info(
        "[V30] parsed %d sections (skipped %d invalid) for chat answer",
        len(sections), skipped,
    )
    return clean_answer, sections


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
    # P0 治本 (NJX 7/27 20:34 反馈"AI 答案依然不便于阅读"):
    #   minimax M3 默认 max_tokens=1024 不够 wiki 完整输出 (含 heading + table + 联系人)
    #   之前实测 wiki_curator 改 12000 (V29b), chat 改 4000 兼容 markdown 完整结构
    #   max_tokens=4000 足够 ~1500-2000 字答案 + heading + 表格 + 引用
    try:
        answer = await llm.chat(messages, max_tokens=4000)
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        await llm.close()
        # 即使 LLM 失败, 也返回 references (NSM-2)
        raise HTTPException(
            status_code=502,
            detail={"error": "upstream LLM error", "message": str(e)[:200]},
        )

    # V30 治本 (NJX 7/27 22:14 拍板 🅰️): 解析 LLM 输出里的 ===JSON_START===...===JSON_END=== sentinel 段
    # 解析成功 → sections 字段填, 前端用 React 组件渲染 (100% 视觉受控)
    # 解析失败 → sections=None, 前端 fallback 到 V29d++ markdown 渲染
    clean_answer, sections = _parse_sections(answer)

    latency_ms = int((time.time() - started) * 1000)
    return ChatResponse(
        answer=clean_answer,
        sections=sections,
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
            # D-043 (NJX 7/28 11:44 反馈 "雅典保障查不到雅典预案"):
            #   召数扩大 + city 1.5x → 2.0x boost, 让 city 主文档不被"通用模板" wiki 顶掉
            #   wiki 召数 5→3 (限制"通用模板"占位), city 召数 5→8 (确保 city 一定召到)
            wiki_hits = await fts5.query(body.q, n_results=3, where={"source_type": "wiki"})
            city_hits = await fts5.query(body.q, n_results=8, where={"source_type": "city"})
            contacts_hits = await fts5.query(body.q, n_results=5, where={"source_type": "city_contacts"})
            experience_hits = await fts5.query(body.q, n_results=2, where={"source_type": "experience"})
            core_plan_hits = await fts5.query(body.q, n_results=1, where={"source_type": "core_plan"})
            # city 主文档 2.0x boost (D-043: 雅典 wiki/city 段被通用模板 wiki 顶掉, 治本)
            for h in city_hits:
                h["score"] = min(1.0, float(h.get("score", 0.0)) * 2.0)
            # wiki 段 1.3x boost (P1-1, LLM 整理的更结构化, 优先召)
            for h in wiki_hits:
                h["score"] = min(1.0, float(h.get("score", 0.0)) * 1.3)
            # 合并去重 (按 wiki > city > contacts > experience > core_plan 顺序)
            # D-043 限制 8 → 12, 让 city + wiki 都有机会进 top
            seen_ids: set = set()
            rag_hits = []
            for h in wiki_hits + city_hits + contacts_hits + experience_hits + core_plan_hits:
                if h.get("id") not in seen_ids:
                    seen_ids.add(h.get("id"))
                    rag_hits.append(h)
                if len(rag_hits) >= 12:
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

    V30 (NJX 7/27 22:14 拍板 🅰️): 加 sections event, 完整 LLM 输出后 emit 一次 sections 数组.
    前端: 打字机显示 markdown (V29d++ 效果) → sections 到达后切换到结构化组件化渲染.

    SSE 协议:
      1) event: refs       data: {json references + model}      ← 立刻 emit, 不等 LLM
      2) event: token      data: {str content_delta}              ← LLM stream_chat yield 一次 emit 一次
      3) event: sections   data: {json {sections:[...]}}          ← LLM 流完后, parser 解析成功才 emit
      4) event: done       data: {latency_ms}                      ← 结束
      5) 出错: event: error data: {json error}
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

        # 4b. LLM 流式 + 累加完整 buffer (V30 解析用)
        full_buffer: List[str] = []
        try:
            # 优先用 stream_chat, 没有则 fallback chat() 然后整段 emit
            # P0 治本 (NJX 7/27 20:34 反馈): max_tokens=4000 兼容 markdown 完整结构 (heading + 表格 + 引用)
            if hasattr(llm, "stream_chat"):
                async for delta in llm.stream_chat(messages, max_tokens=4000):
                    full_buffer.append(delta)
                    yield _sse_format(delta, event="token")
            else:
                # Mock LLM / 老 LLM 没 stream, 走一次性 emit
                full = await llm.chat(messages, max_tokens=4000)
                full_buffer.append(full)
                # 模拟流式: 按字切 + 间隔 10ms (NJX 看得到打字机效果)
                for ch in full:
                    yield _sse_format(ch, event="token")
                    await asyncio.sleep(0.01)
        except Exception as e:
            logger.error("LLM stream failed: %s", e)
            yield _sse_format(json.dumps({"error": str(e)[:200]}), event="error")

        # 4c. V30 治本: 解析完整 LLM 输出, 找 sentinel 段, emit sections event
        full_answer = "".join(full_buffer)
        if full_answer:
            _, sections = _parse_sections(full_answer)
            if sections:
                sections_payload = {
                    "sections": [s.model_dump() if hasattr(s, "model_dump") else s.dict() for s in sections],
                }
                yield _sse_format(json.dumps(sections_payload, ensure_ascii=False), event="sections")
                logger.info("[V30 stream] emit %d sections for q=%r", len(sections), body.q[:60])

        # 4d. 结束
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

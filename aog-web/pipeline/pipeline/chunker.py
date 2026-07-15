"""文本分块: 800 token / overlap 100 (按字符约 1200/150 中文字)。

策略:
- 按段落/换行切分
- 累积到 chunk_size_chars 才产出一个 chunk
- 末尾段不足时合并
- 段落过长 (>chunk_size) 时, 按句号/换行硬切

为什么按字符: 中文不分词, token 化很贵; 对检索影响小,字符够用。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_OVERLAP = 150


@dataclass
class Chunk:
    text: str
    index: int  # 在该 source 内的 chunk 序号 (从 0)
    char_start: int  # 在原文中的起始字符位置
    char_end: int


def split_into_paragraphs(text: str) -> list[str]:
    """按 markdown 段落切分 (保留标题, 跳过空段)。"""
    if not text:
        return []
    # 按 \n\n 切, 兼容 \n
    raw = re.split(r"\n\s*\n", text)
    paras = [r.strip() for r in raw if r.strip()]
    return paras


def _hard_split(p: str, chunk_size: int) -> list[str]:
    """段落过长, 按句末标点或固定长度切。"""
    if len(p) <= chunk_size:
        return [p]
    parts: list[str] = []
    # 优先按句末标点切
    sentences = re.split(r"(?<=[。！？!?\.])\s*", p)
    cur = ""
    for s in sentences:
        if not s:
            continue
        if len(cur) + len(s) + 1 <= chunk_size:
            cur = (cur + " " + s).strip() if cur else s
        else:
            if cur:
                parts.append(cur)
            if len(s) > chunk_size:
                # 再硬切
                for i in range(0, len(s), chunk_size):
                    parts.append(s[i : i + chunk_size])
                cur = ""
            else:
                cur = s
    if cur:
        parts.append(cur)
    return parts


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """主入口: text → list[Chunk]。

    段落优先, 段落内过长则按句切; 段落累积到 chunk_size 就产 chunk,
    overlap 让相邻 chunk 共享若干字符 (从 chunk 末尾取 overlap 长)。
    """
    if not text or not text.strip():
        return []
    paragraphs = split_into_paragraphs(text)
    # 把每个段落按 chunk_size 再切
    pieces: list[tuple[int, str]] = []  # (orig_start, piece)
    cursor = 0
    for para in paragraphs:
        for piece in _hard_split(para, chunk_size):
            pieces.append((cursor, piece))
            cursor += len(piece) + 2  # +2 for "\n\n"

    chunks: list[Chunk] = []
    cur_pieces: list[tuple[int, str]] = []
    cur_len = 0

    def _emit(idx: int, items: list[tuple[int, str]]) -> None:
        if not items:
            return
        text_joined = "\n\n".join(p for _, p in items)
        chunks.append(
            Chunk(
                text=text_joined,
                index=idx,
                char_start=items[0][0],
                char_end=items[-1][0] + len(items[-1][1]),
            )
        )

    chunk_idx = 0
    i = 0
    max_iter = len(pieces) * 3  # 防死循环保险
    iter_count = 0
    while i < len(pieces) and iter_count < max_iter:
        iter_count += 1
        start_pos, p = pieces[i]
        if cur_len + len(p) > chunk_size and cur_pieces:
            # emit current
            _emit(chunk_idx, cur_pieces)
            chunk_idx += 1
            # overlap: 从 cur_pieces 末尾取 overlap 字符
            keep: list[tuple[int, str]] = []
            kept_len = 0
            for pos, txt in reversed(cur_pieces):
                if kept_len + len(txt) > overlap:
                    break
                keep.insert(0, (pos, txt))
                kept_len += len(txt)
            cur_pieces = keep
            cur_len = kept_len
            # 注意: 不 continue, 直接 i += 1 处理当前 piece
        cur_pieces.append((start_pos, p))
        cur_len += len(p)
        i += 1

    if cur_pieces:
        _emit(chunk_idx, cur_pieces)

    return chunks


def chunk_documents(docs: Iterable[tuple[str, dict]], **kw) -> Iterable[tuple[str, dict, int, int]]:
    """批量 chunk: docs (text, meta) → (text, meta, idx, total) 元组。

    用于 indexer 写 Chroma 时拿到 chunk 在源内的 idx。
    """
    for text, meta in docs:
        chunks = chunk_text(text, **kw)
        total = len(chunks)
        for c in chunks:
            yield c.text, {**meta, "chunk_index": c.index, "char_start": c.char_start, "char_end": c.char_end}, c.index, total

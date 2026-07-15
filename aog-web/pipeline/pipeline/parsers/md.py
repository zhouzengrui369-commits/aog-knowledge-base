"""Markdown 解析: 直接读文件原文,保留前导 frontmatter。"""
from __future__ import annotations

from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


def parse_md(path: PathLike) -> str:
    """读 .md 文件原文。空文件返回空串。

    解析策略: AOG 知识库的 .md 是给人读的整理笔记, 整文作为 content_md
    一并索引。前置 YAML frontmatter (`---\\n...\\n---`) 保留。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"md 文件不存在: {p}")
    text = p.read_text(encoding="utf-8", errors="replace")
    return text.strip()


def parse_md_strip_frontmatter(path: PathLike) -> tuple[str, str]:
    """读 .md, 返回 (frontmatter, body) 元组。无 frontmatter 时 frontmatter=""。

    用于 extractors 想读 tags 字段的情况。
    """
    raw = parse_md(path)
    if raw.startswith("---"):
        # 找第二个 ---
        end = raw.find("\n---", 3)
        if end > 0:
            fm = raw[3:end].strip()
            body = raw[end + 4 :].lstrip("\n")
            return fm, body
    return "", raw

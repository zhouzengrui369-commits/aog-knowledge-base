"""PDF 解析: pypdf 抽文本, 按页分隔。

v1 不索引 PDF (CONTRACT §2.5 严禁), 此模块仅作为探测用,
build_index 会把 .pdf 加入 files_failed 列表。
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from pypdf import PdfReader

PathLike = Union[str, Path]


def parse_pdf(path: PathLike) -> str:
    """读 .pdf → 文本 (按页换页)。

    v1 不索引, 调用方需 catch 异常,或由 build_index 跳过 .pdf。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"pdf 文件不存在: {p}")
    if p.suffix.lower() != ".pdf":
        raise ValueError(f"不是 .pdf 文件: {p}")

    reader = PdfReader(str(p))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            pages.append(f"## Page {i + 1}\n\n{text.strip()}")
    return "\n\n".join(pages).strip()

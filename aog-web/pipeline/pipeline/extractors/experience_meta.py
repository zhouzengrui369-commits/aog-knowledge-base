"""Experience 字段提取: docx/xlsx 自由文本 → 结构化字段。

CONTRACT §1.2:
  id: 'exp-001' (sha1(title)[:8] 前缀)
  title: 文件名 (去扩展)
  category: '流程'|'规范'|'案例'|'培训'|'技术'|'管理'
  status: '现行'|'历史'|'待审'|'已废'
  tags: string[]
  summary: ≤ 200 字
  content_md: 完整 md 文本
  related_pn: 件号列表 (从 parts 表抽)
  source_path
  updated_at
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from ..parsers.docx import parse_docx, docx_table_to_markdown
from ..parsers.md import parse_md
from ..parsers.xlsx import parse_xlsx

PathLike = Union[str, Path]


# 关键词 → category 映射 (优先匹配)
CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("案例", "案例"),
    ("复盘", "案例"),
    ("AOG", "案例"),
    ("工作流", "流程"),
    ("流程", "流程"),
    ("检查单", "流程"),
    ("快反", "流程"),
    ("规范", "规范"),
    ("标准", "规范"),
    ("RSPL", "规范"),
    ("手册", "规范"),
    ("培训", "培训"),
    ("课件", "培训"),
    ("技术", "技术"),
    ("尺寸", "技术"),
    ("运输", "技术"),
    ("管理", "管理"),
    ("组织", "管理"),
    ("资质", "管理"),
]


def _category_from(name: str) -> str:
    for kw, cat in CATEGORY_KEYWORDS:
        if kw in name:
            return cat
    return "案例"  # default


def _status_from(name: str) -> str:
    if any(k in name for k in ["（历史）", "(历史)", "已废", "废弃"]):
        return "历史"
    if "待审" in name:
        return "待审"
    return "现行"


def _summary_from_text(text: str, max_chars: int = 200) -> str:
    """抽第一段非空内容, 截到 max_chars。"""
    text = (text or "").strip()
    if not text:
        return ""
    # 跳过 markdown 标题
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        # 去掉 # 标题
        cleaned = re.sub(r"^#+\s*", "", line)
        cleaned = re.sub(r"^[\*\-]\s*", "", cleaned)
        cleaned = re.sub(r"^\d+\.\s*", "", cleaned)
        if cleaned and not cleaned.startswith("---"):
            return cleaned[:max_chars]
    return text[:max_chars]


def _extract_pns(text: str) -> list[str]:
    """从 content_md 抽件号 (大写字母+数字 6+ 字符)。"""
    pns: set[str] = set()
    # 典型件号: C20649000 / 3-1531-3 / C20195162 / HYJET#V#GAL
    patterns = [
        r"\bC\d{6,}\b",  # C20649000
        r"\b\d{1,3}-\d{3,5}-\d?\b",  # 3-1531-3
        r"\b[A-Z]{2,5}\d{3,}[A-Z0-9#\-]*\b",  # HYJET#V#GAL
    ]
    for p in patterns:
        for m in re.findall(p, text):
            pns.add(m)
    return sorted(pns)[:20]  # cap


@dataclass
class Experience:
    id: str
    title: str
    category: str
    status: str
    tags: list[str]
    summary: str
    content_md: str
    related_pn: list[str]
    source_path: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def extract_experience(path: PathLike, knowledge_base_root: PathLike | None = None) -> Experience:
    """从 docx/xlsx/md 抽 Experience 完整字段。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")

    stem = p.stem
    # id: sha1(title)[:8] 前缀 'exp-'
    sha = hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8]
    eid = f"exp-{sha}"

    title = stem
    # 去 (历史) 之类状态后缀作为 title
    title_clean = re.sub(r"[（(](历史|已废|待审|废弃)[）)]\s*$", "", title).strip()
    if title_clean:
        title = title_clean

    # 解析
    suffix = p.suffix.lower()
    if suffix == ".docx":
        dt = parse_docx(p)
        content_md = docx_table_to_markdown(dt)
    elif suffix == ".md":
        content_md = parse_md(p)
    elif suffix == ".xlsx":
        content_md = parse_xlsx(p)
    elif suffix == ".pdf":
        # v1 不索引,但仍记录
        content_md = ""
    else:
        raise ValueError(f"Experience 不支持 .pdf/.pptx 等: {p}")

    category = _category_from(stem)
    status = _status_from(stem)
    summary = _summary_from_text(content_md)
    related_pn = _extract_pns(content_md)

    # tags
    tags: list[str] = []
    for kw in ["B787", "A320", "A321", "A330", "A350"]:
        if kw in stem or kw in content_md[:500]:
            tags.append(kw)
    for kw in ["风挡", "主轮", "前轮", "滑油", "液压油", "RSPL", "GPM", "BMS"]:
        if kw in stem:
            tags.append(kw)
    if not tags:
        tags = [category]

    # source_path
    if knowledge_base_root:
        try:
            source_path = str(p.relative_to(knowledge_base_root))
        except ValueError:
            source_path = str(p)
    else:
        source_path = str(p)

    return Experience(
        id=eid,
        title=title,
        category=category,
        status=status,
        tags=tags,
        summary=summary,
        content_md=content_md,
        related_pn=related_pn,
        source_path=source_path,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

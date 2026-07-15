"""CorePlan 字段提取: 01_AOG预案 下的核心预案。

CONTRACT §1.3:
  id: 'core-20260204' (用 'core-' 前缀 + filename 主段)
  title: 文件名
  type: 'master'|'checklist'|'manual'|'catalog'
  content_md: 完整 md 文本
  source_path
  updated_at
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from ..parsers.docx import parse_docx, docx_table_to_markdown
from ..parsers.md import parse_md
from ..parsers.xlsx import parse_xlsx

PathLike = Union[str, Path]


# 关键词 → type 映射
def _type_from(name: str) -> str:
    if "检查单" in name:
        return "checklist"
    if "手册" in name:
        return "manual"
    if any(k in name for k in ["目录", "整理", "导出", "导出记录"]):
        return "catalog"
    # 默认 master (含 "预案" 或其它)
    return "master"


def _id_from(filename: str) -> str:
    """生成 core_plan 的唯一 id。

    同一文档可能同时有 .md 和 .xlsx 两种格式 (e.g. 检查单 / 导出记录),需要 id 区分。
    也可能两个不同 .md 共享日期后缀 (e.g. 知识库目录20260101.md + 知识库整理20260101.md),
    所以日期后缀要加上关键词。

    规则 (优先级从高到低):
    1. 含日期 8 位 → 关键词 + 日期
    2. 含 R 后缀 → 关键词 + rN
    3. 关键词 (检查单/手册/目录/整理/导出/智能体)
    4. stem 兜底 (但仍加扩展名后缀保证唯一)

    'AOG保障预案20260204.md' → 'core-预案-20260204'
    'AOG保障检查单模板R2.xlsx' → 'core-checklist-r2'
    '知识库目录20260101.md' → 'core-目录-20260101'
    '知识库整理20260101.md' → 'core-整理-20260101'
    '航材AOG智能体.md' → 'core-智能体'
    """
    stem = Path(filename).stem
    ext = Path(filename).suffix.lower().lstrip(".")

    # 关键词
    keyword = ""
    if "检查单" in stem:
        keyword = "checklist"
    elif "手册" in stem:
        keyword = "manual"
    elif "目录" in stem:
        keyword = "目录"
    elif "整理" in stem:
        keyword = "整理"
    elif "导出" in stem:
        keyword = "export"
    elif "智能体" in stem:
        keyword = "智能体"
    elif "预案" in stem:
        keyword = "预案"
    else:
        keyword = "doc"

    # 日期/R 后缀
    m = re.search(r"(\d{8})", stem)
    if m:
        return f"core-{keyword}-{m.group(1)}-{ext}"
    m2 = re.search(r"R(\d+)", stem)
    if m2:
        return f"core-{keyword}-r{m2.group(1)}-{ext}"

    # 无日期: 关键词 + ext 区分 (避免 .md 和 .xlsx 撞)
    return f"core-{keyword}-{ext}"


@dataclass
class CorePlan:
    id: str
    title: str
    type: str
    content_md: str
    source_path: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def extract_core_plan(path: PathLike, knowledge_base_root: PathLike | None = None) -> CorePlan:
    """从 md/docx/xlsx 抽 CorePlan 完整字段。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")

    suffix = p.suffix.lower()
    stem = p.stem

    if suffix == ".docx":
        dt = parse_docx(p)
        content_md = docx_table_to_markdown(dt)
    elif suffix == ".doc":
        # python-docx 不支持旧 .doc
        # 尝试读 .md 伴随,或返回空 content
        md_alt = p.with_suffix(".md")
        if md_alt.exists():
            content_md = parse_md(md_alt)
        else:
            content_md = f"(.doc 旧格式无法解析, 文件: {p.name})"
    elif suffix == ".md":
        content_md = parse_md(p)
    elif suffix == ".xlsx":
        content_md = parse_xlsx(p)
    elif suffix == ".pdf":
        # v1 不索引,但 core_plan 的 pdf 有伴随 md 的可解
        md_alt = p.with_suffix(".md")
        if md_alt.exists():
            content_md = parse_md(md_alt)
        else:
            content_md = ""
    else:
        raise ValueError(f"CorePlan 不支持 .pptx 等: {p}")

    # title = 原始 stem (含日期后缀)
    title = stem

    # type 推断
    ctype = _type_from(stem)

    # id
    cid = _id_from(p.name)

    # source_path
    if knowledge_base_root:
        try:
            source_path = str(p.relative_to(knowledge_base_root))
        except ValueError:
            source_path = str(p)
    else:
        source_path = str(p)

    return CorePlan(
        id=cid,
        title=title,
        type=ctype,
        content_md=content_md,
        source_path=source_path,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

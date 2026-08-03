"""Experience publication policy for public AOG case studies."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_MIN_BODY_CHARS = 4
_PLACEHOLDER_ONLY = {"sheet1", "暂无详细内容", "该经验暂无详细内容", "内容待补", "待采编"}
_GOVERNANCE_TITLES = ("知识库导出记录", "导出记录", "索引构建记录", "同步记录")


def _normalized_text(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[#>*_`|\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _meaningful_body(content_md: str | None) -> str:
    raw = (content_md or "").strip()
    if not raw:
        return ""
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or re.match(r"^#{1,6}(?:\s+|$)", stripped):
            continue
        cleaned = _normalized_text(stripped)
        if cleaned:
            lines.append(cleaned)
    return _normalized_text(" ".join(lines))


def is_governance_record(title: str | None, summary: str | None, source_path: str | None) -> bool:
    title_value = (title or "").strip()
    source_value = (source_path or "").casefold()
    summary_value = (summary or "").strip().casefold()
    return (
        any(keyword in title_value for keyword in _GOVERNANCE_TITLES)
        or summary_value == "sheet1"
        or any(token in source_value for token in ("export", "导出", "index_stats", "sync-log"))
    )


def has_meaningful_experience_content(content_md: str | None, summary: str | None = None) -> bool:
    body = _meaningful_body(content_md)
    return bool(body and body.casefold() not in _PLACEHOLDER_ONLY and len(body) >= _MIN_BODY_CHARS)


@dataclass(frozen=True)
class ExperienceContentFlagStats:
    total: int
    contentful: int
    empty: int


def ensure_experience_content_flags(db_path: str | Path) -> ExperienceContentFlagStats:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"experience database not found: {path}")
    with sqlite3.connect(path) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='experiences'").fetchone():
            raise RuntimeError("experiences table is missing")
        columns = {row[1] for row in con.execute("PRAGMA table_info(experiences)")}
        if "has_content" not in columns:
            try:
                con.execute("ALTER TABLE experiences ADD COLUMN has_content INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
        rows = con.execute(
            "SELECT id, title, content_md, summary, source_path, has_content FROM experiences"
        ).fetchall()
        contentful = 0
        for exp_id, title, content_md, summary, source_path, stored_flag in rows:
            publishable = (
                has_meaningful_experience_content(content_md, summary)
                and not is_governance_record(title, summary, source_path)
            )
            flag = 1 if publishable else 0
            contentful += flag
            if int(stored_flag or 0) != flag:
                con.execute("UPDATE experiences SET has_content = ? WHERE id = ?", (flag, exp_id))
        con.commit()
    return ExperienceContentFlagStats(total=len(rows), contentful=contentful, empty=len(rows) - contentful)


def contentful_experience_ids(db_path: str | Path) -> set[str]:
    ensure_experience_content_flags(db_path)
    with sqlite3.connect(Path(db_path)) as con:
        return {str(row[0]) for row in con.execute("SELECT id FROM experiences WHERE has_content = 1")}


def filter_contentful_experiences(experiences: Iterable[dict], published_ids: set[str]) -> list[dict]:
    return [item for item in experiences if str(item.get("id", "")) in published_ids]

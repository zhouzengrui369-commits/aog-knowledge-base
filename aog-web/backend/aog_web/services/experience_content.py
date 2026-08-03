"""P0-1 experience content publication gate.

Empty or placeholder-only experience records must never appear in the public
experience list or detail endpoint.  The migration is deliberately idempotent
so an existing SQLite database can be upgraded safely at application startup.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_MIN_BODY_CHARS = 4
_PLACEHOLDER_ONLY = {
    "sheet1",
    "暂无详细内容",
    "该经验暂无详细内容",
    "内容待补",
    "待采编",
}


def _normalized_text(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[#>*_`|\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _meaningful_body(content_md: str | None) -> str:
    """Return cleaned non-heading body text.

    A concise checklist is publishable, but a Markdown title, empty worksheet
    marker, or internal placeholder is not.  This avoids an arbitrary document
    length threshold while still rejecting the empty shells observed in P0-1.
    """
    raw = (content_md or "").strip()
    if not raw:
        return ""

    body_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or re.match(r"^#{1,6}(?:\s+|$)", stripped):
            continue
        cleaned = _normalized_text(stripped)
        if cleaned:
            body_lines.append(cleaned)
    return _normalized_text(" ".join(body_lines))


def has_meaningful_experience_content(
    content_md: str | None, summary: str | None = None
) -> bool:
    """Return True only for experience records containing a real body."""
    del summary  # Summary alone must never publish an empty detail page.
    body = _meaningful_body(content_md)
    if not body:
        return False
    if body.casefold() in _PLACEHOLDER_ONLY:
        return False
    return len(body) >= _MIN_BODY_CHARS


@dataclass(frozen=True)
class ExperienceContentFlagStats:
    total: int
    contentful: int
    empty: int


def ensure_experience_content_flags(db_path: str | Path) -> ExperienceContentFlagStats:
    """Add/backfill ``experiences.has_content`` and return migration statistics.

    This function never fabricates content. Existing records are classified
    deterministically from ``content_md``. It is safe to call before reads;
    updates are issued only when a stored flag is stale.
    """
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"experience database not found: {path}")

    with sqlite3.connect(path) as con:
        table = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='experiences'"
        ).fetchone()
        if not table:
            raise RuntimeError("experiences table is missing")

        columns = {row[1] for row in con.execute("PRAGMA table_info(experiences)")}
        if "has_content" not in columns:
            try:
                con.execute(
                    "ALTER TABLE experiences "
                    "ADD COLUMN has_content INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError as exc:
                # Two first requests may race on a newly restored SQLite file.
                if "duplicate column" not in str(exc).lower():
                    raise

        rows = con.execute(
            "SELECT id, content_md, summary, has_content FROM experiences"
        ).fetchall()
        contentful = 0
        for exp_id, content_md, summary, stored_flag in rows:
            flag = 1 if has_meaningful_experience_content(content_md, summary) else 0
            contentful += flag
            if int(stored_flag or 0) != flag:
                con.execute(
                    "UPDATE experiences SET has_content = ? WHERE id = ?",
                    (flag, exp_id),
                )
        con.commit()

    total = len(rows)
    return ExperienceContentFlagStats(
        total=total,
        contentful=contentful,
        empty=total - contentful,
    )


def contentful_experience_ids(db_path: str | Path) -> set[str]:
    """Return the IDs explicitly marked publishable in SQLite."""
    ensure_experience_content_flags(db_path)
    with sqlite3.connect(Path(db_path)) as con:
        return {
            str(row[0])
            for row in con.execute(
                "SELECT id FROM experiences WHERE has_content = 1"
            ).fetchall()
        }


def filter_contentful_experiences(
    experiences: Iterable[dict], published_ids: set[str]
) -> list[dict]:
    """Filter decoded records using the durable database publication flag."""
    return [item for item in experiences if str(item.get("id", "")) in published_ids]

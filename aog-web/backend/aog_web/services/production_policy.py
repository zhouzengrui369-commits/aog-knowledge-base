"""Production truth and release-safety policy for AOG public surfaces."""
from __future__ import annotations

import copy
import sqlite3
from pathlib import Path
from typing import Any, Iterable

_PUBLIC_REVIEW_STATUSES = {"VERIFIED"}


def _connect(db_path: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(Path(db_path), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 10000")
    return con


def ensure_usage_schema(db_path: str | Path) -> None:
    with _connect(db_path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS city_usage (
                city_code TEXT PRIMARY KEY,
                view_count INTEGER NOT NULL DEFAULT 0,
                last_viewed_at TEXT
            )
            """
        )
        con.commit()


def increment_city_view(db_path: str | Path, city_code: str) -> int:
    ensure_usage_schema(db_path)
    with _connect(db_path) as con:
        con.execute(
            """
            INSERT INTO city_usage(city_code, view_count, last_viewed_at)
            VALUES (?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(city_code) DO UPDATE SET
                view_count = city_usage.view_count + 1,
                last_viewed_at = CURRENT_TIMESTAMP
            """,
            (city_code,),
        )
        row = con.execute(
            "SELECT view_count FROM city_usage WHERE city_code = ?", (city_code,)
        ).fetchone()
        con.commit()
    return int(row[0]) if row else 0


def city_view_count(db_path: str | Path, city_code: str) -> int:
    ensure_usage_schema(db_path)
    with _connect(db_path) as con:
        row = con.execute(
            "SELECT view_count FROM city_usage WHERE city_code = ?", (city_code,)
        ).fetchone()
    return int(row[0]) if row else 0


def city_view_counts(db_path: str | Path) -> dict[str, int]:
    ensure_usage_schema(db_path)
    with _connect(db_path) as con:
        rows = con.execute("SELECT city_code, view_count FROM city_usage").fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def _dedupe_contacts(contacts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...], str, str]] = set()
    for raw in contacts:
        if not isinstance(raw, dict):
            continue
        item = copy.deepcopy(raw)
        phones_raw = item.get("phone") or []
        phones = (
            [str(value).strip() for value in phones_raw if str(value).strip()]
            if isinstance(phones_raw, list)
            else [str(phones_raw).strip()] if str(phones_raw).strip() else []
        )
        item["phone"] = phones
        key = (
            str(item.get("org") or "").strip().casefold(),
            tuple(phones),
            str(item.get("email") or "").strip().casefold(),
            str(item.get("role") or item.get("scope") or "").strip().casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def apply_city_release_policy(city: dict[str, Any], *, view_count: int = 0) -> dict[str, Any]:
    """Apply the fail-closed public release policy to a decoded city record."""
    safe = copy.deepcopy(city)
    trust = safe.get("trust") or {}
    status = str(trust.get("review_status") or "UNVERIFIED").upper()
    trust["review_status"] = status
    safe["trust"] = trust
    safe["view_count"] = max(0, int(view_count or 0))
    safe["data_available"] = status in _PUBLIC_REVIEW_STATUSES

    contacts = _dedupe_contacts(safe.get("contacts") or [])
    if status not in _PUBLIC_REVIEW_STATUSES:
        safe["fleet"] = []
        safe["parts"] = []
        safe["contacts"] = []
        safe["warehouse"] = {"location": "[需审核]", "main": []}
        safe["logistics"] = {"rail": "[需审核]", "air": "[需审核]", "road": "[需审核]"}
        safe["content_md"] = ""
        safe["operational_notice"] = "数据未审核，禁止用于实际 AOG 处置。"
    else:
        safe["contacts"] = contacts
        safe["operational_notice"] = None
    return safe


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (name,)
    ).fetchone() is not None


def _count_where(con: sqlite3.Connection, table: str, where: str = "1=1") -> int:
    if not _table_exists(con, table):
        return 0
    return int(con.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0])


def production_stats(db_path: str | Path, *, airline_count: int = 0) -> dict[str, Any]:
    """Calculate the public statistics payload after publication flags are current."""
    ensure_usage_schema(db_path)
    # The first page loaded after a cold start may be the homepage.  Reuse the
    # same deterministic migration as the experience API so stats cannot report
    # zero merely because `/api/experiences` has not been called yet.
    try:
        from aog_web.services.experience_content import ensure_experience_content_flags

        ensure_experience_content_flags(db_path)
    except RuntimeError as exc:
        if "experiences table is missing" not in str(exc):
            raise

    with _connect(db_path) as con:
        columns = {
            str(row[1]) for row in con.execute("PRAGMA table_info(experiences)").fetchall()
        } if _table_exists(con, "experiences") else set()
        exp_where = "has_content = 1" if "has_content" in columns else (
            "TRIM(COALESCE(content_md, '')) <> '' AND LOWER(TRIM(COALESCE(content_md, ''))) <> 'sheet1'"
        )
        city_count = _count_where(con, "cities")
        mapped_city_count = _count_where(con, "cities", "TRIM(COALESCE(iata, '')) <> ''")
        experience_count = _count_where(con, "experiences", exp_where)
        core_plan_count = _count_where(con, "core_plans")
        verified_city_count = _count_where(
            con, "cities", "UPPER(COALESCE(review_status, 'UNVERIFIED')) = 'VERIFIED'"
        )
        unverified_city_count = max(0, city_count - verified_city_count)
        total_views = int(con.execute("SELECT COALESCE(SUM(view_count), 0) FROM city_usage").fetchone()[0])
        indexed_total = 0
        if _table_exists(con, "index_stats"):
            row = con.execute("SELECT indexed_total FROM index_stats WHERE id = 1").fetchone()
            indexed_total = int(row[0] or 0) if row else 0

    return {
        "cities": city_count,
        "mapped_cities": mapped_city_count,
        "experiences": experience_count,
        "core_plans": core_plan_count,
        "airlines": max(0, int(airline_count or 0)),
        "knowledge_chunks": indexed_total,
        "verified_cities": verified_city_count,
        "unverified_cities": unverified_city_count,
        "total_city_views": total_views,
        "source": "sqlite",
    }

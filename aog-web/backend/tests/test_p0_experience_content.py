"""P0-1 regression tests for empty experience suppression."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from aog_web.services.experience_content import (
    contentful_experience_ids,
    ensure_experience_content_flags,
    filter_contentful_experiences,
    has_meaningful_experience_content,
)


def _seed_experiences(db_path: Path) -> None:
    with sqlite3.connect(db_path) as con:
        con.execute(
            """
            CREATE TABLE experiences (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT,
                status TEXT,
                tags TEXT,
                summary TEXT,
                content_md TEXT,
                related_pn TEXT,
                source_path TEXT,
                updated_at TEXT
            )
            """
        )
        con.executemany(
            """
            INSERT INTO experiences
            (id, title, category, status, tags, summary, content_md,
             related_pn, source_path, updated_at)
            VALUES (?, ?, '案例', '现行', '[]', ?, ?, '[]', ?, '2026-08-03')
            """,
            [
                (
                    "exp-good-1",
                    "B787 风挡 AOG 处置",
                    "覆盖首次反馈、航材调拨、TIRE 1 与后续复盘。",
                    "## 处置背景\n飞机停场后确认件号与 MEL 限制。\n"
                    "## 操作步骤\n联系航司 desk、校验库存、形成运输方案并记录回执。",
                    "03_保障经验/B787.md",
                ),
                (
                    "exp-empty",
                    "米兰自有备件取件经验",
                    "",
                    "",
                    "03_保障经验/米兰.xlsx",
                ),
                (
                    "exp-placeholder",
                    "知识库导出记录",
                    "Sheet1",
                    "Sheet1",
                    "03_保障经验/export.xlsx",
                ),
                (
                    "exp-good-2",
                    "西安兰州跨站调拨",
                    "记录跨站调拨的联系人确认、运输时限与交接检查。",
                    "## 场景\n西安缺件时先核对兰州库存与适航状态。\n"
                    "## 验证\n双人复核件号、序号、包装和运输交接单。",
                    "03_保障经验/西安兰州.md",
                ),
                (
                    "exp-good-3",
                    "米兰公开库房取件流程",
                    "说明公开库房取件前置条件、证件与签收要求。",
                    "## 前置条件\n确认库房营业时间和取件授权。\n"
                    "## 交接\n核对包装、标签、件号、序号并留存签收记录。",
                    "03_保障经验/米兰取件.md",
                ),
            ],
        )
        con.commit()


def test_meaningful_content_classifier_rejects_empty_and_sheet_marker():
    assert has_meaningful_experience_content("") is False
    assert has_meaningful_experience_content("Sheet1", "Sheet1") is False
    assert has_meaningful_experience_content("## 标题") is False
    assert has_meaningful_experience_content(
        "## 步骤\n核对件号和序号，联系航司 desk，确认运输方案并留存签收回执。"
    ) is True


def test_migration_adds_and_backfills_has_content(tmp_path: Path):
    db_path = tmp_path / "aog.db"
    _seed_experiences(db_path)

    stats = ensure_experience_content_flags(db_path)

    assert stats.total == 5
    assert stats.contentful == 3
    assert stats.empty == 2
    with sqlite3.connect(db_path) as con:
        columns = {row[1] for row in con.execute("PRAGMA table_info(experiences)")}
        assert "has_content" in columns
        flags = dict(con.execute("SELECT id, has_content FROM experiences"))
    assert flags["exp-good-1"] == 1
    assert flags["exp-good-2"] == 1
    assert flags["exp-good-3"] == 1
    assert flags["exp-empty"] == 0
    assert flags["exp-placeholder"] == 0


def test_public_list_returns_three_contentful_experiences(tmp_path: Path):
    db_path = tmp_path / "aog.db"
    _seed_experiences(db_path)
    published_ids = contentful_experience_ids(db_path)

    decoded = [
        {"id": "exp-good-1", "title": "B787 风挡 AOG 处置"},
        {"id": "exp-empty", "title": "米兰自有备件取件经验"},
        {"id": "exp-placeholder", "title": "知识库导出记录"},
        {"id": "exp-good-2", "title": "西安兰州跨站调拨"},
        {"id": "exp-good-3", "title": "米兰公开库房取件流程"},
    ]
    visible = filter_contentful_experiences(decoded, published_ids)

    assert [item["id"] for item in visible] == [
        "exp-good-1",
        "exp-good-2",
        "exp-good-3",
    ]
    assert all(item["id"] not in {"exp-empty", "exp-placeholder"} for item in visible)

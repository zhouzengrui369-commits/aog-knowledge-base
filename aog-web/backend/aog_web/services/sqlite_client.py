"""SQLite 元数据客户端 - 异步 SQLAlchemy 2.0

3 张表: cities / experiences / core_plans
- 与 CONTRACT §1 数据模型 1:1 (字段名一致, 复杂结构 JSON 序列化)
- 启动时建表 (idempotent)
- 提供 list / get / search 基础查询
- 元数据由 Wave 1 T3 pipeline 写入, 后端只读
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from aog_web.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class CityRow(Base):
    """镜像 T3 pipeline 实际写的 schema（CONTRACT §1.1 1:1，独立列） + P0-5 数据可信度 9 字段"""
    __tablename__ = "cities"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    airport: Mapped[str] = mapped_column(String, default="")
    iata: Mapped[str] = mapped_column(String, default="")
    pinyin: Mapped[str] = mapped_column(String, default="", index=True)
    region: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    # JSON 序列化字段
    tags: Mapped[str] = mapped_column(Text, default="[]")
    fleet: Mapped[str] = mapped_column(Text, default="[]")
    parts: Mapped[str] = mapped_column(Text, default="[]")
    contacts: Mapped[str] = mapped_column(Text, default="[]")
    warehouse: Mapped[str] = mapped_column(Text, default="{}")
    logistics: Mapped[str] = mapped_column(Text, default="{}")
    content_md: Mapped[str] = mapped_column(Text, default="")
    source_path: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # ★ P0-5: 数据可信度 9 字段 (D-044-D, Owner 7/29 授权)
    # 1. source_document
    source_document: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # 2. source_location
    source_location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # 3. source_version
    source_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # 4. updated_at (上面已有, 复用)
    # 5. reviewed_at
    reviewed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # 6. reviewed_by
    reviewed_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # 7. review_status (default UNVERIFIED, 6 状态枚举见 city.py)
    review_status: Mapped[str] = mapped_column(String, default="UNVERIFIED")
    # 8. confidence (0.0-1.0, default None)
    confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    # 9. environment (dev/staging/production/all)
    environment: Mapped[str] = mapped_column(String, default="all")
    # 10. pii_classification (none/internal/confidential/restricted)
    pii_classification: Mapped[str] = mapped_column(String, default="none")


class ExperienceRow(Base):
    """镜像 T3 pipeline 实际写的 schema（CONTRACT §1.2 1:1）"""
    __tablename__ = "experiences"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, index=True)
    category: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True, default="现行")
    # JSON 序列化字段
    tags: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str] = mapped_column(Text, default="")
    content_md: Mapped[str] = mapped_column(Text, default="")
    related_pn: Mapped[str] = mapped_column(Text, default="[]")
    source_path: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class CorePlanRow(Base):
    """镜像 T3 pipeline 实际写的 schema（CONTRACT §1.3 1:1）"""
    __tablename__ = "core_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String, index=True)
    content_md: Mapped[str] = mapped_column(Text, default="")
    source_path: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class IndexStatsRow(Base):
    """index_stats.json 的 DB 镜像 (id=1 单行)"""

    __tablename__ = "index_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_sync: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    indexed_total: Mapped[int] = mapped_column(Integer, default=0)
    queue: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="idle")
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class SQLiteClient:
    """异步 SQLite 客户端 - 单例"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        # aiosqlite + SQLite 内存/D盘
        url = f"sqlite+aiosqlite:///{db_path}"
        self.engine: AsyncEngine = create_async_engine(
            url,
            echo=False,
            future=True,
        )
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False
        )

    async def init(self) -> None:
        """启动时调用: 建表 (idempotent) + P0-5 数据可信度 9 列 ALTER"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # ★ P0-5: ALTER TABLE 加 9 字段 (旧 aog.db 7/26 没这些列)
        # 旧数据: review_status='UNVERIFIED', 其他 trust 字段 NULL
        # ALTER 重复会报 "duplicate column name" → 捕获 (idempotent)
        _P05_CITY_COLUMNS = [
            "source_document TEXT",
            "source_location TEXT",
            "source_version TEXT",
            "reviewed_at TEXT",
            "reviewed_by TEXT",
            "review_status TEXT DEFAULT 'UNVERIFIED'",
            "confidence REAL",
            "environment TEXT DEFAULT 'all'",
            "pii_classification TEXT DEFAULT 'none'",
        ]
        async with self.engine.begin() as conn:
            for col_def in _P05_CITY_COLUMNS:
                col_name = col_def.split()[0]
                try:
                    await conn.execute(text(f"ALTER TABLE cities ADD COLUMN {col_def}"))
                    logger.info("P0-5 migration: cities.{} added", col_name)
                except Exception as e:
                    # 重复列 (已有) → 静默 skip
                    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                        pass
                    else:
                        logger.warning("P0-5 migration cities.{} failed: {}", col_name, e)

        # 确保 index_stats 单行
        async with self.session_factory() as session:
            existing = await session.get(IndexStatsRow, 1)
            if existing is None:
                session.add(IndexStatsRow(id=1))
                await session.commit()
        logger.info("SQLite initialized: %s (P0-5 9 columns ensured)", self.db_path)

    async def close(self) -> None:
        await self.engine.dispose()

    # ============ Cities ============

    async def list_cities(
        self,
        region: Optional[str] = None,
        status: Optional[str] = None,
        letter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按 pinyin 排序的城市列表 (支持筛选)"""
        async with self.session_factory() as session:
            stmt = select(CityRow)
            if region:
                stmt = stmt.where(CityRow.region == region)
            if status:
                stmt = stmt.where(CityRow.status == status)
            stmt = stmt.order_by(CityRow.pinyin.asc())
            rows = (await session.execute(stmt)).scalars().all()
            out = []
            for r in rows:
                if letter and r.pinyin and r.pinyin[0].upper() != letter.upper():
                    continue
                out.append(_decode_city(r))
            return out

    async def get_city(self, code: str) -> Optional[Dict[str, Any]]:
        async with self.session_factory() as session:
            row = await session.get(CityRow, code)
            return _decode_city(row) if row else None

    async def count_cities(self) -> int:
        async with self.session_factory() as session:
            from sqlalchemy import func
            stmt = select(func.count(CityRow.code))
            return (await session.execute(stmt)).scalar_one()

    # ============ Experiences ============

    async def list_experiences(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        q: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        async with self.session_factory() as session:
            stmt = select(ExperienceRow)
            if category:
                stmt = stmt.where(ExperienceRow.category == category)
            if status:
                stmt = stmt.where(ExperienceRow.status == status)
            stmt = stmt.order_by(ExperienceRow.updated_at.desc())
            rows = (await session.execute(stmt)).scalars().all()
            out = []
            for r in rows:
                d = _decode_experience(r)
                if q:
                    q_lower = q.lower()
                    haystack = (d.get("title", "") + " " + d.get("summary", "") + " " + d.get("content_md", "")).lower()
                    if q_lower not in haystack:
                        continue
                out.append(d)
            return out

    async def get_experience(self, exp_id: str) -> Optional[Dict[str, Any]]:
        async with self.session_factory() as session:
            row = await session.get(ExperienceRow, exp_id)
            return _decode_experience(row) if row else None

    async def count_experiences(self) -> int:
        async with self.session_factory() as session:
            from sqlalchemy import func
            stmt = select(func.count(ExperienceRow.id))
            return (await session.execute(stmt)).scalar_one()

    # ============ Core Plans ============

    async def list_core_plans(self) -> List[Dict[str, Any]]:
        async with self.session_factory() as session:
            stmt = select(CorePlanRow).order_by(CorePlanRow.updated_at.desc())
            rows = (await session.execute(stmt)).scalars().all()
            return [_decode_core_plan(r) for r in rows]

    async def get_core_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        async with self.session_factory() as session:
            row = await session.get(CorePlanRow, plan_id)
            return _decode_core_plan(row) if row else None

    async def count_core_plans(self) -> int:
        async with self.session_factory() as session:
            from sqlalchemy import func
            stmt = select(func.count(CorePlanRow.id))
            return (await session.execute(stmt)).scalar_one()

    # ============ Index Stats ============

    async def get_index_stats(self) -> Dict[str, Any]:
        async with self.session_factory() as session:
            row = await session.get(IndexStatsRow, 1)
            if not row:
                return {"status": "idle", "last_sync": None, "queue": 0, "indexed_total": 0, "last_error": None}
            return {
                "status": row.status or "idle",
                "last_sync": row.last_sync,
                "queue": row.queue or 0,
                "indexed_total": row.indexed_total or 0,
                "last_error": row.last_error,
            }

    async def update_index_stats(self, **kwargs: Any) -> None:
        async with self.session_factory() as session:
            row = await session.get(IndexStatsRow, 1)
            if row is None:
                row = IndexStatsRow(id=1)
                session.add(row)
            for k, v in kwargs.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            await session.commit()


# ============ Decode helpers ============


def _classify_contact_permission(contact: dict) -> str:
    """D-052 fail-closed permission 分类 (NJX 7/31 拍板).

    ★ 严禁默认 public (历史 D-030 bug: missing → public 导致 phone leak)
    返回:
      - "public"    : 显式 permission=public + redacted=False
      - "restricted": missing/empty/unknown/internal/restricted/private/redacted=True
                      (全部 fail-closed 视为受限)
    """
    if not contact or not isinstance(contact, dict):
        return "restricted"
    if bool(contact.get("redacted")) is True:
        return "restricted"  # redacted=True 强制受限
    permission_raw = contact.get("permission")
    if not isinstance(permission_raw, str):
        return "restricted"
    permission = permission_raw.strip().lower()
    if permission == "public":
        return "public"
    return "restricted"


def _decode_city(row: CityRow) -> Dict[str, Any]:
    """T3 schema: 所有复杂字段独立列 + JSON 序列化（tags/fleet/parts/contacts/warehouse/logistics） + P0-5 9 字段 + P0-6 REDACTED + D-052 fail-closed"""
    def _j(s: str, default):
        if not s:
            return default
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return default

    # ★ P0-6 + D-052 (NJX 7/31 拍板): contact 脱敏 fail-closed
    # D-052 严令 3: internal/restricted/missing/empty/unknown/redacted 全部 REDACTED
    #   public 保留 phone/email 原值
    # 严禁: 任何隐式 default = public (历史 D-030 bug: missing → public)
    raw_contacts = _j(row.contacts, [])
    decoded_contacts = []
    for c in raw_contacts:
        if not isinstance(c, dict):
            decoded_contacts.append(c)
            continue
        c_copy = dict(c)
        perm_class = _classify_contact_permission(c_copy)
        if perm_class != "public":
            # D-052: non-public (含 missing/empty/unknown/internal/restricted) 全部 REDACTED
            c_copy["phone"] = ["REDACTED"] if c_copy.get("phone") else []
            if c_copy.get("email"):
                c_copy["email"] = "REDACTED"
            # D-052: role/scope 自由文本字段也 REDACTED (避免 PII 通过描述字段泄漏到 API)
            if c_copy.get("role"):
                c_copy["role"] = "[已脱敏/受限]"
            if c_copy.get("scope"):
                c_copy["scope"] = "[已脱敏/受限]"
        decoded_contacts.append(c_copy)

    return {
        "code": row.code,
        "name": row.name,
        "airport": row.airport or "",
        "iata": row.iata or "",
        "pinyin": row.pinyin or "",
        "region": row.region or "",
        "status": row.status or "",
        "tags": _j(row.tags, []),
        "fleet": _j(row.fleet, []),
        "parts": _j(row.parts, []),
        "contacts": decoded_contacts,  # P0-6 REDACTED 兜底
        "warehouse": _j(row.warehouse, {"location": "", "main": []}),
        "logistics": _j(row.logistics, {"rail": "", "air": "", "road": ""}),
        "content_md": row.content_md or "",
        "source_path": row.source_path or "",
        "updated_at": row.updated_at or "",
        # ★ P0-5: 数据可信度 9 字段 (D-044-D, Owner 7/29 授权)
        "trust": {
            "source_document": row.source_document,
            "source_location": row.source_location,
            "source_version": row.source_version,
            "updated_at": row.updated_at,
            "reviewed_at": row.reviewed_at,
            "reviewed_by": row.reviewed_by,
            "review_status": row.review_status or "UNVERIFIED",
            "confidence": row.confidence,
            "environment": row.environment or "all",
            "pii_classification": row.pii_classification or "none",
        },
    }


def _decode_experience(row: ExperienceRow) -> Dict[str, Any]:
    """T3 schema: 独立列（tags/summary/content_md/related_pn 都是列，tags/related_pn JSON）"""
    def _j(s: str, default):
        if not s:
            return default
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return default
    return {
        "id": row.id,
        "title": row.title,
        "category": row.category or "",
        "status": row.status or "",
        "tags": _j(row.tags, []),
        "summary": row.summary or "",
        "content_md": row.content_md or "",
        "related_pn": _j(row.related_pn, []),
        "source_path": row.source_path or "",
        "updated_at": row.updated_at or "",
    }


def _decode_core_plan(row: CorePlanRow) -> Dict[str, Any]:
    """T3 schema: 独立列（content_md/source_path）"""
    return {
        "id": row.id,
        "title": row.title,
        "type": row.type or "",
        "content_md": row.content_md or "",
        "source_path": row.source_path or "",
        "updated_at": row.updated_at or "",
    }


# ============ Singleton ============

_client: Optional[SQLiteClient] = None


def get_sqlite_client() -> SQLiteClient:
    """获取 SQLite 客户端单例"""
    global _client
    if _client is None:
        s = get_settings()
        _client = SQLiteClient(s.sqlite_path)
    return _client


def reset_sqlite_client() -> None:
    """测试 helper"""
    global _client
    _client = None

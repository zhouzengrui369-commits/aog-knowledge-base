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

from sqlalchemy import Column, DateTime, Integer, String, Text, select
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
    __tablename__ = "cities"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    region: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    iata: Mapped[str] = mapped_column(String, default="")
    pinyin: Mapped[str] = mapped_column(String, default="", index=True)
    # JSON 序列化字段
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExperienceRow(Base):
    __tablename__ = "experiences"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, index=True)
    category: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True, default="现行")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CorePlanRow(Base):
    __tablename__ = "core_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String, index=True)
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
        """启动时调用: 建表 (idempotent)"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # 确保 index_stats 单行
        async with self.session_factory() as session:
            existing = await session.get(IndexStatsRow, 1)
            if existing is None:
                session.add(IndexStatsRow(id=1))
                await session.commit()
        logger.info("SQLite initialized: %s", self.db_path)

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


def _decode_city(row: CityRow) -> Dict[str, Any]:
    try:
        data = json.loads(row.data_json or "{}")
    except json.JSONDecodeError:
        data = {}
    # 主键 + 索引字段从 data 取, 索引字段回填
    return {
        "code": row.code,
        "name": row.name,
        "iata": row.iata or data.get("iata", ""),
        "pinyin": row.pinyin or data.get("pinyin", ""),
        "region": row.region,
        "status": row.status,
        "tags": data.get("tags", []),
        "fleet": data.get("fleet", []),
        "parts": data.get("parts", []),
        "contacts": data.get("contacts", []),
        "warehouse": data.get("warehouse", {"location": "", "main": []}),
        "logistics": data.get("logistics", {"rail": "", "air": "", "road": ""}),
        "content_md": data.get("content_md", ""),
        "source_path": data.get("source_path", ""),
        "updated_at": data.get("updated_at", row.updated_at.isoformat() if row.updated_at else ""),
    }


def _decode_experience(row: ExperienceRow) -> Dict[str, Any]:
    try:
        data = json.loads(row.data_json or "{}")
    except json.JSONDecodeError:
        data = {}
    return {
        "id": row.id,
        "title": row.title,
        "category": row.category,
        "status": row.status,
        "tags": data.get("tags", []),
        "summary": data.get("summary", ""),
        "content_md": data.get("content_md", ""),
        "related_pn": data.get("related_pn", []),
        "source_path": data.get("source_path", ""),
        "updated_at": data.get("updated_at", row.updated_at.isoformat() if row.updated_at else ""),
    }


def _decode_core_plan(row: CorePlanRow) -> Dict[str, Any]:
    try:
        data = json.loads(row.data_json or "{}")
    except json.JSONDecodeError:
        data = {}
    return {
        "id": row.id,
        "title": row.title,
        "type": row.type,
        "content_md": data.get("content_md", ""),
        "source_path": data.get("source_path", ""),
        "updated_at": data.get("updated_at", row.updated_at.isoformat() if row.updated_at else ""),
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

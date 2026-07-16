"""pytest fixtures - 隔离的临时 DB + 临时 Chroma + TestClient"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# 必须在 import aog_web 前设置环境变量, 避免 settings 缓存读到真实路径
TEST_ROOT = Path(tempfile.mkdtemp(prefix="aog_web_test_"))


@pytest.fixture(scope="session", autouse=True)
def _test_env():
    """为整个 test session 设置隔离环境变量"""
    test_data = TEST_ROOT / "data"
    test_data.mkdir(parents=True, exist_ok=True)
    (test_data / "chroma").mkdir(parents=True, exist_ok=True)

    os.environ["CHROMA_PATH"] = str(test_data / "chroma")
    os.environ["SQLITE_PATH"] = str(test_data / "test.db")
    os.environ["MINIMAX_API_KEY"] = ""  # 强制 Mock 模式
    os.environ["CORS_ALLOW_ORIGINS"] = "http://localhost:3000,http://test"
    os.environ["KNOWLEDGE_BASE_PATH"] = str(TEST_ROOT / "kb")
    os.environ["RAW_PATH"] = str(TEST_ROOT / "raw")
    os.environ["SYNC_ENABLED"] = "false"  # T6: 测试期间不启动后台 poll, 避免 subprocess
    os.environ["SYNC_STATE_DB_PATH"] = str(test_data / "sync_state.db")
    (TEST_ROOT / "kb").mkdir(parents=True, exist_ok=True)
    (TEST_ROOT / "raw").mkdir(parents=True, exist_ok=True)

    yield

    # 清理
    try:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
    except Exception:
        pass


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """提供 AsyncClient - 触发 FastAPI lifespan, 用真实 ASGI in-process"""
    # 重置所有单例 (避免上一个 test 残留)
    from aog_web.config import reset_settings_cache
    from aog_web.services.chroma_client import reset_chroma_client
    from aog_web.services.sqlite_client import reset_sqlite_client
    from aog_web.services.sync import reset_sync_service

    reset_settings_cache()
    reset_chroma_client()
    reset_sqlite_client()
    reset_sync_service()

    # 重新加载 .env 读取 (确保走 test env vars)
    # 关键: 必须在 import app 之前 reset
    from aog_web.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            yield ac


@pytest_asyncio.fixture
async def seeded_sqlite():
    """在测试 SQLite 里塞一份样例数据 (city/exp/core_plan)"""
    from aog_web.config import get_settings
    from aog_web.services.sqlite_client import get_sqlite_client

    s = get_settings()
    # 重新生成 DB 文件 - 用 fixture 自己的 sqlite
    db_path = s.sqlite_path
    if db_path.exists():
        db_path.unlink()

    # 重置单例
    from aog_web.services.sqlite_client import reset_sqlite_client
    reset_sqlite_client()
    sqlite = get_sqlite_client()
    await sqlite.init()

    # 写测试数据
    from datetime import datetime

    from aog_web.services.sqlite_client import (
        CityRow,
        CorePlanRow,
        ExperienceRow,
    )

    async with sqlite.session_factory() as session:
        # city
        session.add(CityRow(
            code="B-北京大兴",
            name="北京大兴",
            airport="北京大兴国际机场",
            region="华北",
            status="现行",
            iata="PKX",
            pinyin="beijingdaxing",
            tags='["AOG预案","国际枢纽"]',
            fleet='[{"model":"B787","short_stay":false,"after":false}]',
            parts='[{"pn":"C20649000","name":"B787 主轮","stock":0,"unit":"个"}]',
            contacts='[{"org":"东航","phone":["021-22379771"],"role":"7×24"}]',
            warehouse='{"location":"北京大兴东航机务区","main":["B787 主轮"]}',
            logistics='{"rail":"京沪高铁","air":"国内 6h","road":"京津冀 4h"}',
            content_md="# 北京大兴\n\n国际枢纽...",
            source_path="02_外战预案/B-北京大兴.md",
            updated_at=datetime.utcnow().isoformat(),
        ))
        session.add(CityRow(
            code="S-上海浦东",
            name="上海浦东",
            airport="上海浦东国际机场",
            region="华东",
            status="现行",
            iata="PVG",
            pinyin="shanghaipudong",
            tags='["AOG预案","国内最大"]',
            fleet="[]",
            parts="[]",
            contacts="[]",
            warehouse='{"location":"浦东东航机务","main":[]}',
            logistics='{"rail":"沪宁","air":"4h","road":"长三角"}',
            content_md="# 上海浦东\n\n国内最大...",
            source_path="02_外战预案/S-上海浦东.md",
            updated_at=datetime.utcnow().isoformat(),
        ))
        session.add(CityRow(
            code="B-包头",
            name="包头",
            airport="包头机场",
            region="华北",
            status="暂停",
            iata="BAV",
            pinyin="baotou",
            tags="[]",
            fleet="[]",
            parts="[]",
            contacts="[]",
            warehouse='{"location":"","main":[]}',
            logistics='{"rail":"","air":"","road":""}',
            content_md="包头暂停",
            source_path="02_外战预案/B-包头.md",
            updated_at=datetime.utcnow().isoformat(),
        ))

        # experience
        session.add(ExperienceRow(
            id="exp-001",
            title="B787 风挡 AOG 处理流程",
            category="案例",
            status="现行",
            tags='["B787","风挡","案例"]',
            summary="B787 风挡 AOG 标准流程",
            content_md="# B787 风挡\n\n流程内容...",
            related_pn="[]",
            source_path="03_保障经验/exp-001.md",
            updated_at=datetime.utcnow().isoformat(),
        ))
        session.add(ExperienceRow(
            id="exp-002",
            title="BMS9-3 玻璃纤维布保障经验",
            category="案例",
            status="现行",
            tags='["BMS9-3","玻璃纤维布"]',
            summary="BMS9-3 储存与施工经验",
            content_md="# BMS9-3\n\n储存方法...",
            related_pn='["BMS9-3"]',
            source_path="03_保障经验/exp-002.md",
            updated_at=datetime.utcnow().isoformat(),
        ))

        # core plan
        session.add(CorePlanRow(
            id="core-20260204",
            title="AOG 保障预案 2026-02-04",
            type="master",
            content_md="# 核心预案\n\n主预案...",
            source_path="01_AOG预案/2026-02-04.md",
            updated_at=datetime.utcnow().isoformat(),
        ))

        await session.commit()

    yield sqlite

    # 清理
    reset_sqlite_client()
    if db_path.exists():
        db_path.unlink()

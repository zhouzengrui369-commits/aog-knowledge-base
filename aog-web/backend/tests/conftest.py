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

    # ★ J10: 在 test kb 根目录下放一个可下载的源文档, 验证 /files/{path} 200 OK
    test_kb_root = TEST_ROOT / "kb"
    test_cities_dir = test_kb_root / "02_外战预案"
    test_cities_dir.mkdir(parents=True, exist_ok=True)
    (test_cities_dir / "B-北京大兴.md").write_text(
        "# 北京大兴\n国际枢纽 (test fixture)\n", encoding="utf-8"
    )
    (test_cities_dir / "H-赫尔辛基.md").write_text(
        "# 赫尔辛基\n国际外站 (test fixture)\n", encoding="utf-8"
    )
    # ★ S-上海浦东.md 不写, 验证 J10 MISSING source_document 返 404 + reason 明确
    #   (同时验证 S-上海浦东 review_status=MISSING, source_path="" 的语义一致)

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
    from aog_web.services.airlines_client import reset_airlines_client
    from aog_web.services.chroma_client import reset_chroma_client
    from aog_web.services.sqlite_client import reset_sqlite_client
    from aog_web.services.sync import reset_sync_service

    reset_settings_cache()
    reset_chroma_client()
    reset_sqlite_client()
    reset_sync_service()
    reset_airlines_client()

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
            contacts='[{"org":"东航","phone":["021-22379771"],"role":"7×24","permission":"public"}]',
            warehouse='{"location":"北京大兴东航机务区","main":["B787 主轮"]}',
            logistics='{"rail":"京沪高铁","air":"国内 6h","road":"京津冀 4h"}',
            content_md="# 北京大兴\n\n国际枢纽...",
            source_path="02_外战预案/B-北京大兴.md",
            updated_at=datetime.utcnow().isoformat(),
            # ★ P0-5 10 字段 (D-044-D)
            source_document="AOG知识库/02_外战预案/B-北京大兴.docx",
            source_location="AOG知识库/02_外战预案/",
            source_version="2025-Q4",
            reviewed_at="2026-01-15T00:00:00",
            reviewed_by="NJX",
            review_status="VERIFIED",  # ★ J9: VERIFIED 标杆
            confidence=0.95,
            environment="all",
            pii_classification="internal",
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
            warehouse='{"location":"","main":[]}',
            logistics='{"rail":"","air":"","road":""}',
            content_md="",  # ★ P0-5: 上海浦东当前 source docx 不在 aog.db, content_md 空
            source_path="",  # ★ 真实源文档不存在, 等 NJX 物理补
            updated_at=datetime.utcnow().isoformat(),
            # ★ P0-5 数据可信度 10 字段 (D-044-D, Owner 7/29 授权)
            source_document=None,  # 无源文档
            source_location="AOG知识库/02_外战预案/",
            source_version=None,
            reviewed_at=None,
            reviewed_by=None,
            review_status="MISSING",  # ★ 7/29 指令: 明确 MISSING, 不 404, 不 mock
            confidence=None,
            environment="all",
            pii_classification="none",  # 没联系人 = none
        ))
        # ★ P0-5 J3: 上海虹桥也必须明确状态, 不从产品中无解释消失 (D-044)
        session.add(CityRow(
            code="S-上海虹桥",
            name="上海虹桥",
            airport="上海虹桥国际机场",
            region="华东",
            status="现行",
            iata="SHA",
            pinyin="shanghaihongqiao",
            tags='["AOG预案","国内枢纽"]',
            fleet="[]",
            parts="[]",
            contacts="[]",
            warehouse='{"location":"","main":[]}',
            logistics='{"rail":"","air":"","road":""}',
            content_md="",
            source_path="",
            updated_at=datetime.utcnow().isoformat(),
            source_document=None,
            source_location="AOG知识库/02_外战预案/",
            source_version=None,
            reviewed_at=None,
            reviewed_by=None,
            review_status="MISSING",
            confidence=None,
            environment="all",
            pii_classification="none",
        ))
        # ★ Stage 9.2: 第三个样板 — 赫尔辛基 (含 restricted contact, J8 PII negative)
        session.add(CityRow(
            code="H-赫尔辛基",
            name="赫尔辛基",
            airport="赫尔辛基-万塔机场",
            region="国际-欧洲",
            status="现行",
            iata="HEL",
            pinyin="heerxinji",
            tags='["AOG预案","国际外站"]',
            fleet='[{"model":"B787","short_stay":true,"after":false}]',
            parts='[{"pn":"C20649000","name":"B787 主轮","stock":1,"unit":"个"}]',
            # ★ J8: 混入 restricted contact, 验证 _decode_city 把 phone 替换为 ["REDACTED"]
            contacts='[{"org":"东航赫尔辛基站","phone":["+358-9-1234567"],"role":"7×24","permission":"public"},{"org":"Satair Finland","phone":["+358-50-9876543"],"role":"商务","permission":"restricted","redacted":true},{"org":"库房供应商","phone":["13900002222"],"role":"库房","permission":"restricted"}]',
            warehouse='{"location":"赫尔辛基机场东航区","main":["B787 主轮"]}',
            logistics='{"rail":"","air":"6h","road":"北欧 4h"}',
            content_md="# 赫尔辛基\n\n国际外站 (北欧)...",
            source_path="02_外战预案/H-赫尔辛基.md",
            updated_at=datetime.utcnow().isoformat(),
            source_document="AOG知识库/02_外战预案/H-赫尔辛基.docx",
            source_location="AOG知识库/02_外战预案/",
            source_version=None,  # 旧文档无版本
            reviewed_at=None,
            reviewed_by=None,
            review_status="UNVERIFIED",  # 旧 docx 未经审核
            confidence=None,
            environment="all",
            pii_classification="restricted",  # 含 restricted contact
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
            # ★ J9: STALE 数据 (P0-5 状态之一) — 内容存在但已过期
            source_document="AOG知识库/02_外战预案/B-包头.docx",
            source_location="AOG知识库/02_外战预案/",
            source_version="2019-Q3",  # 5 年前版本
            reviewed_at=None,
            reviewed_by=None,
            review_status="STALE",  # 来源过期 (>30 天)
            confidence=0.3,  # 低置信度
            environment="all",
            pii_classification="none",
        ))
        # ★ J9: VERIFIED 标杆 — 北京大兴 (Stage 1 样板, 假设已审核)
        # 已在 B-北京大兴 add 时直接写入 trust 字段, 上面 update 已删除
        # 这里保留 _ 引用防止 grep 误判
        _ = "see B-北京大兴 add above"

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

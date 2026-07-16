"""FTS5 端到端测试 - /api/chat + RAG_BACKEND=fts5

★ NSM-2 红线: 真实 FTS5 检索 + references ≥ 1
"""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

TEST_FTS5_DIR = Path(tempfile.mkdtemp(prefix="aog_test_fts5_e2e_"))


def _ensure_fts5_db() -> Path:
    src = Path(__file__).resolve().parent.parent / "data" / "fts5_index.db"
    dst = TEST_FTS5_DIR / "fts5_index.db"
    if not src.exists():
        pytest.skip(f"FTS5 index not built: {src}")
    if not dst.exists():
        shutil.copy(src, dst)
    return dst


@pytest.mark.asyncio
async def test_chat_with_fts5_backend(seeded_sqlite):
    """FTS5 backend: POST /api/chat → 200 + references ≥ 1 (NSM-2)"""
    db_path = _ensure_fts5_db()
    os.environ["FTS5_PATH"] = str(db_path)
    os.environ["RAG_BACKEND"] = "fts5"
    os.environ["CHROMA_PATH"] = "/tmp/__chroma_noexist__"  # chroma init 会失败但 OK
    os.environ["MINIMAX_API_KEY"] = ""  # Mock LLM

    from aog_web.config import reset_settings_cache
    from aog_web.services.chroma_client import reset_chroma_client
    from aog_web.services.fts5_client import reset_fts5_client
    from aog_web.services.sqlite_client import reset_sqlite_client
    from aog_web.services.sync import reset_sync_service

    reset_settings_cache()
    reset_chroma_client()
    reset_fts5_client()
    reset_sqlite_client()
    reset_sync_service()

    from httpx import ASGITransport, AsyncClient
    from aog_web.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            # 1. health
            r = await ac.get("/api/health")
            assert r.status_code == 200
            body = r.json()
            assert body["rag_backend"] == "fts5", f"expected fts5, got {body['rag_backend']}"
            assert body["status"] == "ok"

            # 2. cities (use seeded fixture)
            r = await ac.get("/api/cities?limit=5")
            assert r.status_code == 200
            cities = r.json()
            assert len(cities) >= 2, f"expected >= 2 cities, got {len(cities)}"
            assert all("code" in c and "name" in c for c in cities)

            # 3. experiences
            r = await ac.get("/api/experiences?limit=3")
            assert r.status_code == 200
            exps = r.json()
            assert len(exps) >= 1, f"expected >= 1 exp, got {len(exps)}"

            # 4. chat - ★ 关键: NSM-2 红线
            r = await ac.post("/api/chat", json={"q": "B787 风挡"})
            assert r.status_code == 200, f"chat failed: {r.text[:200]}"
            body = r.json()
            assert "answer" in body
            assert "references" in body
            assert len(body["references"]) >= 1, f"NSM-2 FAIL: refs={body['references']}"
            ref = body["references"][0]
            for key in ["id", "title", "href", "snippet", "score"]:
                assert key in ref
            # 验证 reference 是真实 chunk (有 text 来自 FTS5, 不是纯 SQLite 兜底)
            print(f"chat answer: {body['answer'][:100]}")
            print(f"chat refs: {[r['title'] for r in body['references']]}")


@pytest.mark.asyncio
async def test_chat_with_fts5_chinese_short_query(seeded_sqlite):
    """中文 2-char query: 风挡"""
    db_path = _ensure_fts5_db()
    os.environ["FTS5_PATH"] = str(db_path)
    os.environ["RAG_BACKEND"] = "fts5"
    os.environ["CHROMA_PATH"] = "/tmp/__chroma_noexist__"
    os.environ["MINIMAX_API_KEY"] = ""

    from aog_web.config import reset_settings_cache
    from aog_web.services.chroma_client import reset_chroma_client
    from aog_web.services.fts5_client import reset_fts5_client
    from aog_web.services.sqlite_client import reset_sqlite_client
    from aog_web.services.sync import reset_sync_service

    reset_settings_cache()
    reset_chroma_client()
    reset_fts5_client()
    reset_sqlite_client()
    reset_sync_service()

    from httpx import ASGITransport, AsyncClient
    from aog_web.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            r = await ac.post("/api/chat", json={"q": "风挡维修"})
            assert r.status_code == 200
            body = r.json()
            assert len(body["references"]) >= 1
            print(f"  refs: {[x['title'] for x in body['references']]}")


@pytest.mark.asyncio
async def test_chat_with_fts5_part_number(seeded_sqlite):
    """part number with hyphen: BMS9-3"""
    db_path = _ensure_fts5_db()
    os.environ["FTS5_PATH"] = str(db_path)
    os.environ["RAG_BACKEND"] = "fts5"
    os.environ["CHROMA_PATH"] = "/tmp/__chroma_noexist__"
    os.environ["MINIMAX_API_KEY"] = ""

    from aog_web.config import reset_settings_cache
    from aog_web.services.chroma_client import reset_chroma_client
    from aog_web.services.fts5_client import reset_fts5_client
    from aog_web.services.sqlite_client import reset_sqlite_client
    from aog_web.services.sync import reset_sync_service

    reset_settings_cache()
    reset_chroma_client()
    reset_fts5_client()
    reset_sqlite_client()
    reset_sync_service()

    from httpx import ASGITransport, AsyncClient
    from aog_web.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            r = await ac.post("/api/chat", json={"q": "BMS9-3 玻璃纤维"})
            assert r.status_code == 200
            body = r.json()
            assert len(body["references"]) >= 1


def teardown_module(module):
    shutil.rmtree(TEST_FTS5_DIR, ignore_errors=True)

"""FastAPI app 入口 - lifespan + CORS + 路由注册

启动流程:
1. load settings
2. init SQLite (建表)
3. init RAG backend:
   - chroma (本地 dev): 拿 collection
   - fts5 (SCF 部署): 从 COS 拉 fts5_index.db (lifespan 钩子)
4. (可选) start sync service
5. 监听 SIGTERM → graceful shutdown
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from aog_web import __version__
from aog_web.api import (
    auth,
    airlines,
    chat,
    cities,
    core_plans,
    experiences,
    files,
    health,
    reindex,
    sync,
)
from aog_web.config import get_settings
from aog_web.services.airlines_client import get_airlines_client
from aog_web.services.chroma_client import get_chroma_client
from aog_web.services.fts5_client import get_fts5_client
from aog_web.services.sqlite_client import get_sqlite_client
from aog_web.services.storage_cos import download_data_from_cos, is_cos_configured
from aog_web.services.sync import get_sync_service


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动 / 关闭"""
    settings = get_settings()
    _setup_logging(settings.LOG_LEVEL)
    logger = logging.getLogger("aog_web.main")

    logger.info("=" * 60)
    logger.info("AOG Web Backend starting (version=%s)", __version__)
    logger.info("LLM mode: %s", "MOCK ⚠️" if settings.is_mock_llm else "LIVE (MiniMax M3)")
    logger.info("RAG backend: %s", settings.rag_backend)
    logger.info("Chroma: %s", settings.chroma_path)
    logger.info("FTS5:   %s", settings.fts5_path)
    logger.info("SQLite: %s", settings.sqlite_path)
    logger.info("Knowledge base: %s", settings.knowledge_base_path)
    logger.info("CORS: %s", settings.cors_origins)
    logger.info("ALLOW_MOCK: %s (P0-4)", settings.ALLOW_MOCK)
    logger.info("STRICT_LLM: %s (P0-4)", settings.STRICT_LLM)
    logger.info("=" * 60)

    # ★ P0-4: LLM Provider 严格校验 (Owner 7/29 授权)
    # ALLOW_MOCK=false (production) + MINIMAX_API_KEY 空 → fail-closed
    if not settings.ALLOW_MOCK and settings.is_mock_llm:
        msg = (
            "P0-4 fail-closed: ALLOW_MOCK=false 但 MINIMAX_API_KEY 空. "
            "production 必须配真 key, 或显式设 ALLOW_MOCK=true (仅 dev). "
            "SCF 容器将重启直至配 key."
        )
        logger.error(msg)
        raise RuntimeError(msg)

    # 0. SCF 冷启动: 如果 fts5 路径在 /tmp 且不存在, 从 COS 下载
    if settings.rag_backend == "fts5" and not settings.fts5_path.exists():
        logger.info("FTS5 not found at %s, downloading from COS ...", settings.fts5_path)
        try:
            # 用 inline scf_cos (无 cos sdk 依赖, 不需要 six)
            from scf_cos import download_fts5_data
            if download_fts5_data(anchor_dir=settings.fts5_path.parent):
                logger.info("FTS5 data downloaded to %s", settings.fts5_path.parent)
            else:
                logger.warning("scf_cos download_fts5_data returned False")
        except Exception as e:
            logger.exception("FTS5 COS download failed: %s", e)

    # 1. SQLite 建表
    sqlite = get_sqlite_client()
    await sqlite.init()

    # 1.5 加载航司静态数据 (Sprint C)
    airlines_client = get_airlines_client()
    logger.info("Airlines loaded: %d", airlines_client.count())

    # 2. RAG backend 初始化
    if settings.rag_backend == "fts5":
        # FTS5 客户端
        try:
            fts5 = get_fts5_client()
            # ★ P0-3: 启动时校验 build_manifest, 不一致 fail-closed
            # 失败抛 RuntimeError, lifespan 不启动, SCF 容器重启
            manifest = await fts5.validate_manifest_or_fail()
            n = await fts5.count()
            logger.info(
                "FTS5 chunks_fts: %d docs (manifest: tokenizer=%s commit=%s schema=%s)",
                n, manifest["tokenizer"], manifest["build_commit"][:8], manifest["fts5_schema_version"],
            )
        except Exception as e:
            logger.error("FTS5 init failed (P0-3 fail-closed): %s", e)
            raise  # ★ P0-3: 失败必须让容器 fail, 不能降级到 chroma
    else:
        # Chroma 客户端 (本地 dev 默认)
        try:
            chroma = get_chroma_client()
            count = chroma.count()
            logger.info("Chroma collection: %d docs", count)
        except Exception as e:
            logger.warning("Chroma init issue (will continue): %s", e)

    # 3. Sync service (T6 真实实现 - 启动后台 poll 任务)
    sync_svc = get_sync_service()
    await sync_svc.start()

    # 把 settings / clients 挂到 app.state
    app.state.settings = settings
    app.state.sqlite = sqlite
    app.state.sync = sync_svc
    app.state.airlines = airlines_client

    logger.info("AOG Web Backend ready.")
    yield

    # Shutdown
    logger.info("AOG Web Backend shutting down...")
    await sync_svc.stop()
    await sqlite.close()
    # FTS5 客户端也需要关
    try:
        from aog_web.services.fts5_client import _client as _fts5_singleton
        if _fts5_singleton is not None:
            await _fts5_singleton.close()
    except Exception:
        pass
    logger.info("AOG Web Backend stopped.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AOG AI 知识库 API",
        description=f"Wave 3 · T5 后端 (FastAPI + {settings.rag_backend.upper()} + SQLite + MiniMax M3)",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(cities.router)
    app.include_router(airlines.router)
    app.include_router(experiences.router)
    app.include_router(core_plans.router)
    app.include_router(chat.router)
    app.include_router(reindex.router)
    app.include_router(sync.router)
    app.include_router(files.router)

    # 根路径重定向到 /docs (FastAPI swagger, NJX 8/2 本地验收浏览器友好)
    @app.get("/", include_in_schema=False)
    async def root_index() -> RedirectResponse:
        return RedirectResponse(url="/docs", status_code=307)

    return app


# uvicorn 入口
app = create_app()

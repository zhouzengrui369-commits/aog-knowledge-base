"""FastAPI app 入口 - lifespan + CORS + 路由注册

启动流程:
1. load settings
2. init SQLite (建表)
3. init Chroma (collection)
4. (可选) start sync service
5. 监听 SIGTERM → graceful shutdown
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aog_web import __version__
from aog_web.api import (
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
from aog_web.services.chroma_client import get_chroma_client
from aog_web.services.sqlite_client import get_sqlite_client
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
    logger.info("Chroma: %s", settings.chroma_path)
    logger.info("SQLite: %s", settings.sqlite_path)
    logger.info("Knowledge base: %s", settings.knowledge_base_path)
    logger.info("CORS: %s", settings.cors_origins)
    logger.info("=" * 60)

    # 1. SQLite 建表
    sqlite = get_sqlite_client()
    await sqlite.init()

    # 2. Chroma 初始化 (拿到 collection)
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

    logger.info("AOG Web Backend ready.")
    yield

    # Shutdown
    logger.info("AOG Web Backend shutting down...")
    await sync_svc.stop()
    await sqlite.close()
    logger.info("AOG Web Backend stopped.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AOG AI 知识库 API",
        description="Wave 1 · T1 后端 (FastAPI + Chroma + SQLite + MiniMax M3)",
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
    app.include_router(cities.router)
    app.include_router(experiences.router)
    app.include_router(core_plans.router)
    app.include_router(chat.router)
    app.include_router(reindex.router)
    app.include_router(sync.router)
    app.include_router(files.router)

    return app


# uvicorn 入口
app = create_app()

"""FastAPI app entry: lifecycle, release gates and public API routing."""
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
    chat_safe as chat,
    cities,
    core_plans,
    experiences,
    files,
    health,
    reindex,
    stats,
    sync,
)
from aog_web.config import get_settings
from aog_web.services.airlines_client import get_airlines_client
from aog_web.services.chroma_client import get_chroma_client
from aog_web.services.fts5_client import get_fts5_client
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
    settings = get_settings()
    _setup_logging(settings.LOG_LEVEL)
    logger = logging.getLogger("aog_web.main")

    logger.info("=" * 60)
    logger.info("AOG Web Backend starting (version=%s)", __version__)
    logger.info("LLM mode: %s", "MOCK" if settings.is_mock_llm else "LIVE (MiniMax M3)")
    logger.info("RAG backend: %s", settings.rag_backend)
    logger.info("FTS5: %s", settings.fts5_path)
    logger.info("SQLite: %s", settings.sqlite_path)
    logger.info("ALLOW_MOCK: %s", settings.ALLOW_MOCK)
    logger.info("STRICT_LLM: %s", settings.STRICT_LLM)
    logger.info("=" * 60)

    if not settings.ALLOW_MOCK and settings.is_mock_llm:
        msg = (
            "P0-4 fail-closed: ALLOW_MOCK=false but MINIMAX_API_KEY is empty. "
            "Production and staging require a live provider key."
        )
        logger.error(msg)
        raise RuntimeError(msg)

    if settings.rag_backend == "fts5" and not settings.fts5_path.exists():
        logger.info("FTS5 missing at %s; downloading from staging storage", settings.fts5_path)
        try:
            from scf_cos import download_fts5_data

            if not download_fts5_data(anchor_dir=settings.fts5_path.parent):
                raise RuntimeError("download_fts5_data returned false")
        except Exception as exc:
            logger.exception("FTS5 storage download failed: %s", exc)
            raise

    sqlite = get_sqlite_client()
    await sqlite.init()

    airlines_client = get_airlines_client()
    logger.info("Airlines loaded: %d", airlines_client.count())

    if settings.rag_backend == "fts5":
        try:
            fts5 = get_fts5_client()
            manifest = await fts5.validate_manifest_or_fail()
            count = await fts5.count()
            logger.info(
                "FTS5 ready: %d docs tokenizer=%s commit=%s schema=%s",
                count,
                manifest["tokenizer"],
                manifest["build_commit"][:8],
                manifest["fts5_schema_version"],
            )
        except Exception as exc:
            logger.error("FTS5 release identity failed: %s", exc)
            raise
    else:
        try:
            chroma = get_chroma_client()
            logger.info("Chroma collection: %d docs", chroma.count())
        except Exception as exc:
            logger.warning("Chroma init issue: %s", exc)

    sync_service = get_sync_service()
    await sync_service.start()

    app.state.settings = settings
    app.state.sqlite = sqlite
    app.state.sync = sync_service
    app.state.airlines = airlines_client

    logger.info("AOG Web Backend ready")
    yield

    logger.info("AOG Web Backend shutting down")
    await sync_service.stop()
    await sqlite.close()
    try:
        from aog_web.services.fts5_client import _client as fts5_singleton

        if fts5_singleton is not None:
            await fts5_singleton.close()
    except Exception:
        pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AOG AI 知识库 API",
        description=(
            "AOG production API: FastAPI + "
            f"{settings.rag_backend.upper()} + SQLite + MiniMax M3"
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(cities.router)
    app.include_router(airlines.router)
    app.include_router(experiences.router)
    app.include_router(core_plans.router)
    app.include_router(stats.router)
    app.include_router(chat.router)
    app.include_router(reindex.router)
    app.include_router(sync.router)
    app.include_router(files.router)

    @app.get("/", include_in_schema=False)
    async def root_index() -> RedirectResponse:
        return RedirectResponse(url="/docs", status_code=307)

    return app


app = create_app()
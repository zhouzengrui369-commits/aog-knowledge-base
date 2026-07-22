"""AOG 后端配置 - pydantic-settings + .env 加载

设计原则:
- 缺 KEY 也能跑: MINIMAX_API_KEY 缺失时使用 Mock LLM, 带 "⚠️ Mock 模式" 标志
- 路径: 默认 ./data/ (相对 backend/ 启动目录), 可被 .env 覆盖
- 知识库路径默认指向真实源 (只读), 后端不写
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _backend_root() -> Path:
    """aog-web/backend/ 目录 — pyproject.toml 所在"""
    return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """从 .env / 环境变量加载配置"""

    model_config = SettingsConfigDict(
        env_file=str(_backend_root() / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== LLM =====
    MINIMAX_API_KEY: str = ""
    MINIMAX_BASE_URL: str = "https://api.MiniMax.chat/v1"
    MINIMAX_MODEL: str = "minimax-m3"

    # ===== 存储路径 (相对 backend/) =====
    CHROMA_PATH: str = "./data/chroma"
    SQLITE_PATH: str = "./data/aog.db"
    # FTS5 索引路径 (Wave 3 SCF 部署用, 默认本地, SCF 部署时改为 /tmp/aog_fts5.db)
    FTS5_PATH: str = "./data/fts5_index.db"
    # RAG backend: "chroma" (本地 dev) | "fts5" (SCF 部署)
    RAG_BACKEND: str = "chroma"
    # 航司静态数据 (Sprint C) — 测试时可临时覆盖路径
    AIRLINES_DATA_PATH: str = ""

    # ===== 知识库源 (只读) =====
    KNOWLEDGE_BASE_PATH: str = "/Users/njx/Project/AOG知识库/AOG知识库"
    RAW_PATH: str = "/Users/njx/Project/AOG知识库/RAW"

    # ===== 运行时 =====
    SYNC_ENABLED: bool = True
    SYNC_INTERVAL_S: int = 300
    # 增量同步状态缓存 (mtime + size hash) - 默认 ./data/sync_state.db
    SYNC_STATE_DB_PATH: str = "./data/sync_state.db"
    # 监听目录 (逗号分隔, 空 = 用默认 01/02/03)
    SYNC_WATCH_DIRS: str = ""
    # Pipeline 工作目录 (build_index.py 所在 package 根)
    PIPELINE_DIR: str = str(_backend_root().parent / "pipeline")
    LOG_LEVEL: str = "INFO"
    CORS_ALLOW_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ===== Sprint A · Auth (本地优先, MVP 简化方案) =====
    # AOG 知识库访问密码 (Sprint A 拍板方案 🅱️)
    # 生产前必须改; 缺失时 fallback 到默认 "13456789" (仅 dev)
    AOG_VIEW_PASSWORD: str = ""
    # JWT 签发 secret (HS256)
    # 生产前必须改; 缺失时 fallback 到默认 dev secret (仅 dev)
    JWT_SECRET: str = ""

    @property
    def backend_root(self) -> Path:
        return _backend_root()

    @property
    def chroma_path(self) -> Path:
        p = Path(self.CHROMA_PATH)
        if not p.is_absolute():
            p = self.backend_root / p
        return p.resolve()

    @property
    def fts5_path(self) -> Path:
        p = Path(self.FTS5_PATH)
        if not p.is_absolute():
            p = self.backend_root / p
        return p.resolve()

    @property
    def rag_backend(self) -> str:
        """RAG backend: 'chroma' (本地 dev) | 'fts5' (SCF 部署)"""
        v = (self.RAG_BACKEND or "chroma").lower().strip()
        return v if v in {"chroma", "fts5"} else "chroma"

    @property
    def sqlite_path(self) -> Path:
        p = Path(self.SQLITE_PATH)
        if not p.is_absolute():
            p = self.backend_root / p
        return p.resolve()

    @property
    def data_dir(self) -> Path:
        return self.backend_root / "data"

    @property
    def airlines_data_path(self) -> Path:
        """航司静态数据 JSON 路径. 优先用 AIRLINES_DATA_PATH, 否则默认
        aog-web/functions/aog-api/data/airlines.json (项目内固定位置)
        """
        if self.AIRLINES_DATA_PATH.strip():
            p = Path(self.AIRLINES_DATA_PATH)
            if not p.is_absolute():
                p = self.backend_root / p
            return p.resolve()
        # 默认: aog-web/backend/aog_web/config.py → aog-web/backend/aog_web/ → aog-web/backend/ → aog-web/
        from pathlib import Path as _P
        here = _P(__file__).resolve().parent.parent.parent  # aog-web/
        candidates = [
            here / "functions" / "aog-api" / "data" / "airlines.json",
            here / "backend" / "data" / "airlines.json",
        ]
        for c in candidates:
            if c.exists():
                return c.resolve()
        return candidates[0].resolve()  # 兜底:返回 SCF 路径 (即使不存在, client 也能容错)

    @property
    def knowledge_base_path(self) -> Path:
        return Path(self.KNOWLEDGE_BASE_PATH).resolve()

    @property
    def raw_path(self) -> Path:
        return Path(self.RAW_PATH).resolve()

    @property
    def sync_state_db_path(self) -> Path:
        """增量同步状态缓存 DB 路径"""
        p = Path(self.SYNC_STATE_DB_PATH)
        if not p.is_absolute():
            p = self.backend_root / p
        return p.resolve()

    @property
    def watch_dirs(self) -> List[Path]:
        """监听目录列表 (空 = 用默认 01/02/03 三目录)"""
        if self.SYNC_WATCH_DIRS.strip():
            return [Path(d).strip() for d in self.SYNC_WATCH_DIRS.split(",") if d.strip()]
        kb = self.knowledge_base_path
        return [
            kb / "01_AOG预案",
            kb / "02_外战预案",
            kb / "03_保障经验",
        ]

    @property
    def pipeline_dir(self) -> Path:
        """T3 pipeline 包根目录 (含 pyproject.toml + pipeline/ 子包)"""
        return Path(self.PIPELINE_DIR).resolve()

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]

    @property
    def is_mock_llm(self) -> bool:
        """LLM 是否处于 Mock 模式 (无 API key)"""
        return not self.MINIMAX_API_KEY.strip()

    @field_validator("LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        v = v.upper()
        if v not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            return "INFO"
        return v


# 全局单例 (延迟加载)
_settings: Settings | None = None


def get_settings() -> Settings:
    """获取配置单例 (测试时可通过 monkeypatch.setattr 覆盖)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_cache() -> None:
    """测试 helper: 重置单例让下次 get_settings() 重新读环境变量"""
    global _settings
    _settings = None

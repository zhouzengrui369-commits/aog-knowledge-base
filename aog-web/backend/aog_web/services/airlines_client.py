"""航司数据客户端 - 静态 JSON 加载 (Sprint C)

- 不进 SQLite, 直接读 functions/aog-api/data/airlines.json
- 启动时一次性 load 到内存 (OFFLINE 兼容: 文件不存在 → 空 list, 不崩)
- 公开 list / get / search 三方法 (同步)
- 单例 (reset_airlines_client for test)

Sprint C 数据模型 1:1 对齐 aog-web/functions/aog-api/data/airlines.json
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from aog_web.config import get_settings

logger = logging.getLogger(__name__)


class AirlinesClient:
    """航司客户端 (内存, 静态数据)"""

    def __init__(self, data_path: Optional[Path] = None):
        if data_path is None:
            data_path = get_settings().airlines_data_path
        self.data_path = data_path
        self._airlines: List[Dict[str, Any]] = []
        self._by_iata: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        self._load()

    def _load(self) -> None:
        """启动时 load 一次. 文件不存在或损坏 → 空 list + warning"""
        if not self.data_path.exists():
            logger.warning(
                "airlines.json not found at %s, returning empty list", self.data_path
            )
            self._airlines = []
            self._by_iata = {}
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                logger.error("airlines.json root must be list, got %s", type(data))
                self._airlines = []
                self._by_iata = {}
                return
            self._airlines = data
            self._by_iata = {
                a.get("iata", "").upper(): a for a in data if a.get("iata")
            }
            logger.info(
                "AirlinesClient loaded %d airlines from %s", len(data), self.data_path
            )
        except Exception as e:
            logger.exception("Failed to load airlines.json: %s", e)
            self._airlines = []
            self._by_iata = {}

    def list(
        self,
        hub: Optional[str] = None,
        alliance: Optional[str] = None,
        letter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """航司列表. 排序: IATA 字母序 (拼音 fallback)."""
        result = self._airlines
        if letter:
            letter = letter.upper()
            result = [
                a for a in result
                if (a.get("iata") or "").upper().startswith(letter)
                or (a.get("name_cn") or "").startswith(letter)
            ]
        if alliance:
            result = [a for a in result if a.get("alliance") == alliance]
        if hub:
            # 过滤包含特定 city_code 的航司
            result = [a for a in result if any(
                (h.get("city_code") or "") == hub for h in a.get("hubs", [])
            )]
        # 排序: IATA 字母序
        return sorted(result, key=lambda a: (a.get("iata") or ""))

    def get(self, iata: str) -> Optional[Dict[str, Any]]:
        """按 IATA 2-letter code 查航司详情"""
        if not iata:
            return None
        return self._by_iata.get(iata.upper())

    def search(self, q: str, limit: int = 20) -> List[Dict[str, Any]]:
        """按 IATA / ICAO / 中文名 / 英文名 / 常用简称 模糊搜索"""
        if not q or not q.strip():
            return []
        q_lower = q.strip().lower()
        pattern = re.compile(re.escape(q_lower), re.IGNORECASE)
        result = []
        for a in self._airlines:
            haystack = " ".join([
                a.get("iata", ""),
                a.get("icao", ""),
                a.get("name_cn", ""),
                a.get("name_en", ""),
                a.get("name_short", ""),
            ])
            if pattern.search(haystack):
                result.append(a)
                if len(result) >= limit:
                    break
        return result

    def count(self) -> int:
        return len(self._airlines)

    def reload(self) -> None:
        """重载 (测试用)"""
        self._load()


# ===== 单例 + reset =====
_client: Optional[AirlinesClient] = None


def get_airlines_client() -> AirlinesClient:
    global _client
    if _client is None:
        _client = AirlinesClient()
    return _client


def reset_airlines_client() -> None:
    global _client
    _client = None

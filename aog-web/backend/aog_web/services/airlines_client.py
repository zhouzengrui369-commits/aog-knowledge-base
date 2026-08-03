"""Airline data client with production verification and conflict isolation."""
from __future__ import annotations

import copy
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from aog_web.config import get_settings

logger = logging.getLogger(__name__)

# Public product terminology.  Juneyao is a Star Alliance Connecting Partner,
# not a full alliance member; HU and JD are separate operating airlines.
_NAME_OVERRIDES = {
    "HU": {"name_cn": "海南航空", "name_short": "海航"},
    "JD": {"name_cn": "首都航空", "name_short": "首都航"},
}
_ALLIANCE_OVERRIDES = {
    "HO": "星空联盟优连伙伴",
}


def _canonical_phone(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _canonical_email(value: str) -> str:
    return (value or "").strip().casefold()


class AirlinesClient:
    """Load, verify and expose the airline registry.

    Duplicate contact points across different IATA operators are fail-closed:
    the conflicting contact is removed from public output and the record is
    marked for data-governance review instead of guessing a replacement.
    """

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or get_settings().airlines_data_path
        self._airlines: List[Dict[str, Any]] = []
        self._by_iata: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.data_path.exists():
            logger.warning("airlines registry missing: %s", self.data_path)
            self._airlines = []
            self._by_iata = {}
            return
        try:
            data = json.loads(self.data_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.exception("airlines registry unreadable: %s", exc)
            self._airlines = []
            self._by_iata = {}
            return
        if not isinstance(data, list):
            logger.error("airlines registry root must be a list")
            self._airlines = []
            self._by_iata = {}
            return

        rows = [copy.deepcopy(item) for item in data if isinstance(item, dict)]
        for row in rows:
            iata = str(row.get("iata") or "").upper()
            row["iata"] = iata
            row.update(_NAME_OVERRIDES.get(iata, {}))
            if iata in _ALLIANCE_OVERRIDES:
                row["alliance"] = _ALLIANCE_OVERRIDES[iata]
            row["verification_status"] = (
                "VERIFIED" if row.get("verified") and row.get("verified_at") else "UNVERIFIED"
            )
            if not row.get("verified_at"):
                row["verified"] = False
                row["verification_issue"] = "缺少 verified_at，不得作为生产联系方式"

        phone_owners: dict[str, set[str]] = defaultdict(set)
        email_owners: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            iata = str(row.get("iata") or "")
            contact = row.get("aog_contact") or {}
            phone = _canonical_phone(str(contact.get("phone") or ""))
            email = _canonical_email(str(contact.get("email") or ""))
            if phone:
                phone_owners[phone].add(iata)
            if email:
                email_owners[email].add(iata)

        for row in rows:
            iata = str(row.get("iata") or "")
            contact = dict(row.get("aog_contact") or {})
            issues: list[str] = []
            phone = _canonical_phone(str(contact.get("phone") or ""))
            email = _canonical_email(str(contact.get("email") or ""))
            if phone and len(phone_owners[phone]) > 1:
                issues.append("AOG 电话与其他航司冲突")
                contact.pop("phone", None)
            if email and len(email_owners[email]) > 1:
                issues.append("AOG 邮箱与其他航司冲突")
                contact.pop("email", None)
            if issues:
                row["verified"] = False
                row["verification_status"] = "CONFLICT"
                row["verification_issue"] = "；".join(issues)
            row["aog_contact"] = contact

        self._airlines = rows
        self._by_iata = {
            str(row.get("iata")): row for row in rows if row.get("iata")
        }
        logger.info("AirlinesClient loaded %d governed records", len(rows))

    def list(
        self,
        hub: Optional[str] = None,
        alliance: Optional[str] = None,
        letter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        result = self._airlines
        if letter:
            initial = letter.upper()
            result = [
                row
                for row in result
                if str(row.get("iata") or "").upper().startswith(initial)
                or str(row.get("name_cn") or "").startswith(initial)
            ]
        if alliance:
            result = [row for row in result if row.get("alliance") == alliance]
        if hub:
            result = [
                row
                for row in result
                if any((item.get("city_code") or "") == hub for item in row.get("hubs", []))
            ]
        return sorted((copy.deepcopy(row) for row in result), key=lambda row: row.get("iata", ""))

    def get(self, iata: str) -> Optional[Dict[str, Any]]:
        row = self._by_iata.get((iata or "").upper())
        return copy.deepcopy(row) if row else None

    def search(self, q: str, limit: int = 20) -> List[Dict[str, Any]]:
        query = (q or "").strip().casefold()
        if not query:
            return []
        output: list[dict[str, Any]] = []
        for row in self._airlines:
            haystack = " ".join(
                str(row.get(key) or "")
                for key in ("iata", "icao", "name_cn", "name_en", "name_short")
            ).casefold()
            if query in haystack:
                output.append(copy.deepcopy(row))
                if len(output) >= limit:
                    break
        return output

    def count(self) -> int:
        return len(self._airlines)

    def reload(self) -> None:
        self._load()


_client: Optional[AirlinesClient] = None


def get_airlines_client() -> AirlinesClient:
    global _client
    if _client is None:
        _client = AirlinesClient()
    return _client


def reset_airlines_client() -> None:
    global _client
    _client = None

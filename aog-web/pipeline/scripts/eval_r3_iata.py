"""R3 IATA matching evaluation script.

R3 introduces a city/flight context intent guard for IATA fallback in
detect_target_cities.  This script loads the new aviation-acronym fixture
(`tests/fixtures/iata_aviation_acronym_cases.json`) and runs each case
through apply_retrieval_policy directly against the production owner
SQLite (R2 frozen stable artifact).  The expected behaviour is:

  - Aviation acronym questions (IATA-01..07) select NO city target
    (detect_target_cities returns 0 records) → policy.unblocked=True →
    chat falls through to grounded FTS5 retrieval.
  - Genuine city/flight questions (IATA-08..12) select the matching city;
    if the city is paused/UNVERIFIED, policy blocks → boundary answer;
    if the city is VERIFIED, policy passes → grounded FTS5 retrieval.

This script is independent of `run_rag_pressure.py` (which is frozen
under the 24-prohibition contract) and reads the new fixture only.

Usage:
    cd aog-web/pipeline
    source .venv/bin/activate
    python scripts/eval_r3_iata.py \\
        --sqlite /Users/njx/Project/aog-focused-artifacts/cda45472b55b31989d0b660dd1a80802d6b2f94b/aog.db \\
        --output /tmp/r3-iata-eval.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from aog_web.services.sqlite_client import SQLiteClient  # noqa: E402
from aog_web.services.verification_policy import (  # noqa: E402
    apply_retrieval_policy,
    city_trust_records,
    detect_target_cities,
)


def _load_fixture(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


async def _evaluate_case(cities, case: Dict[str, Any]) -> Dict[str, Any]:
    question = case["q"]
    expected_codes = set(case.get("expected_target_codes") or [])
    expected_unblocked = bool(case.get("expected_unblocked"))

    records = city_trust_records(cities=cities)
    selected = detect_target_cities(
        question=question,
        context_codes=None,
        records=records,
    )
    selected_codes = [r.code for r in selected]

    # Re-run through apply_retrieval_policy with empty hits so the
    # blocked_target list reflects only the city-detection path (no FTS5
    # influence).
    policy = apply_retrieval_policy(
        hits=[],
        cities=cities,
        question=question,
        context_codes=None,
    )

    actual_codes = set(selected_codes)
    actual_unblocked = not policy.blocked

    code_match = actual_codes == expected_codes
    unblocked_match = actual_unblocked == expected_unblocked
    passed = code_match and unblocked_match

    return {
        "id": case["id"],
        "question": question,
        "mode": case.get("mode"),
        "expected": {
            "target_codes": sorted(expected_codes),
            "unblocked": expected_unblocked,
        },
        "actual": {
            "target_codes": sorted(actual_codes),
            "unblocked": actual_unblocked,
            "blocked_count": len(policy.blocked_targets),
        },
        "passed": passed,
        "rationale": case.get("rationale"),
    }


async def _run(sqlite_path: Path, fixture_path: Path, output_path: Path) -> Dict[str, Any]:
    # Build a fresh SQLiteClient (bypass the module-level singleton whose
    # db_path was set at first call from get_settings()).
    sqlite = SQLiteClient(sqlite_path)
    await sqlite.init()
    cities = await sqlite.list_cities()
    fixture = _load_fixture(fixture_path)
    results = []
    for case in fixture:
        results.append(await _evaluate_case(cities, case))
    total = len(results)
    failures = [r for r in results if not r["passed"]]
    summary = {
        "cases": total,
        "failures": len(failures),
        "fail_rate": (len(failures) / total) if total else 0.0,
        "passed": not failures,
    }
    payload = {"summary": summary, "results": results}
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", required=True, help="Path to aog.db (stable artifact)")
    parser.add_argument("--fixture", required=True, help="Path to iata_aviation_acronym_cases.json")
    parser.add_argument("--output", required=True, help="Path to write eval JSON")
    args = parser.parse_args()

    payload = asyncio.run(
        _run(Path(args.sqlite), Path(args.fixture), Path(args.output))
    )
    s = payload["summary"]
    print(f"R3 IATA evaluation: cases={s['cases']} failures={s['failures']} fail_rate={s['fail_rate']} passed={s['passed']}")
    if not s["passed"]:
        print("\nFailures:")
        for r in payload["results"]:
            if not r["passed"]:
                print(f"  {r['id']}: q={r['question']!r}")
                print(f"    expected={r['expected']}")
                print(f"    actual  ={r['actual']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
select_third_sample.py — Stage 9.2 第三个样板自动选

按 NJX 7/29 指令: 不向 Owner 询问, 由程序按数据完整度自动评分
                  从 AOG知识库/02_外战预案/ 选最完整的站点作第三个样板
                  排除 #1 (北京大兴) + #2 (上海浦东 MISSING) + 暂停 + 待开航

评分维度 (5 项, 总分 30):
  contacts    (10) — 字符数 (0-1000 -> 0-10)
  parts       (10) — 字符数
  warehouse   (5)  — 字符数
  logistics   (3)  — 字符数
  source_docx (2)  — 源 docx 真实存在 + size > 10KB

只读 — 绝不写入源目录 (AOG知识库/02_外战预案/)
输出: data/third_sample.json (选择结果 + 评分明细 + 选择依据)
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

# 配置
REPO_ROOT = Path("/Users/njx/Project/AOG知识库")
AOG_DB = REPO_ROOT / "worktrees/integration-sprint-abc/aog-web/pipeline/data/aog.db"
SOURCE_DIR = REPO_ROOT / "AOG知识库/02_外战预案"
OUTPUT_JSON = REPO_ROOT / "worktrees/integration-sprint-abc/aog-web/pipeline/data/third_sample.json"

# 排除 (已有样板 + MISSING + 暂停/待开航)
EXCLUDE_CODES = {"B-北京大兴", "S-上海浦东", "S-上海虹桥"}
EXCLUDE_STATUS = {"暂停", "待开航"}


def score_field(val: str, max_score: float, max_chars: int = 1000) -> float:
    """字段字符数 -> 0-max_score 线性映射 (达到 max_chars 满分)"""
    if not val or not val.strip():
        return 0.0
    return min(len(val.strip()) / max_chars, 1.0) * max_score


def score_source_docx(source_path: str) -> tuple:
    """源 docx 存在 + size > 10KB = 2.0 分"""
    if not source_path:
        return 0.0, None
    # source_path 是相对路径如 "02_外战预案/D-敦煌.docx"
    full = REPO_ROOT / "AOG知识库" / source_path
    if not full.exists():
        return 0.0, None
    sz = full.stat().st_size
    mtime_iso = datetime.fromtimestamp(full.stat().st_mtime, tz=timezone.utc).isoformat()
    if sz > 10_000:
        return 2.0, {"path": str(full.relative_to(REPO_ROOT)), "size": sz, "mtime": mtime_iso}
    elif sz > 0:
        return 1.0, {"path": str(full.relative_to(REPO_ROOT)), "size": sz, "mtime": mtime_iso}
    return 0.0, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=10, help="输出 top N 候选")
    parser.add_argument("--json-only", action="store_true", help="只输出 JSON 不打 human-readable")
    args = parser.parse_args()

    if not AOG_DB.exists():
        print(f"FAIL: aog.db not found: {AOG_DB}", file=sys.stderr)
        return 1

    con = sqlite3.connect(str(AOG_DB))
    cur = con.execute("""
        SELECT code, name, contacts, parts, warehouse, logistics, source_path, updated_at, status
        FROM cities
    """)
    rows = cur.fetchall()
    con.close()

    scored = []
    for code, name, contacts, parts, warehouse, logistics, source_path, updated_at, status in rows:
        if code in EXCLUDE_CODES:
            continue
        if status in EXCLUDE_STATUS:
            continue

        breakdown = {
            "contacts": round(score_field(contacts, 10.0), 2),
            "parts": round(score_field(parts, 10.0), 2),
            "warehouse": round(score_field(warehouse, 5.0), 2),
            "logistics": round(score_field(logistics, 3.0), 2),
        }
        src_score, src_info = score_source_docx(source_path)
        breakdown["source_docx"] = src_score
        total = sum(breakdown.values())

        # 多样性 bonus: contacts 同时含 phone + email 优先
        if contacts:
            n_phone = len(re.findall(r"1[3-9]\d{9}", contacts))
            n_email = len(re.findall(r"[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}", contacts))
            diversity = min((n_phone + n_email) * 0.1, 1.0)
            breakdown["diversity_bonus"] = round(diversity, 2)
            total += diversity

        scored.append({
            "code": code,
            "name": name,
            "score": round(total, 2),
            "breakdown": breakdown,
            "source_docx": src_info,
            "updated_at": updated_at,
            "field_lengths": {
                "contacts": len(contacts) if contacts else 0,
                "parts": len(parts) if parts else 0,
                "warehouse": len(warehouse) if warehouse else 0,
                "logistics": len(logistics) if logistics else 0,
            },
        })

    scored.sort(key=lambda x: -x["score"])
    top = scored[:args.top]
    winner = top[0] if top else None

    result = {
        "stage": "9.2",
        "purpose": "第三个样板站点自动选 (按数据完整度评分)",
        "exclude_codes": sorted(EXCLUDE_CODES),
        "exclude_status": sorted(EXCLUDE_STATUS),
        "candidate_count": len(scored),
        "winner": {
            "code": winner["code"],
            "name": winner["name"],
            "score": winner["score"],
            "breakdown": winner["breakdown"],
            "source_docx": winner["source_docx"],
            "field_lengths": winner["field_lengths"],
            "selection_rationale": (
                f"5 维评分最高分 ({winner['score']:.2f}/31) — "
                f"contacts={winner['field_lengths']['contacts']} char "
                f"parts={winner['field_lengths']['parts']} char "
                f"warehouse={winner['field_lengths']['warehouse']} char "
                f"logistics={winner['field_lengths']['logistics']} char "
                f"source_docx={'OK' if winner['source_docx'] else 'MISSING'}"
            ),
        } if winner else None,
        "top": top,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aog_db_path": str(AOG_DB.relative_to(REPO_ROOT)),
        "output_path": str(OUTPUT_JSON.relative_to(REPO_ROOT)),
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.json_only:
        print(f"=== Stage 9.2 第三个样板自动选 ===")
        print(f"候选: {len(scored)} 个 (排除 {sorted(EXCLUDE_CODES)} + status {sorted(EXCLUDE_STATUS)})")
        print()
        if winner:
            w = winner
            print(f"🏆 第三个样板: {w['code']} {w['name']} score={w['score']:.2f}/31")
            print(f"   {w['breakdown']}")
            print(f"   field_lengths: {w['field_lengths']}")
            print(f"   source_docx: {w['source_docx']}")
            print()
        print(f"TOP {args.top}:")
        for i, c in enumerate(top, 1):
            print(f"  {i}. {c['code']:20s} {c['name']:20s} score={c['score']:.2f} "
                  f"cont={c['field_lengths']['contacts']} parts={c['field_lengths']['parts']}")
        print()
        print(f"✅ 写入: {OUTPUT_JSON.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

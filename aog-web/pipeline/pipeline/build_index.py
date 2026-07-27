"""Build Index CLI 主入口。

扫描数据源 → 解析 → 抽字段 → 分块 → embedding → 写 Chroma + SQLite。

用法:
  uv run python -m pipeline.build_index [--dry-run] [--paths <abs1> <abs2> ...]
    --dry-run    只扫描, 不写库, 输出 stats 到 stdout
    --paths      增量模式, 只处理指定文件 (绝对路径)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from tqdm import tqdm

from . import __version__
from .chunker import chunk_text
from .embedder import Embedder
from .extractors import extract_city, extract_core_plan, extract_experience
from .indexer import CHROMA_COLLECTION, ChromaIndex, IndexStats, SqliteIndex

# ---------- 默认路径 ----------

DEFAULT_KB_ROOT = Path("/Users/njx/Project/AOG知识库/AOG知识库")
DEFAULT_CITIES_DIR = DEFAULT_KB_ROOT / "02_外战预案"
DEFAULT_EXPERIENCES_DIR = DEFAULT_KB_ROOT / "03_保障经验"
DEFAULT_CORE_PLANS_DIR = DEFAULT_KB_ROOT / "01_AOG预案"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SQLITE = DEFAULT_DATA_DIR / "aog.db"
DEFAULT_CHROMA = DEFAULT_DATA_DIR / "chroma"
DEFAULT_STATS = DEFAULT_DATA_DIR / "index_stats.json"


# ---------- 扫描 ----------

# v1 不索引的扩展名
SKIP_EXTS = {".pdf", ".pptx", ".ppt", ".doc"}
# v1 不索引的目录
SKIP_DIRS = {
    "04_课件",
    "05_项目立项",
    "06_组织人员",
    "07_元数据",
    "99_抓取日志",
    "外战保障预案",
    "RAW",
}


def _is_skip_ext(path: Path) -> bool:
    return path.suffix.lower() in SKIP_EXTS


def _is_in_skip_dir(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return rel.parts[0] in SKIP_DIRS if rel.parts else False


def scan_cities(root: Path = DEFAULT_CITIES_DIR) -> list[Path]:
    """扫外战预案目录下所有可索引的 .docx (md 是 docx 的伴随文件, 跳过)。"""
    if not root.exists():
        return []
    return sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".docx"]
    )


def scan_experiences(root: Path = DEFAULT_EXPERIENCES_DIR) -> list[Path]:
    """扫保障经验目录 (.docx/.md/.xlsx, 跳过 .pdf/.xmind/.pptx)。"""
    if not root.exists():
        return []
    return sorted(
        [
            p
            for p in root.iterdir()
            if p.is_file() and p.suffix.lower() in {".docx", ".md", ".xlsx"}
        ]
    )


def scan_core_plans(root: Path = DEFAULT_CORE_PLANS_DIR) -> list[Path]:
    """扫核心预案目录 (.md/.xlsx, 跳过 .doc/.pdf 等旧格式)。"""
    if not root.exists():
        return []
    out: list[Path] = []
    for p in root.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".md", ".xlsx"}:
            continue
        # 01_AOG预案 下 D-大连 / L-连城 / Q-秦皇岛 / Y-烟台 这 4 个是城市重份,不索引
        if p.stem in {"D-大连", "L-连城", "Q-秦皇岛", "Y-烟台"}:
            continue
        out.append(p)
    return sorted(out)


# ---------- build ----------

@dataclass
class BuildResult:
    files_scanned: int = 0
    files_indexed: int = 0
    files_failed: list[dict] = field(default_factory=list)
    chunks_total: int = 0
    cities_count: int = 0
    experiences_count: int = 0
    core_plans_count: int = 0
    build_time_s: float = 0.0
    chroma_size_mb: float = 0.0

    def to_stats_dict(self) -> dict:
        return {
            "build_time_s": round(self.build_time_s, 2),
            "build_at": datetime.now(timezone.utc).isoformat(),
            "files_scanned": self.files_scanned,
            "files_indexed": self.files_indexed,
            "files_failed": self.files_failed,
            "chunks_total": self.chunks_total,
            "chroma_size_mb": round(self.chroma_size_mb, 2),
            "cities_count": self.cities_count,
            "experiences_count": self.experiences_count,
            "core_plans_count": self.core_plans_count,
        }


def _process_cities(files: list[Path], kb_root: Path) -> tuple[list[dict], list[dict], int]:
    """处理 city 文件 → (city_dicts, failed, indexed_count)。"""
    out: list[dict] = []
    failed: list[dict] = []
    indexed = 0
    for p in tqdm(files, desc="cities", unit="file"):
        try:
            city = extract_city(p, knowledge_base_root=kb_root)
            d = city.to_dict()
            if not d.get("content_md"):
                # 完全空内容算失败
                raise ValueError("content_md 为空")
            out.append(d)
            indexed += 1
        except Exception as e:
            failed.append({"path": str(p), "error": str(e)[:200]})
    return out, failed, indexed


def _process_experiences(files: list[Path], kb_root: Path) -> tuple[list[dict], list[dict], int]:
    out: list[dict] = []
    failed: list[dict] = []
    indexed = 0
    for p in tqdm(files, desc="experiences", unit="file"):
        try:
            exp = extract_experience(p, knowledge_base_root=kb_root)
            d = exp.to_dict()
            if not d.get("content_md"):
                raise ValueError("content_md 为空")
            out.append(d)
            indexed += 1
        except Exception as e:
            failed.append({"path": str(p), "error": str(e)[:200]})
    return out, failed, indexed


def _process_core_plans(files: list[Path], kb_root: Path) -> tuple[list[dict], list[dict], int]:
    out: list[dict] = []
    failed: list[dict] = []
    indexed = 0
    for p in tqdm(files, desc="core_plans", unit="file"):
        try:
            cp = extract_core_plan(p, knowledge_base_root=kb_root)
            d = cp.to_dict()
            if not d.get("content_md"):
                raise ValueError("content_md 为空")
            out.append(d)
            indexed += 1
        except Exception as e:
            failed.append({"path": str(p), "error": str(e)[:200]})
    return out, failed, indexed


def _build_contacts_chunk(c: dict) -> str | None:
    """D-030: 把 city.contacts[] 拼成一段文本, 喂 RAG 让 AI 能召回 "021-22379771" 等具体电话。
    返回 None 表示无 contacts, 跳过。
    """
    contacts = c.get("contacts") or []
    if not contacts:
        return None
    # 按 permission 分组拼, 避免 internal/restricted 联系人直接当答案 (但保留在索引供 RAG 召回)
    lines: list[str] = [f"# {c['name']} ({c['iata']}) 现场联系人清单"]
    for ct in contacts:
        perm = ct.get("permission", "public")
        org = ct.get("org", "")
        phones = ct.get("phone") or []
        email = ct.get("email", "")
        role = ct.get("role", "")
        phone_str = " / ".join(phones) if phones else ""
        parts: list[str] = [f"- [{perm.upper()}] {org}"]
        if role:
            parts.append(f"  职责: {role}")
        if phone_str:
            parts.append(f"  电话: {phone_str}")
        if email:
            parts.append(f"  邮箱: {email}")
        lines.append("\n".join(parts))
    return "\n".join(lines)


def _build_chunks(
    cities: list[dict],
    experiences: list[dict],
    core_plans: list[dict],
) -> list[dict]:
    """把 records 切成 chunks, 准备写 chroma。

    D-030 (P1-1): city 额外把 contacts[] 拼成独立 chunk, 让 RAG 能召 "021-22379771" 等具体电话。
    """
    chunks: list[dict] = []
    for c in cities:
        for chunk in chunk_text(c["content_md"]):
            chunks.append(
                {
                    "text": chunk.text,
                    "metadata": {
                        "source_type": "city",
                        "source_id": c["code"],
                        "source_path": c["source_path"],
                        "title": f"{c['name']} ({c['iata']})",
                        "region": c["region"],
                        "status": c["status"],
                        "chunk_index": chunk.index,
                    },
                }
            )
        # D-030: contacts 单独成 chunk, RAG 召得到具体电话/邮箱
        contacts_text = _build_contacts_chunk(c)
        if contacts_text:
            chunks.append(
                {
                    "text": contacts_text,
                    "metadata": {
                        "source_type": "city_contacts",  # 区分, 便于前端按类型 highlight
                        "source_id": c["code"],
                        "source_path": c["source_path"],
                        "title": f"{c['name']} ({c['iata']}) 联系人",
                        "region": c["region"],
                        "status": c["status"],
                        "chunk_index": 0,  # 单独 1 个 chunk, index 0
                    },
                }
            )
    for e in experiences:
        for chunk in chunk_text(e["content_md"]):
            chunks.append(
                {
                    "text": chunk.text,
                    "metadata": {
                        "source_type": "experience",
                        "source_id": e["id"],
                        "source_path": e["source_path"],
                        "title": e["title"],
                        "category": e["category"],
                        "status": e["status"],
                        "chunk_index": chunk.index,
                    },
                }
            )
    for p in core_plans:
        for chunk in chunk_text(p["content_md"]):
            chunks.append(
                {
                    "text": chunk.text,
                    "metadata": {
                        "source_type": "core_plan",
                        "source_id": p["id"],
                        "source_path": p["source_path"],
                        "title": p["title"],
                        "type": p["type"],
                        "chunk_index": chunk.index,
                    },
                }
            )
    return chunks


def _chroma_dir_size_mb(path: Path) -> float:
    """chroma 持久化目录大小 (MB)。"""
    if not path.exists():
        return 0.0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def build(
    paths: list[Path] | None = None,
    dry_run: bool = False,
    kb_root: Path = DEFAULT_KB_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE,
    chroma_path: Path = DEFAULT_CHROMA,
    stats_path: Path = DEFAULT_STATS,
    batch_size: int = 8,
    ollama_concurrency: int = 12,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> BuildResult:
    """主 build 流程。

    paths: None=全量; 否则仅处理这些文件 (按所在目录判断 kind)
    dry_run: True=不写库, 只统计
    """
    t0 = time.time()
    result = BuildResult()

    # 1. 决定扫描范围
    if paths:
        # 增量模式 - 按文件路径推断 kind
        city_files: list[Path] = []
        exp_files: list[Path] = []
        cp_files: list[Path] = []
        for p in paths:
            try:
                rel = p.relative_to(kb_root)
            except ValueError:
                result.files_failed.append({"path": str(p), "error": "不在 KB 根目录下"})
                continue
            top = rel.parts[0] if rel.parts else ""
            ext = p.suffix.lower()
            if top == "02_外战预案":
                if ext == ".docx":
                    city_files.append(p)
            elif top == "03_保障经验":
                if ext in {".docx", ".md", ".xlsx"}:
                    exp_files.append(p)
            elif top == "01_AOG预案":
                if ext in {".md", ".xlsx"} and p.stem not in {"D-大连", "L-连城", "Q-秦皇岛", "Y-烟台"}:
                    cp_files.append(p)
        result.files_scanned = len(city_files) + len(exp_files) + len(cp_files)
    else:
        # D-030: 全量 mode 走 kb_root 派生 (不再用 hardcode DEFAULT_CITIES_DIR)
        city_files = scan_cities(kb_root / "02_外战预案")
        exp_files = scan_experiences(kb_root / "03_保障经验")
        cp_files = scan_core_plans(kb_root / "01_AOG预案")
        result.files_scanned = len(city_files) + len(exp_files) + len(cp_files)

    print(f"[scan] cities={len(city_files)} experiences={len(exp_files)} core_plans={len(cp_files)} total={result.files_scanned}")

    # 2. 抽字段
    cities, failed_c, _ = _process_cities(city_files, kb_root)
    experiences, failed_e, _ = _process_experiences(exp_files, kb_root)
    core_plans, failed_p, _ = _process_core_plans(cp_files, kb_root)

    result.files_failed.extend(failed_c)
    result.files_failed.extend(failed_e)
    result.files_failed.extend(failed_p)
    result.cities_count = len(cities)
    result.experiences_count = len(experiences)
    result.core_plans_count = len(core_plans)
    result.files_indexed = result.cities_count + result.experiences_count + result.core_plans_count

    print(f"[extract] cities={result.cities_count} experiences={result.experiences_count} core_plans={result.core_plans_count} failed={len(result.files_failed)}")

    if dry_run:
        result.build_time_s = time.time() - t0
        return result

    # 3. 写 SQLite (全清重建)
    print(f"[sqlite] writing to {sqlite_path} ...")
    sqlite = SqliteIndex(sqlite_path)
    sqlite.reset()
    for c in tqdm(cities, desc="sqlite.cities", unit="row"):
        sqlite.upsert_city(c)
    for e in tqdm(experiences, desc="sqlite.experiences", unit="row"):
        sqlite.upsert_experience(e)
    for p in tqdm(core_plans, desc="sqlite.core_plans", unit="row"):
        sqlite.upsert_core_plan(p)
    print(f"[sqlite] cities={sqlite.count('cities')} experiences={sqlite.count('experiences')} core_plans={sqlite.count('core_plans')}")

    # 4. 分块
    print("[chunk] building chunks ...")
    chunks = _build_chunks(cities, experiences, core_plans)
    result.chunks_total = len(chunks)
    print(f"[chunk] total chunks = {result.chunks_total}")

    if not chunks:
        result.build_time_s = time.time() - t0
        return result

    # 5. Embedding
    embedder = Embedder(batch_size=batch_size, ollama_concurrency=ollama_concurrency, backend="sentence-transformers")  # V26 严禁 ollama
    print(f"[embed] model={embedder.model_name} backend={embedder.backend} concurrency={ollama_concurrency}")
    texts = [c["text"] for c in chunks]
    # 分 batch 显示进度
    all_vecs: list[list[float]] = []
    BATCH = max(batch_size * 4, 32)
    for i in tqdm(range(0, len(texts), BATCH), desc="embed", unit="batch"):
        batch = texts[i : i + BATCH]
        vecs = embedder.embed(batch, show_progress=False)
        all_vecs.extend(vecs)
    print(f"[embed] done {len(all_vecs)} vectors, dim={embedder.dimension()}")

    # 6. 写 Chroma (全清重建)
    print(f"[chroma] writing to {chroma_path} ...")
    chroma = ChromaIndex(chroma_path, CHROMA_COLLECTION)
    chroma.reset()
    # 分批 add (避免单次过大)
    BATCH = 500
    for i in tqdm(range(0, len(chunks), BATCH), desc="chroma.add", unit="batch"):
        batch_chunks = chunks[i : i + BATCH]
        batch_vecs = all_vecs[i : i + BATCH]
        ids = [f"{c['metadata']['source_type']}:{c['metadata']['source_id']}:{c['metadata']['chunk_index']}" for c in batch_chunks]
        chroma.add_chunks(
            ids=ids,
            texts=[c["text"] for c in batch_chunks],
            embeddings=batch_vecs,
            metadatas=[c["metadata"] for c in batch_chunks],
        )
    print(f"[chroma] collection='{CHROMA_COLLECTION}' count={chroma.count()}")
    result.chroma_size_mb = _chroma_dir_size_mb(chroma_path)

    result.build_time_s = time.time() - t0
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="aog-build",
        description=f"AOG 知识库数据 pipeline (v{__version__})",
    )
    parser.add_argument("--dry-run", action="store_true", help="只扫描, 不写库")
    parser.add_argument("--paths", nargs="+", default=None, help="增量模式: 指定文件绝对路径")
    parser.add_argument("--kb-root", type=Path, default=DEFAULT_KB_ROOT, help="知识库根目录")
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE, help="SQLite 输出路径")
    parser.add_argument("--chroma", type=Path, default=DEFAULT_CHROMA, help="Chroma 持久化目录")
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS, help="index_stats.json 路径")
    parser.add_argument("--batch-size", type=int, default=8, help="embedding batch size")
    parser.add_argument("--ollama-concurrency", type=int, default=12, help="ollama 并发请求数 (调高加速)")
    parser.add_argument("--chunk-size", type=int, default=1200, help="字符数 / chunk")
    parser.add_argument("--overlap", type=int, default=150, help="overlap 字符数")
    args = parser.parse_args()

    paths = [Path(p) for p in (args.paths or [])]
    result = build(
        paths=paths or None,
        dry_run=args.dry_run,
        kb_root=args.kb_root,
        sqlite_path=args.sqlite,
        chroma_path=args.chroma,
        stats_path=args.stats,
        batch_size=args.batch_size,
        ollama_concurrency=args.ollama_concurrency,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )

    # 写 stats
    stats = result.to_stats_dict()
    if not args.dry_run:
        args.stats.parent.mkdir(parents=True, exist_ok=True)
        args.stats.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[stats] written to {args.stats}")

    print("\n========== BUILD SUMMARY ==========")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

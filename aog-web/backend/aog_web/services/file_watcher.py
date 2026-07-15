"""FileWatcher - 扫描知识库目录, 检测文件变化 (T6 增量同步)

设计:
- 同步接口 (只做 stat + dict 查询, 不读文件内容)
- 用 (mtime, size) 当轻量 hash, 不读内容 (省 IO)
- 返回 (changed, new) 两组 path; deleted 由 scan_deleted() 单独算
- SKIP_EXTS / SKIP_DIRS 跟 pipeline (T3 build_index.py) 一致, 避免噪声触发
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Tuple

from aog_web.services.sync_db import SyncDB

logger = logging.getLogger(__name__)


# 跟 pipeline/build_index.py SKIP_EXTS 一致 (略加 .xlsx 让 pipeline 也可处理)
SKIP_EXTS = {".pdf", ".pptx", ".ppt", ".doc"}

# 跟 pipeline/build_index.py SKIP_DIRS 一致
SKIP_DIRS = {
    "04_课件",
    "05_项目立项",
    "06_组织人员",
    "07_元数据",
    "99_抓取日志",
    "外战保障预案",
    "RAW",
}


class FileWatcher:
    """扫描 WATCH_DIRS, 对比 SyncDB 缓存, 返回变化文件

    同步接口, 单次 scan 是 O(n_files) stat, 不读文件内容.
    """

    def __init__(self, watch_dirs: List[Path], db: SyncDB):
        self.watch_dirs = [Path(d).resolve() for d in watch_dirs]
        self.db = db

    def _walk(self) -> List[Path]:
        """walk 所有 watch_dirs, 返回 indexable 文件 (排除 SKIP_DIRS + SKIP_EXTS)"""
        out: List[Path] = []
        for root in self.watch_dirs:
            if not root.exists():
                logger.debug("watch dir missing: %s", root)
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                # 排除 SKIP_DIRS (in-place 修改, 避免 walk 进去)
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for fn in filenames:
                    p = Path(dirpath) / fn
                    if p.suffix.lower() in SKIP_EXTS:
                        continue
                    out.append(p)
        return out

    def scan(self) -> Tuple[List[Path], List[Path]]:
        """扫描, 返回 (changed, new) - 不含 deleted

        changed: db 里有, 但 (mtime, size) 跟现在不一样
        new:     db 里没有
        """
        changed: List[Path] = []
        new: List[Path] = []

        files = self._walk()
        for p in files:
            try:
                st = p.stat()
            except OSError as e:
                logger.warning("stat failed for %s: %s", p, e)
                continue
            mtime = st.st_mtime
            size = st.st_size
            path_str = str(p)
            old = self.db.get(path_str)
            if old is None:
                new.append(p)
            elif old[0] != mtime or old[1] != size:
                changed.append(p)
            else:
                # 未变, 刷 last_seen (健康检查)
                self.db.touch_seen(path_str)
        return changed, new

    def scan_deleted(self, currently_seen: List[Path] | None = None) -> List[Path]:
        """找 db 里有但 fs 已删的 path

        currently_seen: 本轮 scan 已知的 path 列表 (避免重复 walk); 传 None 时走 _walk()
        """
        if currently_seen is None:
            currently_seen = self._walk()
        seen = {str(p) for p in currently_seen}
        known = self.db.all_paths()
        deleted_str = known - seen
        # deleted 一定是 watch_dirs 内的 (防止外部 dir 误判)
        deleted: List[Path] = []
        for s in deleted_str:
            p = Path(s)
            if any(str(p).startswith(str(d) + os.sep) or str(p) == str(d) for d in self.watch_dirs):
                deleted.append(p)
        return sorted(deleted)

    def update_cache(
        self,
        changed: List[Path],
        new: List[Path],
        deleted: List[Path],
    ) -> None:
        """把本轮变化写入 db (mtime/size + last_synced + delete)"""
        for p in changed + new:
            try:
                st = p.stat()
                self.db.upsert(str(p), st.st_mtime, st.st_size, last_synced=None)
            except OSError as e:
                logger.warning("update_cache stat failed for %s: %s", p, e)
        if deleted:
            for p in deleted:
                self.db.delete(str(p))

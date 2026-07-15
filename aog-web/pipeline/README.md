# AOG Pipeline

AOG 知识库数据 pipeline — 解析 md/docx/xlsx/pdf → 向量化 → 写 Chroma + SQLite

## 快速开始

```bash
uv sync --extra dev
uv run python -m pipeline.build_index --dry-run  # 扫描不写库
uv run pytest -v                                  # 单元测试
uv run python -m pipeline.build_index             # 全量 build
```

## 项目结构

- `pipeline/parsers/`     — md / docx / xlsx / pdf → markdown text
- `pipeline/extractors/`  — 从 markdown 抽 City / Experience / CorePlan 字段
- `pipeline/chunker.py`   — 800 token / overlap 100 文本分块
- `pipeline/embedder.py`  — bge-m3 embedding
- `pipeline/indexer.py`   — 写 Chroma + SQLite
- `pipeline/build_index.py` — CLI 主入口
- `data/`                  — 输出 (gitignore)

## 数据源

只读:
- `AOG知识库/01_AOG预案/`  → core_plans
- `AOG知识库/02_外战预案/` → cities (220+)
- `AOG知识库/03_保障经验/` → experiences (18)

## 字段对齐

所有字段严格按 `../CONTRACT.md` §1 定义。修改字段需先改 CONTRACT,这里跟着改。

## 输出

- `data/aog.db`           — SQLite 元数据
- `data/chroma/`          — Chroma 持久化
- `data/index_stats.json` — build 统计

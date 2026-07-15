#!/usr/bin/env bash
# AOG pipeline build 脚本
# 用法:
#   ./scripts/run_build.sh          # 全量 build
#   ./scripts/run_build.sh dry      # dry run
#   ./scripts/run_build.sh inc <abs1> <abs2> ...  # 增量

set -euo pipefail

cd "$(dirname "$0")/.."

MODE="${1:-build}"

case "$MODE" in
  dry)
    echo "[run_build] DRY RUN (no DB writes)"
    exec uv run python -m pipeline.build_index --dry-run
    ;;
  inc)
    shift
    echo "[run_build] INCREMENTAL paths: $*"
    exec uv run python -m pipeline.build_index --paths "$@"
    ;;
  build|"")
    echo "[run_build] FULL BUILD"
    exec uv run python -m pipeline.build_index
    ;;
  *)
    echo "Usage: $0 [build|dry|inc <paths>...]" >&2
    exit 2
    ;;
esac

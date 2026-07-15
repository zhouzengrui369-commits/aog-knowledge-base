"""测试 fixtures: 共享 KB 路径, 测试用 docx/md 路径等。"""
import os
import sys
from pathlib import Path

import pytest

# 把项目根加进 sys.path (这样 import pipeline 不需要 PYTHONPATH=)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

KB_ROOT = Path("/Users/njx/Project/AOG知识库/AOG知识库")
CITIES_DIR = KB_ROOT / "02_外战预案"
EXPERIENCES_DIR = KB_ROOT / "03_保障经验"
CORE_PLANS_DIR = KB_ROOT / "01_AOG预案"


@pytest.fixture(scope="session")
def kb_root() -> Path:
    if not KB_ROOT.exists():
        pytest.skip(f"KB_ROOT 不存在: {KB_ROOT}")
    return KB_ROOT


@pytest.fixture(scope="session")
def sample_city_docx(kb_root: Path) -> Path:
    """澳门 docx (典型 5 列)"""
    p = CITIES_DIR / "A-澳门.docx"
    if not p.exists():
        pytest.skip(f"样例不存在: {p}")
    return p


@pytest.fixture(scope="session")
def sample_experience_docx(kb_root: Path) -> Path:
    p = EXPERIENCES_DIR / "B787 风挡AOG处理流程.docx"
    if not p.exists():
        pytest.skip(f"样例不存在: {p}")
    return p


@pytest.fixture(scope="session")
def sample_core_plan_md(kb_root: Path) -> Path:
    p = CORE_PLANS_DIR / "AOG保障预案20260204.md"
    if not p.exists():
        pytest.skip(f"样例不存在: {p}")
    return p

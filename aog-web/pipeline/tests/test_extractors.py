"""Extractor 单元测试。"""
import re

import pytest

from pipeline.extractors import extract_city, extract_core_plan, extract_experience
from pipeline.extractors.city_meta import (
    REGION_DOMESTIC,
    REGION_INTL,
    parse_code_and_status,
    pinyin_of,
    region_from_name,
)


def test_pinyin_of():
    assert pinyin_of("北京大兴") == "beijingdaxing"
    assert pinyin_of("上海") == "shanghai"
    assert pinyin_of("") == ""


def test_region_from_name():
    assert region_from_name("广东") == "华南"
    assert region_from_name("日本") == "国际-亚洲"
    assert region_from_name("不存在的国家") == "国际-亚洲"  # fallback
    assert region_from_name("") == "国际-亚洲"


def test_parse_code_and_status():
    code, name, status, raw = parse_code_and_status("B-北京大兴.docx")
    assert code == "B-北京大兴"
    assert name == "北京大兴"
    assert status == "现行"
    assert raw == "B"

    # 暂停状态: code 保留后缀以保证主键唯一, name 去除后缀
    code, name, status, raw = parse_code_and_status("A-阿姆斯特丹（暂停）.docx")
    assert code == "A-阿姆斯特丹（暂停）"
    assert name == "阿姆斯特丹"
    assert status == "暂停"

    code, name, status, raw = parse_code_and_status("Q-青岛流亭（已废除）.docx")
    assert name == "青岛流亭"
    assert status == "已废"


def test_extract_city_ams_fallback():
    """docx 没写 IATA 时, 从城市名 fallback 字典查。"""
    from pathlib import Path

    p = Path("/Users/njx/Project/AOG知识库/AOG知识库/02_外战预案/A-阿姆斯特丹（暂停）.docx")
    if not p.exists():
        pytest.skip("样例不存在")
    city = extract_city(p)
    assert city.iata == "AMS"  # 从 COMMON_IATA fallback
    assert city.region == "国际-欧洲"  # 荷兰 → 欧洲


def test_extract_city_basic(sample_city_docx):
    city = extract_city(sample_city_docx)
    assert city.code.startswith("A-")
    assert city.name == "澳门"
    assert "机场" in city.airport
    assert city.iata == "MFM"
    assert city.region in {"华南", "国际-亚洲"}  # 澳门特殊,REGION_DOMESTIC 也有
    assert city.status == "现行"
    assert isinstance(city.fleet, list)
    assert len(city.fleet) >= 2, f"应至少有 2 个机型 (A320, A321), 实际 {len(city.fleet)}"
    assert isinstance(city.parts, list)
    assert len(city.parts) >= 3, f"应至少有 3 个航材, 实际 {len(city.parts)}"
    assert isinstance(city.contacts, list)
    assert len(city.contacts) >= 1, f"应至少有 1 个联系人, 实际 {len(city.contacts)}"
    assert isinstance(city.tags, list)
    assert city.pinyin, "pinyin 不能为空"
    assert len(city.content_md) > 100, "content_md 至少 100 字符"
    assert city.source_path.endswith("A-澳门.docx")


def test_extract_city_paused():
    from pathlib import Path

    p = Path("/Users/njx/Project/AOG知识库/AOG知识库/02_外战预案/A-阿姆斯特丹（暂停）.docx")
    if not p.exists():
        pytest.skip("样例不存在")
    city = extract_city(p)
    assert city.status == "暂停"
    assert city.name == "阿姆斯特丹"
    assert city.iata == "AMS"


def test_extract_experience_docx(sample_experience_docx):
    exp = extract_experience(sample_experience_docx)
    assert exp.id.startswith("exp-")
    assert "B787" in exp.title or "风挡" in exp.title
    assert exp.category in {"流程", "案例", "规范", "培训", "技术", "管理"}
    assert exp.status in {"现行", "历史", "待审", "已废"}
    assert isinstance(exp.tags, list)
    assert isinstance(exp.related_pn, list)
    assert len(exp.content_md) > 100, f"content_md 应该 > 100 字符, 实际 {len(exp.content_md)}"
    # 段落式 docx 应有 markdown heading
    assert "# " in exp.content_md or "## " in exp.content_md


def test_extract_core_plan_md(sample_core_plan_md):
    cp = extract_core_plan(sample_core_plan_md)
    assert cp.id.startswith("core-")
    assert cp.type in {"master", "checklist", "manual", "catalog"}
    assert cp.title
    assert len(cp.content_md) > 0
    assert cp.source_path.endswith(".md")


def test_extract_core_plan_xlsx():
    from pathlib import Path

    p = Path("/Users/njx/Project/AOG知识库/AOG知识库/01_AOG预案/AOG航材保障手册.xlsx")
    if not p.exists():
        pytest.skip("样例不存在")
    cp = extract_core_plan(p)
    assert cp.type == "manual"
    assert "手册" in cp.title or "AOG" in cp.title
    assert len(cp.content_md) > 50


def test_extract_core_plan_checklist():
    from pathlib import Path

    p = Path("/Users/njx/Project/AOG知识库/AOG知识库/01_AOG预案/AOG保障检查单模板R2.xlsx")
    if not p.exists():
        pytest.skip("样例不存在")
    cp = extract_core_plan(p)
    assert cp.type == "checklist"

"""Parser 单元测试。"""
import pytest

from pipeline.parsers import parse_docx, parse_md, parse_pdf, parse_xlsx
from pipeline.parsers.docx import docx_table_to_markdown


def test_parse_md_simple(tmp_path):
    p = tmp_path / "test.md"
    p.write_text("# Title\n\nparagraph one\n\nparagraph two", encoding="utf-8")
    out = parse_md(p)
    assert "Title" in out
    assert "paragraph one" in out


def test_parse_md_strip_frontmatter(tmp_path):
    from pipeline.parsers.md import parse_md_strip_frontmatter

    p = tmp_path / "test.md"
    p.write_text("---\ntags: [AOG]\n---\n\nbody", encoding="utf-8")
    fm, body = parse_md_strip_frontmatter(p)
    assert "tags" in fm
    assert "body" in body


def test_parse_docx_real(sample_city_docx):
    dt = parse_docx(sample_city_docx)
    assert len(dt.sections) > 0
    # 至少应有 机场信息 section
    section_names = [s.name for s in dt.sections]
    assert any("机场信息" in n for n in section_names), f"未找到机场信息 section: {section_names}"
    # 第一个 title row 应是机场名
    assert dt.title_rows, "未找到 title row"
    assert "机场" in dt.title_rows[0][0] or "国际机场" in dt.title_rows[0][0]


def test_docx_to_markdown(sample_city_docx):
    dt = parse_docx(sample_city_docx)
    md = docx_table_to_markdown(dt)
    assert "## 机场信息" in md
    assert "## 航材保障预案" in md
    # markdown table 格式
    assert "|" in md


def test_parse_xlsx_real(sample_experience_docx):
    """经验目录里没 xlsx, 跳到 core_plan xlsx"""
    from pathlib import Path

    cp_xlsx = Path("/Users/njx/Project/AOG知识库/AOG知识库/01_AOG预案/AOG航材保障手册.xlsx")
    if not cp_xlsx.exists():
        pytest.skip("core plan xlsx 样例不存在")
    md = parse_xlsx(cp_xlsx)
    assert len(md) > 0
    assert "|" in md  # markdown table


def test_parse_pdf_real():
    """v1 不索引 pdf, 但 parser 仍应能跑 (pypdf 抽文字)"""
    from pathlib import Path

    pdf = Path("/Users/njx/Project/AOG知识库/AOG知识库/03_保障经验/AOG保障工作流R1.pdf")
    if not pdf.exists():
        pytest.skip("pdf 样例不存在")
    text = parse_pdf(pdf)
    # pypdf 可能返回空, 但不该抛异常
    assert isinstance(text, str)

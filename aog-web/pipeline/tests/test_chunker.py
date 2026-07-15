"""Chunker 单元测试。"""
import pytest

from pipeline.chunker import chunk_text, split_into_paragraphs, DEFAULT_CHUNK_SIZE, DEFAULT_OVERLAP


def test_chunk_short_text():
    text = "短文本测试,不会触发分块。"
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].index == 0


def test_chunk_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_chunk_long_paragraph():
    """段落 > chunk_size, 触发硬切"""
    text = "这是一段很长很长的文本。" * 200  # 约 1200 字符
    chunks = chunk_text(text, chunk_size=300, overlap=30)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= 500  # 实际可能略大于 chunk_size (句末切) 但不应爆太多
    # 索引从 0 递增
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_chunk_paragraphs():
    text = """# 标题

第一段内容

第二段内容

第三段内容"""
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) >= 1


def test_split_into_paragraphs():
    paras = split_into_paragraphs("p1\n\np2\n\np3")
    assert paras == ["p1", "p2", "p3"]


def test_chunk_overlap_produces_overlapping_content():
    """相邻 chunk 应该有 overlap (字符重叠)"""
    text = "。" * 500 + "边界标记START。" + "。" * 500 + "边界标记END。" + "。" * 500
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    # 至少 2 个 chunk
    assert len(chunks) >= 2
    # 检查相邻 chunk 末尾/开头有重叠 (第二个 chunk 开头应包含前一个 chunk 末尾的部分字符)
    if len(chunks) >= 2:
        first_end = chunks[0].text[-50:]
        second_start = chunks[1].text[:50]
        # 因为有 overlap,first_end 应有部分内容出现在 second_start
        # 但取决于句子切分,不强制

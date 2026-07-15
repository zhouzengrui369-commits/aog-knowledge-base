"""单元测试 - config + LLM 工厂 + 兜底逻辑"""
import pytest

from aog_web.config import Settings, get_settings, reset_settings_cache
from aog_web.services.llm import MockLLM, get_llm


def test_settings_is_mock_when_no_key(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    reset_settings_cache()
    s = get_settings()
    assert s.is_mock_llm is True


def test_settings_is_live_when_key_set(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key-123")
    reset_settings_cache()
    s = get_settings()
    assert s.is_mock_llm is False
    # 恢复
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    reset_settings_cache()


def test_settings_cors_origins_parsed():
    reset_settings_cache()
    s = get_settings()
    assert isinstance(s.cors_origins, list)
    assert "http://localhost:3000" in s.cors_origins


def test_settings_paths_resolved():
    reset_settings_cache()
    s = get_settings()
    assert s.sqlite_path.is_absolute()
    assert s.chroma_path.is_absolute()
    assert s.data_dir.is_absolute()


def test_settings_log_level_validation():
    s = Settings(LOG_LEVEL="debug")
    assert s.LOG_LEVEL == "DEBUG"
    s2 = Settings(LOG_LEVEL="invalid")
    assert s2.LOG_LEVEL == "INFO"


@pytest.mark.asyncio
async def test_mock_llm_returns_text():
    m = MockLLM()
    out = await m.chat([{"role": "user", "content": "B787 风挡 AOG 怎么处理？"}])
    assert "Mock 模式" in out
    assert len(out) > 0


@pytest.mark.asyncio
async def test_mock_llm_handles_contact_question():
    m = MockLLM()
    out = await m.chat([{"role": "user", "content": "浦东 AOG 联系人是谁？"}])
    assert "联系" in out or "联系人" in out


@pytest.mark.asyncio
async def test_mock_llm_counts_context_refs():
    m = MockLLM()
    sys_msg = "参考资料:\n1. doc1\n2. doc2\n3. doc3\n"
    out = await m.chat([
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": "B787"},
    ])
    assert "3" in out  # 命中数


def test_get_llm_returns_mock_when_no_key(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    reset_settings_cache()
    s = get_settings()
    llm = get_llm(settings=s)
    assert isinstance(llm, MockLLM)
    assert llm.model == "minimax-m3" or "mock" in llm.model


def test_get_llm_raises_for_unknown_when_key_set(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    reset_settings_cache()
    s = get_settings()
    with pytest.raises(Exception):
        # unknown name 不在注册表里, 也不是 minimax 前缀
        get_llm(name="totally-unknown-llm-xxx", settings=s)
    # 恢复
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    reset_settings_cache()

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from core.llm import _read_rc_section, _strip_code_fences, load_llm_config, LLMConfig


def _write_rc(tmp_path: Path, content: str) -> None:
    """Helper: write content to tmp_path/.dockerbrain/.dockerbrainrc."""
    rc_dir = tmp_path / ".dockerbrain"
    rc_dir.mkdir(exist_ok=True)
    (rc_dir / ".dockerbrainrc").write_text(content, encoding="utf-8")


class TestReadRcSection:
    def test_reads_llm_section(self, tmp_path):
        _write_rc(
            tmp_path,
            '[llm]\nprovider = "gemini"\nmodel = "flash"\napi_key = "abc123"\n',
        )
        with patch("core.llm.Path.home", return_value=tmp_path):
            data = _read_rc_section("llm")
        assert data["provider"] == "gemini"
        assert data["model"] == "flash"
        assert data["api_key"] == "abc123"

    def test_strips_inline_comments(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nmodel = "flash" # fast model\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            data = _read_rc_section("llm")
        assert data["model"] == "flash"

    def test_strips_quotes(self, tmp_path):
        _write_rc(tmp_path, "[llm]\nmodel = 'single-quoted'\n")
        with patch("core.llm.Path.home", return_value=tmp_path):
            assert _read_rc_section("llm")["model"] == "single-quoted"

    def test_ignores_other_sections(self, tmp_path):
        _write_rc(tmp_path, '[monitor]\ninterval = 5\n[llm]\nmodel = "test"\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            data = _read_rc_section("llm")
        assert "interval" not in data
        assert data["model"] == "test"

    def test_missing_file_returns_empty(self, tmp_path):
        with patch("core.llm.Path.home", return_value=tmp_path):
            assert _read_rc_section("llm") == {}

    def test_skips_comments_and_blanks(self, tmp_path):
        _write_rc(tmp_path, '# comment\n\n[llm]\n# another comment\nmodel = "x"\n\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            data = _read_rc_section("llm")
        assert data == {"model": "x"}

    def test_reads_monitor_section(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nmodel = "x"\n[monitor]\ninterval = 10\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            data = _read_rc_section("monitor")
        assert data["interval"] == "10"


class TestStripCodeFences:
    def test_strips_json_fences(self):
        text = '```json\n{"key": "value"}\n```'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_strips_generic_fences(self):
        text = "```\nsome content\n```"
        assert _strip_code_fences(text) == "some content"

    def test_no_fences(self):
        text = '{"key": "value"}'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_empty_string(self):
        assert _strip_code_fences("") == ""

    def test_whitespace_around_fences(self):
        text = "  ```dockerfile\nFROM alpine\n```  "
        assert "FROM alpine" in _strip_code_fences(text)

    def test_only_opening_fence(self):
        text = "```\ncontent here"
        result = _strip_code_fences(text)
        assert "content here" in result

    def test_only_closing_fence(self):
        text = "some text\n```"
        result = _strip_code_fences(text)
        assert "some text" in result


class TestLoadLlmConfig:
    def test_default_gemini_config(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "gemini"\napi_key = "test-key"\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.provider == "gemini"
        assert cfg.api_key == "test-key"
        assert cfg.model == "gemini-3.1-flash-lite-preview"

    def test_chatgpt_config(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "chatgpt"\napi_key = "sk-test"\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.provider == "chatgpt"
        assert cfg.model == "gpt-5.4-mini"
        assert "api.openai.com" in cfg.base_url

    def test_claude_config(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "claude"\napi_key = "sk-ant-test"\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.provider == "claude"
        assert cfg.model == "claude-sonnet-4-6"
        assert cfg.base_url == ""

    def test_groq_config(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "groq"\napi_key = "gsk_test"\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.provider == "groq"
        assert "groq.com" in cfg.base_url

    def test_ollama_no_key_required(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "ollama"\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.provider == "ollama"
        assert cfg.api_key == "ollama"
        assert "localhost" in cfg.base_url

    def test_custom_model(self, tmp_path):
        _write_rc(
            tmp_path,
            '[llm]\nprovider = "gemini"\nmodel = "custom-model"\napi_key = "key"\n',
        )
        with patch("core.llm.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.model == "custom-model"

    def test_custom_base_url(self, tmp_path):
        _write_rc(
            tmp_path,
            '[llm]\nprovider = "ollama"\nbase_url = "http://myhost:11434/v1"\n',
        )
        with patch("core.llm.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.base_url == "http://myhost:11434/v1"

    def test_invalid_provider_exits(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "invalid_provider"\napi_key = "x"\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit):
                load_llm_config()

    def test_missing_api_key_exits(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "gemini"\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit):
                load_llm_config()

    def test_missing_rc_file_defaults_to_gemini(self, tmp_path):
        with patch("core.llm.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit):
                load_llm_config()

    def test_provider_case_insensitive(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "GEMINI"\napi_key = "key"\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.provider == "gemini"

    def test_returns_llm_config_dataclass(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "gemini"\napi_key = "k"\n')
        with patch("core.llm.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert isinstance(cfg, LLMConfig)

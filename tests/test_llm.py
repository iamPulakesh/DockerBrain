from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from dockerbrain.config.rc_file import read_rc_section
from dockerbrain.config.settings import load_llm_config, LLMConfig
from dockerbrain.llm.base import strip_code_fences


def _write_rc(tmp_path: Path, content: str) -> None:
    """Helper: write content to tmp_path/.dockerbrain/.dockerbrainrc."""
    rc_dir = tmp_path / ".dockerbrain"
    rc_dir.mkdir(exist_ok=True)
    (rc_dir / ".dockerbrainrc").write_text(content, encoding="utf-8")


class TestReadRcSection:
    def test_reads_llm_section(self, tmp_path):
        _write_rc(
            tmp_path,
            '[llm]\nprovider = "openai"\nmodel = "gpt-5.4-mini"\napi_key = "abc123"\n',
        )
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            data = read_rc_section("llm")
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-5.4-mini"
        assert data["api_key"] == "abc123"

    def test_strips_inline_comments(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nmodel = "flash" # fast model\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            data = read_rc_section("llm")
        assert data["model"] == "flash"

    def test_strips_quotes(self, tmp_path):
        _write_rc(tmp_path, "[llm]\nmodel = 'single-quoted'\n")
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            assert read_rc_section("llm")["model"] == "single-quoted"

    def test_ignores_other_sections(self, tmp_path):
        _write_rc(tmp_path, '[monitor]\ninterval = 5\n[llm]\nmodel = "test"\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            data = read_rc_section("llm")
        assert "interval" not in data
        assert data["model"] == "test"

    def test_missing_file_returns_empty(self, tmp_path):
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            assert read_rc_section("llm") == {}

    def test_skips_comments_and_blanks(self, tmp_path):
        _write_rc(tmp_path, '# comment\n\n[llm]\n# another comment\nmodel = "x"\n\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            data = read_rc_section("llm")
        assert data == {"model": "x"}

    def test_reads_monitor_section(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nmodel = "x"\n[monitor]\ninterval = 10\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            data = read_rc_section("monitor")
        assert data["interval"] == "10"


class TestStripCodeFences:
    def test_strips_json_fences(self):
        text = '```json\n{"key": "value"}\n```'
        assert strip_code_fences(text) == '{"key": "value"}'

    def test_strips_generic_fences(self):
        text = "```\nsome content\n```"
        assert strip_code_fences(text) == "some content"

    def test_no_fences(self):
        text = '{"key": "value"}'
        assert strip_code_fences(text) == '{"key": "value"}'

    def test_empty_string(self):
        assert strip_code_fences("") == ""

    def test_whitespace_around_fences(self):
        text = "  ```dockerfile\nFROM alpine\n```  "
        assert "FROM alpine" in strip_code_fences(text)

    def test_only_opening_fence(self):
        text = "```\ncontent here"
        result = strip_code_fences(text)
        assert "content here" in result

    def test_only_closing_fence(self):
        text = "some text\n```"
        result = strip_code_fences(text)
        assert "some text" in result


class TestLoadLlmConfig:
    def test_default_openai_config(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "openai"\nmodel = "gpt-5.4-mini"\napi_key = "test-key"\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.provider == "openai"
        assert cfg.api_key == "test-key"
        assert cfg.model == "gpt-5.4-mini"

    def test_openai_base_url(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "openai"\nmodel = "gpt-5.4-mini"\napi_key = "sk-test"\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-5.4-mini"
        assert "api.openai.com" in cfg.base_url

    def test_anthropic_config(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "anthropic"\nmodel = "claude-sonnet-4-6"\napi_key = "sk-ant-test"\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-sonnet-4-6"
        assert cfg.base_url == ""

    def test_custom_model(self, tmp_path):
        _write_rc(
            tmp_path,
            '[llm]\nprovider = "openai"\nmodel = "custom-model"\napi_key = "key"\n',
        )
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.model == "custom-model"

    def test_invalid_provider_exits(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "invalid_provider"\napi_key = "x"\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            with pytest.raises(ValueError, match="Unknown LLM provider"):
                load_llm_config()

    def test_missing_api_key_exits(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "openai"\nmodel = "m"\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            with pytest.raises(ValueError, match="Missing API key"):
                load_llm_config()

    def test_missing_rc_file_raises_error(self, tmp_path):
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            with pytest.raises(ValueError, match="Missing 'provider'"):
                load_llm_config()

    def test_provider_case_insensitive(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "OPENAI"\nmodel = "gpt"\napi_key = "key"\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert cfg.provider == "openai"

    def test_returns_llm_config_dataclass(self, tmp_path):
        _write_rc(tmp_path, '[llm]\nprovider = "openai"\nmodel = "m"\napi_key = "k"\n')
        with patch("dockerbrain.config.rc_file.Path.home", return_value=tmp_path):
            cfg = load_llm_config()
        assert isinstance(cfg, LLMConfig)

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from core.ai_advisor import AIAdvisor, _render_compact_table


class TestRenderCompactTable:
    def test_valid_container_json(self, capsys):
        data = json.dumps([
            {"container": "web", "issue": "High CPU", "recommendation": "Scale horizontally"}
        ])
        _render_compact_table(data)
        out = capsys.readouterr().out
        assert "web" in out
        assert "High CPU" in out

    def test_valid_dockerfile_json(self, capsys):
        data = json.dumps([
            {"line": 5, "issue": "Large base image", "recommendation": "Use alpine"}
        ])
        _render_compact_table(data)
        out = capsys.readouterr().out
        assert "Large base image" in out

    def test_empty_array(self, capsys):
        _render_compact_table("[]")
        out = capsys.readouterr().out
        assert "No issues found" in out

    def test_invalid_json(self, capsys):
        _render_compact_table("not valid json at all")
        out = capsys.readouterr().out
        assert "Parse Error" in out or "Could not parse" in out

    def test_strips_code_fences(self, capsys):
        data = '```json\n[{"container":"a","issue":"b","recommendation":"c"}]\n```'
        _render_compact_table(data)
        out = capsys.readouterr().out
        assert "a" in out

    def test_multiple_findings_count(self, capsys):
        data = json.dumps([
            {"container": "a", "issue": "x", "recommendation": "y"},
            {"container": "b", "issue": "x2", "recommendation": "y2"},
            {"container": "c", "issue": "x3", "recommendation": "y3"},
        ])
        _render_compact_table(data)
        out = capsys.readouterr().out
        assert "3 finding(s)" in out


class TestBuildContainerPrompt:
    @patch("core.ai_advisor.docker.from_env")
    @patch("core.ai_advisor.get_all_container_names", return_value=["web-app"])
    @patch("core.ai_advisor.get_metrics_since")
    @patch("core.ai_advisor.load_llm_config")
    def test_includes_metrics(self, mock_cfg, mock_metrics, mock_names, mock_docker):
        mock_cfg.return_value = MagicMock()
        mock_metrics.return_value = [
            {
                "container": "web-app",
                "cpu_percent": 15.0,
                "mem_usage_mb": 256.0,
                "mem_limit_mb": 512.0,
                "mem_percent": 50.0,
                "idle_polls": 0,
            },
            {
                "container": "web-app",
                "cpu_percent": 25.0,
                "mem_usage_mb": 300.0,
                "mem_limit_mb": 512.0,
                "mem_percent": 58.6,
                "idle_polls": 0,
            },
        ]
        mock_docker.side_effect = Exception("no docker")

        advisor = AIAdvisor()
        prompt = advisor._build_container_prompt("web-app", window_minutes=30)

        assert "web-app" in prompt
        assert "Avg CPU" in prompt
        assert "Peak Memory" in prompt
        assert "300.0" in prompt

    @patch("core.ai_advisor.docker.from_env")
    @patch("core.ai_advisor.get_all_container_names", return_value=[])
    @patch("core.ai_advisor.get_metrics_since", return_value=[])
    @patch("core.ai_advisor.load_llm_config")
    def test_handles_no_data(self, mock_cfg, mock_metrics, mock_names, mock_docker):
        mock_cfg.return_value = MagicMock()
        advisor = AIAdvisor()
        prompt = advisor._build_container_prompt(None, window_minutes=30)
        assert "Container Metrics Report" in prompt

    @patch("core.ai_advisor.docker.from_env")
    @patch("core.ai_advisor.get_all_container_names", return_value=["a", "b"])
    @patch("core.ai_advisor.get_metrics_since", return_value=[])
    @patch("core.ai_advisor.load_llm_config")
    def test_includes_all_containers_when_none_specified(
        self, mock_cfg, mock_metrics, mock_names, mock_docker,
    ):
        mock_cfg.return_value = MagicMock()
        mock_docker.side_effect = Exception("no docker")
        advisor = AIAdvisor()
        prompt = advisor._build_container_prompt(None, window_minutes=30)
        assert "### a" in prompt
        assert "### b" in prompt

    @patch("core.ai_advisor.docker.from_env")
    @patch("core.ai_advisor.get_all_container_names", return_value=["x"])
    @patch("core.ai_advisor.get_metrics_since")
    @patch("core.ai_advisor.load_llm_config")
    def test_no_rules_flag_skips_optimizer(
        self, mock_cfg, mock_metrics, mock_names, mock_docker,
    ):
        mock_cfg.return_value = MagicMock()
        mock_metrics.return_value = []
        mock_docker.side_effect = Exception("no docker")
        advisor = AIAdvisor()
        prompt = advisor._build_container_prompt(None, window_minutes=30, no_rules=True)
        assert "Rule-Based Findings" in prompt
        assert "None" in prompt


class TestBuildDockerfilePrompt:
    @patch("core.ai_advisor.load_llm_config")
    def test_includes_file_content(self, mock_cfg, tmp_path):
        mock_cfg.return_value = MagicMock()
        df = tmp_path / "Dockerfile"
        df.write_text("FROM python:3.12\nRUN pip install flask\nCMD flask run")

        advisor = AIAdvisor()
        prompt = advisor._build_dockerfile_prompt(str(df))

        assert "FROM python:3.12" in prompt
        assert "pip install flask" in prompt

    @patch("core.ai_advisor.load_llm_config")
    def test_missing_dockerfile_exits(self, mock_cfg):
        mock_cfg.return_value = MagicMock()
        advisor = AIAdvisor()
        with pytest.raises(SystemExit):
            advisor._build_dockerfile_prompt("/nonexistent/Dockerfile")

    @patch("core.ai_advisor.load_llm_config")
    def test_detects_dockerignore_exists(self, mock_cfg, tmp_path):
        mock_cfg.return_value = MagicMock()
        df = tmp_path / "Dockerfile"
        df.write_text("FROM alpine")
        (tmp_path / ".dockerignore").write_text("node_modules")

        advisor = AIAdvisor()
        prompt = advisor._build_dockerfile_prompt(str(df))
        assert "already exists" in prompt

    @patch("core.ai_advisor.load_llm_config")
    def test_detects_dockerignore_missing(self, mock_cfg, tmp_path):
        mock_cfg.return_value = MagicMock()
        df = tmp_path / "Dockerfile"
        df.write_text("FROM alpine")

        advisor = AIAdvisor()
        prompt = advisor._build_dockerfile_prompt(str(df))
        assert "No .dockerignore" in prompt


class TestRunAiSuggest:
    @patch("core.ai_advisor.AIAdvisor.suggest_for_dockerfile")
    @patch("core.ai_advisor.load_llm_config")
    def test_routes_to_dockerfile_mode(self, mock_cfg, mock_suggest):
        mock_cfg.return_value = MagicMock()
        from core.ai_advisor import run_ai_suggest
        run_ai_suggest(dockerfile_path="/some/Dockerfile")
        mock_suggest.assert_called_once_with("/some/Dockerfile")

    @patch("core.ai_advisor.AIAdvisor.suggest_for_containers")
    @patch("core.ai_advisor.load_llm_config")
    def test_routes_to_container_mode(self, mock_cfg, mock_suggest):
        mock_cfg.return_value = MagicMock()
        from core.ai_advisor import run_ai_suggest
        run_ai_suggest(container_name="web", window_minutes=15, no_rules=True)
        mock_suggest.assert_called_once_with(
            container_name="web", window_minutes=15, no_rules=True,
        )

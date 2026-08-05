from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from dockerbrain.advisor.service import AIAdvisor, run_ai_suggest
from dockerbrain.ui.cli.tables import render_findings_table, parse_findings_json
from dockerbrain.ui.cli.panels import print_parse_error


class TestRenderCompactTable:
    def test_valid_container_json(self, capsys):
        data = [
            {"container": "web", "issue": "High CPU", "recommendation": "Scale horizontally"}
        ]
        render_findings_table(data, mode="container")
        out = capsys.readouterr().out
        assert "web" in out
        assert "High CPU" in out

    def test_valid_dockerfile_json(self, capsys):
        data = [
            {"line": 5, "issue": "Large base image", "recommendation": "Use alpine"}
        ]
        render_findings_table(data, mode="dockerfile")
        out = capsys.readouterr().out
        assert "Large base image" in out

    def test_empty_array(self, capsys):
        render_findings_table([], mode="container")
        out = capsys.readouterr().out
        assert "No issues found" in out

    def test_invalid_json(self, capsys):
        result = parse_findings_json("not valid json at all")
        assert result is None

    def test_strips_code_fences(self, capsys):
        raw = '```json\n[{"container":"a","issue":"b","recommendation":"c"}]\n```'
        findings = parse_findings_json(raw)
        assert findings is not None
        render_findings_table(findings, mode="container")
        out = capsys.readouterr().out
        assert "a" in out

    def test_multiple_findings_count(self, capsys):
        data = [
            {"container": "a", "issue": "x", "recommendation": "y"},
            {"container": "b", "issue": "x2", "recommendation": "y2"},
            {"container": "c", "issue": "x3", "recommendation": "y3"},
        ]
        render_findings_table(data, mode="container")
        out = capsys.readouterr().out
        assert "3 finding(s)" in out


class TestBuildContainerPrompt:
    @patch("dockerbrain.advisor.service.get_provider")
    @patch("dockerbrain.advisor.service.docker.from_env")
    @patch("dockerbrain.advisor.service.MetricsRepository")
    @patch("dockerbrain.advisor.service.load_llm_config")
    def test_includes_metrics(self, mock_cfg, mock_repo_cls, mock_docker, mock_provider):
        mock_cfg.return_value = MagicMock(provider="gemini")
        mock_provider.return_value = MagicMock()
        repo = MagicMock()
        repo.get_since.return_value = [
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
        repo.get_all_container_names.return_value = ["web-app"]
        mock_repo_cls.return_value = repo
        mock_docker.side_effect = Exception("no docker")

        advisor = AIAdvisor()
        advisor._metrics_repo = repo
        prompt = advisor._build_container_prompt("web-app", window_minutes=30)

        assert "web-app" in prompt
        assert "Avg CPU" in prompt
        assert "Peak Memory" in prompt
        assert "300.0" in prompt

    @patch("dockerbrain.advisor.service.get_provider")
    @patch("dockerbrain.advisor.service.docker.from_env")
    @patch("dockerbrain.advisor.service.MetricsRepository")
    @patch("dockerbrain.advisor.service.load_llm_config")
    def test_handles_no_data(self, mock_cfg, mock_repo_cls, mock_docker, mock_provider):
        mock_cfg.return_value = MagicMock(provider="gemini")
        mock_provider.return_value = MagicMock()
        repo = MagicMock()
        repo.get_since.return_value = []
        repo.get_all_container_names.return_value = []
        mock_repo_cls.return_value = repo
        advisor = AIAdvisor()
        advisor._metrics_repo = repo
        prompt = advisor._build_container_prompt(None, window_minutes=30)
        assert "Container Metrics Report" in prompt

    @patch("dockerbrain.advisor.service.get_provider")
    @patch("dockerbrain.advisor.service.docker.from_env")
    @patch("dockerbrain.advisor.service.MetricsRepository")
    @patch("dockerbrain.advisor.service.load_llm_config")
    def test_includes_all_containers_when_none_specified(
        self, mock_cfg, mock_repo_cls, mock_docker, mock_provider,
    ):
        mock_cfg.return_value = MagicMock(provider="gemini")
        mock_provider.return_value = MagicMock()
        repo = MagicMock()
        repo.get_since.return_value = []
        repo.get_all_container_names.return_value = ["a", "b"]
        mock_repo_cls.return_value = repo
        mock_docker.side_effect = Exception("no docker")
        advisor = AIAdvisor()
        advisor._metrics_repo = repo
        prompt = advisor._build_container_prompt(None, window_minutes=30)
        assert "### a" in prompt
        assert "### b" in prompt

    @patch("dockerbrain.advisor.service.get_provider")
    @patch("dockerbrain.advisor.service.docker.from_env")
    @patch("dockerbrain.advisor.service.MetricsRepository")
    @patch("dockerbrain.advisor.service.load_llm_config")
    def test_no_rules_flag_skips_optimizer(
        self, mock_cfg, mock_repo_cls, mock_docker, mock_provider,
    ):
        mock_cfg.return_value = MagicMock(provider="gemini")
        mock_provider.return_value = MagicMock()
        repo = MagicMock()
        repo.get_since.return_value = []
        repo.get_all_container_names.return_value = ["x"]
        mock_repo_cls.return_value = repo
        mock_docker.side_effect = Exception("no docker")
        advisor = AIAdvisor()
        advisor._metrics_repo = repo
        prompt = advisor._build_container_prompt(None, window_minutes=30, no_rules=True)
        assert "Rule-Based Findings" in prompt
        assert "None" in prompt


class TestBuildDockerfilePrompt:
    @patch("dockerbrain.advisor.service.get_provider")
    @patch("dockerbrain.advisor.service.load_llm_config")
    def test_includes_file_content(self, mock_cfg, mock_provider, tmp_path):
        mock_cfg.return_value = MagicMock(provider="gemini")
        mock_provider.return_value = MagicMock()
        df = tmp_path / "Dockerfile"
        df.write_text("FROM python:3.12\nRUN pip install flask\nCMD flask run")

        advisor = AIAdvisor()
        prompt = advisor._build_dockerfile_prompt(str(df))

        assert "FROM python:3.12" in prompt
        assert "pip install flask" in prompt

    @patch("dockerbrain.advisor.service.get_provider")
    @patch("dockerbrain.advisor.service.load_llm_config")
    def test_missing_dockerfile_exits(self, mock_cfg, mock_provider):
        mock_cfg.return_value = MagicMock(provider="gemini")
        mock_provider.return_value = MagicMock()
        advisor = AIAdvisor()
        with pytest.raises(SystemExit):
            advisor._build_dockerfile_prompt("/nonexistent/Dockerfile")

    @patch("dockerbrain.advisor.service.get_provider")
    @patch("dockerbrain.advisor.service.load_llm_config")
    def test_detects_dockerignore_exists(self, mock_cfg, mock_provider, tmp_path):
        mock_cfg.return_value = MagicMock(provider="gemini")
        mock_provider.return_value = MagicMock()
        df = tmp_path / "Dockerfile"
        df.write_text("FROM alpine")
        (tmp_path / ".dockerignore").write_text("node_modules")

        advisor = AIAdvisor()
        prompt = advisor._build_dockerfile_prompt(str(df))
        assert "already exists" in prompt

    @patch("dockerbrain.advisor.service.get_provider")
    @patch("dockerbrain.advisor.service.load_llm_config")
    def test_detects_dockerignore_missing(self, mock_cfg, mock_provider, tmp_path):
        mock_cfg.return_value = MagicMock(provider="gemini")
        mock_provider.return_value = MagicMock()
        df = tmp_path / "Dockerfile"
        df.write_text("FROM alpine")

        advisor = AIAdvisor()
        prompt = advisor._build_dockerfile_prompt(str(df))
        assert "No .dockerignore" in prompt


class TestRunAiSuggest:
    @patch("dockerbrain.advisor.service.AIAdvisor.suggest_for_dockerfile")
    @patch("dockerbrain.advisor.service.get_provider")
    @patch("dockerbrain.advisor.service.load_llm_config")
    def test_routes_to_dockerfile_mode(self, mock_cfg, mock_provider, mock_suggest):
        mock_cfg.return_value = MagicMock(provider="gemini")
        mock_provider.return_value = MagicMock()
        run_ai_suggest(dockerfile_path="/some/Dockerfile")
        mock_suggest.assert_called_once_with("/some/Dockerfile")

    @patch("dockerbrain.advisor.service.AIAdvisor.suggest_for_containers")
    @patch("dockerbrain.advisor.service.get_provider")
    @patch("dockerbrain.advisor.service.load_llm_config")
    def test_routes_to_container_mode(self, mock_cfg, mock_provider, mock_suggest):
        mock_cfg.return_value = MagicMock(provider="gemini")
        mock_provider.return_value = MagicMock()
        run_ai_suggest(container_name="web", window_minutes=15, no_rules=True)
        mock_suggest.assert_called_once_with(
            container_name="web", window_minutes=15, no_rules=True,
        )

from __future__ import annotations

from pathlib import Path

from core.dockerizer import _scan_project, _LANGUAGE_SIGNATURES, _SKIP_DIRS


class TestScanProject:
    def test_detects_python(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        (tmp_path / "app.py").write_text("print('hello')\n")
        result = _scan_project(tmp_path)
        assert "Python" in result["detected_languages"]

    def test_detects_node(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "app"}\n')
        result = _scan_project(tmp_path)
        assert "Node.js" in result["detected_languages"]

    def test_detects_go(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/app\n")
        result = _scan_project(tmp_path)
        assert "Go" in result["detected_languages"]

    def test_detects_rust(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'app'\n")
        result = _scan_project(tmp_path)
        assert "Rust" in result["detected_languages"]

    def test_detects_multiple_languages(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        (tmp_path / "package.json").write_text('{"name": "app"}\n')
        result = _scan_project(tmp_path)
        assert "Python" in result["detected_languages"]
        assert "Node.js" in result["detected_languages"]

    def test_no_language_detected(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello\n")
        result = _scan_project(tmp_path)
        assert result["detected_languages"] == []

    def test_reads_key_files(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask\nrequests\n")
        result = _scan_project(tmp_path)
        assert "requirements.txt" in result["key_files"]
        assert "flask" in result["key_files"]["requirements.txt"]

    def test_max_5_key_files(self, tmp_path):
        files = [
            "requirements.txt", "pyproject.toml", "setup.py",
            "package.json", "go.mod", "Cargo.toml",
        ]
        for f in files:
            (tmp_path / f).write_text("content\n")
        result = _scan_project(tmp_path)
        assert len(result["key_files"]) <= 5

    def test_detects_existing_dockerfile(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM alpine\n")
        result = _scan_project(tmp_path)
        assert result["has_dockerfile"] is True

    def test_detects_missing_dockerfile(self, tmp_path):
        result = _scan_project(tmp_path)
        assert result["has_dockerfile"] is False

    def test_detects_existing_dockerignore(self, tmp_path):
        (tmp_path / ".dockerignore").write_text("node_modules\n")
        result = _scan_project(tmp_path)
        assert result["has_dockerignore"] is True

    def test_skips_venv_directory(self, tmp_path):
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
        result = _scan_project(tmp_path)
        assert ".venv" not in result["tree"]

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "express").mkdir()
        result = _scan_project(tmp_path)
        assert "node_modules" not in result["tree"]

    def test_tree_includes_files(self, tmp_path):
        (tmp_path / "main.py").write_text("pass\n")
        (tmp_path / "utils.py").write_text("pass\n")
        result = _scan_project(tmp_path)
        assert "main.py" in result["tree"]
        assert "utils.py" in result["tree"]

    def test_tree_includes_subdirectories(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("pass\n")
        result = _scan_project(tmp_path)
        assert "src/" in result["tree"]

    def test_empty_directory(self, tmp_path):
        result = _scan_project(tmp_path)
        assert result["tree"] == ""
        assert result["detected_languages"] == []
        assert result["key_files"] == {}
        assert result["has_dockerfile"] is False
        assert result["has_dockerignore"] is False


class TestSkipDirs:
    def test_common_dirs_in_skip_list(self):
        assert ".git" in _SKIP_DIRS
        assert "node_modules" in _SKIP_DIRS
        assert "__pycache__" in _SKIP_DIRS
        assert ".venv" in _SKIP_DIRS
        assert "venv" in _SKIP_DIRS

    def test_build_dirs_in_skip_list(self):
        assert "dist" in _SKIP_DIRS
        assert "build" in _SKIP_DIRS
        assert "target" in _SKIP_DIRS


class TestLanguageSignatures:
    def test_covers_major_languages(self):
        langs = set(_LANGUAGE_SIGNATURES.keys())
        assert "Python" in langs
        assert "Node.js" in langs
        assert "Go" in langs
        assert "Rust" in langs
        assert "Java/Kotlin" in langs
        assert "Ruby" in langs
        assert "PHP" in langs

    def test_each_language_has_signatures(self):
        for lang, sigs in _LANGUAGE_SIGNATURES.items():
            assert len(sigs) > 0, f"{lang} has no signatures"

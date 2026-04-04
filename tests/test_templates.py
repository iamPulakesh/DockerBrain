from __future__ import annotations

from core.templates import TEMPLATES, get_template_names, get_template


class TestTemplates:
    def test_templates_dict_is_populated(self):
        assert len(TEMPLATES) > 0

    def test_all_templates_have_required_keys(self):
        for key, tpl in TEMPLATES.items():
            assert "name" in tpl, f"Template '{key}' missing 'name'"
            assert "description" in tpl, f"Template '{key}' missing 'description'"
            assert "dockerfile" in tpl, f"Template '{key}' missing 'dockerfile'"

    def test_all_dockerfiles_start_with_from(self):
        for key, tpl in TEMPLATES.items():
            content = tpl["dockerfile"].strip()
            assert content.startswith("FROM"), f"Template '{key}' Dockerfile doesn't start with FROM"

    def test_all_dockerfiles_have_cmd_or_entrypoint(self):
        for key, tpl in TEMPLATES.items():
            content = tpl["dockerfile"].upper()
            assert "CMD" in content or "ENTRYPOINT" in content, (
                f"Template '{key}' has no CMD or ENTRYPOINT"
            )


class TestGetTemplateNames:
    def test_returns_sorted_list(self):
        names = get_template_names()
        assert names == sorted(names)

    def test_contains_known_templates(self):
        names = get_template_names()
        assert "fastapi" in names
        assert "node" in names
        assert "go" in names

    def test_matches_templates_keys(self):
        names = get_template_names()
        assert set(names) == set(TEMPLATES.keys())


class TestGetTemplate:
    def test_valid_template(self):
        tpl = get_template("fastapi")
        assert tpl is not None
        assert tpl["name"] == "FastAPI"
        assert "FROM" in tpl["dockerfile"]

    def test_case_insensitive(self):
        assert get_template("FastAPI") is not None
        assert get_template("FASTAPI") is not None
        assert get_template("Node") is not None

    def test_invalid_template(self):
        assert get_template("nonexistent-stack") is None

    def test_empty_string(self):
        assert get_template("") is None

    def test_each_template_accessible(self):
        for key in TEMPLATES:
            assert get_template(key) is not None

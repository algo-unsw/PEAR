"""Repository-level checks that hold before any schema exists."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

YAML_FILES = sorted(
    p
    for folder in ("data", ".github")
    for pattern in ("*.yml", "*.yaml")
    for p in (ROOT / folder).rglob(pattern)
)


def test_licences_are_separate():
    code = (ROOT / "LICENSE").read_text()
    data = (ROOT / "data" / "LICENSE").read_text()
    assert code.startswith("MIT License")
    assert "CC0 1.0 Universal" in data


@pytest.mark.parametrize("path", YAML_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_yaml_parses(path):
    yaml.safe_load(path.read_text())


ISSUE_FORMS = sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))


@pytest.mark.parametrize("path", [p for p in ISSUE_FORMS if p.name != "config.yml"], ids=lambda p: p.name)
def test_issue_form_shape(path):
    form = yaml.safe_load(path.read_text())
    assert {"name", "description", "body"} <= form.keys()
    ids = [item["id"] for item in form["body"] if "id" in item]
    assert len(ids) == len(set(ids)), "duplicate field ids"
    assert any(
        item.get("validations", {}).get("required") for item in form["body"]
    ), "a form needs at least one required field"

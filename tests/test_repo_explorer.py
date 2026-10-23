"""Source explorer must be complete, honest about edges, and safe to open offline."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from scripts.repo_explorer import flow_svg, index, main


def _fixture(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "scripts" / "a.py").write_text(
        'from scripts.b import target\n'
        'VALUE = 3\n'
        'def outer(arg):\n'
        '    """</script><script>alert(1)</script>"""\n'
        '    local = target(arg)\n'
        '    def inner():\n'
        '        unknown()\n'
        '    return local\n', encoding="utf-8")
    (tmp_path / "scripts" / "b.py").write_text(
        'def target(value):\n    return value\n', encoding="utf-8")
    (tmp_path / "tests" / "test_a.py").write_text(
        'from scripts.a import outer\n'
        'def test_outer():\n    assert outer(2) == 2\n', encoding="utf-8")
    journeys = [{"id": "sample", "title": "Fixture", "description": "One path",
                 "steps": [{"call": "outer → target", "source": "scripts/a.py:3",
                            "guard": "check", "output": "value", "failure": "none", "risk": "static"}]}]
    (tmp_path / "journeys.json").write_text(json.dumps(journeys), encoding="utf-8")
    return journeys


def test_index_resolves_explicit_calls_and_keeps_unknowns(tmp_path):
    _fixture(tmp_path)
    data = index(tmp_path)
    by_id = {row["id"]: row for row in data["functions"]}
    outer = by_id["scripts.a.outer"]
    assert data["files"] == 3
    assert len(data["functions"]) == 4
    assert outer["args"] == ["arg"]
    assert "local" in outer["locals"]
    assert {edge["to"] for edge in outer["resolved"]} == {"scripts.b.target"}
    assert "unknown" not in {edge["name"] for edge in outer["unresolved"]}
    assert "unknown" in {edge["name"] for edge in by_id["scripts.a.outer.inner"]["unresolved"]}
    assert data["parse_errors"] == []


def test_render_and_drift_check_are_offline_and_read_only(tmp_path):
    journeys = _fixture(tmp_path)
    output = tmp_path / "atlas.html"
    args = ["--root", str(tmp_path), "--journeys", str(tmp_path / "journeys.json"),
            "--out", str(output)]
    assert main(args) == 0
    content = output.read_text(encoding="utf-8")
    assert "scripts.a.outer" in content and "tests.test_a.test_outer" in content
    assert "\\u003c/script>" in content
    assert "<script>alert(1)</script>" not in content
    ET.fromstring(flow_svg(journeys[0]))
    before = output.read_bytes()
    assert main([*args, "--check"]) == 0
    (tmp_path / "scripts" / "b.py").write_text("def target(value):\n    return value + 1\n")
    assert main([*args, "--check"]) == 2
    assert output.read_bytes() == before


def test_english_and_vietnamese_atlases_have_separate_assets(tmp_path):
    _fixture(tmp_path)
    common = ["--root", str(tmp_path), "--journeys", str(tmp_path / "journeys.json")]
    for lang, suffix in (("en", ".en"), ("vi", "")):
        output = tmp_path / f"atlas{suffix}.html"
        args = [*common, "--lang", lang, "--out", str(output)]
        assert main(args) == 0
        content = output.read_text(encoding="utf-8")
        assert f'<html lang="{lang}">' in content
        assert f'repo-sample{suffix}.svg' in content
        assert main([*args, "--check"]) == 0
        ET.parse(tmp_path / f"repo-sample{suffix}.svg")
    assert "All Python functions" in (tmp_path / "atlas.en.html").read_text()
    assert "Toàn bộ hàm Python" in (tmp_path / "atlas.html").read_text()


def test_translated_journeys_preserve_source_contract():
    root = Path(__file__).resolve().parents[1]
    vi = json.loads((root / "docs/repo_journeys.json").read_text(encoding="utf-8"))
    en = json.loads((root / "docs/repo_journeys.en.json").read_text(encoding="utf-8"))
    assert len(vi) == len(en) == 5
    for original, translated in zip(vi, en, strict=True):
        assert original["id"] == translated["id"]
        assert len(original["steps"]) == len(translated["steps"])
        for source, target in zip(original["steps"], translated["steps"], strict=True):
            assert source.keys() == target.keys()
            assert source["source"] == target["source"]
            assert source["call"].split(" (")[0] == target["call"].split(" (")[0]


def test_generated_index_covers_runtime_and_tests_without_checkpoints(tmp_path):
    _fixture(tmp_path)
    hidden = tmp_path / "scripts" / ".ipynb_checkpoints"
    hidden.mkdir()
    (hidden / "old.py").write_text("def stale(): pass\n")
    data = index(tmp_path)
    assert data["files"] == 3
    assert all("checkpoint" not in row["file"] for row in data["functions"])


def test_bad_source_anchor_is_rejected(tmp_path):
    journeys = _fixture(tmp_path)
    journeys[0]["steps"][0]["source"] = "scripts/a.py:999"
    (tmp_path / "journeys.json").write_text(json.dumps(journeys))
    with pytest.raises(ValueError, match="invalid source anchor"):
        main(["--root", str(tmp_path), "--journeys", str(tmp_path / "journeys.json"),
              "--out", str(tmp_path / "atlas.html")])


def test_generic_explorer_indexes_guards_raises_and_variables(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text(
        "def handle(value):\n"
        "    result = value + 1\n"
        "    if result < 0:\n"
        "        raise ValueError('bad')\n"
        "    return result\n")
    output = tmp_path / "report" / "source.html"
    assert main(["--generic", "--root", str(tmp_path), "--sources", "src",
                 "--out", str(output)]) == 0
    data = json.loads(output.with_suffix(".json").read_text())
    row = data["functions"][0]
    assert row["locals"] == ["result"]
    assert row["guards"] == [{"line": 3, "kind": "if", "expression": "result < 0"}]
    assert row["raises"][0]["line"] == 4
    page = output.read_text()
    assert "Source Explorer" in page and "Calls unresolved" in page
    assert 'id="ego"' in page and "Download selected SVG" in page
    assert "function renderEgo(x)" in page and "x.guards.length" in page
    assert '"src.service.handle"' in page


def test_generic_explorer_requires_an_explicit_existing_source_scope(tmp_path):
    with pytest.raises(SystemExit) as missing:
        main(["--generic", "--root", str(tmp_path)])
    assert missing.value.code == 2
    with pytest.raises(SystemExit) as absent:
        main(["--generic", "--root", str(tmp_path), "--sources", "missing"])
    assert absent.value.code == 2

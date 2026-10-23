"""Architecture layers must preserve provenance and avoid safety overclaims."""

import json

import pytest

from scripts.architecture_atlas import build, render
from scripts.repo_explorer import index


def _fixture(tmp_path):
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "src" / "core").mkdir()
    (tmp_path / "README.md").write_text(
        "# Patient Service\n\nThis service handles patient requests without retaining raw IDs.\n"
        "\n## Request architecture\n"
        "1. Accept a request through `handle`.\n"
        "2. Call `run` to process it.\n"
        "3. Send a response through a dynamic boundary.\n")
    (tmp_path / "src" / "api" / "README.md").write_text(
        "# API\n\nReceives patient input and hands it to the core.\n")
    (tmp_path / "src" / "core" / "README.md").write_text(
        "# Core\n\nMasks the identifier before downstream processing.\n")
    (tmp_path / "src" / "api" / "request.py").write_text(
        "from src.core.service import run\n"
        "def handle(patient):\n"
        "    return run(patient)\n")
    (tmp_path / "src" / "core" / "service.py").write_text(
        "def mask(value):\n"
        "    return value\n"
        "def run(patient):\n"
        "    return mask(patient)\n")
    data = index(tmp_path, sources=("src",), asset_dirs=())
    return build(tmp_path, ("src",), data)


def test_docs_blocks_calls_and_unbound_steps_are_distinct(tmp_path):
    model = _fixture(tmp_path)
    blocks = {block["id"]: block for block in model["blocks"]}
    assert set(blocks) == {"src/api", "src/core"}
    assert blocks["src/api"]["purpose"]["state"] == "documented"
    assert blocks["src/api"]["purpose"]["source"] == "src/api/README.md:3"
    assert any(edge["from"] == "src/api" and edge["to"] == "src/core"
               and edge["kind"] == "static_call" and edge["examples"][0]["source"] == "src/api/request.py:3"
               for edge in model["edges"])
    journey = next(j for j in model["journeys"] if j["title"] == "Request architecture")
    assert journey["steps"][0]["functions"] == ["src.api.request.handle"]
    assert journey["steps"][1]["functions"] == ["src.core.service.run"]
    assert journey["steps"][2]["binding"] == "unknown"
    assert model["coverage"]["journey_steps_unbound"] == 1


def test_mask_name_is_candidate_never_a_safety_verdict(tmp_path):
    model = _fixture(tmp_path)
    controls = {item["id"]: item for item in model["controls"]}
    assert "pii" in model["profiles_candidate"]
    assert controls["P02"]["status"] == "source_candidate"
    assert "production readiness unverified" in controls["P02"]["claim"]
    assert all(item["status"] not in {"passed", "safe", "production_ready"}
               for item in model["controls"])


def test_render_is_offline_and_escapes_documentation(tmp_path):
    model = _fixture(tmp_path)
    model["overview"]["purpose"] = "</script><script>alert(1)</script>"
    output = tmp_path / "report" / "architecture.html"
    output.parent.mkdir()
    render(model, tmp_path, output)
    page = output.read_text()
    assert "<script>alert(1)</script>" not in page
    assert "\\u003c/script>" in page
    assert "Functional blocks and connections" in page
    assert "Function leads and source" in page
    assert "Harness & sensitive controls" in page
    parsed = json.loads(output.with_suffix(".json").read_text())
    assert parsed["overview"]["purpose"] == "</script><script>alert(1)</script>"


def test_explicit_doc_outside_scope_is_rejected(tmp_path):
    data = index(tmp_path, sources=(), asset_dirs=())
    with pytest.raises(ValueError, match="unsafe"):
        build(tmp_path, (), data, extra_docs=("../secret.md",))


def test_excluded_python_scope_is_not_indexed_or_reported(tmp_path):
    (tmp_path / "src" / "test_e2e").mkdir(parents=True)
    (tmp_path / "src" / "SOTA_run_v1").mkdir()
    (tmp_path / "src" / "main.py").write_text("def run():\n    return 1\n")
    (tmp_path / "src" / "test_e2e" / "secret_case.py").write_text(
        "def sensitive_case():\n    return 'synthetic'\n")
    (tmp_path / "src" / "SOTA_run_v1" / "generated.py").write_text(
        "def old_result():\n    return 2\n")
    data = index(tmp_path, sources=("src",), asset_dirs=())
    model = build(tmp_path, ("src",), data)
    assert list(data["modules"].values()) == ["src/main.py"]
    assert all("test_e2e" not in path for block in model["blocks"] for path in block["files"])


def test_explicit_doc_through_symlink_into_excluded_tree_is_rejected(tmp_path):
    private = tmp_path / "src" / "test_e2e"
    private.mkdir(parents=True)
    (private / "README.md").write_text("# Synthetic restricted artifact\n")
    (tmp_path / "src" / "alias").symlink_to(private, target_is_directory=True)
    data = index(tmp_path, sources=("src",), asset_dirs=())
    with pytest.raises(ValueError, match="unsafe"):
        build(tmp_path, ("src",), data, extra_docs=("src/alias/README.md",))


def test_root_source_keeps_root_files_and_nested_blocks(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "main.py").write_text("from src.service import run\ndef main():\n    return run()\n")
    (tmp_path / "src" / "service.py").write_text("def run():\n    return 1\n")
    (tmp_path / "config.yaml").write_text("mode: synthetic\n")
    data = index(tmp_path, sources=(".",), asset_dirs=())
    model = build(tmp_path, (".",), data)
    blocks = {item["id"]: item for item in model["blocks"]}
    assert set(blocks) == {".", "src"}
    assert blocks["."]["label"] == "Root"
    assert blocks["src"]["area"] == "."
    assert blocks["."]["context_assets"] == [{"path": "config.yaml", "role": "config"}]
    assert any(edge["from"] == "." and edge["to"] == "src" for edge in model["edges"])


def test_unique_short_import_connects_blocks_but_ambiguous_name_does_not(tmp_path):
    for directory in ("src/api", "src/core", "src/other"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "src/api/request.py").write_text(
        "import service as CORE\n"
        "from helper import assist\n"
        "def handle(value):\n"
        "    return CORE.run(value) + assist(value)\n")
    (tmp_path / "src/core/service.py").write_text("def run(value):\n    return value\n")
    (tmp_path / "src/core/helper.py").write_text("def assist(value):\n    return value\n")
    (tmp_path / "src/other/helper.py").write_text("def assist(value):\n    return value\n")
    data = index(tmp_path, sources=("src",), asset_dirs=())
    fn = next(item for item in data["functions"] if item["id"] == "src.api.request.handle")
    assert [entry["to"] for entry in fn["resolved"]] == ["src.core.service.run"]
    assert fn["resolved"][0]["resolution"] == "unique_module_suffix"
    assert any(entry["name"] == "assist" for entry in fn["unresolved"])
    model = build(tmp_path, ("src",), data)
    assert any(edge["from"] == "src/api" and edge["to"] == "src/core"
               and edge["kind"] == "static_call" for edge in model["edges"])

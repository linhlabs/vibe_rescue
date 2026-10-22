import subprocess
from pathlib import Path

import pytest

from scripts import logic_atlas
from scripts.atlas_render import write_graph
from scripts.syntax_map import extract


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "ui").mkdir(parents=True)
    (repo / "backend").mkdir()
    (repo / "native" / "src").mkdir(parents=True)
    (repo / "ui" / "page.tsx").write_text("export const Page = () => null;\n")
    (repo / "backend" / "api.py").write_text("def route():\n    return 1\n")
    (repo / "native" / "Cargo.toml").write_text("[package]\nname='native'\nversion='0.1.0'\n")
    (repo / "native" / "src" / "lib.rs").write_text("pub fn compute() -> i32 { 1 }\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "-qm", "initial"], cwd=repo, check=True)
    return repo


def test_inventory_is_multilanguage_and_does_not_write_target(tmp_path):
    repo = _repo(tmp_path)
    out = tmp_path / "atlas"
    result = logic_atlas.generate(repo, repo, out, inventory_only=True)
    assert result["language_files"]["python"] == 1
    assert result["language_files"]["frontend"] == 1
    assert result["language_files"]["rust"] == 1
    assert (out / "INDEX.md").exists()
    assert (out / "JOURNEY_TEMPLATE.md").exists()
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout == ""


def test_scope_cannot_escape_target(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(ValueError, match="scope phải nằm"):
        logic_atlas.resolve_scope(repo, "../")
    assert logic_atlas.tracked_files(repo, repo / "backend") == [Path("backend/api.py")]


def test_tool_failure_is_explicit_and_does_not_create_graph(tmp_path):
    out = tmp_path / "missing.dot"
    result = logic_atlas._run(["python3", "-c", "raise RuntimeError('probe')"],
                              tmp_path, out, timeout=5)
    assert result["status"] == "failed"
    assert not out.exists()


def test_rust_syntax_map_has_exact_local_call_with_line(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    repo = _repo(tmp_path)
    (repo / "native" / "src" / "lib.rs").write_text(
        "pub fn compute() -> i32 { helper() }\nfn helper() -> i32 { 1 }\n")
    graph = extract(repo, [Path("native/src/lib.rs")], "rust")
    assert {n["label"] for n in graph["nodes"]} == {"compute", "helper"}
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["line"] == 1


@pytest.mark.parametrize(("language", "filename", "source"), [
    ("go", "a.go", "package p\nfunc a() int { return b() }\nfunc b() int { return 1 }\n"),
    ("java", "A.java", "class A { int a() { return b(); } int b() { return 1; } }"),
    ("csharp", "A.cs", "class A { int a() { return b(); } int b() { return 1; } }"),
    ("php", "a.php", "<?php function a() { return b(); } function b() { return 1; }"),
])
def test_syntax_map_local_calls_in_supported_languages(tmp_path, language, filename, source):
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / filename).write_text(source)
    graph = extract(tmp_path, [Path(filename)], language)
    assert {n["label"] for n in graph["nodes"]} == {"a", "b"}
    assert len(graph["edges"]) == 1


def test_frontend_unresolved_import_is_explicit():
    raw = '{"modules":[{"source":"ui/a.ts","dependencies":[' \
          '{"module":"./missing","resolved":"./missing","couldNotResolve":true}]}]}'
    graph = logic_atlas._frontend_graph(raw, [Path("ui/a.ts")])
    assert graph["edges"] == []
    assert graph["unknown"][0]["import"] == "./missing"


def test_frontend_functions_keep_member_dispatch_unknown(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "app.ts").write_text(
        "export function submit(x){ return charge(x) }\n"
        "const charge=(x)=>client.post(x);\n"
        "class Agent { run(y){ return charge(y) } }\n"
        "export const handler = async (req)=> await Agent.run(req);\n")
    graph = extract(tmp_path, [Path("app.ts")], "frontend")
    assert {n["label"] for n in graph["nodes"]} == {"submit", "charge", "run", "handler"}
    assert {(e["source"].split(":")[-1], e["target"].split(":")[-1])
            for e in graph["edges"]} == {("submit", "charge"), ("run", "charge")}
    assert {u["call"] for u in graph["unknown"]} == {"post", "run"}
    assert all(u["reason"] == "member/dynamic call unresolved" for u in graph["unknown"])


def test_frontend_scope_exports_import_and_function_views(tmp_path, monkeypatch):
    pytest.importorskip("tree_sitter_language_pack")
    repo = _repo(tmp_path)
    graph = {"nodes": [{"id": "ui/page.tsx", "label": "page.tsx", "file": "ui/page.tsx"}],
             "edges": [], "unknown": []}

    def fake_frontend(_target, _paths, output, _timeout, _cfg):
        output.write_text("{}")
        return {"status": "ok", "artifact": output.name}, graph

    monkeypatch.setattr(logic_atlas, "_run_frontend", fake_frontend)
    out = tmp_path / "atlas-frontend"
    result = logic_atlas.generate(repo, repo / "ui", out)
    assert result["tools"]["frontend"]["status"] == "ok"
    assert result["tools"]["frontend_symbols"]["status"] == "ok"
    assert (out / "frontend-symbols.json").is_file()
    assert (out / "frontend-functions.html").is_file()
    assert (out / "frontend-functions.svg").is_file()


def test_frontend_function_map_survives_missing_npx(tmp_path, monkeypatch):
    pytest.importorskip("tree_sitter_language_pack")
    repo = _repo(tmp_path)
    monkeypatch.setattr(logic_atlas.shutil, "which", lambda _name: None)
    result = logic_atlas.generate(repo, repo / "ui", tmp_path / "atlas-no-npx")
    assert result["tools"]["frontend"]["status"] == "unavailable"
    assert result["tools"]["frontend_symbols"]["status"] == "ok"


def test_html_svg_export_escapes_repository_labels(tmp_path):
    graph = {"nodes": [{"id": "x", "label": "<script>alert(1)</script>",
                        "file": "src/a.py", "line": 5}], "edges": [], "unknown": []}
    result = write_graph(graph, "Demo", tmp_path, "demo")
    assert result["html"] == "demo.html"
    page = (tmp_path / "demo.html").read_text()
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    assert (tmp_path / "demo.svg").exists()


def test_html_catalog_keeps_nodes_edges_and_unknown_beyond_svg_limit(tmp_path):
    nodes = [{"id": str(i), "label": f"function_{i}", "file": "src/a.py", "line": i + 1}
             for i in range(125)]
    graph = {"nodes": nodes,
             "edges": [{"source": "0", "target": "124", "kind": "direct call",
                        "file": "src/a.py", "line": 1}],
             "unknown": [{"file": "src/a.py", "line": 2, "call": "dynamic", "reason": "unknown"}]}
    result = write_graph(graph, "Large graph", tmp_path, "large")
    page = (tmp_path / "large.html").read_text()
    assert result["truncated"] and result["shown_nodes"] == 120
    assert '<details class="diagram">' in page
    assert 'Full source catalog · 125 symbols · 1 static edges' in page
    assert 'function_124' in page and 'direct call' in page
    assert 'dynamic' in page and 'src/a.py:2' in page


def test_atlas_does_not_follow_tracked_symlinks(tmp_path):
    repo = _repo(tmp_path)
    outside = tmp_path / "secret.py"
    outside.write_text("TOKEN='private'\n")
    (repo / "backend" / "link.py").symlink_to(outside)
    subprocess.run(["git", "add", "backend/link.py"], cwd=repo, check=True)
    assert Path("backend/link.py") not in logic_atlas.tracked_files(repo, repo)
    result = logic_atlas.generate(repo, repo, tmp_path / "atlas", inventory_only=True)
    assert result["tools"]["safety"]["status"] == "skipped"


def test_unmapped_language_is_reported_instead_of_claiming_complete(tmp_path):
    repo = tmp_path / "kotlin"
    repo.mkdir()
    (repo / "App.kt").write_text("fun main() {}\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "-qm", "initial"], cwd=repo, check=True)
    result = logic_atlas.generate(repo, repo, tmp_path / "atlas")
    assert result["tools"]["other"]["status"] == "unmapped"
    assert result["unmapped_code_files"] == 1

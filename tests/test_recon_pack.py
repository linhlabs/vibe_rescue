from tools.meta import context_pack, recon


def test_recon_basic(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def f():\n    return 1\n")
    (tmp_path / "src" / "app.js").write_text("console.log(1)\n")
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    (tmp_path / "CLAUDE.md").write_text("x\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_x(): pass\n")
    big = tmp_path / "src" / "big.py"
    big.write_text("\n".join(f"# {i}" for i in range(900)))
    info = {
        "target": str(tmp_path),
        "ext_counts": recon.count_exts(tmp_path),
        "langs": recon.langs(recon.count_exts(tmp_path)),
        "entrypoints": [str(p.relative_to(tmp_path)) for p in [
            tmp_path / "pyproject.toml"] if p.exists()],
        "test_files": sum(1 for p in tmp_path.rglob("*") if p.is_file() and "test" in str(p.relative_to(tmp_path))),
        "big_files": recon.big_files(tmp_path),
        "git": recon.git_info(tmp_path),
        "assets": recon.assets(tmp_path),
    }
    assert info["langs"].get("python", {}).get("files", 0) >= 1
    assert "pyproject.toml" in info["entrypoints"]
    assert info["test_files"] >= 1
    assert info["big_files"] and info["big_files"][0]["file"].endswith("big.py")
    assert any(r["path"].endswith("CLAUDE.md") for r in info["assets"]["rules_files"])


def test_context_pack_ignores_node_modules(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("let a=1\n" * 50)
    (tmp_path / "main.py").write_text("print('hi')\n")
    stats = {"files": 0, "lines": 0, "binaries": 0, "big_files": 0, "truncated": 0,
             "packed_files": 0, "packed_bytes": 0, "engine": "builtin"}
    out = tmp_path / "context.txt"
    context_pack.write_pack(tmp_path, out, stats)
    content = out.read_text()
    assert "### FILE: main.py" in content
    assert "node_modules" not in content
    assert stats["packed_files"] == 1

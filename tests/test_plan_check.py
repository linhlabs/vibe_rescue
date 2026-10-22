import subprocess

from scripts import plan_check

VALID = """# PLAN-001: loại bỏ cycle import giữa a và b
Plan SHA: abc123
Scope: [src/a.py, src/b.py]
Out-of-scope: [tests/, docs/, dependencies, public API]
Baseline evidence: [ARCH-01]
Steps:
  1. Rút helper dùng chung ra src/common.py — Verification: `python3 -c "import src.a"` 
  2. Đổi import trong src/b.py — Verification: `python3 -m pytest tests/test_a.py -q`
STOP conditions: pytest test_b fail | diff > 5 file | xuất hiện dep mới
Rollback: `git checkout abc123 -- src/a.py src/b.py`
Done criteria: `python3 -m pytest -q` xanh; delta_gate 0 finding mới
"""


def test_parse_plan_sections():
    sections = plan_check.parse_plan(VALID)
    for h in plan_check.REQUIRED:
        assert any(x for x in sections.get(h, [])), h
    files = plan_check.scope_files(sections)
    assert "src/a.py" in files and "src/b.py" in files


def test_check_plan_missing_stop(tmp_path):
    text = VALID.replace("STOP conditions: pytest test_b fail | diff > 5 file | xuất hiện dep mới", "")
    sections = plan_check.parse_plan(text)
    problems, _files, _missing = plan_check.check_plan(sections)
    assert any("STOP" in p for p in problems)


def test_check_plan_scope_file_missing(tmp_path):
    sections = plan_check.parse_plan(VALID)
    _problems, _files, missing = plan_check.check_plan(sections, target=tmp_path)
    assert "src/a.py" in missing


def test_check_plan_ok_with_target(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("")
    (tmp_path / "src" / "b.py").write_text("")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "--allow-empty", "-qm", "init"], cwd=tmp_path, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                         capture_output=True, text=True, check=True).stdout.strip()
    sections = plan_check.parse_plan(VALID.replace("abc123", sha))
    problems, _files, missing = plan_check.check_plan(sections, target=tmp_path)
    assert not missing and not problems


def test_check_worktree_scope(tmp_path):
    d = tmp_path / "wt"
    d.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=d, check=True)
    (d / "src").mkdir()
    (d / "src" / "a.py").write_text("x=1")
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=d, check=True)
    (d / "src" / "a.py").write_text("x=2")       # trong scope
    (d / "src" / "z.py").write_text("x=3")       # NGOÀI scope
    problems = plan_check.check_worktree(d, ["src/a.py", "src/b.py"])
    assert any("ngoài scope" in p and "src/z.py" in p for p in problems)


def test_scope_accepts_arbitrary_languages_and_explicit_new_file(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "service.cs").write_text("class Service {}")
    sections = plan_check.parse_plan(VALID.replace(
        "Scope: [src/a.py, src/b.py]", "Scope: [app/service.cs, +app/new.vue]"))
    entries, invalid = plan_check.scope_entries(sections)
    assert entries == [("app/service.cs", False), ("app/new.vue", True)]
    assert invalid == []
    _problems, files, missing = plan_check.check_plan(sections, target=tmp_path)
    assert files == ["app/service.cs", "app/new.vue"]
    assert missing == []


def test_scope_rejects_traversal_symlink_and_unmarked_new_file(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "escape.py").symlink_to(tmp_path.parent / "secret.py")
    sections = plan_check.parse_plan(VALID.replace(
        "Scope: [src/a.py, src/b.py]",
        "Scope: [../secret.py, src/escape.py, src/new.rs]"))
    problems, _files, missing = plan_check.check_plan(sections, target=tmp_path)
    assert any("không an toàn" in p for p in problems)
    assert any("symlink" in p for p in problems)
    assert "src/new.rs" in missing


def test_scope_checks_untracked_filename_with_spaces(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "--allow-empty", "-qm", "base"], cwd=repo, check=True)
    (repo / "new file.cs").write_text("class C {}")
    assert plan_check.check_worktree(repo, ["new file.cs"]) == []
    assert any("ngoài scope" in p for p in plan_check.check_worktree(repo, ["other.cs"]))


def test_worktree_rejects_new_symlink_even_when_in_scope(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "--allow-empty", "-qm", "base"], cwd=repo, check=True)
    (repo / "alias.py").symlink_to(tmp_path / "outside.py")
    problems = plan_check.check_worktree(repo, ["alias.py"])
    assert any("symlink" in p for p in problems)

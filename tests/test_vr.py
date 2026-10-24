"""The one-command front end (scripts/vr.py): friendly errors, one output folder, a clean Git status for the user's project."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import vr


def make_project(path):
    path.mkdir()
    (path / "src").mkdir()
    (path / "src" / "billing.py").write_text("import os, sys\n\n\ndef total(items):\n    return sum(i['price'] for i in items)\n")
    (path / "main.py").write_text("from src.billing import total\nprint(total([{'price': 2}]))\n")
    for cmd in (["init", "-q"], ["config", "user.email", "a@b"], ["config", "user.name", "n"], ["add", "-A"], ["commit", "-qm", "init"]):
        subprocess.run(["git", "-C", str(path), *cmd], check=True, capture_output=True)
    return path


def git_status(path):
    return subprocess.run(["git", "-C", str(path), "status", "--short"], capture_output=True, text=True, check=True).stdout.strip()


def test_not_a_git_repository_explains_the_fix(tmp_path, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(SystemExit) as exc:
        vr.main(["explore", str(plain)])
    assert exc.value.code == 2
    assert "git init" in capsys.readouterr().out


def test_explore_writes_one_folder_and_keeps_git_clean(tmp_path):
    project = make_project(tmp_path / "proj")
    assert vr.main(["explore", str(project)]) == 0
    out = project / "VIBE_RESCUE"
    assert (out / "START_HERE.md").is_file() and (out / "HANDOFF.md").is_file() and (out / "atlas" / "INDEX.md").is_file()
    assert (out / ".gitignore").read_text().strip() == "*"
    start = (out / "START_HERE.md").read_text()
    assert "Start here" in start and "Bắt đầu từ đây" in start and "Python files: 2" in start
    assert git_status(project) == ""                       # nothing of ours shows up in the project's Git status


@pytest.mark.skipif(shutil.which("uvx", path=str(Path(sys.executable).parent)) is None and shutil.which("uvx") is None, reason="uvx not available")
def test_check_summarises_findings_and_ignores_its_own_folders(tmp_path):
    project = make_project(tmp_path / "proj")
    assert vr.main(["check", str(project), "--tools", "ruff"]) == 0
    start = (project / "VIBE_RESCUE" / "START_HERE.md").read_text()
    assert "Problems found (done)" in start and "F401" in start
    assert (project / "VIBE_RESCUE" / "check" / "findings.md").is_file()
    assert git_status(project) == ""


def test_report_and_fix_explain_the_ai_setup_when_none_is_configured(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(vr, "ROOT", tmp_path)               # no config.local.toml here
    monkeypatch.delenv("VIBE_LLM_CONFIG", raising=False)
    project = make_project(tmp_path / "proj")
    for argv in (["report", str(project)], ["fix", str(project), "--test", "true"]):
        with pytest.raises(SystemExit) as exc:
            vr.main(argv)
        assert exc.value.code == 2
        text = capsys.readouterr().out
        assert "./vr ai claude" in text and "--checker-model" in text


def test_fix_needs_a_safety_command(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(vr, "ROOT", tmp_path)
    (tmp_path / "config.local.toml").write_text("[roles.write]\ncli = \"claude\"\n")
    project = make_project(tmp_path / "proj")
    assert vr.main(["fix", str(project)]) == 2
    assert "--test" in capsys.readouterr().out


def test_ai_openai_writes_config_without_a_key(tmp_path, monkeypatch):
    monkeypatch.setattr(vr, "ROOT", tmp_path)
    assert vr.main(["ai", "openai", "--url", "http://localhost:8000/v1", "--model", "writer", "--checker-model", "checker", "--allow-http"]) == 0
    body = (tmp_path / "config.local.toml").read_text()
    assert 'model = "writer"' in body and 'model = "checker"' in body and "--base-url" in body and "--allow-http" in body
    assert "key" not in body.lower().replace("--api-key", "")
    assert vr.main(["ai", "claude"]) == 2                   # refuses to overwrite without --force


def test_doctor_runs(capsys):
    assert vr.main(["doctor"]) in (0, 2)
    assert "Vibe Rescue doctor" in capsys.readouterr().out

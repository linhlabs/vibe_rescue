"""The MAP+PROVE shortcut must not bless stale or incomplete evidence."""
import json
import subprocess

import pytest

from scripts import run_target


@pytest.mark.parametrize("failed_step", ["context_pack", "recon", "fanout", "merge_findings"])
def test_failed_step_never_creates_baseline(tmp_path, monkeypatch, failed_step):
    monkeypatch.setattr(run_target, "ROOT", tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    out = tmp_path / "reports" / "targets" / "demo"
    stale = out / "run" / "findings.json"
    stale.parent.mkdir(parents=True)
    stale.write_text('{"meta":{},"findings":[]}')

    def fake_run(command, check=False):
        step = command[1].rsplit("/", 1)[-1].removesuffix(".py")
        rc = 1 if step == failed_step else 0
        if step == "context_pack" and rc == 0:
            path = out / ".rescue" / "context.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")
        if step == "recon" and rc == 0:
            (out / "recon.json").write_text("{}")
        if step == "fanout" and rc == 0:
            (out / "run" / "run.summary.json").write_text(
                json.dumps({"ok": 1, "skipped": 0, "failed": 0}))
        if step == "merge_findings":
            stale.write_text('{"meta":{},"findings":[]}')
        return subprocess.CompletedProcess(command, rc)

    monkeypatch.setattr(run_target.subprocess, "run", fake_run)
    assert run_target.main(["--name", "demo", "--path", str(target), "--tools", "ruff"]) == 2
    assert not (out / "baseline" / "findings.json").exists()


def test_zero_successful_scanners_blocks_baseline(tmp_path, monkeypatch):
    monkeypatch.setattr(run_target, "ROOT", tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    out = tmp_path / "reports" / "targets" / "demo"

    def fake_run(command, check=False):
        step = command[1].rsplit("/", 1)[-1].removesuffix(".py")
        if step == "context_pack":
            path = out / ".rescue" / "context.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")
        elif step == "recon":
            (out / "recon.json").write_text("{}")
        elif step == "fanout":
            path = out / "run" / "run.summary.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"ok": 0, "skipped": 1, "failed": 0}))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(run_target.subprocess, "run", fake_run)
    assert run_target.main(["--name", "demo", "--path", str(target), "--tools", "ruff"]) == 2
    assert not (out / "baseline" / "findings.json").exists()

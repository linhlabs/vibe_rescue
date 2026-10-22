import json
import subprocess
import sys
from types import SimpleNamespace

from scripts import rescue_voyage


def _result(rc=0):
    return SimpleNamespace(returncode=rc, stdout="", stderr="failed" if rc else "")


def test_map_blocks_failed_context_and_missing_recon(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()
    context = rescue_voyage.Ctx(target=target, session=tmp_path / "session",
                                stages=[], max_rounds=1)
    monkeypatch.setattr(rescue_voyage, "sh", lambda *args, **kwargs: _result(2))
    assert rescue_voyage._stage_map(context) == 2
    monkeypatch.setattr(rescue_voyage, "sh", lambda *args, **kwargs: _result())
    assert rescue_voyage._stage_map(context) == 2  # recon must create artifact


def test_review_blocks_missing_evidence_package(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()
    context = rescue_voyage.Ctx(target=target, session=tmp_path / "session",
                                stages=[], max_rounds=1, review_cmd="false",
                                review_cmd_custom=True)
    err_file = context.session / "review" / "EVIDENCE" / "review-cmd.err"
    err_file.parent.mkdir(parents=True)
    err_file.write_text("agent unavailable")

    def fake_sh(*args, **kwargs):
        return _result(2 if "collect_evidence.py" in str(args[1]) else 0)

    monkeypatch.setattr(rescue_voyage, "sh", fake_sh)
    assert rescue_voyage._stage_review(context) == 2


def test_unhandled_stage_error_is_recorded_as_blocked(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    target.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)

    def fail(_context):
        raise ValueError("corrupt evidence")

    monkeypatch.setitem(rescue_voyage.STAGE_FUNCS, "map", fail)
    monkeypatch.setattr(sys, "argv", ["rescue_voyage.py", "--path", str(target),
                                      "--stages", "map"])
    assert rescue_voyage.main() == 2
    state = json.loads((target / ".rescue" / "voyage" / "voyage.json").read_text())
    assert state["state"] == "error_map"

"""v0.4 hardening — H1 redact + H2 kiểm số (audit v0.3.5) + R2 standalone launch."""
import json
import subprocess
import sys
from pathlib import Path

from scripts import check_review_numbers as cn
from scripts.merge_findings import load_raw
from tools.meta import redact, scan

ROOT = Path(__file__).resolve().parents[1]

# key giả nối lúc runtime — scanner quét source không match (repo public không đựng
# chuỗi dạng khóa, kể cả khóa giả), còn test vẫn có giá trị key-like để kiểm chứng masking
FAKE_KEY = "sk-test" + "1" * 22


# ---------- H1: redact ----------

def test_mask_text_patterns():
    s = f"OPENAI_API_KEY={FAKE_KEY} và AKIAIOSFODNN7EXAMPLE và dapi{'a'*28} "
    out = redact.mask_text(s)
    assert FAKE_KEY not in out and "AKIAIOSFODNN7EXAMPLE" not in out
    assert "OPENAI_API_KEY=[REDACTED]" in out  # giữ tên biến, che giá trị
    assert f"dapi{'a'*28}" not in out
    # chuỗi thường KHÔNG bị che nhầm
    keep = 'sha = "a3f1c2b4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0"; log("token debug")'
    assert redact.mask_text(keep) == keep
    pem = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
    assert "[REDACTED]" in redact.mask_text(pem)


def test_mask_findings_and_obj():
    fs = redact.mask_findings([
        {"rule": "LEAK", "message": f"key {FAKE_KEY}", "evidence": FAKE_KEY}])
    assert FAKE_KEY not in json.dumps(fs)
    obj = redact.mask_obj({"a": [FAKE_KEY], "b": {"c": "plain"}})
    assert FAKE_KEY not in json.dumps(obj) and obj["b"]["c"] == "plain"


def test_scan_emit_masks_at_source(tmp_path):
    out = tmp_path / "raw" / "x.json"
    result = {"tool": "gitleaks", "version": "t", "target": ".", "ok": True,
              "skipped": None, "error": None,
              "findings": [{"rule": "L", "severity": "high", "file": "a.env",
                            "line": 1, "message": f"k={FAKE_KEY}",
                            "evidence": FAKE_KEY}]}
    scan.emit(result, str(out))
    text = out.read_text()
    assert FAKE_KEY not in text and "[REDACTED]" in text


def test_gitleaks_cmd_uses_redact():
    cmd = scan.cmd_for("gitleaks", Path("."), [])
    assert "--redact" in cmd


def test_merge_findings_masks_foreign_raw(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "gitleaks.json").write_text(json.dumps({
        "tool": "gitleaks", "findings": [
            {"rule": "L", "severity": "high", "file": ".env", "line": 3,
             "message": "leak", "evidence": FAKE_KEY}]}))
    items, _ = load_raw(raw)
    assert FAKE_KEY not in json.dumps(items)
    assert items[0]["evidence"] == "[REDACTED]"


def test_context_pack_masks_context_txt(tmp_path, monkeypatch):
    import tools.meta.context_pack as cp
    target = tmp_path / "tgt"
    (target / "src").mkdir(parents=True)
    (target / "src" / "keys.txt").write_text(f"OPENAI_API_KEY = {FAKE_KEY}\n")
    monkeypatch.setattr(cp.shutil, "which", lambda name: None)  # ép builtin packer
    monkeypatch.setattr(sys, "argv", ["context_pack.py",
                                      "--target", str(target),
                                      "--outdir", str(tmp_path / "out")])
    assert cp.main() == 0
    ctx = (tmp_path / "out" / "context.txt").read_text()
    assert FAKE_KEY not in ctx and "OPENAI_API_KEY = [REDACTED]" in ctx


def test_redact_cli_in_place(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text(f"token: {FAKE_KEY}\n")
    assert redact.main([str(p)]) == 0
    assert FAKE_KEY not in p.read_text()


# ---------- H2: check_review_numbers ----------

def _make_fixture(tmp_path):
    target = tmp_path / "tgt"
    (target / "pkg").mkdir(parents=True)
    (target / "pkg" / "mod.py").write_text(
        "def outer(x):\n"          # 1
        "    def inner():\n"       # 2  nested 1
        "        return x\n"       # 3
        "    def inner2():\n"      # 4  nested 2
        "        return x + 1\n"   # 5
        "    return inner() + inner2()\n")  # 6
    rdir = tmp_path / "review"
    (rdir / "EVIDENCE").mkdir(parents=True)
    raw = tmp_path / "prove" / "raw"
    raw.mkdir(parents=True)
    (raw / "gitleaks.json").write_text(json.dumps({
        "tool": "gitleaks", "findings": [
            {"rule": "L", "severity": "high", "file": ".env", "line": 1,
             "message": "m", "evidence": ""} for _ in range(5)]}))
    (raw / "ruff.json").write_text(json.dumps({
        "tool": "ruff", "findings": [
            {"rule": "BLE001", "severity": "medium", "file": "pkg/mod.py", "line": 2,
             "message": "m", "evidence": ""} for _ in range(3)]}))
    (raw / "radon.json").write_text(json.dumps({
        "tool": "radon", "findings": [
            {"rule": "C901", "severity": "high", "file": "pkg/mod.py", "line": 1,
             "message": "outer complexity 7", "evidence": "cyclo=7.0"}]}))
    (rdir / "archgraph.json").write_text(json.dumps(
        {"cycles": [], "modules": ["pkg.mod", "a", "b", "c"]}))
    (rdir / "README.md").write_text(
        "# REVIEW\n\n## Câu trả lời ngắn\n"
        "- `pkg/mod.py:1` là điểm nóng, cyclomatic 7.\n"
        "- gitleaks 5 phát hiện, BLE001 3, ruff 99.\n"
        "- archgraph: 0 vòng, 4 modules.\n"
        "- thẻ này nói **2 hàm con** lồng trong hàm ở `pkg/mod.py:1`.\n"
        "- `pkg/mod.py` có 999 dòng (sai cố ý).\n")
    (rdir / "PROPOSALS.md").write_text("# PROPOSALS\n\n## A1 · thẻ\n- 2 hàm con ở `pkg/mod.py:1`.\n")
    return target, rdir


def test_number_checker_flags_and_confirms(tmp_path):
    target, rdir = _make_fixture(tmp_path)
    rc = cn.main(["--review-dir", str(rdir), "--target", str(target)])
    assert rc == 0  # advisory
    rep = (rdir / "EVIDENCE" / "number-check.md").read_text()
    assert "✓" in rep and "✗" in rep
    assert "999 dòng" in rep and "SAI" in rep           # sai cố ý bị bắt
    assert "2 hàm con" in rep                            # AST check chạy
    assert "thật: 2" in rep                              # đúng -> OK
    assert "ruff = 99" in rep                            # lệch tổng tool bị bắt


def test_number_checker_strict_exit(tmp_path):
    target, rdir = _make_fixture(tmp_path)
    assert cn.main(["--review-dir", str(rdir), "--target", str(target),
                    "--strict"]) == 1


# ---------- R2 (round-2 audit): chạy standalone từ cwd NGOÀI repo ----------
# Bug thật round-2: môi trường có package 'tools' ở site-packages làm import fallback
# trỏ nhầm -> merge_findings/collect_evidence chết khi production gọi (cwd khác repo).

def test_merge_findings_standalone_from_foreign_cwd(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "gitleaks.json").write_text(json.dumps({
        "tool": "gitleaks", "findings": [
            {"rule": "L", "severity": "high", "file": ".env", "line": 2,
             "message": f"leak {FAKE_KEY}", "evidence": FAKE_KEY}]}))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "merge_findings.py"),
                        "--rundir", str(tmp_path), "--sarif", str(tmp_path / "f.sarif")],
                       cwd="/tmp", capture_output=True, text=True, timeout=120, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    assert FAKE_KEY not in (tmp_path / "findings.json").read_text()
    assert FAKE_KEY not in (tmp_path / "f.sarif").read_text()


def test_collect_evidence_standalone_from_foreign_cwd(tmp_path):
    session = tmp_path / "tgt" / ".rescue" / "voyage"
    (session / "prove" / "raw").mkdir(parents=True)
    (session / "prove" / "raw" / "gitleaks.json").write_text(json.dumps({
        "tool": "gitleaks", "findings": [
            {"rule": "L", "severity": "high", "file": ".env", "line": 1,
             "message": "m", "evidence": FAKE_KEY}]}))
    (session / "prove" / "findings.json").write_text(json.dumps(
        {"meta": {}, "findings": []}))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "collect_evidence.py"),
                        "--session", str(session)],
                       cwd="/tmp", capture_output=True, text=True, timeout=120, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    edir = session / "review" / "EVIDENCE"
    assert (edir / "summary.md").exists()
    assert FAKE_KEY not in (edir / "raw" / "gitleaks.json").read_text()


def test_voyage_standalone_from_foreign_cwd(tmp_path):
    """rescue_voyage phải sống khi gọi từ cwd khác (production pattern của fanout)."""
    target = tmp_path / "t"
    target.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=target, check=True)
    (target / "a.txt").write_text("1")
    subprocess.run(["git", "add", "-A"], cwd=target, check=True)
    subprocess.run(["git", "commit", "-qm", "i"], cwd=target, check=True)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "rescue_voyage.py"),
                        "--path", str(target), "--stages", "review",
                        "--review-cmd", "false"],
                       cwd="/tmp", capture_output=True, text=True, timeout=180, check=False)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------- H4 (round-2): crosscheck end-to-end bằng fake CLI đúng production ----------

def _fake_clis(tmp_path):
    audit = tmp_path / "fake_audit.sh"
    audit.write_text(
        "#!/bin/bash\nmkdir -p \"$REVIEW_DIR\"\n"
        "printf '# RE\\n\\n## A1 — slot\\n`a.py:1` co 3 dong\\n' > \"$REVIEW_DIR/README.md\"\n"
        "printf '# PROPOSALS\\n\\n## A1 — slot\\n' > \"$REVIEW_DIR/PROPOSALS.md\"\n")
    verify = tmp_path / "fake_verify.sh"
    verify.write_text(
        "#!/bin/bash\nmkdir -p \"$REVIEW_DIR/EVIDENCE\"\n"
        "printf 'da doc EVIDENCE.\\nCROSSCHECK: N ISSUE\\n' > \"$REVIEW_DIR/EVIDENCE/cross-check.md\"\n")
    for f in (audit, verify):
        f.chmod(0o755)
    return audit, verify


def _voyage_cfg(tmp_path, audit, verify_cli):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        f'[roles.audit]\ncli = "{audit}"\nmodel = ""\nextra_args = []\n\n'
        f'[roles.verify]\ncli = "{verify_cli}"\nmodel = ""\nextra_args = []\n\n'
        '[roles.write]\ncli = "claude"\nmodel = ""\nextra_args = []\n')
    return cfg


def _git_target(tmp_path):
    target = tmp_path / "t"
    target.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=target, check=True)
    (target / "a.py").write_text("def f():\n    return 1\n# end\n")
    subprocess.run(["git", "add", "-A"], cwd=target, check=True)
    subprocess.run(["git", "commit", "-qm", "i"], cwd=target, check=True)
    return target


def _run_review(target, cfg):
    import os as _os
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "rescue_voyage.py"),
         "--path", str(target), "--stages", "review"],
        cwd="/tmp", capture_output=True, text=True, timeout=300, check=False,
        env={**_os.environ, "VIBE_LLM_CONFIG": str(cfg)})


def test_crosscheck_end_to_end(tmp_path):
    audit, verify = _fake_clis(tmp_path)
    target = _git_target(tmp_path)
    r = _run_review(target, _voyage_cfg(tmp_path, audit, str(verify)))
    assert r.returncode == 0, r.stdout + r.stderr
    rdir = target / ".rescue" / "voyage" / "review"
    assert "agent_wrote=True" in r.stdout, r.stdout
    assert "mắt thứ hai đã chấm" in r.stdout
    cross = (rdir / "EVIDENCE" / "cross-check.md").read_text()
    assert "CROSSCHECK: N ISSUE" in cross
    # H2 + H3 cũng phải được nối trong cùng lần chạy review
    assert (rdir / "EVIDENCE" / "number-check.md").exists()
    assert (rdir / "EVIDENCE" / "summary.md").exists()


def test_crosscheck_skips_when_verify_cli_missing(tmp_path):
    audit, _ = _fake_clis(tmp_path)
    target = _git_target(tmp_path)
    r = _run_review(target, _voyage_cfg(tmp_path, audit, "codex-khong-ton-tai-xyz"))
    assert r.returncode == 0, r.stdout + r.stderr  # fail-open: review vẫn xong
    assert "bỏ qua" in r.stdout
    assert not (target / ".rescue" / "voyage" / "review" / "EVIDENCE"
                / "cross-check.md").exists()

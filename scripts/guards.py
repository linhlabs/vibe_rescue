#!/usr/bin/env python3
"""
guards.py — bộ bảo vệ "NEVER BREAK WHAT IS WORKING" + "backup mọi thay đổi":
  - backup_tag(): git tag mốc an toàn (dễ revert: git reset --hard <tag>)
  - run_probe(): chạy probe (tests/smoke) -> mẫu so sánh trước/sau
  - probes_equal(): so sánh (rc + hash output) — regression = không bằng
  - track_change(): ghi CHANGES.log (JSONL) + tái sinh REVERT.md (lệnh revert cụ thể)
Chỉ thao tác trong thư mục evidence của phiên (.rescue/voyage/), không đụng code target.
"""
import hashlib
import json
import shlex
import subprocess
from pathlib import Path


def snapshot_sha(target: Path):
    r = subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"],
                       capture_output=True, text=True, check=False)
    return r.stdout.strip() or None


def backup_tag(target: Path, label="backup-pre-rescue"):
    """Tạo git tag mốc an toàn (bỏ qua nếu trùng tên — suffix số). Trả tên tag."""
    base = label
    n = 0
    tag = base
    while True:
        r = subprocess.run(["git", "-C", str(target), "tag", "-l", tag],
                           capture_output=True, text=True, check=False)
        if not r.stdout.strip():
            break
        n += 1
        tag = f"{base}-{n}"
    r = subprocess.run(["git", "-C", str(target), "tag", tag],
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"không tạo được backup tag {tag}: {r.stderr[:200]}")
    return tag


def run_probe(target: Path, commands):
    """Run each probe command and return {cmd, rc, out_hash, tail} samples.

    Probes are owner-authored test/smoke commands. They are split with shlex and
    run without a shell (shell=False): probes are single commands, so no shell is
    needed, and avoiding it removes the shell-injection surface (bandit B602).
    """
    results = []
    for cmd in commands:
        try:
            r = subprocess.run(shlex.split(cmd), cwd=str(target), capture_output=True,
                               text=True, timeout=1800, check=False)
            rc = r.returncode
            out = (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            rc, out = 124, "probe timed out"
        except (OSError, ValueError):
            rc, out = 127, "probe command unavailable or invalid"
        results.append({"cmd": cmd, "rc": rc,
                        "out_hash": hashlib.sha256(out.encode()).hexdigest(),
                        "tail": out[-300:]})
    return results


def probes_equal(before, after):
    """Never-break: mọi probe phải giống hệt (rc + hash)."""
    if len(before) != len(after):
        return False
    return all(b["cmd"] == a["cmd"] and b["rc"] == a["rc"]
               and b["out_hash"] == a["out_hash"] for b, a in zip(before, after))


def track_change(evidence_dir: Path, entry):
    """Ghi CHANGES.log (JSONL) + tái sinh REVERT.md. entry: {ts, action, branch,
    before_sha, after_sha, revert_cmd, note}."""
    log = evidence_dir / "CHANGES.log"
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    events = []
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    lines = ["# REVERT.md — lệnh phục hồi MỌI thay đổi của phiên này",
             "> Sinh tự động bởi guards.track_change(). Chạy LẦN LƯỢT từ cuối lên đầu.",
             ""]
    for e in reversed(events):
        lines.append(f"## {e.get('ts')} — {e.get('action')} ({e.get('branch', '')})")
        lines.append(f"- trước: `{e.get('before_sha')}` sau: `{e.get('after_sha')}`")
        lines.append(f"- REVERT: `{e.get('revert_cmd')}`")
        if e.get("note"):
            lines.append(f"- note: {e['note']}")
        lines.append("")
    (evidence_dir / "REVERT.md").write_text("\n".join(lines), encoding="utf-8")

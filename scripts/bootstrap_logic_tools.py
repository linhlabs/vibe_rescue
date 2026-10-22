#!/usr/bin/env python3
"""Fetch pinned upstream map tools without changing a target repository."""
import argparse
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "tools" / "upstream"


def sources():
    with (ROOT / "tools" / "manifest.toml").open("rb") as fh:
        return tomllib.load(fh)["logic_map"]["sources"]


def head(path):
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def fetch_one(name, entry, dest=DEST, check_only=False):
    """Existing checkouts are immutable; mismatch is an explicit error."""
    want = entry["commit"]
    path = dest / name
    if path.exists():
        got = head(path)
        if got != want:
            raise RuntimeError(f"[WHAT] {name}: checkout={got}, pin={want}; "
                               "[HOW] move checkout aside and bootstrap again")
        return "ready"
    if check_only:
        return "missing"
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{name}-", dir=dest) as temp:
        tmp = Path(temp) / "src"
        subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--depth", "1",
                        "--no-checkout", entry["url"], str(tmp)], check=True, timeout=180)
        if head(tmp) != want:
            subprocess.run(["git", "-C", str(tmp), "fetch", "--quiet", "--depth", "1",
                            "origin", want], check=True, timeout=180)
        subprocess.run(["git", "-C", str(tmp), "checkout", "--quiet", "--detach", want],
                       check=True, timeout=180)
        if head(tmp) != want:
            raise RuntimeError(f"[WHAT] {name}: checkout không khớp pin {want}")
        tmp.rename(path)
    return "fetched"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tải source tool tạo bản đồ logic, pin SHA.")
    parser.add_argument("--only", help="tên cách nhau bằng dấu phẩy; mặc định: tất cả")
    parser.add_argument("--check", action="store_true", help="chỉ kiểm tra checkout, không tải")
    args = parser.parse_args(argv)
    entries = sources()
    names = [n.strip() for n in args.only.split(",")] if args.only else list(entries)
    unknown = [n for n in names if n not in entries]
    if unknown:
        parser.error(f"tool không có trong manifest: {unknown}")
    failed = False
    for name in names:
        try:
            status = fetch_one(name, entries[name], check_only=args.check)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            status = f"ERROR: {exc}"
            failed = True
        print(f"{name}: {status}")
    return 2 if failed or (args.check and any(not (DEST / n).exists() for n in names)) else 0


if __name__ == "__main__":
    sys.exit(main())

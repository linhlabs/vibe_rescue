#!/usr/bin/env python3
"""Build a deterministic source-only archive without this repository's Git history."""
import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".rescue", "reports", "node_modules", "__pycache__"}


def _paths(repo):
    run = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "--cached",
                          "--others", "--exclude-standard"], capture_output=True, check=False)
    if run.returncode != 0:
        raise RuntimeError("không đọc được Git index")
    names = sorted({p.decode("utf-8", errors="strict") for p in run.stdout.split(b"\0") if p})
    selected = []
    for name in names:
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"đường dẫn Git không an toàn: {name}")
        if any(part in EXCLUDED for part in rel.parts) or rel.parts[:2] in {
                ("tools", "bin"), ("tools", "upstream")}:
            continue
        if rel.parts[0] == "logs_audit" and name != "logs_audit/README.md":
            continue
        path = repo / rel
        if path.is_symlink():
            raise ValueError(f"snapshot từ chối symlink: {name}")
        if not path.is_file():
            continue  # staged deletion
        if not path.resolve().is_relative_to(repo.resolve()):
            raise ValueError(f"snapshot thoát repo: {name}")
        selected.append((name, path))
    return selected


def build(repo: Path, output: Path):
    repo = repo.resolve()
    files = _paths(repo)
    if not files:
        raise ValueError("không có file để đóng gói")
    output.parent.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=False).stdout.strip()
    manifest = {"source_head": head, "files": {},
                "notice": "Source snapshot only; inspect content/secrets before publication."}
    with (output.open("wb") as fh,
          gzip.GzipFile(fileobj=fh, mode="wb", mtime=0,
                        filename="", compresslevel=9) as gz,
          tarfile.open(fileobj=gz, mode="w") as archive):
        for name, path in files:
            data = path.read_bytes()
            manifest["files"][name] = hashlib.sha256(data).hexdigest()
            info = tarfile.TarInfo(f"vibe_rescue/{name}")
            info.size, info.mtime, info.uid, info.gid = len(data), 0, 0, 0
            info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            archive.addfile(info, io.BytesIO(data))
        data = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode()
        info = tarfile.TarInfo("SNAPSHOT_MANIFEST.json")
        info.size, info.mtime, info.uid, info.gid, info.mode = len(data), 0, 0, 0, 0o644
        archive.addfile(info, io.BytesIO(data))
    return {"archive": str(output), "file_count": len(files),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Đóng gói source hiện tại, không mang Git history.")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.repo, args.out), ensure_ascii=False))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"[WHAT] {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

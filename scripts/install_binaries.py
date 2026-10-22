#!/usr/bin/env python3
# Chính sách noqa: 1 tool hỏng không được dừng cả đợt cài còn lại — except rộng có chủ đích.
# ruff: noqa: BLE001
"""
install_binaries.py — tải binary tool (trivy/gitleaks/osv-scanner/lychee/vale/ast-grep)
từ GitHub Releases API về tools/bin/ (gitignored, không commit).

Đọc danh sách từ tools/manifest.toml [binaries]. Mỗi lần cài ghi tools/bin/<tool>.VERSION
(kèm sha256) để tái lập; chạy lại khi cần update.

Usage:
  python3 scripts/install_binaries.py [--only trivy,gitleaks] [--bin-dir tools/bin]
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def fetch_json(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "vibe_rescue"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def pinned_release(owner_repo, tag):
    return fetch_json(f"https://api.github.com/repos/{owner_repo}/releases/tags/{tag}")


def _extract_to(tmp_dir: Path, asset_path: Path, kind):
    """Giải nén về tmp_dir rồi trả về danh sách file bên trong (không phụ thuộc cấu trúc).

    Bảo vệ path traversal: tar dùng filter='data' (py3.12+ cấm abs path/'..'/symlink/device),
    zip kiểm tra member thủ công trước khi extract.
    """
    if kind == "tar.gz":
        with tarfile.open(asset_path) as t:
            for member in t.getmembers():
                path = Path(member.name)
                if (path.is_absolute() or ".." in path.parts or
                        not (member.isfile() or member.isdir())):
                    raise ValueError(f"tar chứa member không an toàn: {member.name}")
            t.extractall(tmp_dir, filter="data")  # nosec B202 - đã kiểm từng member
    elif kind == "zip":
        with zipfile.ZipFile(asset_path) as z:
            for member in z.infolist():
                p = Path(member.filename)
                is_link = (member.external_attr >> 16) & 0o170000 == 0o120000
                if p.is_absolute() or ".." in p.parts or is_link:
                    raise ValueError(f"zip chứa member không an toàn: {member.filename}")
            z.extractall(tmp_dir)  # nosec B202 - member đã kiểm tra thủ công ở vòng lặp trên
    else:
        (tmp_dir / "raw").write_bytes(asset_path.read_bytes())
    return [p for p in tmp_dir.rglob("*") if p.is_file()]


def extract(asset_path: Path, dest: Path, kind, binary_name=None):
    with tempfile.TemporaryDirectory(prefix="vibe-bin-") as td:
        files = _extract_to(Path(td), asset_path, kind)
        cands = files if kind == "raw" else [p for p in files if p.name == (binary_name or dest.name)]
        if len(cands) != 1:
            raise FileNotFoundError(f"không tìm thấy binary '{dest.name}' trong archive")
        shutil.copy(cands[0], dest)
    return dest


def install_one(tool, conf, bin_dir, dry):
    repo_url = conf["url"]
    owner_repo = "/".join(repo_url.split("/releases")[0].split("github.com/")[-1].split("/")[-2:])
    tag, name, digest = conf["tag"], conf["asset"], conf["sha256"]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"{tool}: manifest sha256 thiếu hoặc sai")
    release = pinned_release(owner_repo, tag)
    if release.get("tag_name") != tag:
        raise ValueError(f"{tool}: release tag không khớp manifest")
    ver = tag
    assets = release.get("assets", [])
    asset = next((a for a in assets if a.get("name") == name), None)
    if not asset:
        raise ValueError(f"{tool}: asset {name} không có trong release {tag}")
    kind = "tar.gz" if name.endswith(".tar.gz") else "zip" if name.endswith(".zip") else "raw"
    state = {"tool": tool, "version": ver, "sha256": digest, "asset": name}
    if dry:
        return f"PIN {tool} {tag} {name} sha256:{digest}"
    url = asset["browser_download_url"]
    # GitHub 404 nếu thiếu User-Agent — bắt buộc header cho mọi request
    req = urllib.request.Request(url, headers={"User-Agent": "vibe_rescue"})
    with urllib.request.urlopen(req, timeout=900) as r, tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(asset["name"])[1], delete=False) as f:
        shutil.copyfileobj(r, f)
        tmp = Path(f.name)
    dest = bin_dir / tool
    try:
        actual = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f"{tool}: checksum archive không khớp manifest")
        extract(tmp, dest, kind, conf.get("binary"))
        dest.chmod(0o755)
        (bin_dir / f"{tool}.VERSION").write_text(json.dumps(state, indent=1))
    finally:
        tmp.unlink(missing_ok=True)
    return f"OK {tool} {tag} -> {dest} (archive sha256 {digest})"


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Tải binary scanner (pin từ manifest) vào tools/bin/.")
    ap.add_argument("--only", help="chỉ 1 số tool, cách nhau bằng ','")
    ap.add_argument("--bin-dir", default=str(ROOT / "tools" / "bin"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    only = [x.strip() for x in a.only.split(",") if x.strip()] if a.only else None
    bin_dir, dry = Path(a.bin_dir), a.dry_run
    with open(ROOT / "tools" / "manifest.toml", "rb") as f:
        man = tomllib.load(f)
    bin_dir.mkdir(parents=True, exist_ok=True)
    tools = only or list(man["binaries"].keys())
    failed = 0
    for t in tools:
        try:
            print(install_one(t, man["binaries"][t], bin_dir, dry))
        except Exception as e:
            failed += 1
            print(f"FAIL {t}: {e}")
    print(f"[DONE] {len(tools) - failed}/{len(tools)} ok -> {bin_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

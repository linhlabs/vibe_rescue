import json
import subprocess
import tarfile

import pytest

from scripts.public_snapshot import build


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("reports/\n")
    (repo / "main.py").write_text("print('public')\n")
    (repo / "reports").mkdir()
    (repo / "reports" / "private.txt").write_text("private report")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", ".gitignore", "main.py"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-f", "reports/private.txt"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "-qm", "base"], cwd=repo, check=True)
    return repo


def test_public_snapshot_is_history_free_and_deterministic(tmp_path):
    repo = _repo(tmp_path)
    (repo / "new.rs").write_text("fn new() {}\n")
    first, second = tmp_path / "a.tar.gz", tmp_path / "b.tar.gz"
    one, two = build(repo, first), build(repo, second)
    assert one["sha256"] == two["sha256"]
    with tarfile.open(first) as archive:
        names = archive.getnames()
        assert "vibe_rescue/main.py" in names
        assert "vibe_rescue/new.rs" in names
        assert "vibe_rescue/reports/private.txt" not in names
        assert not any(".git/" in name for name in names)
        manifest = json.load(archive.extractfile("SNAPSHOT_MANIFEST.json"))
        assert "main.py" in manifest["files"]


def test_public_snapshot_rejects_symlink_to_outside(tmp_path):
    repo = _repo(tmp_path)
    (repo / "link.py").symlink_to(tmp_path / "outside.py")
    with pytest.raises(ValueError, match="symlink"):
        build(repo, tmp_path / "release.tar.gz")

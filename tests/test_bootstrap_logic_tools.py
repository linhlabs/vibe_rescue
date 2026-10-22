import subprocess

import pytest

from scripts.bootstrap_logic_tools import fetch_one, head


def test_fetch_is_pinned_and_never_overwrites_existing_checkout(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    (source / "README.md").write_text("first\n")
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "-qm", "first"], cwd=source, check=True)
    pin = head(source)
    entry = {"url": str(source), "commit": pin}
    dest = tmp_path / "upstream"
    assert fetch_one("tool", entry, dest, check_only=True) == "missing"
    assert fetch_one("tool", entry, dest) == "fetched"
    assert fetch_one("tool", entry, dest, check_only=True) == "ready"
    assert head(dest / "tool") == pin
    with pytest.raises(RuntimeError, match="checkout"):
        fetch_one("tool", {**entry, "commit": "0" * 40}, dest)

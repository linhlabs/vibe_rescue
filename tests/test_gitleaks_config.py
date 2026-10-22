"""Gitleaks exclusions must not silently skip the whole public source tree."""
import re
import tomllib
from pathlib import Path


def test_global_allowlist_does_not_match_repo_root():
    root = Path(__file__).resolve().parents[1]
    with (root / ".gitleaks.toml").open("rb") as file:
        config = tomllib.load(file)
    patterns = config["allowlist"]["paths"]
    source = "/tmp/vibe_rescue/scripts/rescue_voyage.py"
    assert not any(re.search(pattern, source) for pattern in patterns)
    assert not any(re.search(pattern, "/tmp/reports/vibe_rescue/README.md")
                   for pattern in patterns)
    assert not any(re.search(pattern, "/tmp/vibe_rescue/.rescue/evidence.json")
                   for pattern in patterns)
    assert any(re.search(pattern, "/tmp/vibe_rescue/tests/fixtures/fake.py")
               for pattern in patterns)

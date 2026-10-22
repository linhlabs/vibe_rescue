import pytest

from scripts.delta_gate import allowed
from tools.meta import scan


def test_manifest_single_source():
    """Pins của scan.py phải đọc từ tools/manifest.toml (không nhân bản trong code)."""
    man = scan.load_manifest()
    assert scan.PY_PIN == man["core"]["python"]
    assert scan.JS_PIN == man["core"]["js"]
    assert scan.CORE == man["core"]["order"]["tools"]
    assert "ruff" in scan.CORE and "semgrep" in scan.CORE


def test_scan_parsers_registered():
    """scan.py dùng PARSERS của parsers.py — không nhân bản parser."""
    assert "ruff" in scan.PARSERS and "semgrep" in scan.PARSERS


@pytest.mark.parametrize("k, allow, expected", [
    ("ruff|src/a.py|F401", ["ruff"], True),
    ("ruff|src/a.py|F401", ["src/gen/"], False),
    ("bandit|src/gen/x.py|B301", ["src/gen/"], True),
    ("bandit|src/gen/x.py|B301", ["bandit|src/"], True),
    ("bandit|src/gen/x.py|B301", ["bandit|src/*"], True),
    ("ruff|src/a.py|F401", [], False),
])
def test_delta_allowed(k, allow, expected):
    assert allowed(k, allow) is expected

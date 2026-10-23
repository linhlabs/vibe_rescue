"""Generic handoff must be complete enough to assign review without claiming safety."""

from scripts.architecture_atlas import build
from scripts.handoff import render
from scripts.repo_explorer import index


def _model(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "core").mkdir()
    (tmp_path / "README.md").write_text(
        "# Example service\n\nThis app routes requests to a backend with no runtime proof yet.\n"
        "\n## Request journey\n"
        "1. `api.entry.handle` accepts a request.\n"
        "2. An unobserved worker finishes it.\n")
    (tmp_path / "api" / "entry.py").write_text(
        "from core.service import mask\n"
        "def handle(value):\n    return mask(value)\n")
    (tmp_path / "core" / "service.py").write_text(
        "def mask(value):\n    return value\n")
    (tmp_path / "core" / "config.yaml").write_text("mode: example\n")
    data = index(tmp_path, sources=("api", "core"), asset_dirs=())
    return build(tmp_path, ("api", "core"), data, profiles=("pii", "agent"))


def test_handoff_contains_all_layers_and_keeps_controls_unverified(tmp_path):
    model = _model(tmp_path)
    out = tmp_path / "reports"
    paths = render(model, tmp_path, out)
    assert {p.name for p in paths} == {"HANDOFF.md", "HANDOFF.vi.md", "handoff.html", "handoff.vi.html", "REVIEW_WORKSHEET.md", "REVIEW_WORKSHEET.vi.md"}
    en = (out / "HANDOFF.md").read_text()
    vi = (out / "HANDOFF.vi.md").read_text()
    page = (out / "handoff.html").read_text()
    for value in ("api/entry.py:2", "core/config.yaml", "Unknown binding", "H02"):
        assert value in en
    assert "api.entry.handle" in en and "core/service.py" in en
    assert "candidate" in en and "runtime" in en.lower()
    assert "Bàn giao cho team" in vi and "Chưa nối được hàm" in vi
    assert "REVIEW REQUIRED" in page and "api/entry.py:2" in page
    assert "REVIEW_WORKSHEET.md" in page
    assert "| H02 —" in (out / "REVIEW_WORKSHEET.md").read_text()
    assert "| H02 —" in (out / "REVIEW_WORKSHEET.vi.md").read_text()
    assert "Production ready" not in page


def test_handoff_rerun_preserves_team_review(tmp_path):
    model = _model(tmp_path)
    out = tmp_path / "reports"
    render(model, tmp_path, out)
    worksheet = out / "REVIEW_WORKSHEET.md"
    worksheet.write_text("Reviewed on a pinned build.\n")
    render(model, tmp_path, out)
    assert worksheet.read_text() == "Reviewed on a pinned build.\n"


def test_handoff_html_escapes_untrusted_documentation(tmp_path):
    model = _model(tmp_path)
    model["overview"]["purpose"] = "</script><script>alert(1)</script>"
    render(model, tmp_path, tmp_path / "reports")
    page = (tmp_path / "reports" / "handoff.html").read_text()
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page

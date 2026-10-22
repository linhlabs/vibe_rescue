from tools.meta import parsers

JUNIT = """<?xml version="1.0"?><testsuite name="schemathesis">
<testcase classname="openapi.json::POST /drugs" name="test_1">
  <failure message="500 Internal Server Error">response 500</failure>
</testcase>
<testcase classname="openapi.json::GET /patients/{id}" name="test_2">
  <error message="requests.exceptions.ConnectionError" />
</testcase>
</testsuite>"""


def test_parse_mutmut():
    text = ("1. Survived ./src/price.py:12 (line 12)\n"
            "2. Survived ./src/price.py:30 (line 30)\n"
            "3. Killed ./src/q.py:1\n")
    out = parsers.parse_mutmut(text)
    assert len(out) == 2
    assert out[0]["rule"] == "MUT-survived" and out[0]["file"] == "./src/price.py"
    assert out[0]["severity"] == "medium"


def test_parse_schemathesis_junit():
    out = parsers.parse_schemathesis_junit(JUNIT)
    assert len(out) == 2
    assert out[0]["rule"] == "SCH-failure" and out[0]["severity"] == "medium"
    assert out[1]["rule"] == "SCH-error" and out[1]["severity"] == "high"
    assert "POST /drugs" in out[0]["file"]


def test_parse_depcruise_real_violations():
    """Regression F2: real dependency-cruiser output nests violations in summary."""
    data = {"modules": [{"source": "a.js"}],
            "summary": {"violations": [
                {"rule": "circular", "from": {"source": "a.js"}, "to": "b.js",
                 "message": "cycle a->b"}]}}
    out = parsers.parse_depcruise(data)
    assert len(out) == 1
    assert out[0]["rule"] == "circular" and out[0]["file"] == "a.js"


def test_parse_knip_real_issues():
    """Regression F3: knip 6.x emits top-level issues (not files[].issues)."""
    data = {"files": [{"file": "src/a.js"}],
            "issues": [{"file": "src/a.js", "symbol": "unusedFn",
                        "issueType": "unused", "line": 3}]}
    out = parsers.parse_knip(data)
    assert len(out) == 1
    assert out[0]["rule"] == "KNIP-unused" and out[0]["file"] == "src/a.js"
    assert out[0]["line"] == 3


def test_parse_knip_legacy_nested_issues():
    """Regression: legacy files[].issues shape must keep the parent file."""
    data = {"files": [{"file": "src/a.js", "issues": [
        {"type": "unused", "symbol": "unusedFn", "line": 3}]}]}
    out = parsers.parse_knip(data)
    assert len(out) == 1 and out[0]["file"] == "src/a.js"


def test_parse_promptfoo():
    data = {"results": [
        {"prompt": {"id": "p1"}, "success": True},
        {"prompt": {"id": "p2"}, "success": False, "vars": {"task": "x"},
         "error": None},
        {"prompt": {"id": "p3"}, "success": False, "error": "provider timeout"},
    ]}
    out = parsers.parse_promptfoo(data)
    assert len(out) == 2
    assert out[0]["rule"] == "BEHAVIOR-fail" and out[0]["severity"] == "medium"
    assert out[1]["severity"] == "high"


def test_parse_osv():
    data = {"results": [{"source": {"path": "requirements.txt"}, "packages": [
        {"package": {"name": "requests"}, "vulnerabilities": [
            {"id": "OSV-2026-1", "summary": "SSRF",
             "severity": [{"type": "CVSS_V3", "score": "9.8"}]},
            {"id": "OSV-2026-2", "severity": [{"type": "CVSS_V3", "score": "5.1"}]},
        ]}]}]}
    out = parsers.parse_osv(data)
    assert len(out) == 2
    assert out[0]["severity"] == "high" and out[1]["severity"] == "medium"


def test_parse_lychee():
    data = [{"input": {"path": "docs/README.md"},
             "output": {"failures": [{"code": 404, "message": "Not Found",
                                      "link": "https://x.com/dead"}]}}]
    out = parsers.parse_lychee(data)
    assert len(out) == 1 and out[0]["rule"] == "LINK-broken"
    assert out[0]["file"] == "docs/README.md"

from tools.meta import parsers as scan

ROOT = "/repo"


def test_parse_ruff():
    data = {"results": [
        {"code": "F401", "filename": "/repo/src/x.py", "location": {"row": 12}, "message": "imported but unused"},
        {"code": "E501", "filename": "/repo/src/y.py", "location": {"row": 3}, "message": "too long"},
    ]}
    out = scan.parse_ruff(data, ROOT)
    assert out[0]["rule"] == "F401" and out[0]["severity"] == "high" and out[0]["file"] == "src/x.py"
    assert out[1]["severity"] == "medium"


def test_parse_vulture():
    text = "src/a.py:12: unused function 'foo' (90% confidence)\nsrc/b.py:4: unused variable 'x' (60% confidence)"
    out = scan.parse_vulture(text, ROOT)
    assert len(out) == 2
    assert out[0]["severity"] == "medium" and out[0]["line"] == 12
    assert out[1]["severity"] == "low"


def test_parse_radon():
    text = "src/a.py\n    F:12 foo - (14)\n    M:30 Bar.run - (22)\nsrc/b.py\n    F:1 ok - (5)"
    out = scan.parse_radon(text)
    assert len(out) == 2
    assert out[0]["severity"] == "medium" and out[0]["line"] == 12
    assert out[1]["severity"] == "high" and out[1]["line"] == 30


def test_parse_radon_new_format():
    """radon 6.x format 'F 25:0 main - D (23)' — parser regression."""
    text = ("skills/x.py\n    F 25:0 main - D (23)\n"
            "    F 65:0 run - C (12)\n"
            "src/y.py\n    F 1:0 ok - A (4)")
    out = scan.parse_radon(text)
    assert len(out) == 2
    assert out[0]["line"] == 25 and out[0]["severity"] == "high"
    assert out[0]["file"] == "skills/x.py"
    assert out[1]["line"] == 65 and out[1]["severity"] == "medium"


def test_parse_bandit():
    data = {"results": [{"test_id": "B301", "filename": "/repo/src/a.py", "line_number": 7,
                         "issue_text": "pickle", "issue_severity": "HIGH", "issue_confidence": "MEDIUM"}]}
    out = scan.parse_bandit(data, ROOT)
    assert out[0]["rule"] == "B301" and out[0]["severity"] == "high"


def test_parse_jscpd():
    data = {"duplicates": [{"firstFile": {"name": "a.js", "start": 1},
                            "secondFile": {"name": "b.js", "start": 40}, "lines": 12}]}
    out = scan.parse_jscpd(data)
    assert out[0]["file"] == "b.js" and out[0]["severity"] == "medium"
    data["duplicates"][0]["lines"] = 60
    out = scan.parse_jscpd(data)
    assert out[0]["severity"] == "high"


def test_parse_depcruise_cycle():
    data = {"summary": {"cycles": [[{"source": "a.js"}, {"source": "b.js"}, {"source": "a.js"}]]}}
    out = scan.parse_depcruise(data)
    assert len(out) == 3 and out[0]["severity"] == "high"


def test_parse_mdlint():
    data = {"docs/x.md": [{"lineNumber": 1, "ruleNames": ["MD013"], "ruleDescription": "line length"},
                          {"lineNumber": 2, "ruleNames": ["MD001"]}]}
    out = scan.parse_mdlint(data)
    assert len(out) == 2 and out[0]["rule"] == "MD013"


def test_parse_trivy():
    data = {"Results": [{"Target": "app:1.0", "Vulnerabilities": [
        {"VulnerabilityID": "CVE-2026-1", "Severity": "CRITICAL", "PkgName": "libx", "Title": "boom"}],
        "Secrets": [{"RuleID": "R1", "StartLine": 9, "Description": "key", "Match": "AKIA..."}]}]}
    out = scan.parse_trivy(data)
    assert out[0]["severity"] == "critical" and out[1]["severity"] == "high"

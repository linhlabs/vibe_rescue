#!/usr/bin/env python3
# Chính sách noqa: norm_path phải trả được path tương đối dù đường dẫn đầu vào lạ (kể cả Windows).
# ruff: noqa: BLE001
"""
parsers.py — pure functions: chuyển output thô của từng scanner thành findings chuẩn.

Không IO, không subprocess — unit-testable. scan.py gọi qua `from tools.meta.parsers import *`.
Schema finding: {"rule","severity","file","line","message","evidence"},
severity ∈ high|medium|low.

Thêm tool mới = thêm 1 parse_<tool>() + 1 dòng vào PARSERS.
"""
import os
import re
import xml.etree.ElementTree as ET

__all__ = ["PARSERS", "norm_path", "sev_of_rule"]


def norm_path(p, root):
    try:
        base = os.path.abspath(root)
        full = os.path.abspath(p if os.path.isabs(p) else os.path.join(base, p))
        rel = os.path.relpath(full, base)
        return rel if not rel.startswith("..") else str(p)
    except Exception:
        return str(p)


def sev_of_rule(code):
    code = code or ""
    if code.startswith(("F", "E9")):
        return "high"
    return "medium" if code[:1] in ("E", "C", "B") else "low"


def parse_ruff(data, root):
    out = []
    for item in data.get("results") if isinstance(data, dict) else data:
        if not isinstance(item, dict):
            continue
        loc = item.get("location", {})
        out.append({
            "rule": item.get("code", "RUFF"),
            "severity": sev_of_rule(item.get("code")),
            "file": norm_path(item.get("filename", ""), root),
            "line": loc.get("row"),
            "message": item.get("message", ""),
            "evidence": item.get("code", ""),
        })
    return out


def parse_vulture(text, root):
    out = []
    pat = re.compile(r"^(?P<file>.+?):(?P<line>\d+):\s+(?P<message>.*?)\s+\((?P<conf>\d+)% confidence\)$")
    for line in text.splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        conf = int(m.group("conf"))
        out.append({
            "rule": "V101-dead-code",
            "severity": "medium" if conf >= 90 else "low",
            "file": norm_path(m.group("file"), root),
            "line": int(m.group("line")),
            "message": m.group("message"),
            "evidence": f"{conf}% confidence",
        })
    return out


def parse_radon(text, root=None):
    """radon 6.x đổi format: '    F 25:0 main - D (23)' (mới)
    và '    F:25 main - (23)' (cũ) — parse cả hai (bug phát hiện trên target thật)."""
    out = []
    cur = None
    pat_new = re.compile(r"^\s+[FCM]\s+(\d+):\d+\s+(.+?)\s+-\s+[A-F]?\s*\(\s*([\d.]+)\)")
    pat_old = re.compile(r"^\s+[FCM]:(\d+)\s+(.+?)\s*- \(([\d.]+)\)")
    for line in text.splitlines():
        if line and not line[0].isspace():
            cur = line.strip()
            continue
        m = pat_new.match(line) or pat_old.match(line)
        if not m or not cur:
            continue
        c = float(m.group(3))
        if c < 11:
            continue
        out.append({
            "rule": "C901-complexity",
            "severity": "high" if c >= 20 else "medium",
            "file": norm_path(cur, root) if root is not None else cur,
            "line": int(m.group(1)),
            "message": f"{m.group(2).strip()} complexity {c:.0f}"[:120],
            "evidence": f"cyclo={c}",
        })
    return out


def parse_bandit(data, root):
    out = []
    for r in data.get("results", []):
        sev = (r.get("issue_severity") or "LOW").lower()
        if sev not in ("high", "medium", "low"):
            sev = "low"  # bandit can emit "UNDEFINED"; normalize to the lowest rank
        out.append({
            "rule": r.get("test_id", "B000"),
            "severity": sev,
            "file": norm_path(r.get("filename", ""), root),
            "line": r.get("line_number"),
            "message": r.get("issue_text", ""),
            "evidence": r.get("issue_confidence", ""),
        })
    return out


def parse_jscpd(data, root=None):
    out = []
    for d in data.get("duplicates", []):
        f1, f2 = d.get("firstFile", {}), d.get("secondFile", {})
        lines = d.get("lines", 0)
        if not f1 or not f2:
            continue
        out.append({
            "rule": "CPD-copy-paste",
            "severity": "high" if lines >= 50 else "medium",
            "file": f2.get("name", ""),
            "line": f2.get("start"),
            "message": f"{lines} lines duplicated with {f1.get('name')}",
            "evidence": f"lines={lines} first={f1.get('start')}",
        })
    return out


def _knip_issue_list(data):
    """Collect issue dicts from both supported knip JSON shapes.

    In the legacy ``files[].issues`` shape the issue has no own "file" key, so
    the parent file is copied onto each issue to keep attribution intact.
    """
    issues = [i for i in (data.get("issues") or []) if isinstance(i, dict)]
    for f in data.get("files", []):
        if not isinstance(f, dict):
            continue
        parent_file = f.get("file", "")
        for i in (f.get("issues") or []):
            if not isinstance(i, dict):
                continue
            if not i.get("file"):
                i = {**i, "file": parent_file}
            issues.append(i)
    return issues


def parse_knip(data, root=None):
    """knip --reporter json.

    knip 6.x emits a top-level ``issues`` array ({file, symbol, issueType, line}).
    The older ``files[].issues`` nesting is also accepted so neither is dropped.
    """
    if isinstance(data, list):
        data = {"files": data}
    out = []
    for issue in _knip_issue_list(data or {}):
        issue_type = issue.get("issueType") or issue.get("type") or "unused"
        out.append({
            "rule": f"KNIP-{issue_type}",
            "severity": "medium" if issue_type == "unused" else "low",
            "file": issue.get("file", ""),
            "line": issue.get("line"),
            "message": issue.get("message", "") or issue.get("symbol", ""),
            "evidence": issue.get("symbol", ""),
        })
    return out


def _depcruise_cycle_findings(cycles):
    out = []
    for c in cycles:
        if not isinstance(c, (list, tuple)):
            continue
        for m in c:
            if not isinstance(m, dict):
                continue
            chain = [x.get("source", "?") if isinstance(x, dict) else str(x) for x in c[:4]]
            out.append({
                "rule": "ARCH-cycle",
                "severity": "high",
                "file": m.get("source", ""),
                "line": None,
                "message": "import cycle: " + " -> ".join(chain),
                "evidence": f"cycle of {len(c)} modules",
            })
    return out


def _depcruise_violation_findings(violations):
    out = []
    for v in violations:
        if not isinstance(v, dict):
            continue
        src = v.get("from")
        file = src.get("source", "") if isinstance(src, dict) else str(src or "")
        out.append({
            "rule": v.get("rule", "ARCH-violation"),
            "severity": "high",
            "file": file,
            "line": None,
            "message": v.get("message", ""),
            "evidence": str(v.get("to", "")),
        })
    return out


def parse_depcruise(data, root=None):
    """dependency-cruiser --output-type json.

    Real output nests rule violations in ``summary.violations`` (e.g. circular,
    forbidden). Legacy fixtures put cycles in ``summary.cycles``; both are kept.
    """
    if not isinstance(data, dict):
        return []
    summary = data.get("summary") or {}
    out = _depcruise_cycle_findings(summary.get("cycles") or data.get("cycles") or [])
    out += _depcruise_violation_findings(summary.get("violations") or data.get("violations") or [])
    return out


def parse_mdlint(data, root=None):
    out = []
    if isinstance(data, list):
        data = {d.get("fileName", "?"): d.get("messages", []) for d in data}
    for path, msgs in data.items():
        if isinstance(msgs, dict):
            msgs = msgs.get("messages", [])
        for m in msgs:
            out.append({
                "rule": (m.get("ruleNames") or ["MD000"])[0],
                "severity": "medium" if str(m.get("ruleNames", [""])[0]).startswith("MD03") else "low",
                "file": path,
                "line": m.get("lineNumber"),
                "message": m.get("ruleDescription", "") or m.get("errorDetail", ""),
                "evidence": m.get("errorDetail", ""),
            })
    return out


def parse_deptry(data, root=None):
    out = []
    for e in data.get("errors", []) if isinstance(data, dict) else []:
        out.append({
            "rule": e.get("code", "DEP"),
            "severity": "medium",
            "file": e.get("file", ""),
            "line": e.get("line"),
            "message": f"{e.get('message', '')} module={e.get('module', '')}",
            "evidence": e.get("data", ""),
        })
    return out


def parse_importlinter(data, root):
    out = []
    if isinstance(data, dict) and "contracts" in data:
        items = []
        for c in data["contracts"].values() if isinstance(data["contracts"], dict) else []:
            items += c.get("violations", [])
    else:
        items = []
        for line in (data if isinstance(data, list) else [data]):
            if isinstance(line, dict) and "violations" in line:
                items += line["violations"]
    for v in items:
        if isinstance(v, dict):
            loc = v.get("location", {})
            f = loc.get("module", "") if isinstance(loc, dict) else str(loc)
            line = loc.get("line") if isinstance(loc, dict) else None
            out.append({
                "rule": "LAYER-violation",
                "severity": "high",
                "file": f,
                "line": line,
                "message": v.get("message", ""),
                "evidence": v.get("code", ""),
            })
    # text fallback: "src/x.py:12 violates ..."
    if isinstance(data, str):
        pat = re.compile(r"^\(?([^:\s()]+):?(\d+)?\)?.*?violates")
        for line in data.splitlines():
            m = pat.match(line.strip())
            if not m:
                continue
            out.append({"rule": "LAYER-violation", "severity": "high",
                        "file": m.group(1), "line": int(m.group(2)) if m.group(2) else None,
                        "message": line.strip()[:200], "evidence": "import-linter"})
    return out


def parse_trivy(data, root=None):
    out = []
    for r in data.get("Results", []):
        for v in r.get("Vulnerabilities", []):
            out.append({
                "rule": v.get("VulnerabilityID", "CVE"),
                "severity": (v.get("Severity") or "LOW").lower(),
                "file": r.get("Target", ""),
                "line": None,
                "message": f"{v.get('Title', '')} pkg={v.get('PkgName', '')}",
                "evidence": v.get("InstalledVersion", ""),
            })
        for m in r.get("Misconfigurations", []):
            out.append({
                "rule": m.get("ID", "MISCONF"),
                "severity": (m.get("Severity") or "LOW").lower(),
                "file": r.get("Target", ""),
                "line": m.get("StartLine"),
                "message": m.get("Title", "") or m.get("Message", ""),
                "evidence": m.get("CauseMetadata", {}).get("Code", "") if isinstance(m.get("CauseMetadata"), dict) else "",
            })
        for s in r.get("Secrets", []):
            out.append({
                "rule": s.get("RuleID", "SECRET"),
                "severity": "high",
                "file": r.get("Target", ""),
                "line": s.get("StartLine"),
                "message": s.get("Description", ""),
                "evidence": s.get("Match", "")[:80],
            })
    return out


def parse_gitleaks(data, root=None):
    out = []
    items = data if isinstance(data, list) else data.get("findings", [])
    for f in items:
        out.append({
            "rule": f.get("RuleID", "LEAK"),
            "severity": "high",
            "file": f.get("File", ""),
            "line": f.get("StartLine"),
            "message": f.get("Description", ""),
            "evidence": f.get("Secret", "")[:40],
        })
    return out


def _semgrep_parse(data):
    out = []
    for r in data.get("results", []):
        sev = (r.get("extra", {}).get("severity") or "WARNING").upper()
        sev = {"ERROR": "high", "WARNING": "medium"}.get(sev, "low")
        out.append({
            "rule": r.get("check_id", "SEMGREP"),
            "severity": sev,
            "file": r.get("path", ""),
            "line": r.get("start", {}).get("line"),
            "message": r.get("extra", {}).get("message", ""),
            "evidence": r.get("extra", {}).get("lines", "")[:120],
        })
    return out


def parse_mutmut(text, root=None):
    """mutmut run — mỗi mutant 'sống sót' là một finding (tests chưa đủ tư cách gate)."""
    out = []
    pat = re.compile(r"Survived\s+(.+?\.py):(\d+)")
    for line in text.splitlines():
        m = pat.search(line)
        if not m:
            continue
        out.append({
            "rule": "MUT-survived",
            "severity": "medium",
            "file": m.group(1),
            "line": int(m.group(2)),
            "message": line.strip()[:160],
            "evidence": "mutant survived — test không bắt được thay đổi logic",
        })
    return out


def parse_schemathesis_junit(xml_text, root=None):
    """schemathesis --junit-xml: testcase failure/error = finding."""
    out = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out
    for tc in root.iter("testcase"):
        for f in tc.iter("failure"):
            out.append({
                "rule": "SCH-failure", "severity": "medium",
                "file": tc.get("classname", ""), "line": None,
                "message": (f.get("message") or (f.text or ""))[:200],
                "evidence": "schemathesis contract failure",
            })
        for e in tc.iter("error"):
            out.append({
                "rule": "SCH-error", "severity": "high",
                "file": tc.get("classname", ""), "line": None,
                "message": (e.get("message") or (e.text or ""))[:200],
                "evidence": "schemathesis contract error",
            })
    return out


def parse_promptfoo(data, root=None):
    """promptfoo eval --format json: test có error/success=false = finding."""
    out = []
    for r in data.get("results", []) or []:
        fail = r.get("error") is not None or r.get("success") is False
        if not fail:
            continue
        out.append({
            "rule": "BEHAVIOR-fail",
            "severity": "high" if r.get("error") else "medium",
            "file": str(r.get("prompt", {}).get("id", "")) or "prompt",
            "line": None,
            "message": (r.get("error") or "")[:200],
            "evidence": f"vars={r.get('vars')}",
        })
    return out


def parse_osv(data, root=None):
    """osv-scanner --format json: vulnerability theo package."""
    out = []
    for res in data.get("results", []) or []:
        path = res.get("source", {}).get("path", "")
        for pkg in res.get("packages", []) or []:
            name = pkg.get("package", {}).get("name", "")
            for v in pkg.get("vulnerabilities", []) or []:
                sev = "medium"
                for s in v.get("severity", []) or []:
                    if s.get("type") == "CVSS_V3" and s.get("score"):
                        try:
                            score = float(str(s["score"])[:3])
                        except ValueError:
                            continue
                        sev = "high" if score >= 9.0 else "medium" if score >= 4.0 else "low"
                        break
                out.append({
                    "rule": v.get("id", "OSV"),
                    "severity": sev,
                    "file": path,
                    "line": None,
                    "message": f"{name}: {v.get('summary', '')[:150]}",
                    "evidence": f"aliases={v.get('aliases', [])} fixed={v.get('fixed', '?')}",
                })
    return out


def parse_lychee(data, root=None):
    """lychee --format json: link hỏng trong tài liệu."""
    out = []
    for item in data if isinstance(data, list) else []:
        for f in item.get("output", {}).get("failures", []) or []:
            out.append({
                "rule": "LINK-broken",
                "severity": "low",
                "file": item.get("input", {}).get("path", ""),
                "line": None,
                "message": f"{f.get('link', '')} -> {f.get('message', '')[:100]}",
                "evidence": f"code={f.get('code')}",
            })
    return out


def parse_archgraph(data, root=None):
    """archgraph.py: import cycles + hub modules (bằng chứng cho over-engineering)."""
    out = []
    for cyc in data.get("cycles", []) or []:
        out.append({
            "rule": "ARCH-cycle",
            "severity": "high",
            "file": cyc[0] if cyc else "",
            "line": None,
            "message": "import cycle: " + " -> ".join(cyc[:5]),
            "evidence": f"cycle {len(cyc)} modules",
        })
    for h in data.get("summary", {}).get("hub_modules", []) or []:
        out.append({
            "rule": "HUB-fan-in",
            "severity": "medium",
            "file": h.get("module", ""),
            "line": None,
            "message": f"{h.get('fan_in')} modules import file này (god/hub)",
            "evidence": f"lines={h.get('lines')}",
        })
    return out


PARSERS = {
    "ruff": parse_ruff, "vulture": parse_vulture, "radon": parse_radon,
    "bandit": parse_bandit, "jscpd": parse_jscpd, "knip": parse_knip,
    "dependency-cruiser": parse_depcruise, "markdownlint-cli": parse_mdlint,
    "deptry": parse_deptry, "import-linter": parse_importlinter,
    "semgrep": _semgrep_parse, "trivy": parse_trivy, "gitleaks": parse_gitleaks,
    "mutmut": parse_mutmut, "schemathesis": parse_schemathesis_junit,
    "promptfoo": parse_promptfoo, "osv-scanner": parse_osv,
    "lychee": parse_lychee, "archgraph": parse_archgraph,
}

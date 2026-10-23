#!/usr/bin/env python3
# Chính sách noqa: loader phải không bao giờ crash vì output tool xấu — except rộng
# và pattern "trả về fallback" là có chủ đích (RULES R11: evidence vẫn phải chạy tiếp).
# Pins + danh sách tool nằm ở tools/manifest.toml (single source of truth), KHÔNG nhân bản.
# ruff: noqa: BLE001
"""
scan.py — runner scanner deterministic của vibe_rescue.

Chạy 1 tool (lệnh pin từ tools/manifest.toml qua uvx/npx/binary), chuẩn hóa kết quả bằng
tools/meta/parsers.py về dạng:
  {"tool","version","target","ok","skipped","error","findings":[
     {"rule","severity","file","line","message","evidence"}]}

severity: high|medium|low. Đây là tầng MÁY — bình luận của LLM nằm ở auditor, không ở đây.

Usage:
  python3 tools/meta/scan.py --tool <name> --target <dir> [--out <json>] [--rules <dir>]
  python3 tools/meta/scan.py --tool schemathesis --target <dir> -- --scenario? (xem precheck)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

if __package__:
    from tools.meta import parsers, redact
else:
    import parsers
    import redact

PARSERS = parsers.PARSERS

ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / "tools" / "bin"
# Per-run temp artifacts (file paths + one dir). Created lazily in main() and removed
# in a finally block so fanout subprocesses never leak files into the system temp dir.
DEPTRY_REPORT = None
GITLEAKS_REPORT = None
SCH_REPORT = None
PF_REPORT = None
JSCPD_OUT = None


def _make_tmp(suffix, prefix):
    """mkstemp wrapper that closes the file descriptor (only the path is used)."""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)
    return path


def _init_tmp_artifacts():
    """Create the temp paths referenced by scanner command builders."""
    global DEPTRY_REPORT, GITLEAKS_REPORT, SCH_REPORT, PF_REPORT, JSCPD_OUT
    DEPTRY_REPORT = _make_tmp(".json", "deptry-report-")
    GITLEAKS_REPORT = _make_tmp(".json", "gitleaks-report-")
    SCH_REPORT = _make_tmp(".xml", "schemathesis-")
    PF_REPORT = _make_tmp(".json", "promptfoo-")
    JSCPD_OUT = tempfile.mkdtemp(prefix="jscpd-out-")


def _cleanup_tmp_artifacts():
    """Remove temp files and the jscpd output dir (best effort)."""
    import shutil as _shutil
    for path in (DEPTRY_REPORT, GITLEAKS_REPORT, SCH_REPORT, PF_REPORT):
        try:
            if path:
                Path(path).unlink(missing_ok=True)
        except OSError:
            pass
    try:
        if JSCPD_OUT:
            _shutil.rmtree(JSCPD_OUT, ignore_errors=True)
    except OSError:
        pass


def load_manifest():
    """Đọc tools/manifest.toml — nguồn pin duy nhất. Fail-loud nếu thiếu."""
    with open(ROOT / "tools" / "manifest.toml", "rb") as f:
        return tomllib.load(f)


MAN = load_manifest()
PY_PIN = MAN["core"]["python"]
JS_PIN = MAN["core"]["js"]
CORE = MAN["core"]["order"]["tools"]
TIER3_PY = MAN["tier3"]["python"]
TIER3_JS = MAN["tier3"]["js"]
BINARIES = MAN["binaries"]
MCP_CONF = MAN["mcp"]["mcp-conformance"]


def tool_version(tool):
    """Return the version of a tool.

    Python/JS tools are pinned in tools/manifest.toml. Binary tools record the
    real installed version in tools/bin/<tool>.VERSION (written by
    install_binaries.py), so evidence is reproducible instead of showing "?".
    """
    if tool == "archgraph":
        return "builtin"
    for table in (PY_PIN, JS_PIN, TIER3_PY, TIER3_JS):
        v = table.get(tool)
        if isinstance(v, str):
            return v
    if tool == "mcp-conformance":
        return MCP_CONF.get("version", "?")
    if tool in BINARIES:
        vfile = BIN_DIR / f"{tool}.VERSION"
        if vfile.exists():
            try:
                return json.loads(vfile.read_text()).get("version", "?")
            except (json.JSONDecodeError, OSError):
                return "?"
    return "?"


def emit(result, out):
    # H1 (audit v0.3.5): che khóa ở NGUỒN — mọi raw/<tool>.json đi qua đây,
    # không bao giờ ghi giá trị key-like ra đĩa (gitleaks --redact chỉ là lớp 2).
    result["findings"] = redact.mask_findings(result.get("findings"))
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=1))


def run(cmd, cwd=None, timeout=600):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                          check=False)


def find_openapi(root: Path):
    for name in ("openapi.json", "openapi.yaml", "openapi.yml", "swagger.json"):
        if (root / name).exists():
            return name
    return None


def _arg_value(extra, flag):
    for i, a in enumerate(extra):
        if a == flag and i + 1 < len(extra):
            return extra[i + 1]
    return None


def vulture_py_files(root: Path, excludes):
    """.py của target trừ exclude — vulture không có option exclude dir."""
    rels = []
    for p in root.rglob("*.py"):
        rel = str(p.relative_to(root))
        if any(e in rel for e in excludes):
            continue
        rels.append(rel)
    return rels


# ---------- commands (tách theo họ — mỗi họ một hàm bảng-lệnh, dễ thêm tool mới) ----------

def _cmd_python(tool, root, rootp, extra):
    pin = PY_PIN.get(tool)
    if tool == "ruff":
        excludes = MAN.get("tool_options", {}).get("ruff", {}).get("exclude_paths", [])
        cmd = ["uvx", "--from", f"ruff=={pin}", "ruff", "check",
               "--output-format", "json", "-q"]
        for e in excludes:
            cmd += ["--exclude", e]
        return cmd + extra + [rootp]
    if tool == "vulture":
        excludes = MAN.get("tool_options", {}).get("vulture", {}).get("exclude_paths", [])
        targets = vulture_py_files(root, excludes)
        if not targets:
            return None  # precheck sẽ báo skip trước (xem precheck vulture_files)
        return ["uvx", "--from", f"vulture=={pin}", "vulture"] \
            + targets + ["--min-confidence", "60"] + extra
    if tool == "radon":
        return ["uvx", "--from", f"radon=={pin}", "radon", "cc",
                "-s", "-n", "C", "--order", "SCORE", rootp] + extra
    if tool == "bandit":
        # bandit loại trừ theo đường dẫn tương đối khi scan root '.', nên:
        # cwd=target (đã set ở main), khoảng exclude phải bắt đầu bằng './'
        excludes = MAN.get("tool_options", {}).get("bandit", {}).get("exclude_paths", [])
        cmd = ["uvx", "--from", f"bandit=={pin}", "bandit", "-r", ".", "-f", "json", "-q"]
        if excludes:
            cmd += ["-x", ",".join(f"./{e}" for e in excludes)]
        return cmd + extra
    if tool == "deptry":
        return ["uvx", "--from", f"deptry=={pin}", "deptry", ".", "-o", DEPTRY_REPORT] + extra
    if tool == "import-linter":
        return ["uvx", "--from", f"import-linter=={pin}", "lint-imports",
                "--config", "setup.cfg", "--format", "json"] + extra
    if tool == "semgrep":
        excludes = MAN.get("tool_options", {}).get("semgrep", {}).get("exclude_paths", [])
        cmd = ["uvx", "--from", f"semgrep=={pin}", "semgrep", "scan",
               "--json", "--quiet"]
        for e in excludes:
            cmd += ["--exclude", e]
        return cmd + extra + [rootp]
    if tool == "mutmut":
        return ["uvx", "--from", f"mutmut=={TIER3_PY[tool]}", "mutmut", "run"] + extra
    if tool == "schemathesis":
        spec = find_openapi(root)
        return ["uvx", "--from", f"schemathesis=={TIER3_PY[tool]}", "schemathesis",
                "run", spec, "--checks", "all", "--max-examples", "20",
                "--hypothesis-seed", "0", "--junit-xml", SCH_REPORT] + extra
    return None


def _cmd_js(tool, rootp, extra):
    if tool == "jscpd":
        # jscpd 5.x: -f là LOC extension filter (KHÔNG phải report format!);
        # report JSON qua --reporters json --output <dir> (mkstemp an toàn hơn /tmp)
        return ["npx", "-y", f"jscpd@{JS_PIN[tool]}", rootp, "--min-lines", "10",
                "--ignore", ("**/.rescue/**,**/.ipynb_checkpoints/**,**/node_modules/**,"
                             "**/.git/**,**/reports/**,**/__pycache__/**,**/.venv/**,*.json"),
                "--reporters", "json", "--output", JSCPD_OUT] + extra  # nosec B108
    if tool == "knip":
        return ["npx", "-y", f"knip@{JS_PIN[tool]}", "--reporter", "json", "--no-progress"]
    if tool == "dependency-cruiser":
        return ["npx", "-y", f"dependency-cruiser@{JS_PIN[tool]}", ".",
                "--output-type", "json", "--no-feedback", "--no-summary"]
    if tool == "markdownlint-cli":
        return ["npx", "-y", f"markdownlint-cli@{JS_PIN[tool]}", "--json"] + extra + [rootp]
    if tool == "repomix":
        return ["npx", "-y", f"repomix@{JS_PIN[tool]}", "-t", rootp, "-o",
                os.path.join(tempfile.gettempdir(), "repomix-context.txt")]
    if tool == "promptfoo":
        cfg = _arg_value(extra, "--config") or str(ROOT / "tools" / "promptfoo" / "default.yaml")
        return ["npx", "-y", f"promptfoo@{TIER3_JS[tool]}", "eval",
                "-c", cfg, "--output", PF_REPORT, "--format", "json"]
    if tool == "mcp-conformance":
        scenario = _arg_value(extra, "--scenario")
        return ["npx", "-y", f"@modelcontextprotocol/conformance@{MCP_CONF['version']}",
                "run", "--scenario", scenario]
    return None


def _cmd_binary(tool, rootp):
    exe = str(BIN_DIR / tool) if (BIN_DIR / tool).exists() else tool
    if tool == "trivy":
        return [exe, "fs", "--quiet", "--exit-code", "0", "--format", "json",
                "--scanners", "vuln,misconfig,secret,license", rootp]
    if tool == "gitleaks":
        return [exe, "dir", rootp, "--report-format", "json",
                "--report-path", GITLEAKS_REPORT, "--exit-code", "0", "--no-banner",
                "--redact"]  # lớp 1: gitleaks tự che; lớp 2: emit() mask lại
    if tool == "osv-scanner":
        return [exe, "--format", "json", "."]
    if tool == "lychee":
        return [exe, "--format", "json", "--no-progress", rootp]
    return None


def cmd_for(tool, root, extra):
    rootp = str(root)
    if tool == "archgraph":  # builtin stdlib — không cần pin (xem tools/manifest.toml)
        return [sys.executable, str(Path(__file__).resolve().parent / "archgraph.py"), rootp]
    if tool in PY_PIN or tool in TIER3_PY:
        return _cmd_python(tool, root, rootp, extra)
    if tool in JS_PIN or tool in TIER3_JS or tool == "mcp-conformance":
        return _cmd_js(tool, rootp, extra)
    if tool in BINARIES:
        return _cmd_binary(tool, rootp)
    return None


def precheck(tool, root, extra):
    """Trả về (skip_reason hoặc None, cwd). Trả về lý do cụ thể — không skip im lặng."""
    if tool != "archgraph" and tool not in PY_PIN and tool not in JS_PIN \
            and tool not in BINARIES and tool not in TIER3_PY and tool not in TIER3_JS \
            and tool != "mcp-conformance":
        return f"tool '{tool}' không có trong tools/manifest.toml", None
    if tool in BINARIES:
        if tool in ("vale", "ast-grep"):
            return f"'{tool}' chưa khai báo lệnh quét — dùng tay ở LOCK phase", None
        if not shutil.which(tool) and not (BIN_DIR / tool).exists():
            return f"binary '{tool}' chưa cài — chạy scripts/install_binaries.py --only {tool}", None
        return None, None
    if tool == "stryker-js":
        return "mutation testing for JS is not wired yet (tier3) — run manually at LOCK", None
    if tool in JS_PIN:
        if tool in ("knip", "dependency-cruiser") and not (root / "package.json").exists():
            return "no package.json (không phải repo JS)", None
        return None, None
    if tool == "import-linter":
        if not (root / "setup.cfg").exists():
            return "không tìm thấy setup.cfg [importlinter] contract", None
        return None, None
    if tool == "deptry" and not (root / "pyproject.toml").exists():
        return "không phải Python project (pyproject.toml)", None
    if tool == "vulture" and not vulture_py_files(
            root, MAN.get("tool_options", {}).get("vulture", {}).get("exclude_paths", [])):
        return "không còn file .py sau exclude_paths", None
    if tool == "mutmut":
        if not (root / "pyproject.toml").exists():
            return "không phải Python project (pyproject.toml)", None
        return None, None
    if tool == "schemathesis":
        if not find_openapi(root):
            return "không tìm thấy openapi.json/yaml/swagger.json (tier3 cần API contract)", None
        return None, None
    if tool == "promptfoo":
        cfg = _arg_value(extra, "--config") or str(ROOT / "tools" / "promptfoo" / "default.yaml")
        if not Path(cfg).exists():
            return f"chưa có promptfoo config ({cfg}) — tạo bằng tools/promptfoo/example.yaml", None
        return None, None
    if tool == "mcp-conformance":
        return ("gate protocol MCP: chạy bởi orchestrator ở LOCK phase với --scenario "
                + "(xem tools/mcp/); chưa nhúng vào fanout mặc định", None)
    return None, None


def load_json_file(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


CWWD_TOOLS = ("deptry", "import-linter", "dependency-cruiser", "knip",
              "bandit", "mutmut", "schemathesis", "osv-scanner", "vulture")
JSON_TOOLS = ("ruff", "bandit", "semgrep", "knip", "dependency-cruiser",
              "import-linter", "trivy")
# These tools may return 1 when they found issues. Every other nonzero status is
# a failed scan, even if the process left a plausible partial JSON artifact.
FINDING_EXIT_ONE = frozenset({
    "ruff", "vulture", "bandit", "deptry", "import-linter", "jscpd", "knip",
    "dependency-cruiser", "markdownlint-cli", "semgrep", "osv-scanner",
    "lychee", "promptfoo", "mutmut", "schemathesis",
})


def _findings_from_json_text(tool, text, stderr, root):
    """Tool JSON-on-stdout (ruff/bandit/semgrep/knip/dep-cruise/import-linter/trivy)."""
    try:
        data = json.loads(text)
    except Exception:
        if tool == "import-linter":
            return PARSERS["import-linter"](text, root), None
        return None, f"không parse được JSON: {(text or stderr)[:200]}"
    if tool == "dependency-cruiser" and isinstance(data, dict) and "modules" in data:
        return PARSERS["dependency-cruiser"](data), None
    if tool == "import-linter":
        return PARSERS["import-linter"](data, root), None
    if tool == "trivy" and isinstance(data, dict) and "Results" in data:
        return PARSERS["trivy"](data), None
    findings = PARSERS[tool](data, root) if tool != "semgrep" else PARSERS["semgrep"](data)
    return findings, None


def collect_findings(tool, r, root, result):
    """(findings, error). Máy đổi output thô của từng tool -> findings chuẩn.
    Lỗi parse TRẢ về lý do — không chết âm thầm (R11)."""
    text = r.stdout or ""
    if tool == "jscpd":
        data = None
        for f in sorted(Path(JSCPD_OUT).glob("*.json")):
            cand = load_json_file(f)
            if isinstance(cand, dict) and "duplicates" in cand:
                data = cand
                break
        if data is None:
            return None, "jscpd không ra report JSON"
        return PARSERS["jscpd"](data), None
    if tool == "deptry":
        data = load_json_file(DEPTRY_REPORT)
        if data is None:
            if "no dependency issues found" in re.sub(r"\x1b\[[0-9;]*m", "", text).lower():
                return [], None
            return None, f"deptry không ra report: {(text or r.stderr)[:200]}"
        return PARSERS["deptry"](data), None
    if tool == "gitleaks":
        return PARSERS["gitleaks"](load_json_file(GITLEAKS_REPORT) or {"findings": []}), None
    if tool == "schemathesis":
        xml_text = Path(SCH_REPORT).read_text(encoding="utf-8", errors="ignore")
        return PARSERS["schemathesis"](xml_text), None
    if tool == "promptfoo":
        data = load_json_file(PF_REPORT)
        if not isinstance(data, dict) or "results" not in data:
            return None, "promptfoo không ra report JSON"
        return PARSERS["promptfoo"](data), None
    if tool == "mutmut":
        return PARSERS["mutmut"](text), None
    if tool == "osv-scanner":
        try:
            return PARSERS["osv-scanner"](json.loads(text)), None
        except Exception:
            combined = text + (r.stderr or "")
            if r.returncode == 0 and "No package sources" in combined:
                return [], None
            return None, f"không parse được JSON osv-scanner: {combined[:200]}"
    if tool == "archgraph":
        try:
            return PARSERS["archgraph"](json.loads(text)), None
        except Exception:
            return None, f"không parse được JSON archgraph: {(text or r.stderr)[:200]}"
    if tool == "lychee":
        try:
            return PARSERS["lychee"](json.loads(text)), None
        except Exception:
            return None, "lychee không parse được JSON"
    if tool == "mcp-conformance":
        return [], None
    if tool == "vulture":
        return PARSERS["vulture"](text + (r.stderr or ""), root), None
    if tool == "radon":
        return PARSERS["radon"](text, root), None
    if tool == "markdownlint-cli":
        data = json.loads(text) if text.strip().startswith(("{", "[")) else None
        if data is None:
            return None, "markdownlint-cli không ra JSON"
        return PARSERS["markdownlint-cli"](data), None
    if tool in JSON_TOOLS:
        return _findings_from_json_text(tool, text, r.stderr, root)
    result["scanned"] = False  # tool không parser riêng (repomix) — coi như đã chạy
    return [], None


def _run_tool(tool, out, rules, root, extra, result):
    """Run one scanner and normalize findings; temp artifacts are owned by main()."""
    if tool is None:
        result["error"] = "missing --tool"
        emit(result, out)
        return 2

    skip, _cwd = precheck(tool, root, extra)
    if skip:
        result["skipped"] = skip
        emit(result, out)
        return 0

    if tool == "semgrep":
        rdir = rules or (ROOT / (MAN.get("tool_options", {})
                                 .get("semgrep", {}).get("rules_dir", "tools/rules")))
        if not Path(rdir).exists():
            result["skipped"] = f"rules dir '{rdir}' does not exist (create semgrep rules first)"
            emit(result, out)
            return 0
        extra = ["--config", str(rdir)] + extra

    cmd = cmd_for(tool, root, extra)
    if not cmd:
        result["error"] = f"no command implemented for tool '{tool}'"
        emit(result, out)
        return 2

    cwdd = str(root) if tool in CWWD_TOOLS else None
    try:
        r = run(cmd, cwd=cwdd)
    except FileNotFoundError as e:
        result["error"] = f"command not found ({e}); uvx/npx required"
        emit(result, out)
        return 2
    except subprocess.TimeoutExpired:
        result["error"] = "timeout"
        emit(result, out)
        return 2

    findings, error = collect_findings(tool, r, root, result)
    result["exit_code"] = r.returncode
    if error:
        result["error"] = error
        emit(result, out)
        return 2
    if r.returncode != 0 and not (r.returncode == 1 and tool in FINDING_EXIT_ONE
                                 and findings):
        result["error"] = f"scanner exit={r.returncode} không phải findings exit hợp lệ"
        emit(result, out)
        return 2
    result["findings"] = findings
    result["ok"] = True
    emit(result, out)
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="Run one scanner (pinned command from tools/manifest.toml) and normalize findings.")
    ap.add_argument("--tool")
    ap.add_argument("--target", default=".")
    ap.add_argument("--out", help="write result JSON to a file (default: stdout)")
    ap.add_argument("--rules", help="semgrep rules dir (default: tools/rules)")
    a, extra_unknown = ap.parse_known_args(argv)
    tool, out, rules = a.tool, a.out, a.rules
    root = Path(a.target)
    # Extra flags or anything after '--' are forwarded verbatim to the tool
    # (e.g. promptfoo --config X, mcp-conformance --scenario S).
    extra = [x for x in extra_unknown if x != "--"]

    result = {"tool": tool, "version": tool_version(tool),
              "target": str(root), "ok": False, "skipped": None, "error": None, "findings": []}

    _init_tmp_artifacts()
    try:
        return _run_tool(tool, out, rules, root, extra, result)
    finally:
        _cleanup_tmp_artifacts()


if __name__ == "__main__":
    sys.exit(main())

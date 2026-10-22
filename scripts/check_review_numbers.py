#!/usr/bin/env python3
# ruff: noqa: BLE001  # checker đọc nhiều dạng JSON lạ từ raw/ — không được chết vì 1 file
"""
check_review_numbers.py — MÁY TỰ KIỂM SỐ trong bản review do LLM viết (H2, audit v0.3.5).

Vì sao: LLM auditor viết số vào README/PROPOSALS. Phần lớn đúng, nhưng đã có số KHÔNG
tái lập được (vd "142 hàm con" — thực tế 114). Kết luận sai chưa chết người, con số sai
làm team mất niềm tin vào bằng chứng. Nguyên tắc: **số phải do máy kiểm lại**, không ai
tin lời ai — kể cả lời LLM.

Máy kiểm được gì (tất cả là tra cứu CƠ KHÍ vào JSON scanner của chính harness):
  - "N dòng" gần tên file            -> wc -l thật của file trong target (nêu "~" => nới ±5%)
  - `file.py:DÒNG`                   -> file tồn tại và có dòng đó
  - "cyclomatic / CC / độ rối = N"   -> N có trong evidence (cyclo=...) của radon.json
  - "<rule> N" (BLE001, B101...)     -> đếm rule trong ruff.json / bandit.json
  - "gitleaks/ruff/trivy... N"       -> N == số findings của tool đó trong raw/ (jscpd bỏ qua
                                        — con số "cặp/dòng" của jscpd là ngữ nghĩa riêng)
  - "0 vòng/cycle", "498 module"     -> archgraph.json
  - "N hàm con" trong 1 thẻ có mỏ neo file.py:DÒNG -> đếm def lồng thật bằng AST

Không kiểm được -> ghi rõ "n.a." (không bỏ im lặng). Thoát 0 luôn trừ khi --strict.

Usage:
  python3 scripts/check_review_numbers.py --review-dir <target>/.rescue/voyage/review [--strict]
Kết quả: <review-dir>/EVIDENCE/number-check.md + dòng tóm tắt ra stdout.
"""
import argparse
import ast
import json
import re
import sys
from pathlib import Path

TOOL_TOTAL_RE = re.compile(
    r"\b(gitleaks|ruff|bandit|radon|semgrep|vulture|trivy|deptry|knip|osv|lychee"
    r"|markdownlint|dependency-cruiser|import-linter|archgraph)\b"
    r"(?:\.json)?[^0-9\n]{0,15}?(?<![A-Za-z])(\d{1,3}(?:[.,]\d{3})+|\d+)\b", re.IGNORECASE)
RULE_TOTAL_RE = re.compile(
    r"\b([A-Z]{2,4}\d{3}|B\d{3})\b[^0-9\n]{0,15}?(?<![A-Za-z])(\d{1,3}(?:[.,]\d{3})+|\d+)\b")
# 'Verify: chạy lại ... → 0 phát hiện mới' là HƯỚNG DẪN TƯƠNG LAI, không phải claim hiện tại
_INSTRUCTION_WORDS = ("verify", "chạy lại", "kiểm lại", "re-run")


def _is_instruction(text, start, end, window=90):
    # CHỈ nhìn về phía TRƯỚC claim: nhãn section ("**Verify:**", "chạy lại ...") đứng
    # trước nội dung của nó; nhìn cả sau sẽ nuốt claim thật đứng ngay trước Verify card.
    ctx = text[max(0, start - window):start].lower()
    return any(w in ctx for w in _INSTRUCTION_WORDS)


CC_RE = re.compile(
    r"(?:cyclomatic|complexity|độ rối|CC)\s*(?:=|:|là)?\s*\*{0,2}(\d{2,5})\*{0,2}", re.IGNORECASE)
LINES_RE = re.compile(
    r"([\w./\-]+\.(?:py|js|ts|tsx|jsx|md|json|toml|ya?ml))[^\n]{0,90}?"
    r"(~?\d{1,3}(?:[.,]\d{3})+|~?\d{2,})\s*(?:dòng|lines)\b", re.IGNORECASE)
ANCHOR_RE = re.compile(r"([\w./\-]+\.(?:py|js|ts|md|json|toml))\s*:\s*(\d+)")
CYCLE_RE = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(?:vòng\s*(?:import\s*)?(?:lặp|lap)?|cycles?)", re.IGNORECASE)
MODULE_RE = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(?:modules?)\b", re.IGNORECASE)
NESTED_DEF_RE = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(?:hàm con|nested def(?:s)?|ham con)", re.IGNORECASE)


def parse_int(s):
    """'11.000'->11000, '3,735'->3735, '4555'->4555; không rõ dạng -> None."""
    s = s.strip().lstrip("~").replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        return int(re.sub(r"[.,]", "", s))
    if re.fullmatch(r"\d+", s):
        return int(s)
    return None


def _load(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def _norm(p):
    return str(p).replace("\\", "/").lstrip("./")


def load_facts(raw_dir, archgraph_path):
    """Toàn bộ sự thật máy cho vào 1 dict — kiểm số = tra cứu đây."""
    facts = {"tool_counts": {}, "rule_counts": {}, "cyclo": set(),
             "cycles": None, "modules": None}
    raw = Path(raw_dir)
    if raw.exists():
        for f in sorted(raw.glob("*.json")):
            d = _load(f)
            if not isinstance(d, dict):
                continue
            items = d.get("findings", []) or []
            facts["tool_counts"][f.stem] = len(items)
            if f.stem in ("ruff", "bandit", "semgrep"):
                rc = facts["rule_counts"]
                for x in items:
                    rule = str(x.get("rule", ""))
                    rule = rule.rsplit(".", 1)[-1] if rule.startswith("tools.rules.") else rule
                    rc[rule] = rc.get(rule, 0) + 1
            if f.stem == "radon":
                for x in items:
                    m = re.search(r"cyclo=([\d.]+)", str(x.get("evidence", "")))
                    if m:
                        facts["cyclo"].add(int(float(m.group(1))))
    ag = _load(archgraph_path) if archgraph_path else None
    if isinstance(ag, dict):
        facts["cycles"] = len(ag.get("cycles", []) or [])
        mods = ag.get("modules", ag.get("nodes", []))
        facts["modules"] = len(mods) if isinstance(mods, (list, dict)) else None
    return facts


_RESOLVE_CACHE = {}
_SKIP_DIRS = ("node_modules", ".venv", "venv", "__pycache__", "site-packages")


def _resolve(target, rel):
    """target/rel; nếu chỉ là tên trần thì chấp nhận khi target có ĐÚNG 1 file tên
    vậy (2 bản như url_cache.py -> n.a., máy không đoán bừa)."""
    if not target:
        return None
    key = (str(target), rel)
    if key in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[key]
    p = Path(rel)
    out = p if p.is_absolute() else Path(target) / rel
    if not out.exists():
        name = Path(rel).name
        hits = [q for q in Path(target).rglob(name)
                if q.is_file()
                and not any(seg.startswith(".") or seg in _SKIP_DIRS for seg in q.parts)]
        out = hits[0] if len(hits) == 1 else None
    _RESOLVE_CACHE[key] = out
    return out


def count_lines(p):
    try:
        with open(p, errors="ignore") as fh:
            return sum(1 for _ in fh)
    except Exception:
        return None


def count_nested_defs(path, line_no):
    """Đếm def lồng trong hàm cấp-1 chứa `line_no` (AST — cách đếm duy nhất khách quan)."""
    try:
        tree = ast.parse(Path(path).read_text(errors="ignore"))
    except Exception:
        return None
    best = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.lineno <= line_no <= (node.end_lineno or node.lineno):
            best = node
            break
    if best is None:
        return None
    return sum(1 for n in ast.walk(best)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not best)


def _check_line_counts(text, facts, target, row):
    """1) số dòng của file. Bỏ qua các claim KHÔNG phải độ dài file:
    'trùng N dòng' (jscpd), 'hàm ... N dòng' (độ dài hàm) — máy không đoán mò."""
    for m in LINES_RE.finditer(text):
        span = m.group(0)
        if "trùng" in span or "hàm" in span.lower():
            continue
        rel, num = _norm(m.group(1)), parse_int(m.group(2))
        if num is None:
            continue
        approx = m.group(2).strip().startswith("~")
        p = _resolve(target, rel)
        real = count_lines(p) if p else None
        if real is None:
            row(f"{rel} ~ {num} dòng", "wc -l", "n.a.", "không đọc được file trong target")
        elif real == num or (approx and abs(real - num) <= max(1, real * 5 // 100)):
            row(f"{rel} ~ {num} dòng", "wc -l", "OK", f"thật: {real}")
        else:
            row(f"{rel} ~ {num} dòng", "wc -l", "SAI", f"thật: {real}")


def _check_anchors(text, facts, target, row):
    """2) mỏ neo file:dòng."""
    seen = set()
    for m in ANCHOR_RE.finditer(text):
        rel, ln = _norm(m.group(1)), int(m.group(2))
        if (rel, ln) in seen:
            continue
        seen.add((rel, ln))
        p = _resolve(target, rel)
        real = count_lines(p) if p else None
        if real is None:
            row(f"{rel}:{ln}", "file tồn tại", "n.a.", "không đọc được file trong target")
        elif 1 <= ln <= real:
            row(f"{rel}:{ln}", "file tồn tại", "OK", f"file {real} dòng")
        else:
            row(f"{rel}:{ln}", "file tồn tại", "SAI", f"file chỉ {real} dòng")


def _check_cc(text, facts, target, row):
    """3) cyclomatic/CC."""
    for m in CC_RE.finditer(text):
        n = parse_int(m.group(1))
        if n is None:
            continue
        if n in facts["cyclo"]:
            row(f"CC = {n}", "radon.json (cyclo)", "OK")
        elif facts["cyclo"]:
            row(f"CC = {n}", "radon.json (cyclo)", "SAI",
                f"các CC thật (gần): {sorted(facts['cyclo'])[-5:]}")
        else:
            row(f"CC = {n}", "radon.json (cyclo)", "n.a.", "không có radon.json")


def _check_rule_counts(text, facts, target, row):
    """4) đếm theo rule (BLE001, B101...). Bỏ dòng lệnhVerify/hướng-dẫn-chạy-lại."""
    for m in RULE_TOTAL_RE.finditer(text):
        rule, n = m.group(1), parse_int(m.group(2))
        real = facts["rule_counts"].get(rule)
        if n is None or real is None:
            continue
        if _is_instruction(text, m.start(), m.end()):
            row(f"{rule} = {n}", "ruff/bandit/semgrep.json", "n.a.", "lệnh verify, không phải claim")
            continue
        status = "OK" if real == n else "SAI"
        row(f"{rule} = {n}", "ruff/bandit/semgrep.json", status, f"thật: {real}")


def _check_tool_totals(text, facts, target, row):
    """5) tổng theo tool (jscpd bỏ qua — ngữ nghĩa 'cặp/dòng' riêng, không đối chiếu mù)."""
    for m in TOOL_TOTAL_RE.finditer(text):
        tool, n = m.group(1).lower(), parse_int(m.group(2))
        if n is None or tool not in facts["tool_counts"] or tool == "jscpd":
            continue
        if _is_instruction(text, m.start(), m.end()):
            row(f"{tool} = {n}", f"raw/{tool}.json", "n.a.", "lệnh verify, không phải claim")
            continue
        real = facts["tool_counts"][tool]
        row(f"{tool} = {n}", f"raw/{tool}.json", "OK" if real == n else "SAI", f"thật: {real}")


def _check_archgraph(text, facts, target, row):
    """6) archgraph cycles / modules. Claim kiểu '151 module không thấy ai import'
    là fan-in, KHÔNG phải tổng module — chỉ kiểm khi quanh đó không có 'import'."""
    if facts["cycles"] is not None:
        for m in CYCLE_RE.finditer(text):
            n = parse_int(m.group(1))
            if n is not None:
                row(f"cycles = {n}", "archgraph.json", "OK" if n == facts["cycles"] else "SAI",
                    f"thật: {facts['cycles']}")
    if facts["modules"] is not None:
        for m in MODULE_RE.finditer(text):
            n = parse_int(m.group(1))
            if n is None:
                continue
            ctx = text[max(0, m.start() - 120):m.end() + 120].lower()
            if "import" in ctx or "fan-in" in ctx or "fan_in" in ctx:
                row(f"modules = {n}", "archgraph.json", "n.a.",
                    "gần chữ 'import' — có thể là claim fan-in, không phải tổng")
                continue
            row(f"modules = {n}", "archgraph.json", "OK" if n == facts["modules"] else "SAI",
                f"thật: {facts['modules']}")


def _check_nested_def_claims(text, facts, target, row):
    """7) 'N hàm con' — mỗi THẺ (## ...) dùng mỏ neo file:dòng đầu tiên của thẻ đó."""
    for card in re.split(r"\n##\s", text):
        mm = NESTED_DEF_RE.search(card)
        if not mm:
            continue
        n = parse_int(mm.group(1))
        anchor = ANCHOR_RE.search(card)
        if n is None or not anchor:
            row(f"{mm.group(0)}", "AST", "n.a.", "thẻ không nêu mỏ neo file:dòng")
            continue
        p = _resolve(target, _norm(anchor.group(1)))
        real = count_nested_defs(p, int(anchor.group(2))) if p else None
        if real is None:
            row(f"{mm.group(1)} hàm con @{anchor.group(0)}", "AST", "n.a.", "không parse được")
        else:
            row(f"{mm.group(1)} hàm con @{anchor.group(0)}", "AST",
                "OK" if real == n else "SAI", f"thật: {real}")


CHECKS = (_check_line_counts, _check_anchors, _check_cc, _check_rule_counts,
          _check_tool_totals, _check_archgraph, _check_nested_def_claims)


def check(text, facts, target, rows):
    def row(claim, source, status, note=""):
        rows.append({"claim": claim, "source": source, "status": status, "note": note})

    for fn in CHECKS:
        fn(text, facts, target, row)


def render(rows):
    icon = {"OK": "✓", "SAI": "✗", "n.a.": "?"}
    lines = ["# KIỂM SỐ TỰ ĐỘNG (check_review_numbers.py)", "",
             "> Máy đối chiếu từng con số trong README/PROPOSALS với JSON scanner.",
             "> ✓ = khớp · ✗ = lệch (đọc cột 'thật') · ? = máy không kiểm được.",
             "", "| Con số tuyên bố | Nguồn kiểm | Kết | Ghi chú |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['claim']} | {r['source']} | {icon[r['status']]} {r['status']} "
                     f"| {r['note']} |")
    ok = sum(1 for r in rows if r["status"] == "OK")
    bad = sum(1 for r in rows if r["status"] == "SAI")
    na = sum(1 for r in rows if r["status"] == "n.a.")
    lines += ["", (f"**Tổng:** {ok} khớp · {bad} lệch · {na} không kiểm được "
                   f"(trên {len(rows)} con số máy đọc thấy).")]
    return "\n".join(lines) + "\n", ok, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description="Máy tự kiểm số trong review (H2).")
    ap.add_argument("--review-dir", required=True)
    ap.add_argument("--raw-dir", default=None)
    ap.add_argument("--target", default=None)
    ap.add_argument("--strict", action="store_true",
                    help="thoát 1 nếu có số SAI (mặc định: chỉ cảnh báo)")
    a = ap.parse_args(argv)

    rdir = Path(a.review_dir)
    raw_dir = Path(a.raw_dir) if a.raw_dir else rdir.parent / "prove" / "raw"
    target = Path(a.target) if a.target else (rdir.parents[2] if len(rdir.parents) > 2 else None)
    text = "\n".join((rdir / n).read_text(errors="ignore")
                     for n in ("README.md", "PROPOSALS.md") if (rdir / n).exists())
    facts = load_facts(raw_dir, rdir / "archgraph.json")
    rows = []
    check(text, facts, target, rows)
    out, ok, bad = render(rows)
    edir = rdir / "EVIDENCE"
    edir.mkdir(parents=True, exist_ok=True)
    (edir / "number-check.md").write_text(out, encoding="utf-8")
    print(f"[NUMCHECK] {ok} khớp / {bad} lệch -> {edir / 'number-check.md'}")
    return 1 if (a.strict and bad) else 0


if __name__ == "__main__":
    sys.exit(main())

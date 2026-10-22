#!/usr/bin/env python3
# Chính sách noqa: 1 file raw hỏng không được làm hỏng đợt gom evidence (RULES R11).
# ruff: noqa: BLE001
"""
collect_evidence.py — H3 (audit v0.3.5): EVIDENCE/ phải TỰ CHỨA, không chỉ là con trỏ.

Trước đây EVIDENCE/ chỉ chứa đường dẫn tới prove/raw — người đọc ở máy khác mở không
được là không kiểm chứng được gì. Giờ: copy JSON scanner (ĐÃ redact khóa ở nguồn) +
findings/sarif vào <session>/review/EVIDENCE/ và viết summary.md (tổng theo tool +
cách tự kiểm lại 1 con số bằng 1 lệnh).

Che lớp 3 khi copy (mask_obj) — artifact đã an toàn vẫn được che lần nữa (belt&braces).

Usage:
  python3 scripts/collect_evidence.py --session <target>/.rescue/voyage
"""
import argparse
import json
import sys
from pathlib import Path

try:
    from tools.meta import redact  # dùng như package (pytest/ROOT đã có trong sys.path)
except ImportError:                 # standalone — load theo ĐÚNG ĐƯỜNG DẪN FILE
    # (KHÔNG insert-ROOT-rồi-import-lại — xem ghi chú merge_findings.py, round-2 audit).
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "vibe_rescue_redact", Path(__file__).resolve().parents[1] / "tools" / "meta" / "redact.py")
    redact = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(redact)

# raw/<tool>.json nào được mang theo — mặc định: mọi tool có findings
COPY_TOP = ("findings.json", "findings.sarif", "findings.md")


def _load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def _copy_masked(src: Path, dst_dir: Path):
    """Copy JSON sau khi mask_obj — trả về data nếu OK, None nếu không đọc được."""
    d = _load(src)
    if d is None:
        return None
    (dst_dir / src.name).write_text(
        json.dumps(redact.mask_obj(d), ensure_ascii=False, indent=1))
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gom evidence đã redact vào review/EVIDENCE (H3).")
    ap.add_argument("--session", required=True, help="dir .rescue/voyage của target")
    a = ap.parse_args(argv)
    session = Path(a.session)
    prove = session / "prove"
    edir = session / "review" / "EVIDENCE"
    edir.mkdir(parents=True, exist_ok=True)
    target = session.parent.parent  # <target>/.rescue/voyage -> <target>
    copied, counts = [], {}

    for name in COPY_TOP:
        p = prove / name
        if not p.exists():
            continue
        if p.suffix == ".json":
            if _copy_masked(p, edir) is not None:
                copied.append(name)
        else:  # .md / .sarif-adjacent text — mask_text rồi chép
            (edir / name).write_text(redact.mask_text(p.read_text(errors="ignore")),
                                     encoding="utf-8")
            copied.append(name)

    raw = prove / "raw"
    if raw.exists():
        (edir / "raw").mkdir(exist_ok=True)
        for f in sorted(raw.glob("*.json")):
            d = _copy_masked(f, edir / "raw")
            if d is not None:
                copied.append(f"raw/{f.name}")
                counts[f.stem] = len(d.get("findings", []) or []) if isinstance(d, dict) else 0

    ag = session / "review" / "archgraph.json"
    if ag.exists() and _copy_masked(ag, edir) is not None:
        copied.append("archgraph.json")

    total = sum(counts.values())
    lines = ["# SỐ LIỆU MÁY (đã redact khóa — tools/meta/redact.py)", "",
             f"- target: {target}",
             f"- tổng findings: {total}", ""]
    for t, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {t}: {n}")
    lines += ["", "## Tự kiểm lại 1 con số (không ai phải tin lời ai)", "",
              "```bash",
              (f"python3 -c \"import json; d=json.load(open('{edir}/raw/ruff.json'));"
               f" print('ruff:', len(d['findings']))\""),
              "```"]
    (edir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (edir / "README.md").write_text(
        "# EVIDENCE — tự chứa (H3)\n"
        "- `summary.md`: tổng findings theo tool + 1 lệnh kiểm lại mẫu.\n"
        "- `findings.json` / `findings.sarif` / `findings.md`: bản gộp đã redact.\n"
        "- `raw/<tool>.json`: output gốc từng scanner (đã redact ở nguồn qua scan.emit).\n"
        "- `number-check.md`: máy tự đối chiếu số LLM nêu với số liệu ở đây (H2).\n"
        f"- Đã copy lần này: {', '.join(copied) if copied else '(chưa có — chạy prove trước)'}\n",
        encoding="utf-8")
    print(f"[EVIDENCE] copied={len(copied)} findings={total} -> {edir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

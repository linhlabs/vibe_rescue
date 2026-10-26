#!/usr/bin/env python3
"""
po_report.py: build the two PO deliverables of RULES R13 from Markdown, with no LLM.

The agent writes PO_SUMMARY.md (short) and PO_DETAIL.md (detailed) in the structure of
docs/OUTPUT_PROTOCOL.md, section "Hiển thị output cuối cùng cho PO và business". This
script turns them into two self-contained HTML files (no network, no external asset):

  PO_SUMMARY.html  16:9 slides stacked vertically, read by scrolling, scaled to the
                   window, one slide per page when printed to PDF
  PO_DETAIL.html   one-column Notion-style page: properties, callouts, pastel tags,
                   ruled tables, developer appendix in a toggle

A code such as [P3] on either page opens row P3 of the appendix in PO_DETAIL.html. The
cover links to the detailed page and the detailed page links back.

Fails closed (exit 2, every problem listed with its fix, no HTML written) when the
Markdown breaks the structure: a missing section, more items than a slide holds, a [Pn]
with no appendix row, an emoji. Text overflow can only be measured in a browser: the
slide page lists overflowing slides in <body data-overflow="..."> and the console.

Usage:
  python3 scripts/po_report.py <review-dir>      # PO_SUMMARY.md + PO_DETAIL.md in, HTML beside
  python3 scripts/po_report.py --summary S.md --detail D.md [--out-dir DIR]
"""
import argparse
import html
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

SUMMARY_SECTIONS = 8
DETAIL_SECTIONS = 9  # the last one is the developer appendix
ROWS_PER_SLIDE = 7
# section number -> (what is counted, maximum), from docs/OUTPUT_PROTOCOL.md "Cấu trúc bản ngắn"
SUMMARY_LIMITS = {"1": ("dòng 'Hiện tại'", 5), "2": ("dòng", 3), "5": ("việc", 6),
                  "6": ("dòng", 3), "7": ("dòng", 3), "8": ("câu hỏi", 3)}
SMALL_GROUP = 3  # a risk group with at most this many lines shares a slide with the next one

LEVEL = {"cao": "high", "trung bình": "med", "thấp": "low"}
RATING = {"tốt": "good", "tạm": "ok", "yếu": "weak"}

LIST_RE = re.compile(r"^\s*([-*]|\d+\.)\s+")
PROP_RE = re.compile(r"^[-*]\s+\*\*([^*:]+?)(?::\*\*|\*\*:)\s*(.*)$")
SECTION_RE = re.compile(r"^(\d+)\.\s+(.+)$")
LABEL_RE = re.compile(r"\*\*(Hiện tại|Cần cải thiện[^*]*)\*\*:?")
LEVEL_RE = re.compile(r"\s*\((?:rủi ro\s+)?(cao|trung bình|thấp)\)\s*$", re.IGNORECASE)
PREF_RE = re.compile(r"\[(P\d+(?:\s*,\s*P\d+)*)\]")
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u231A\u231B"
                      "\u23E9-\u23FA\uFE0F\u200D]")


class ReportError(Exception):
    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass
class Doc:
    name: str
    title: str = ""
    props: dict = field(default_factory=dict)
    intro: str = ""
    sections: dict = field(default_factory=dict)  # "3" -> (title, body)

    def prop(self, key, default=""):
        for k, v in self.props.items():
            if k.casefold() == key.casefold():
                return v
        return default


@dataclass
class Result:
    summary_name: str
    detail_name: str
    summary_html: str
    detail_html: str
    slides: int
    codes: int
    notes: list


# ------------------------------------------------------------------ Markdown subset
def split_row(line):
    cells, buf, in_code = [], "", False
    for ch in line.strip().strip("|"):
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append(buf.strip())
            buf = ""
        else:
            buf += ch
    cells.append(buf.strip())
    return cells


def tokens(md):
    """Blocks of a section body: ("p", text) ("label", "now"|"fix", text)
    ("list", ordered, items) ("table", header, rows) ("quote", text) ("h3", text)."""
    lines, out, i = md.split("\n"), [], 0
    while i < len(lines):
        s = lines[i].strip()
        if not s or s == "---":
            i += 1
        elif s.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            rows = [split_row(r) for r in block if not set(r) <= set("|-: ")]
            out.append(("table", rows[0], rows[1:]))
        elif LIST_RE.match(lines[i]):
            ordered, items = LIST_RE.match(lines[i]).group(1)[0].isdigit(), []
            while i < len(lines) and lines[i].strip():
                if LIST_RE.match(lines[i]):
                    items.append(LIST_RE.sub("", lines[i], count=1).strip())
                elif lines[i][0] in " \t":  # wrapped continuation of the previous item
                    items[-1] += " " + lines[i].strip()
                else:
                    break
                i += 1
            out.append(("list", ordered, items))
        elif s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(("quote", " ".join(buf)))
        elif s.startswith("#"):
            out.append(("h3", s.lstrip("#").strip()))
            i += 1
        else:
            buf = []
            while i < len(lines):
                s = lines[i].strip()
                if not s or s == "---" or s.startswith(("|", ">", "#")) or LIST_RE.match(lines[i]):
                    break
                buf.append(s)
                i += 1
            text = " ".join(buf)
            m = LABEL_RE.fullmatch(text)
            if m:
                out.append(("label", "now" if m.group(1) == "Hiện tại" else "fix", m.group(1)))
            else:
                out.append(("p", text))
    return out


def _link(m):
    text, url = m.group(1), m.group(2)
    scheme = re.match(r"^([a-zA-Z][\w+.-]*):", url)
    if scheme and scheme.group(1).lower() not in ("http", "https", "mailto"):
        return text
    return f'<a href="{url.replace(chr(34), "%22")}">{text}</a>'


def inline(text, pref=""):
    """Escape, then **bold**, `code`, [text](url) and [P1, P2] links to the appendix."""
    codes = []

    def keep(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = html.escape(re.sub(r"`([^`]+)`", keep, text), quote=False)
    text = PREF_RE.sub(lambda m: '<span class="refs">' + "".join(
        f'<a class="pref" href="{pref}#{p}">{p}</a>' for p in re.findall(r"P\d+", m.group(1))) + "</span>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def tag(cls, label):
    return f'<span class="tag {cls}">{html.escape(label)}</span>'


def cell(header, raw, pref=""):
    h, txt = header.strip().lower(), raw.strip()
    if h in ("ưu tiên", "mức", "mức độ") and txt.lower() in LEVEL:
        return tag(LEVEL[txt.lower()], txt)
    if h == "đánh giá":
        first = txt.split(" ", 1)[0].strip("*.")
        if first.lower() in RATING:
            return tag(RATING[first.lower()], first) + inline(txt.split(" ", 1)[1] if " " in txt else "", pref)
    if h == "rủi ro chính":
        m = re.match(r"^\*{0,2}(Cao|Trung bình|Thấp)\.?\*{0,2}\.?\s*(.*)$", txt, flags=re.IGNORECASE)
        if m:
            return tag(LEVEL[m.group(1).lower()], m.group(1)) + " " + inline(m.group(2), pref)
    return inline(txt, pref)


def table_html(header, rows, pref="", cls="", row_ids=False):
    head = "".join(f"<th>{inline(c, pref)}</th>" for c in header)
    body = []
    for r in rows:
        rid = f' id="{r[0]}"' if row_ids and re.fullmatch(r"P\d+", r[0]) else ""
        tds = "".join(f"<td>{cell(header[i] if i < len(header) else '', c, pref)}</td>" for i, c in enumerate(r))
        body.append(f"<tr{rid}>{tds}</tr>")
    return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def list_items(toks):
    return sum(len(t[2]) for t in toks if t[0] == "list")


def zones(toks):
    """Split at the Hiện tại / Cần cải thiện labels -> ({"pre", "now", "fix"}: tokens, labels)."""
    z, cur, labels = {"pre": [], "now": [], "fix": []}, "pre", {}
    for t in toks:
        if t[0] == "label":
            cur, labels[t[1]] = t[1], t[2]
        else:
            z[cur].append(t)
    return z, labels


def groups(toks):
    """Split a section at its ### headings -> (lead tokens, [(num, label, level, tokens)])."""
    lead, out = [], []
    for t in toks:
        if t[0] == "h3":
            title = t[1]
            m = LEVEL_RE.search(title)
            level = m.group(1).lower() if m else ""
            name = title[:m.start()].strip() if m else title.strip()
            n = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$", name)
            num, label = (n.group(1), n.group(2)) if n else ("", name)
            out.append((num, label, level, []))
        elif out:
            out[-1][3].append(t)
        else:
            lead.append(t)
    return lead, out


def first_table(toks):
    return next((i for i, t in enumerate(toks) if t[0] == "table"), None)


# ------------------------------------------------------------------ parse and check
def parse(text, name, problems):
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n")
    doc = Doc(name)
    for n, line in enumerate(text.split("\n"), 1):
        m = EMOJI_RE.search(line)
        if m:
            problems.append(f"{name}:{n}: có emoji (U+{ord(m.group()):04X}); AGENTS.md cấm emoji trong file, thay bằng chữ.")
    head, *chunks = re.split(r"^## ", text, flags=re.MULTILINE)
    lines = head.strip().split("\n")
    if lines[0].startswith("# "):
        doc.title = lines.pop(0)[2:].strip()
    else:
        problems.append(f"{name}: dòng đầu phải là tiêu đề '# Tên báo cáo'.")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and PROP_RE.match(lines[0]):
        m = PROP_RE.match(lines.pop(0))
        doc.props[m.group(1).strip()] = m.group(2).strip()
    doc.intro = "\n".join(lines).strip()
    for chunk in chunks:
        heading, _, body = chunk.partition("\n")
        m = SECTION_RE.match(heading.strip())
        if not m:
            problems.append(f"{name}: mục '## {heading.strip()}' phải đánh số, dạng '## 3. Tính năng và đánh giá'.")
        elif m.group(1) in doc.sections:
            problems.append(f"{name}: mục số {m.group(1)} xuất hiện hai lần; đánh số lại theo docs/OUTPUT_PROTOCOL.md.")
        else:
            doc.sections[m.group(1)] = (m.group(2).strip(), body.strip())
    for key in ("Ngày", "Kết luận"):
        if not doc.prop(key):
            problems.append(f"{name}: thiếu dòng '- **{key}:** ...' trong danh sách thuộc tính ngay dưới tiêu đề.")
    return doc


def check_sections(doc, count, problems, notes):
    for i in range(1, count + 1):
        if str(i) not in doc.sections:
            problems.append(f"{doc.name}: thiếu mục '## {i}. ...'; bản này cần đủ mục 1 đến {count} theo docs/OUTPUT_PROTOCOL.md.")
    for num in doc.sections:
        if int(num) > count:
            notes.append(f"{doc.name}: bỏ qua mục {num} ({doc.sections[num][0]}); bản này chỉ dựng mục 1 đến {count}.")


def check_summary(doc, problems):
    for num, (what, limit) in SUMMARY_LIMITS.items():
        if num not in doc.sections:
            continue
        toks = tokens(doc.sections[num][1])
        if num == "5":
            t = first_table(toks)
            n = len(toks[t][2]) if t is not None else 0
        elif num == "1":
            z, labels = zones(toks)
            n = list_items(z["now"] if "now" in labels else toks)
        else:
            n = list_items(toks)
        if n > limit:
            problems.append(f"{doc.name} mục {num} ({doc.sections[num][0]}): {n} {what}, tối đa {limit} trên slide; "
                            f"chuyển phần còn lại sang bản chi tiết.")
    for num, need in (("3", "bảng '# | Tính năng | Trạng thái | Đánh giá | Rủi ro chính'"),
                      ("5", "bảng '# | Việc | Effort | Ai làm'")):
        if num in doc.sections and first_table(tokens(doc.sections[num][1])) is None:
            problems.append(f"{doc.name} mục {num}: cần {need}.")
    if "4" in doc.sections and not groups(tokens(doc.sections["4"][1]))[1]:
        problems.append(f"{doc.name} mục 4: mỗi nhóm rủi ro cao cần một tiêu đề '### 4.1 Tên nhóm (rủi ro cao)'.")


def appendix_ids(doc, problems):
    if str(DETAIL_SECTIONS) not in doc.sections:
        return []
    toks = tokens(doc.sections[str(DETAIL_SECTIONS)][1])
    t = first_table(toks)
    if t is None or toks[t][1][0].strip().lower() != "mã":
        problems.append(f"{doc.name} mục {DETAIL_SECTIONS}: phụ lục cần bảng '| Mã | Rủi ro | file:dòng | Ghi chú kỹ thuật |'.")
        return []
    ids = [r[0] for r in toks[t][2] if re.fullmatch(r"P\d+", r[0])]
    dup = sorted({p for p in ids if ids.count(p) > 1})
    if dup:
        problems.append(f"{doc.name} phụ lục: mã {', '.join(dup)} có nhiều dòng; mỗi mã P một dòng.")
    return ids


def referenced(doc, upto):
    refs = []
    for num, (_, body) in doc.sections.items():
        if int(num) <= upto:
            for m in PREF_RE.finditer(body):
                refs += re.findall(r"P\d+", m.group(1))
    return refs


def metric_list(doc, fallback, problems):
    raw = doc.prop("Số chính")
    if not raw:
        return fallback
    out = []
    for part in (p.strip().rstrip(".") for p in raw.split(";")):
        if not part:
            continue
        m = re.match(r"^\**(\S*\d\S*?)\**\s+(.+)$", part)
        if m:
            out.append((m.group(1), m.group(2)))
        else:
            problems.append(f"{doc.name}: '{part}' trong 'Số chính' phải bắt đầu bằng con số, ví dụ '24 mã trong thư viện'.")
    if len(out) > 4:
        problems.append(f"{doc.name}: 'Số chính' có {len(out)} số, bìa chỉ hiện tối đa 4.")
    return out


# ------------------------------------------------------------------ icons (SVG, no emoji)
def icon(name, size=22):
    paths = {
        "alert": '<circle cx="12" cy="12" r="9.5"/><path d="M12 7.5v5.5"/><circle cx="12" cy="16.5" r=".6" fill="currentColor"/>',
        "info": '<circle cx="12" cy="12" r="9.5"/><path d="M12 11v6"/><circle cx="12" cy="7.6" r=".6" fill="currentColor"/>',
        "chart": '<rect x="3.5" y="3.5" width="17" height="17" rx="3"/><path d="M8 16v-4M12 16V8M16 16v-6"/>',
    }
    return (f'<svg class="ico" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>')


# ------------------------------------------------------------------ slides
SLIDE_CSS = """
:root{--text:#18181b;--body:#3f3f46;--muted:#71717a;--faint:#a1a1aa;--line:#ececee;--accent:#0f766e;--panel:#f7f7f5}
*{box-sizing:border-box}
html{scroll-snap-type:y proximity;scroll-padding-top:24px}
html,body{margin:0;background:#eeeef0;font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;color:var(--body)}
body{padding:24px 0 48px}
.frame{position:relative;width:calc(1280px * var(--s,1));height:calc(720px * var(--s,1));margin:0 auto 28px;scroll-snap-align:start}
.slide{position:absolute;top:0;left:0;width:1280px;height:720px;transform:scale(var(--s,1));transform-origin:0 0;background:#fff;border-radius:14px;
  box-shadow:0 1px 2px rgba(0,0,0,.04),0 6px 20px rgba(0,0,0,.05);padding:60px 80px 76px;display:flex;flex-direction:column;overflow:hidden}
.kicker{font-size:13px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);margin-bottom:10px}
h1,h2,h3{margin:0;color:var(--text);letter-spacing:-.025em}
h2{font-size:40px;line-height:1.15;font-weight:700;margin-bottom:26px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.content{flex:1;min-height:0;display:flex;flex-direction:column}
p{margin:0}p.lead{font-size:20px;line-height:1.45;color:var(--muted);margin:0 0 18px}
ul,ol{margin:0;padding-left:26px}li{font-size:22px;line-height:1.45;margin:0 0 14px}li::marker{color:var(--faint)}
ul.tight li,ol.tight li{font-size:20px;margin-bottom:10px}
strong{color:var(--text);font-weight:650}
a{color:inherit;text-decoration:none}
.pref{display:inline-block;font-size:12px;line-height:18px;color:var(--muted);background:#ededeb;border-radius:4px;padding:0 6px;margin-left:5px;vertical-align:2px}
.pref:hover{background:#dcdcd8;color:var(--text)}.refs{white-space:nowrap}
code{font:85% ui-monospace,SFMono-Regular,Menlo,monospace}
.tag{display:inline-flex;align-items:center;height:24px;padding:0 9px;border-radius:5px;font-size:15px;font-weight:500;white-space:nowrap;margin-right:6px;letter-spacing:0}
h2 .tag{font-size:16px;height:28px}h3 .tag{font-size:14px;height:24px}
.tag.high,.tag.weak{background:#ffe2dd;color:#5d1715}.tag.med,.tag.ok{background:#fdecc8;color:#402c1b}.tag.low,.tag.good{background:#dbeddb;color:#1c3829}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:start}
.panel{background:var(--panel);border-radius:14px;padding:26px 30px}
.label{font-size:13px;font-weight:650;letter-spacing:.12em;text-transform:uppercase;margin-bottom:14px;color:var(--faint)}
.label.fix{color:var(--accent)}
.sub{font-size:18px;color:var(--muted);margin:-10px 0 20px}.sub li{font-size:18px;margin-bottom:4px}.sub p{margin-bottom:6px}
.note{margin-top:auto;font-size:15px;line-height:1.45;color:var(--muted);border-top:1px solid var(--line);padding-top:14px}
.note+.note{margin-top:6px;border-top:0;padding-top:0}.note li{font-size:15px;margin-bottom:4px}.note a{border-bottom:1px solid currentColor}
table{border-collapse:collapse;width:100%;font-size:16px}
th{text-align:left;font-size:13px;font-weight:600;color:var(--faint);letter-spacing:.04em;padding:0 14px 10px 0;border-bottom:1px solid #e4e4e7;white-space:nowrap}
td{padding:9px 14px 9px 0;border-bottom:1px solid var(--line);vertical-align:top;line-height:1.35;color:var(--body)}
td:first-child,th:first-child{color:var(--faint);width:36px}
table.big{font-size:20px}table.big td{padding:15px 16px 15px 0}
.verdict{display:flex;gap:16px;align-items:flex-start;background:#fbf3db;border-radius:14px;padding:22px 26px}
.verdict .ico{color:#a16207;flex:none;margin-top:2px}.verdict b{display:block;font-size:28px;color:var(--text);letter-spacing:-.01em}.verdict span{font-size:17px;color:#6b5a2e}
.foot{position:absolute;left:80px;right:80px;bottom:28px;display:flex;justify-content:space-between;font-size:13px;color:var(--faint)}
.slide.cover{padding:84px 96px}
.cover .eyebrow{font-size:14px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);margin-bottom:26px;padding-right:240px}
.cover h1{line-height:1.05;font-weight:750;letter-spacing:-.04em}.cover h1 em{font-style:normal;color:var(--accent)}
.cover .verdict{margin:36px 0 0;max-width:820px}
.metrics{margin-top:auto;display:grid;grid-template-columns:repeat(var(--n,4),1fr);border-top:1px solid var(--line);padding-top:22px}
.metrics div{font-size:15px;color:var(--muted);padding-right:16px}.metrics b{display:block;font-size:34px;color:var(--text);font-weight:650;letter-spacing:-.03em}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start}
.pair h3{font-size:24px;margin:0 0 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.pair li{font-size:19px;margin-bottom:10px}
.detail-link{position:absolute;top:84px;right:96px;font-size:15px;color:var(--accent);border:1px solid #cfe5e0;border-radius:8px;padding:8px 14px}
.detail-link:hover{background:#f0f7f5}
@media print{@page{size:1280px 720px;margin:0}html,body{background:#fff;padding:0}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .frame{width:1280px!important;height:720px!important;margin:0}.frame+.frame{break-before:page}
  .slide{transform:none!important;box-shadow:none;border-radius:0}}
"""

SLIDE_JS = """
(function(){
function fit(){var s=Math.min((innerWidth-64)/1280,(innerHeight-48)/720);document.documentElement.style.setProperty('--s',Math.max(.25,s));}
addEventListener('resize',fit);fit();
function check(){var bad=[];document.querySelectorAll('.slide').forEach(function(sl){var c=sl.querySelector('.content');
if(c&&(c.scrollHeight>c.clientHeight+1||c.scrollWidth>c.clientWidth+1))bad.push(sl.id);});
document.body.setAttribute('data-overflow',bad.join(' '));if(bad.length)console.warn('po_report: text overflows on '+bad.join(', '));}
addEventListener('load',check);
var h=location.hash.match(/^#slide(\\d+)$/);if(h){var e=document.getElementById('slide'+h[1]);if(e)e.parentNode.scrollIntoView();}
})();
"""


def _lower_first(s):
    return s[0].lower() + s[1:] if len(s) > 1 and s[1].islower() else s


class Deck:
    def __init__(self, pref):
        self.pref, self.slides = pref, []

    def il(self, text):
        return inline(text, self.pref)

    def ul(self, items, ordered=False, cls=""):
        t = "ol" if ordered else "ul"
        return f'<{t} class="{cls}">' + "".join(f"<li>{self.il(x)}</li>" for x in items) + f"</{t}>"

    def flow(self, toks, cls=""):
        """Blocks in order; paragraphs after the last list or table drop to the bottom as notes."""
        last = max((i for i, t in enumerate(toks) if t[0] in ("list", "table")), default=-1)
        out = []
        for i, t in enumerate(toks):
            if t[0] == "p":
                out.append(f'<div class="note">{self.il(t[1])}</div>' if 0 <= last < i else f'<p class="lead">{self.il(t[1])}</p>')
            elif t[0] == "quote":
                out.append(f'<div class="note">{self.il(t[1])}</div>')
            elif t[0] == "label":
                out.append(f'<div class="label {t[1]}">{html.escape(t[2])}</div>')
            elif t[0] == "list":
                out.append(self.ul(t[2], t[1], cls))
            elif t[0] == "table":
                out.append(table_html(t[1], t[2], self.pref))
            elif t[0] == "h3":
                out.append(f"<h3>{self.il(t[1])}</h3>")
        return "".join(out)

    def add(self, kicker, title_html, inner, cls=""):
        head = f'<div class="kicker">{html.escape(kicker)}</div><h2>{title_html}</h2>' if title_html else ""
        self.slides.append((cls, head + f'<div class="content">{inner}</div>'))


def _level_tag(level):
    return tag(LEVEL[level], "Rủi ro " + level) if level else ""


def _small(group):
    z, labels = zones(group[3])
    return bool(labels) and list_items(z["now"]) + list_items(z["fix"]) <= SMALL_GROUP


def _zone(d, z, labels, kind, cls=""):
    if kind not in labels:
        return ""
    return f'<div class="label {kind}">{html.escape(labels[kind])}</div>{d.flow(z[kind], cls)}'


def risk_slides(d, num, title, toks):
    """One slide per risk group, two columns Hiện tại / Cần cải thiện; two short groups share a slide."""
    lead, gs = groups(toks)
    sub = f'<div class="sub">{d.flow(lead)}</div>' if lead else ""
    i = 0
    while i < len(gs):
        if i + 1 < len(gs) and _small(gs[i]) and _small(gs[i + 1]):
            panels = ""
            for _, label, level, gt in gs[i:i + 2]:
                z, labels = zones(gt)
                panels += (f'<div class="panel"><h3>{d.il(label)}{_level_tag(level)}</h3>{d.flow(z["pre"])}'
                           f'{_zone(d, z, labels, "now")}{_zone(d, z, labels, "fix")}</div>')
            d.add(f"Phần {num}", html.escape(title), sub + f'<div class="pair">{panels}</div>')
            i += 2
        else:
            _, label, level, gt = gs[i]
            z, labels = zones(gt)
            if labels:
                inner = (f'{d.flow(z["pre"])}<div class="cols"><div>{_zone(d, z, labels, "now", "tight")}</div>'
                         f'<div class="panel">{_zone(d, z, labels, "fix", "tight")}</div></div>')
            else:
                inner = d.flow(gt, "tight")
            d.add(f"Phần {num} · {title}", d.il(label) + _level_tag(level), sub + inner)
            i += 1
        sub = ""


def render_slides(s, detail_href, metrics, n_codes):
    d = Deck(detail_href)
    sec = s.sections
    project = s.prop("Dự án")
    title_html = html.escape(s.title)
    if project and project in s.title:
        title_html = title_html.replace(html.escape(project), f"<em>{html.escape(project)}</em>", 1)
    size = 72 if len(s.title) <= 28 else 56 if len(s.title) <= 48 else 46 if len(s.title) <= 72 else 40
    eyebrow = " · ".join(x for x in (f"Báo cáo cho {s.prop('Người đọc', 'PO')}", s.prop("Ngày"), s.prop("Thời gian đọc")) if x)
    status = s.prop("Trạng thái")
    metrics_html = "".join(f"<div><b>{html.escape(v)}</b>{html.escape(k)}</div>" for v, k in metrics)
    d.slides.append(("cover", f'<div class="content"><div class="eyebrow">{html.escape(eyebrow)}</div>'
                              f'<h1 style="font-size:{size}px">{title_html}</h1>'
                              f'<div class="verdict">{icon("alert", 30)}<div><b>{d.il(s.prop("Kết luận"))}</b>'
                              + (f"<span>{d.il(status)}</span>" if status else "") + "</div></div>"
                              + (f'<div class="metrics" style="--n:{len(metrics)}">{metrics_html}</div>' if metrics else "")
                              + f'</div><a class="detail-link" href="{html.escape(detail_href)}">Xem bản chi tiết &rarr;</a>'))

    for num in ("1", "2"):
        d.add(f"Phần {num}", html.escape(sec[num][0]), d.flow(tokens(sec[num][1])))

    t3, toks = sec["3"][0], tokens(sec["3"][1])
    k = first_table(toks)
    header, rows = toks[k][1], toks[k][2]
    chunks = [rows[j:j + ROWS_PER_SLIDE] for j in range(0, len(rows), ROWS_PER_SLIDE)] or [[]]
    pre, post = toks[:k], toks[k + 1:]
    for j, chunk in enumerate(chunks):
        inner = (f'<div class="sub">{d.flow(pre)}</div>' if j == 0 and pre else "") + table_html(header, chunk, detail_href)
        if j == len(chunks) - 1 and post:
            inner += f'<div class="note">{d.flow(post)}</div>'
        d.add("Phần 3" + (f" · {j + 1}/{len(chunks)}" if len(chunks) > 1 else ""), html.escape(t3), inner)

    risk_slides(d, "4", sec["4"][0], tokens(sec["4"][1]))

    toks = tokens(sec["5"][1])
    k = first_table(toks)
    d.add("Phần 5", html.escape(sec["5"][0]),
          d.flow(toks[:k]) + table_html(toks[k][1], toks[k][2], detail_href, "big") + d.flow(toks[k + 1:]))

    (t6, b6), (t7, b7) = sec["6"], sec["7"]
    d.add("Phần 6 và 7", html.escape(f"{t6} và {_lower_first(t7)}"),
          f'<div class="cols"><div><div class="label now">{html.escape(t6)}</div>{d.flow(tokens(b6), "tight")}</div>'
          f'<div class="panel"><div class="label now">{html.escape(t7)}</div>{d.flow(tokens(b7), "tight")}</div></div>')

    d.add("Phần 8", html.escape(sec["8"][0]),
          d.flow(tokens(sec["8"][1])) + f'<div class="note">Bằng chứng cho {n_codes} mã P (phụ lục cho dev) nằm ở '
                                        f'<a href="{html.escape(detail_href)}">bản chi tiết</a>.</div>')

    n = len(d.slides)
    foot_left = html.escape(project or s.title)
    frames = []
    for k, (cls, inner) in enumerate(d.slides, 1):
        foot = f'<div class="foot"><span>{foot_left}</span><span>{k} / {n}</span></div>' if cls != "cover" else ""
        frames.append(f'<div class="frame"><section class="slide {cls}" id="slide{k}">{inner}{foot}</section></div>')
    page = (f'<!doctype html>\n<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{html.escape(s.title)}</title><style>{SLIDE_CSS}</style></head>\n"
            f'<body data-slides="{n}">\n' + "\n".join(frames) + f"\n<script>{SLIDE_JS}</script>\n</body></html>\n")
    return page, n


# ------------------------------------------------------------------ detailed page
PAGE_CSS = """
:root{color-scheme:light;--text:#37352f;--muted:rgba(55,53,47,.65);--faint:rgba(55,53,47,.45);--line:rgba(55,53,47,.09);--cell:#e9e9e7;--hover:rgba(55,53,47,.06);
--accent:#0f766e;--gray-bg:#f1f1ef;--yellow-bg:#fbf3db}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:#fff;color:var(--text);font:16px/1.5 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.page{max-width:760px;margin:0 auto;padding:96px 48px 160px}
a{color:inherit;text-decoration:none;border-bottom:.05em solid rgba(55,53,47,.4)}a:hover{border-bottom-color:var(--text)}
p{margin:2px 0;padding:3px 2px;line-height:1.5}strong{font-weight:600}
.page-icon{color:var(--accent);margin-bottom:12px}
h1.title{font-size:40px;line-height:1.2;font-weight:700;letter-spacing:-.01em;margin:0 0 14px}
.props{margin:0 0 6px}
.prop{display:flex;align-items:flex-start;min-height:34px;padding:5px 0;font-size:14px}
.prop .k{flex:0 0 170px;color:var(--muted);padding-right:8px}
.prop .v{flex:1;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
hr{border:0;border-top:1px solid var(--line);margin:16px 0}
.callout{display:flex;gap:10px;padding:16px 16px 16px 12px;border-radius:4px;margin:6px 0}
.callout .ico{flex:none;margin-top:2px;color:var(--muted)}.callout.yellow .ico{color:#a16207}
.callout-body{flex:1;min-width:0}.callout-body p:first-child{padding-top:0}.callout-body>*:last-child{margin-bottom:0}
.callout.gray{background:var(--gray-bg)}.callout.yellow{background:var(--yellow-bg)}
.toc{margin:10px 0 4px}
.toc a{display:block;width:fit-content;color:var(--muted);border-bottom:0;font-size:14px;padding:3px 2px}
.toc a span{border-bottom:1px solid rgba(55,53,47,.16)}.toc a:hover{background:var(--hover);border-radius:3px}
h2{font-size:30px;line-height:1.3;font-weight:600;margin:2em 0 4px;padding:3px 2px;scroll-margin-top:24px}
h3{display:flex;align-items:center;flex-wrap:wrap;gap:10px;font-size:20px;line-height:1.3;font-weight:600;margin:1.6em 0 2px;padding:3px 2px}
h3 .num{color:var(--faint);font-weight:500;margin-right:-2px}
.risk{scroll-margin-top:24px}
ul,ol{margin:2px 0;padding-left:1.6em}li{padding:3px 0;line-height:1.5}
.sub{font-size:14px;font-weight:600;margin:12px 0 0;padding:3px 2px}.sub.now{color:#787774}.sub.fix{color:var(--accent)}
.tag{display:inline-flex;align-items:center;height:20px;padding:0 6px;border-radius:3px;font-size:13px;font-weight:400;line-height:120%;white-space:nowrap;margin-right:4px;vertical-align:1px}
.tag.high,.tag.weak{background:#ffe2dd;color:#5d1715}.tag.med,.tag.ok{background:#fdecc8;color:#402c1b}
.tag.low,.tag.good{background:#dbeddb;color:#1c3829}.tag.gray{background:#e3e2e0;color:#32302c}
.table-wrap{overflow-x:auto;margin:10px 0 6px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid var(--cell);padding:7px 9px;vertical-align:top;text-align:left;line-height:1.45}
th{background:#f7f6f3;color:var(--muted);font-weight:500;white-space:nowrap}
code{font:85% ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#eb5757;background:rgba(135,131,120,.15);border-radius:4px;padding:.2em .4em;overflow-wrap:anywhere}
.refs{white-space:nowrap}
a.pref{display:inline-block;font-size:11.5px;line-height:18px;color:var(--muted);background:#e3e2e0;border:0;border-radius:3px;padding:0 5px;margin-left:4px}
a.pref:hover{background:#d3d1cb;color:var(--text)}
details.appendix{margin:4px 0}
details.appendix>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:6px;font-size:16px;padding:3px 2px;border-radius:3px}
details.appendix>summary::-webkit-details-marker{display:none}
details.appendix>summary::before{content:"";width:0;height:0;border-left:7px solid var(--text);border-top:4.5px solid transparent;border-bottom:4.5px solid transparent;transition:transform .15s;margin:0 6px 0 4px}
details.appendix[open]>summary::before{transform:rotate(90deg)}
details.appendix>summary:hover{background:var(--hover)}
details.appendix>.toggle-body{padding-left:26px}
details.appendix td{font-size:13px}
tr:target td{background:var(--yellow-bg)}
.fine{font-size:13px;color:var(--faint);margin-top:48px}
@media(max-width:700px){.page{padding:56px 20px 96px}.prop .k{flex-basis:120px}h1.title{font-size:32px}}
@media print{.page{padding:24px 0}details.appendix{display:none}.toc{display:none}}
"""

PAGE_JS = """
function openRef(){var id=location.hash.slice(1);if(!/^P\\d+$/.test(id))return;var d=document.querySelector('details.appendix');
if(d&&!d.open)d.open=true;var el=document.getElementById(id);if(el)el.scrollIntoView({block:'center',behavior:'instant'});}
addEventListener('hashchange',openRef);addEventListener('DOMContentLoaded',openRef);
"""


def callout(kind, color, inner):
    return f'<div class="callout {color}">{icon(kind)}<div class="callout-body">{inner}</div></div>'


def blocks(toks, row_ids=False):
    out = []
    for t in toks:
        if t[0] == "p":
            out.append(f"<p>{inline(t[1])}</p>")
        elif t[0] == "quote":
            out.append(callout("info", "gray", f"<p>{inline(t[1])}</p>"))
        elif t[0] == "label":
            out.append(f'<div class="sub {t[1]}">{html.escape(t[2])}</div>')
        elif t[0] == "list":
            tg = "ol" if t[1] else "ul"
            out.append(f"<{tg}>" + "".join(f"<li>{inline(x)}</li>" for x in t[2]) + f"</{tg}>")
        elif t[0] == "table":
            out.append(f'<div class="table-wrap">{table_html(t[1], t[2], row_ids=row_ids)}</div>')
        elif t[0] == "h3":
            out.append(f"<h3>{inline(t[1])}</h3>")
    return "\n".join(out)


def render_detail(doc, summary_href, metrics):
    props = [("Phiên bản", tag("gray", "Bản chi tiết") + f'<a href="{html.escape(summary_href)}">Xem bản tóm tắt dạng slide</a>')]
    for k, v in doc.props.items():
        if k.casefold() == "số chính":
            v_html = "".join(f'<span class="tag gray"><strong>{html.escape(n)}</strong>&nbsp;{html.escape(lbl)}</span>' for n, lbl in metrics)
        else:
            v_html = inline(v)
        props.append((html.escape(k), v_html))
    props_html = '<div class="props">' + "".join(
        f'<div class="prop"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in props) + "</div>"
    howto = callout("info", "gray", "<p><strong>Cách đọc</strong></p>" + blocks(tokens(doc.intro))) if doc.intro else ""
    nums = sorted((n for n in doc.sections if int(n) <= DETAIL_SECTIONS), key=int)
    toc = '<div class="toc">' + "".join(
        f'<a href="#sec{n}"><span>{n}. {html.escape(doc.sections[n][0])}</span></a>' for n in nums) + "</div>"

    body = []
    for n in nums:
        title, md = doc.sections[n]
        toks = tokens(md)
        content = ""
        if n == "1":
            status = doc.prop("Trạng thái")
            content = callout("alert", "yellow", f'<p><strong>{inline(doc.prop("Kết luận"))}</strong>'
                                                 + (f" {inline(status)}" if status else "") + "</p>")
        if n == str(DETAIL_SECTIONS):
            content += ('<details class="appendix"><summary>Bằng chứng file:dòng cho từng mã P (bấm để mở)</summary>'
                        f'<div class="toggle-body">{blocks(toks, row_ids=True)}</div></details>')
        else:
            lead, gs = groups(toks)
            content += blocks(lead)
            for num, label, level, gt in gs:
                anchor = f' id="s{num}"' if num else ""
                numspan = f'<span class="num">{num}</span>' if num else ""
                content += f'<div class="risk"{anchor}><h3>{numspan}{inline(label)}{_level_tag(level)}</h3>{blocks(gt)}</div>'
        body.append(f'<h2 id="sec{n}">{n}. {html.escape(title)}</h2>\n{content}')

    return (f'<!doctype html>\n<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{html.escape(doc.title)}</title><style>{PAGE_CSS}</style></head>\n<body><div class=\"page\">\n"
            f'<div class="page-icon">{icon("chart", 64)}</div>\n<h1 class="title">{html.escape(doc.title)}</h1>\n'
            f"{props_html}\n<hr>\n{howto}\n{toc}\n" + "\n".join(body)
            + f'\n<p class="fine">Dựng từ {html.escape(doc.name)} bằng scripts/po_report.py. Sửa file .md rồi chạy lại script để cập nhật trang này.</p>\n'
            f"</div>\n<script>{PAGE_JS}</script>\n</body></html>\n")


# ------------------------------------------------------------------ build and CLI
def build(summary_md, detail_md, summary_name="PO_SUMMARY.md", detail_name="PO_DETAIL.md"):
    problems, notes = [], []
    s = parse(summary_md, summary_name, problems)
    d = parse(detail_md, detail_name, problems)
    check_sections(s, SUMMARY_SECTIONS, problems, notes)
    check_sections(d, DETAIL_SECTIONS, problems, notes)
    check_summary(s, problems)
    ids = appendix_ids(d, problems)
    if ids:
        for doc, upto in ((s, SUMMARY_SECTIONS), (d, DETAIL_SECTIONS - 1)):
            missing = sorted(set(referenced(doc, upto)) - set(ids), key=lambda p: int(p[1:]))
            if missing:
                problems.append(f"{doc.name}: mã {', '.join(missing)} không có dòng trong phụ lục của {detail_name}; "
                                f"thêm dòng vào bảng phụ lục hoặc sửa mã.")
    if s.prop("Kết luận") and d.prop("Kết luận") and s.prop("Kết luận") != d.prop("Kết luận"):
        notes.append(f"'Kết luận' của {summary_name} và {detail_name} khác nhau; hai bản nên cùng một câu.")
    if problems:
        raise ReportError(problems)

    feat = tokens(s.sections["3"][1])
    rows = feat[first_table(feat)][2]
    header = [h.strip().lower() for h in feat[first_table(feat)][1]]
    col = header.index("đánh giá") if "đánh giá" in header else None
    weak = sum(1 for r in rows if col is not None and col < len(r) and r[col].strip("* ").lower().startswith("yếu"))
    actions = tokens(s.sections["5"][1])
    fallback = [(f"{weak}/{len(rows)}", "tính năng đánh giá Yếu"),
                (str(len(groups(tokens(s.sections["4"][1]))[1])), "nhóm rủi ro cao"),
                (str(len(actions[first_table(actions)][2])), "việc cần làm trước"),
                (str(len(ids)), "mã bằng chứng trong phụ lục")]
    s_metrics = metric_list(s, fallback, problems)
    d_metrics = metric_list(d, [], problems)
    if problems:
        raise ReportError(problems)

    summary_html_name = Path(summary_name).with_suffix(".html").name
    detail_html_name = Path(detail_name).with_suffix(".html").name
    slides, n = render_slides(s, detail_html_name, s_metrics, len(ids))
    page = render_detail(d, summary_html_name, d_metrics)
    return Result(summary_html_name, detail_html_name, slides, page, n, len(ids), notes)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build PO_SUMMARY.html (slides) and PO_DETAIL.html (one-column page) "
                                             "from the two PO Markdown files of RULES R13.")
    ap.add_argument("review_dir", nargs="?", type=Path, help="folder holding PO_SUMMARY.md and PO_DETAIL.md; HTML is written there")
    ap.add_argument("--summary", type=Path, help="short version (slides)")
    ap.add_argument("--detail", type=Path, help="detailed version (page with appendix)")
    ap.add_argument("--out-dir", type=Path, help="where to write both HTML files (default: beside the summary)")
    a = ap.parse_args(argv)
    if a.review_dir:
        summary = a.summary or a.review_dir / "PO_SUMMARY.md"
        detail = a.detail or a.review_dir / "PO_DETAIL.md"
    elif a.summary and a.detail:
        summary, detail = a.summary, a.detail
    else:
        ap.error("give a review folder, or both --summary and --detail")
    out = a.out_dir or summary.parent
    missing = [str(p) for p in (summary, detail) if not p.is_file()]
    if missing:
        print(f"po_report: ERROR không thấy {', '.join(missing)}. Agent viết 2 file Markdown theo "
              "docs/OUTPUT_PROTOCOL.md trước, rồi chạy lại.", file=sys.stderr)
        return 2
    try:
        res = build(summary.read_text(encoding="utf-8"), detail.read_text(encoding="utf-8"), summary.name, detail.name)
    except ReportError as e:
        print("po_report: ERROR Markdown chưa đúng cấu trúc docs/OUTPUT_PROTOCOL.md; chưa ghi HTML.", file=sys.stderr)
        for p in e.problems:
            print("  - " + p, file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    (out / res.summary_name).write_text(res.summary_html, encoding="utf-8")
    (out / res.detail_name).write_text(res.detail_html, encoding="utf-8")
    for n in res.notes:
        print("po_report: note: " + n, file=sys.stderr)
    print(f"{out / res.summary_name}  slides={res.slides}")
    print(f"{out / res.detail_name}  appendix_codes={res.codes}")
    print("Check in a browser: <body data-overflow> on the slides must be empty (no slide overflows).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

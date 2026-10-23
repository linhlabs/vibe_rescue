"""Turn a scoped Architecture Atlas into a source-linked team handoff.

The packet reports static evidence and missing proofs. It never promotes a
candidate control to a safety verdict or executes target application code.
"""

import html
import os
import subprocess
from pathlib import Path
from urllib.parse import quote

TEXT = {
    "en": {
        "title": "Team handoff", "claim": "Evidence packet, not a readiness verdict",
        "intro": "Open the architecture map, follow source anchors, then assign the probes below. No target tests or runtime traces were run by this command.",
        "snapshot": "Snapshot", "purpose": "Documented purpose", "blocks": "Functional blocks",
        "journeys": "Documented journeys", "controls": "Harness and sensitive controls",
        "assets": "Config, prompt and workflow paths", "next": "Next work for the team",
        "coverage": "Coverage and unknowns", "source": "Source", "functions": "Function leads",
        "links": "Open the maps", "unknown": "Unknown binding", "candidate": "Candidate only",
        "verify": "Next proof", "evidence": "Located evidence", "none": "Not located in approved scope",
        "runtime": "Runtime path unverified", "docs": "Documentation can be stale",
        "no_controls": "No control profile selected or inferred; choose --profile for a focused review.",
        "no_journeys": "No numbered architecture or workflow journey found in approved docs.",
        "no_edges": "No cross-block Python call/import resolved in this scope.",
        "review": "REVIEW REQUIRED", "relations": "source relations", "markdown": "Markdown",
        "files": "files", "python_functions": "Python functions", "tracked": "tracked changes",
        "fingerprint": "Atlas fingerprint", "code_files": "code files", "docs_count": "docs",
        "non_python": "non-Python files at file level", "parse": "parse errors",
        "skipped": "skipped docs", "paths_summary": "paths; loader and precedence unverified",
        "section_start": "START HERE", "section_map": "MAP", "section_trace": "TRACE",
        "section_verify": "VERIFY", "section_limits": "LIMITS",
        "status_label": "Status", "candidate_count": "candidate(s)",
        "worksheet": "Review worksheet", "worksheet_note": "Assign owners and attach exact-build receipts here. This file is never overwritten by a rerun.",
    },
    "vi": {
        "title": "Bàn giao cho team", "claim": "Gói bằng chứng, chưa là phán quyết sẵn sàng",
        "intro": "Mở bản đồ kiến trúc, lần theo source rồi giao các phép thử bên dưới. Lệnh này không chạy test hay trace runtime của target.",
        "snapshot": "Tổng quan", "purpose": "Mục đích theo tài liệu", "blocks": "Khối chức năng",
        "journeys": "Hành trình theo tài liệu", "controls": "Control harness và dữ liệu nhạy cảm",
        "assets": "Đường dẫn config, prompt và workflow", "next": "Việc tiếp theo cho team",
        "coverage": "Độ phủ và điều chưa biết", "source": "Nguồn", "functions": "Hàm để bắt đầu đọc",
        "links": "Mở các bản đồ", "unknown": "Chưa nối được hàm", "candidate": "Chỉ là dấu vết",
        "verify": "Cần chứng minh", "evidence": "Bằng chứng tìm thấy", "none": "Chưa thấy trong scope được duyệt",
        "runtime": "Chưa chứng minh đường chạy", "docs": "Tài liệu có thể đã cũ",
        "no_controls": "Chưa chọn hoặc suy ra profile; dùng --profile để review đúng control.",
        "no_journeys": "Không thấy hành trình đánh số trong tài liệu kiến trúc/workflow được duyệt.",
        "no_edges": "Không phân giải được call/import Python giữa các khối trong scope này.",
        "review": "CẦN REVIEW", "relations": "quan hệ source", "markdown": "Bản Markdown",
        "files": "file", "python_functions": "hàm Python", "tracked": "file đã đổi",
        "fingerprint": "Dấu vân tay Atlas", "code_files": "file code", "docs_count": "tài liệu",
        "non_python": "file ngoài Python ở mức file", "parse": "lỗi parse",
        "skipped": "tài liệu bỏ qua", "paths_summary": "đường dẫn; loader và ưu tiên chưa chứng minh",
        "section_start": "BẮT ĐẦU", "section_map": "BẢN ĐỒ", "section_trace": "LẦN THEO",
        "section_verify": "KIỂM CHỨNG", "section_limits": "GIỚI HẠN",
        "status_label": "Trạng thái", "candidate_count": "dấu vết",
        "worksheet": "Phiếu review", "worksheet_note": "Giao người phụ trách và gắn receipt của đúng build tại đây. Chạy lại sẽ không ghi đè file này.",
    },
}

VI_CONTROLS = {
    "H01": ("Ý định và kế hoạch", "Trace đầu vào tới intent/plan có cấu trúc, gồm trường hợp mơ hồ và planner lỗi."),
    "H02": ("Quyền gọi tool và scope", "Chứng minh agent chỉ gọi tool được duyệt và không ghi ngoài scope."),
    "H03": ("Timeout, hủy và kết thúc", "Tiêm lỗi timeout/hủy; chứng minh trạng thái cuối có giới hạn và không còn việc mồ côi."),
    "H04": ("Retry và ngân sách", "Đo giới hạn retry/token/chi phí; chứng minh lỗi không lặp vô hạn hoặc bị bỏ qua."),
    "H05": ("Bằng chứng và kiểm cuối", "Trace một claim từ nguồn qua writer tới phán quyết kiểm cuối."),
    "H06": ("Audit từng bước", "Kiểm mọi quyết định và lỗi đều có event audit đúng thứ tự, đã che dữ liệu."),
    "S01": ("Phân việc song song", "Nếu dùng nhiều agent song song, chứng minh giới hạn fan-out, thứ tự và backpressure."),
    "S02": ("Review độc lập", "Chỉ ra reviewer khác biệt, cách xử lý bất đồng và không có đường tự duyệt."),
    "S03": ("Cô lập lỗi worker", "Dừng một worker giữa chừng; kiểm sibling, shared state và câu trả lời cuối fail-safe."),
    "P01": ("Đầu vào dữ liệu nhạy cảm", "Xác định entrypoint và loại dữ liệu mà không chép PII thật vào báo cáo."),
    "P02": ("Che dữ liệu trước egress", "Tiêm lỗi masker tại mọi ranh giới outbound; chứng minh không lộ định danh thô."),
    "P03": ("Lưu trữ, thời hạn và đồng ý", "Test consent, cách ly chủ thể, xóa/TTL và chính sách lưu trữ."),
    "P04": ("Che dữ liệu trong audit", "Kiểm audit từng bước/cuối và telemetry bằng định danh giả; không còn giá trị thô."),
    "M01": ("Bằng chứng và citation y khoa", "Thử thiếu nguồn/nguồn mâu thuẫn; chặn số và citation y khoa bịa đặt."),
    "M02": ("Cách ly bệnh nhân/chủ thể", "Thử self/người thân/chưa rõ; chặn nhớ nhầm người và cá nhân hóa sai."),
    "B01": ("Quyền và idempotency thanh toán", "Gửi lặp yêu cầu thanh toán; chứng minh có quyền và chỉ một khoản thu bền vững."),
    "B02": ("Sổ cái và đối soát", "Chứng minh audit giao dịch, đối soát và đường bù trừ khi lỗi."),
}
VI_STATUS = {
    "source_candidate": "dấu vết source", "test_only": "chỉ có test",
    "documented_only": "chỉ có tài liệu", "not_located_in_scope": "chưa thấy trong scope",
}


def _control_text(control, lang):
    return VI_CONTROLS.get(control["id"], (control["title"], control["recommendation"])) if lang == "vi" else (
        control["title"], control["recommendation"])


def _git_state(root):
    def run(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else ""

    top = run("rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != Path(root).resolve():
        return "unknown", "unknown"
    head = run("rev-parse", "HEAD") or "unknown"
    changed = run("status", "--porcelain", "--untracked-files=no")
    return head, len(changed.splitlines()) if changed else 0


def _source_url(root, output, source):
    path, sep, line = source.rpartition(":")
    if not sep or not line.isdigit():
        path, line = source, ""
    target = os.path.relpath(root / path, output.parent).replace(os.sep, "/")
    return quote(target, safe="/.-_") + (f"#L{line}" if line else "")


def _md(value):
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("<", "&lt;")


def _md_link(label, url):
    return f"[{_md(label).replace('[', '&#91;').replace(']', '&#93;')}]({url})"


def _html_link(label, url):
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(str(label))}</a>'


def _tasks(model, t):
    tasks = []
    if model["coverage"]["journey_steps_unbound"]:
        n = model["coverage"]["journey_steps_unbound"]
        tasks.append((f"Bind {n} documented steps to current source and a served trace." if t is TEXT["en"] else
                      f"Nối {n} bước tài liệu với source hiện tại và trace được serve.", "journeys"))
    if model["coverage"]["parse_errors"]:
        tasks.append(("Resolve Python parse errors before relying on graph coverage." if t is TEXT["en"] else
                      "Xử lý lỗi parse Python trước khi tin vào độ phủ graph.", "coverage"))
    if model["coverage"]["non_python_files"]:
        tasks.append(("Trace UI/API and other cross-language edges; this Atlas inventories those files only." if t is TEXT["en"] else
                      "Trace UI/API và cạnh khác ngôn ngữ; Atlas mới kiểm kê các file đó.", "coverage"))
    if model["controls"]:
        tasks.append(("For each selected control, collect an exact-build runtime/fault receipt; names and tests are leads only." if t is TEXT["en"] else
                      "Với từng control đã chọn, lấy receipt runtime/fault trên đúng build; tên hàm và test chỉ là dấu vết.", "controls"))
    if not tasks:
        tasks.append(("Select one user journey and verify its runtime behavior against the static map." if t is TEXT["en"] else
                      "Chọn một hành trình người dùng và đối chiếu runtime với bản đồ tĩnh.", "journeys"))
    return tasks


def render_markdown(model, root, output, lang="en"):
    t = TEXT[lang]
    head, changed = _git_state(root)
    c = model["coverage"]
    snapshot_line = (f"- Git HEAD: `{head}`; tracked changes: `{changed}`. "
                     "Working-tree evidence is not a deployed-build identity." if lang == "en" else
                     f"- Git HEAD: `{head}`; file đã đổi: `{changed}`. "
                     "Bằng chứng worktree chưa là định danh build đang deploy.")
    fingerprint_line = (f"- Atlas fingerprint: `{model['fingerprint']}`; "
                        f"approved source areas: `{', '.join(model['sources'])}`." if lang == "en" else
                        f"- Dấu vân tay Atlas: `{model['fingerprint']}`; "
                        f"scope source được duyệt: `{', '.join(model['sources'])}`.")
    count_line = (f"- {c['code_files']} code files; {len(model['blocks'])} blocks; "
                  f"{len(model['edges'])} cross-block relations; documented journeys: {len(model['journeys'])}; "
                  f"unbound steps: {c['journey_steps_unbound']}." if lang == "en" else
                  f"- {c['code_files']} file code; {len(model['blocks'])} khối; "
                  f"{len(model['edges'])} quan hệ giữa khối; hành trình tài liệu: {len(model['journeys'])}; "
                  f"bước chưa nối: {c['journey_steps_unbound']}.")
    lines = ["<!-- markdownlint-disable MD013 -->", "",
             f"# {t['title']} — {_md(model['repo'])}", "",
             f"**{t['claim']}.** {t['intro']}", "",
             (f"{_md_link(t['worksheet'], 'REVIEW_WORKSHEET' + ('.vi' if lang == 'vi' else '') + '.md')} · "
              f"{_md_link('Architecture Atlas', 'architecture.html')} · "
              f"{_md_link('Source Explorer', 'source-explorer.html')} · "
              f"{_md_link('Machine JSON', 'architecture.json')}"), "",
             f"## {t['snapshot']}", "",
             snapshot_line, fingerprint_line, count_line, "",
             f"## {t['purpose']}", "",
             _md(model["overview"]["purpose"]), "",
             f"{t['source']}: " + (_md_link(model["overview"]["source"],
             _source_url(root, output, model["overview"]["source"])) if model["overview"]["source"] else t["none"]),
             f"**{t['docs']}.**", "", f"## {t['next']}", ""]
    for task, section in _tasks(model, t):
        section_url = f"handoff{'.vi' if lang == 'vi' else ''}.html#{section}"
        lines.append(f"- {task} " + (f"See [{section}]({section_url})." if lang == "en" else
                                     f"Xem [{section}]({section_url})."))
    lines += ["", f"## {t['blocks']}", ""]
    for block in model["blocks"]:
        lines += [f"### `{_md(block['id'])}` · {block['label']}", "",
                  f"{_md(block['purpose']['text'])} ({block['purpose']['state']})."]
        if block["purpose"]["source"]:
            source = block["purpose"]["source"]
            lines.append(f"{t['source']}: {_md_link(source, _source_url(root, output, source))}.")
        files_line = (f"{len(block['files'])} files; {len(block['functions'])} indexed Python functions. "
                      if lang == "en" else
                      f"{len(block['files'])} file; {len(block['functions'])} hàm Python đã index. ")
        lines.append(files_line + _md_link("Open block" if lang == "en" else "Mở khối",
                                          "architecture.html?block=" + quote(block["id"])) + ".")
        if block["function_leads"]:
            leads = [(_md_link(fn, "source-explorer.html?function=" + quote(fn)) + " " +
                      _md_link(model["function_anchors"][fn],
                               _source_url(root, output, model["function_anchors"][fn])))
                     for fn in block["function_leads"][:5]]
            lines.append(f"{t['functions']}: " + ", ".join(leads) + ".")
        outgoing = [e for e in model["edges"] if e["from"] == block["id"]]
        if outgoing:
            lines.append("")
        for edge in sorted(outgoing, key=lambda e: (e["kind"].startswith("test"), -e["count"]))[:5]:
            ex = edge["examples"][0]
            source = ex.get("source") or f"{ex['file']}:{ex['line']}"
            lines.append(f"- → `{_md(edge['to'])}` · {edge['kind']} · {edge['count']} "
                         f"{'refs' if lang == 'en' else 'tham chiếu'}; "
                         f"{_md_link(source, _source_url(root, output, source))} ({ex['resolution']}).")
        lines.append("")
    if not model["edges"]:
        lines += [t["no_edges"], ""]
    lines += [f"## {t['journeys']}", ""]
    if not model["journeys"]:
        lines += [t["no_journeys"], ""]
    for journey in model["journeys"]:
        lines += [f"### {_md(journey['title'])}", "",
                  f"{t['source']}: {_md_link(journey['source'], _source_url(root, output, journey['source']))}.", ""]
        for n, step in enumerate(journey["steps"], 1):
            refs = ", ".join(_md_link(fn, "source-explorer.html?function=" + quote(fn)) + " " +
                             _md_link(model["function_anchors"][fn],
                                      _source_url(root, output, model["function_anchors"][fn]))
                             for fn in step["functions"]) or f"**{t['unknown']}**"
            lines.append(f"{n}. {_md(step['text'])} — {refs}; "
                         f"{_md_link(step['source'], _source_url(root, output, step['source']))}.")
        lines.append("")
    lines += [f"## {t['controls']}", "",
              f"**{t['candidate']}. {t['runtime']}.**", ""]
    if not model["controls"]:
        lines += [t["no_controls"], ""]
    for control in model["controls"]:
        title, recommendation = _control_text(control, lang)
        status = VI_STATUS.get(control["status"], control["status"]) if lang == "vi" else control["status"]
        lines += [f"### {control['id']} · {title} ({control['group']})", "",
                  (f"{t['status_label']}: `{control['status']}` ({status}); "
                   f"{control['candidate_count']} {t['candidate_count']}."), ""]
        for item in control["evidence"]:
            lines.append(f"- {item['kind']}: "
                         f"{_md_link(item['source'], _source_url(root, output, item['source']))}" +
                         (f" · {_md_link(item['symbol'], 'source-explorer.html?function=' + quote(item['symbol']))}"
                          if item['symbol'] else ""))
        if not control["evidence"]:
            lines.append(f"- {t['none']}.")
        lines += ["", f"**{t['verify']}:** {recommendation}", ""]
    lines += [f"## {t['assets']}", "",
              "Path inventory only; the active loader and precedence are unverified." if lang == "en" else
              "Chỉ kiểm kê đường dẫn; loader và thứ tự ưu tiên đang chạy chưa được chứng minh.", ""]
    for block in model["blocks"]:
        if block["context_assets"]:
            lines += [f"### `{_md(block['id'])}`", ""]
            for asset in block["context_assets"]:
                lines.append(f"- {asset['role']}: {_md_link(asset['path'], _source_url(root, output, asset['path']))}")
            lines.append("")
    coverage_line = (f"- {c['documents_read']} bounded docs read; {len(c['documents_skipped'])} skipped; "
                     f"{len(c['parse_errors'])} Python parse errors; {c['non_python_files']} non-Python files have file-level coverage."
                     if lang == "en" else
                     f"- Đã đọc {c['documents_read']} tài liệu có giới hạn; bỏ qua {len(c['documents_skipped'])}; "
                     f"{len(c['parse_errors'])} lỗi parse Python; {c['non_python_files']} file ngoài Python chỉ được map ở mức file.")
    lines += [f"## {t['coverage']}", "", coverage_line]
    for limit in model["limits"]:
        lines.append(f"- {limit}")
    for error in c["parse_errors"]:
        lines.append(f"- Parse error: `{_md(error['file'])}:{error['line']}` — {_md(error['error'])}.")
    for path in c["documents_skipped"]:
        lines.append(f"- Skipped document: `{_md(path)}`.")
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def render_html(model, root, output, lang="en"):
    t = TEXT[lang]
    e = html.escape
    c = model["coverage"]
    head, changed = _git_state(root)
    def link_source(source):
        return _html_link(source, _source_url(root, output, source))

    def block_card(block):
        purpose = e(block["purpose"]["text"])
        source = link_source(block["purpose"]["source"]) if block["purpose"]["source"] else e(t["none"])
        leads = " · ".join(_html_link(fn, "source-explorer.html?function=" + quote(fn)) +
                           " <small>" + link_source(model["function_anchors"][fn]) + "</small>"
                           for fn in block["function_leads"][:4])
        edges = [edge for edge in model["edges"] if edge["from"] == block["id"]]
        edge_text = "".join(f'<li>→ {_html_link(edge["to"], "architecture.html?block=" + quote(edge["to"]))} '
                            f'<span>{e(edge["kind"])} · {edge["count"]}</span></li>'
                            for edge in sorted(edges, key=lambda item: (item["kind"].startswith("test"),
                                                                        -item["count"]))[:5])
        return (f'<article class="block"><div class="block-head"><h3>{e(block["label"])}</h3>'
                f'<code>{e(block["id"])}</code></div><p>{purpose}</p>'
                f'<p class="fine">{source} · {len(block["files"])} {e(t["files"])} · '
                f'{len(block["functions"])} {e(t["python_functions"])}</p>'
                f'<div class="leads">{leads}</div>'
                f'<ul class="edges">{edge_text}</ul></article>')

    def control_card(control):
        title, recommendation = _control_text(control, lang)
        status = VI_STATUS.get(control["status"], control["status"]) if lang == "vi" else control["status"]
        evidence = "".join(f'<li>{link_source(item["source"])} <span>· {e(item["kind"])}</span></li>'
                           for item in control["evidence"]) or f'<li>{e(t["none"])}</li>'
        return (f'<article class="control"><div class="control-head"><span class="badge">{e(control["id"])}</span>'
                f'<span class="fine">{e(control["group"])}</span></div><h3>{e(title)}</h3>'
                f'<p class="state">{e(status.replace("_", " "))} · {e(t["candidate"])}</p>'
                f'<ul>{evidence}</ul><p><strong>{e(t["verify"])}:</strong> {e(recommendation)}</p></article>')

    tasks = "".join(f'<li><a href="#{section}">{e(task)}</a></li>' for task, section in _tasks(model, t))
    journeys = []
    for journey in model["journeys"]:
        steps = "".join(f'<li><p>{e(step["text"])}</p><small>{link_source(step["source"])}</small><br>' +
                        (" · ".join(_html_link(fn, "source-explorer.html?function=" + quote(fn)) +
                                    " <small>" + link_source(model["function_anchors"][fn]) + "</small>"
                                    for fn in step["functions"]) or f'<span class="unknown">{e(t["unknown"])}</span>') +
                        '</li>' for step in journey["steps"])
        journeys.append(f'<article class="journey"><h3>{e(journey["title"])}</h3>'
                        f'<p class="fine">{link_source(journey["source"])}</p><ol>{steps}</ol></article>')
    assets = "".join(f'<li><span>{e(asset["role"])}</span> {link_source(asset["path"])}</li>'
                     for block in model["blocks"] for asset in block["context_assets"])
    errors = "".join(f'<li>{e(item["file"])}:{item["line"]} · {e(item["error"])}</li>'
                     for item in c["parse_errors"])
    purpose_source = link_source(model["overview"]["source"]) if model["overview"]["source"] else e(t["none"])
    body = f'''<header><div class="eyebrow">VIBE RESCUE · v0.8-preview</div>
<h1>{e(t["title"])}<br><em>{e(model["repo"])}</em></h1><p class="hero">{e(t["intro"])}</p>
<div class="header-links"><a href="REVIEW_WORKSHEET{'.vi' if lang == 'vi' else ''}.md">{e(t["worksheet"])} ↗</a><a href="architecture.html">Architecture Atlas ↗</a><a href="source-explorer.html">Source Explorer ↗</a><a href="HANDOFF{'.vi' if lang == 'vi' else ''}.md">{e(t["markdown"])} ↗</a></div>
</header><nav><a href="#overview">{e(t["snapshot"])}</a><a href="#blocks">{e(t["blocks"])}</a><a href="#journeys">{e(t["journeys"])}</a><a href="#controls">{e(t["controls"])}</a><a href="#coverage">{e(t["coverage"])}</a></nav>
<main><aside class="warning"><span>{e(t["review"])}</span><strong>{e(t["claim"])}</strong><p>{e(t["runtime"])}. {e(t["docs"])}.</p></aside>
<section id="overview"><div class="section-label">01 / {e(t["section_start"])}</div><h2>{e(t["snapshot"])}</h2>
<div class="metrics"><article><b>{len(model["blocks"])}</b><span>{e(t["blocks"])}</span></article><article><b>{len(model["edges"])}</b><span>{e(t["relations"])}</span></article><article><b>{len(model["journeys"])}</b><span>{e(t["journeys"])}</span></article><article class="amber"><b>{c["journey_steps_unbound"]}</b><span>{e(t["unknown"])}</span></article></div>
<div class="overview-grid"><article class="surface"><h3>{e(t["purpose"])}</h3><p>{e(model["overview"]["purpose"])}</p><small>{purpose_source}</small></article>
<article class="surface"><h3>{e(t["next"])}</h3><ol>{tasks}</ol></article></div>
<p class="fingerprint">Git HEAD {e(head[:12])} · {changed} {e(t["tracked"])} · {e(t["fingerprint"])} {e(model["fingerprint"][:12])} · {c["code_files"]} {e(t["code_files"])}</p></section>
<section id="blocks"><div class="section-label">02 / {e(t["section_map"])}</div><h2>{e(t["blocks"])}</h2><p>{e(t["docs"])}. {e(t["runtime"])}.</p><div class="cards">{''.join(block_card(block) for block in model["blocks"])}</div></section>
<section id="journeys"><div class="section-label">03 / {e(t["section_trace"])}</div><h2>{e(t["journeys"])}</h2><div class="journey-grid">{''.join(journeys) or e(t["no_journeys"])}</div></section>
<section id="controls"><div class="section-label">04 / {e(t["section_verify"])}</div><h2>{e(t["controls"])}</h2><p>{e(t["candidate"])}. {e(t["runtime"])}.</p><div class="cards controls">{''.join(control_card(item) for item in model["controls"]) or e(t["no_controls"])}</div></section>
<section id="coverage"><div class="section-label">05 / {e(t["section_limits"])}</div><h2>{e(t["coverage"])}</h2><div class="surface"><p>{c["documents_read"]} {e(t["docs_count"])} · {c["non_python_files"]} {e(t["non_python"])} · {len(c["parse_errors"])} {e(t["parse"])} · {len(c["documents_skipped"])} {e(t["skipped"])}.</p><ul>{''.join(f'<li>{e(limit)}</li>' for limit in model["limits"])}</ul><ul>{errors}</ul></div>
<h3>{e(t["assets"])}</h3><details class="surface"><summary>{c["context_assets"]} {e(t["paths_summary"])}</summary><ul>{assets}</ul></details></section></main>'''
    template = Path(__file__).with_name("handoff_template.html").read_text(encoding="utf-8")
    output.write_text(template.replace("__LANG__", lang).replace("__TITLE__", e(model["repo"], quote=True))
                      .replace("__HANDOFF_TITLE__", e(t["title"], quote=True))
                      .replace("__BODY__", body), encoding="utf-8")


def render(model, root, directory):
    """Write English and Vietnamese handoffs beside the Atlas; return paths."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for lang, suffix in (("en", ""), ("vi", ".vi")):
        md = directory / f"HANDOFF{suffix}.md"
        page = directory / f"handoff{suffix}.html"
        render_markdown(model, root, md, lang)
        render_html(model, root, page, lang)
        paths.extend((md, page))
        worksheet = directory / f"REVIEW_WORKSHEET{suffix}.md"
        if not worksheet.exists():
            if lang == "en":
                lines = ["<!-- markdownlint-disable MD013 -->", "", "# Review worksheet", "",
                         "Fill this in against one exact build and active configuration. Keep sensitive receipts in your controlled workspace; link only to redacted evidence here. Regenerating the Atlas preserves this file.",
                         "", "- Build / commit:", "- Active configuration:", "- Reviewer / date:",
                         "- Target journey and served trace:", "", "## Control decisions", "",
                         "| ID | Owner | Runtime / fault receipt | Result | Decision |",
                         "| --- | --- | --- | --- | --- |"]
            else:
                lines = ["<!-- markdownlint-disable MD013 -->", "", "# Phiếu review", "",
                         "Điền theo đúng một build và cấu hình đang chạy. Giữ receipt nhạy cảm trong workspace được kiểm soát; tại đây chỉ link bằng chứng đã che dữ liệu. Chạy lại Atlas sẽ giữ nguyên file này.",
                         "", "- Build / commit:", "- Cấu hình đang chạy:", "- Reviewer / ngày:",
                         "- Hành trình và trace được serve:", "", "## Quyết định theo control", "",
                         "| ID | Người phụ trách | Receipt runtime / fault | Kết quả | Quyết định |",
                         "| --- | --- | --- | --- | --- |"]
            for control in model["controls"]:
                title, _ = _control_text(control, lang)
                if lang == "en":
                    lines.append(f"| {control['id']} — {_md(title)} | Unassigned | Missing | Unknown | OPEN |")
                else:
                    lines.append(f"| {control['id']} — {_md(title)} | Chưa giao | Thiếu | Chưa rõ | MỞ |")
            if not model["controls"]:
                lines.append("| Select a profile | Unassigned | Missing | Unknown | OPEN |" if lang == "en" else
                             "| Chọn profile | Chưa giao | Thiếu | Chưa rõ | MỞ |")
            lines += (["", "## Handoff rule", "",
                       "Keep a control OPEN if its active path, failure path, or exact-build receipt is missing. A source lead or passing unit test alone is not a release decision.", ""]
                      if lang == "en" else
                      ["", "## Quy tắc bàn giao", "",
                       "Giữ control MỞ nếu thiếu đường chạy thật, đường lỗi hoặc receipt đúng build. Dấu vết source hay unit test xanh chưa đủ để quyết định phát hành.", ""])
            worksheet.write_text("\n".join(lines), encoding="utf-8")
        paths.append(worksheet)
    return paths

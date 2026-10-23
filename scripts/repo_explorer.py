#!/usr/bin/env python3
"""Build an offline, source-linked explorer of this harness without calling an LLM.

The index is deliberately static: resolved edges mean explicit Python references,
not observed runtime calls. Unknown calls stay visible. No target code is executed.
"""
import argparse
import ast
import hashlib
import html
import json
import os
import re
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("scripts", "tools/meta", "tests")
ASSETS = ("agents", "tools/rules", "tools/mcp", "tools/promptfoo", "targets")


def _attr(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _attr(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return None


def _source_files(root, directories=SOURCES):
    for directory in directories:
        for path in sorted((root / directory).rglob("*.py")):
            if path.is_file() and not path.is_symlink() and not {"__pycache__", ".ipynb_checkpoints"}.intersection(path.parts):
                yield path


def index(root=ROOT, sources=SOURCES, asset_dirs=ASSETS):
    """Inventory every Python definition and exact static calls in source and tests."""
    root = Path(root).resolve()
    files = list(_source_files(root, sources))
    records, modules, import_maps, constants, parse_errors = [], {}, {}, {}, []
    digest = hashlib.sha256()
    for path in files:
        rel = path.relative_to(root).as_posix()
        source = path.read_bytes()
        digest.update(rel.encode() + b"\0" + source + b"\0")
        module = rel[:-3].replace("/", ".")
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            parse_errors.append({"file": rel, "line": exc.lineno, "error": exc.msg})
            continue
        modules[module] = rel
        aliases = {}
        for item in tree.body:
            if isinstance(item, ast.Import):
                for alias in item.names:
                    aliases[alias.asname or alias.name.split(".")[0]] = (
                        alias.name if alias.asname else alias.name.split(".")[0])
            elif isinstance(item, ast.ImportFrom) and item.module:
                for alias in item.names:
                    aliases[alias.asname or alias.name] = f"{item.module}.{alias.name}"
        import_maps[module] = aliases
        constants[module] = sorted({name.id for item in tree.body
                                    if isinstance(item, (ast.Assign, ast.AnnAssign))
                                    for target in (item.targets if isinstance(item, ast.Assign)
                                                   else [item.target])
                                    for name in ast.walk(target)
                                    if isinstance(name, ast.Name)})

        def walk_body(body, prefix="", module=module, rel=rel):
            for item in body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qual = prefix + item.name
                    calls, locals_, fields, guards, raises = [], set(), set(), [], []
                    stack = list(item.body)
                    while stack:
                        node = stack.pop()
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                             ast.ClassDef, ast.Lambda)):
                            continue  # nested body belongs to another definition
                        if isinstance(node, ast.Call):
                            name = _attr(node.func)
                            if name:
                                calls.append({"name": name, "line": node.lineno})
                        if isinstance(node, (ast.If, ast.While, ast.Assert)):
                            guards.append({"line": node.lineno, "kind": type(node).__name__.lower(),
                                           "expression": ast.unparse(node.test)})
                        elif isinstance(node, ast.ExceptHandler):
                            guards.append({"line": node.lineno, "kind": "except",
                                           "expression": ast.unparse(node.type) if node.type else "*"})
                        elif isinstance(node, ast.Raise):
                            raises.append({"line": node.lineno,
                                           "expression": ast.unparse(node.exc) if node.exc else "raise"})
                        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                            locals_.add(node.id)
                        elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                              and node.value.id in {"c", "self", "state", "result"}):
                            fields.add(f"{node.value.id}.{node.attr}")
                        stack.extend(ast.iter_child_nodes(node))
                    args = [a.arg for a in item.args.posonlyargs + item.args.args +
                            item.args.kwonlyargs]
                    if item.args.vararg:
                        args.append("*" + item.args.vararg.arg)
                    if item.args.kwarg:
                        args.append("**" + item.args.kwarg.arg)
                    records.append({"id": f"{module}.{qual}", "name": qual,
                                    "module": module, "file": rel, "line": item.lineno,
                                    "end": item.end_lineno, "args": args,
                                    "locals": sorted(locals_ - set(args)),
                                    "fields": sorted(fields), "calls": calls,
                                    "guards": sorted(guards, key=lambda x: x["line"]),
                                    "raises": sorted(raises, key=lambda x: x["line"]),
                                    "doc": ast.get_docstring(item) or "",
                                    "kind": "async" if isinstance(item, ast.AsyncFunctionDef)
                                    else "function"})
                    walk_body(item.body, qual + ".")
                elif isinstance(item, ast.ClassDef):
                    walk_body(item.body, prefix + item.name + ".")
        walk_body(tree.body)
    ids = {item["id"] for item in records}
    for item in records:
        aliases = import_maps[item["module"]]
        resolved, unknown = [], []
        for call in item.pop("calls"):
            name = call["name"]
            head, _, tail = name.partition(".")
            candidates = [f"{item['module']}.{name}"]
            shadowed = head != "self" and head in (set(item["args"]) | set(item["locals"]))
            if head in aliases and not shadowed:
                candidates.insert(0, aliases[head] + ("." + tail if tail else ""))
            if name.startswith("self."):
                candidates.insert(0, item["id"].rsplit(".", 1)[0] + name[4:])
            hit = next((candidate for candidate in candidates if candidate in ids), None) if not shadowed else None
            entry = {"name": name, "line": call["line"]}
            if hit:
                entry["to"] = hit
                resolved.append(entry)
            else:
                unknown.append(entry)
        item["resolved"] = resolved
        item["unresolved"] = unknown
    callers = {item["id"]: [] for item in records}
    for item in records:
        for edge in item["resolved"]:
            callers[edge["to"]].append({"from": item["id"], "line": edge["line"]})
    for item in records:
        item["callers"] = sorted(callers[item["id"]], key=lambda e: (e["from"], e["line"]))
    assets = {}
    for directory in asset_dirs:
        assets[directory] = sorted(p.relative_to(root).as_posix() for p in (root / directory).rglob("*")
                                   if p.is_file() and not p.is_symlink()
                                   and ".ipynb_checkpoints" not in p.parts)
    config = {}
    for name in ("config.toml", "tools/manifest.toml", "targets/registry.toml", "pyproject.toml"):
        path = root / name
        if path.is_file():
            config[name] = sorted(tomllib.loads(path.read_text(encoding="utf-8")))
    return {"fingerprint": digest.hexdigest(), "files": len(files),
            "functions": sorted(records, key=lambda r: (r["file"], r["line"])),
            "modules": modules, "constants": constants, "assets": assets,
            "configs": config, "parse_errors": parse_errors,
            "claim": "Static syntax index of working tree; unresolved/dynamic calls are not runtime evidence."}


def _escape(value):
    return html.escape(str(value), quote=True)


def _source_link(source):
    path, _, _line = source.partition(":")
    return f'<a href="../../{_escape(path)}">{_escape(source)}</a>'


def flow_svg(flow, lang="vi"):
    """A legible, exportable two-lane SVG: call path and guard/failure rail."""
    steps = flow["steps"]
    height = 110 + len(steps) * 124
    parts = [(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1180 {height}" '
              'role="img">'),
             ('<defs><marker id="next" markerWidth="8" markerHeight="8" refX="7" '
              'refY="4" orient="auto" markerUnits="userSpaceOnUse">'
              '<path d="M0 0 L8 4 L0 8 Z" fill="#40c9a2"/></marker>'
              '<marker id="evidence" markerWidth="8" markerHeight="8" refX="7" '
              'refY="4" orient="auto" markerUnits="userSpaceOnUse">'
              '<path d="M0 0 L8 4 L0 8 Z" fill="#d58c49"/></marker></defs>'),
             ('<style>text{font-family:system-ui,sans-serif}'
             '.heading{font-size:24px;font-weight:750;fill:#f8fafc}'
             '.title{font-size:16px;font-weight:700;fill:#e2e8f0}'
             '.small{font-size:13px;fill:#b8c9df}.guard{font-size:13px;fill:#ffdfad}'
             '.label{font-size:14px;font-weight:700;fill:#93bff0;letter-spacing:.04em}'
             '.node{fill:#17233a;stroke:#4c6b91;stroke-width:1.5}'
             '.risk{fill:#2b2230;stroke:#d58c49;stroke-width:1.2}'
             '.line{stroke:#40c9a2;stroke-width:3;fill:none;marker-end:url(#next)}'
             '.cross{stroke:#d58c49;stroke-width:2;marker-end:url(#evidence)}</style>'),
             f'<rect width="1180" height="{height}" fill="#0b1220"/>',
             f'<text x="30" y="43" class="heading">{_escape(flow["title"])}</text>',
             (f'<text x="30" y="70" class="label">'
              f'{"SOURCE / CALL" if lang == "en" else "NGUỒN / LỜI GỌI"}</text>'),
             (f'<text x="683" y="70" class="label">'
              f'{"GUARD / FAILURE / OUTPUT" if lang == "en" else "CHẶN / LỖI / ĐẦU RA"}</text>')]
    for i, step in enumerate(steps):
        y = 87 + i * 124
        if i:
            parts.append(f'<path class="line" d="M 330 {y - 26} L 330 {y - 6}"/>')
        parts += [f'<rect class="node" x="28" y="{y}" width="612" height="100" rx="11"/>',
                  f'<text class="title" x="47" y="{y + 28}">{i + 1:02d}  {_escape(step["call"][:64])}</text>',
                  f'<text class="small" x="47" y="{y + 54}">{_escape(step["source"][:85])}</text>',
                  f'<text class="small" x="47" y="{y + 77}">{_escape(step.get("output", "")[:87])}</text>',
                  f'<path class="cross" d="M 640 {y + 50} L 663 {y + 50}"/>',
                  f'<rect class="risk" x="670" y="{y}" width="480" height="100" rx="11"/>',
                  f'<text class="guard" x="689" y="{y + 28}">{_escape(step.get("guard", "")[:61])}</text>',
                  f'<text class="small" x="689" y="{y + 55}">{_escape(step.get("failure", "")[:62])}</text>',
                  f'<text class="small" x="689" y="{y + 78}">{_escape(step.get("risk", "")[:62])}</text>']
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def render(index_data, flows, output, lang="vi"):
    labels = ("Guard", "Output", "Failure", "Risk") if lang == "en" else (
        "Điều kiện", "Đầu ra", "Khi lỗi", "Rủi ro")
    flow_nav, flow_sections = [], []
    for flow in flows:
        flow_nav.append(f'<a href="#{_escape(flow["id"])}">{_escape(flow["title"])}</a>')
        svg_name = f"repo-{flow['id']}{'.en' if lang == 'en' else ''}.svg"
        (output.parent / svg_name).write_text(flow_svg(flow, lang), encoding="utf-8")
        cards = []
        for n, step in enumerate(flow["steps"], 1):
            cards.append(f'<article class="step"><b>{n:02d} · {_escape(step["call"])}</b>'
                         f'<p>{_source_link(step["source"])} · {_escape(step.get("why", ""))}</p>'
                         f'<dl><dt>{labels[0]}</dt><dd>{_escape(step.get("guard", "—"))}</dd>'
                         f'<dt>{labels[1]}</dt><dd>{_escape(step.get("output", "—"))}</dd>'
                         f'<dt>{labels[2]}</dt><dd>{_escape(step.get("failure", "—"))}</dd>'
                         f'<dt>{labels[3]}</dt><dd>{_escape(step.get("risk", "—"))}</dd></dl></article>')
        flow_sections.append(f'<section id="{_escape(flow["id"])}"><div class="section-head">'
                             f'<h2>{_escape(flow["title"])}</h2><a download href="{svg_name}">SVG</a></div>'
                             f'<p>{_escape(flow["description"])}</p>'
                             f'<div class="diagram"><img src="{svg_name}" alt="{_escape(flow["title"])}"></div>'
                             f'<div class="steps">{"".join(cards)}</div></section>')
    payload = json.dumps(index_data, ensure_ascii=False).replace("<", "\\u003c")
    page = '''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Vibe Rescue Source Atlas: searchable Python function and call graph with source-linked workflows, configuration, prompts, scanner evidence, owner approvals, repair gates and risks.">
<title>Vibe Rescue Source Atlas · Codebase Map and Call Graph</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#0b1220;color:#e2e8f0;font:15px/1.5 system-ui,sans-serif}a{color:#67dfc1}a:hover{color:#fff}header{padding:40px clamp(20px,5vw,80px);background:linear-gradient(125deg,#113047,#17233a 60%,#392a31);border-bottom:1px solid #38546a}h1{font-size:clamp(34px,5vw,64px);line-height:1.06;margin:8px 0 16px;letter-spacing:-.04em}h2{font-size:29px;margin:0}.eyebrow{letter-spacing:.2em;color:#67dfc1;text-transform:uppercase;font-weight:750;font-size:12px}.lead{max-width:850px;color:#c5d4df;font-size:18px}.meta{display:flex;gap:16px;flex-wrap:wrap;color:#93adc3}nav{position:sticky;top:0;z-index:4;background:#0d1929ee;backdrop-filter:blur(10px);display:flex;gap:10px;overflow:auto;padding:12px clamp(20px,5vw,80px);border-bottom:1px solid #344e61}nav a{white-space:nowrap;text-decoration:none;border:1px solid #416477;padding:6px 12px;border-radius:50px;font-size:13px}main{max-width:1600px;margin:auto;padding:0 clamp(20px,5vw,80px) 90px}section{padding-top:52px;scroll-margin-top:65px}.section-head{display:flex;align-items:center;justify-content:space-between;gap:16px}.section-head a{border:1px solid #4f857f;border-radius:8px;padding:7px 12px;text-decoration:none}section>p{color:#aabfcb;max-width:940px}.diagram{overflow:auto;border:1px solid #355169;border-radius:14px;background:#0b1220;margin:20px 0}.diagram img{display:block;min-width:970px;width:100%}.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:12px}.step,.panel{background:#162338;border:1px solid #38516c;border-radius:12px;padding:18px}.step b{font-size:16px}.step p{color:#a7bbc9;margin:8px 0}.step dl{display:grid;grid-template-columns:57px 1fr;gap:5px 10px;margin:0}.step dt{color:#70ddbc;font-weight:700}.step dd{margin:0;color:#c6d4de}.toolbar{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}.toolbar input,.toolbar select{background:#0e1a2b;border:1px solid #547087;color:#eef6fa;border-radius:8px;padding:10px 12px;font:inherit}.toolbar input{flex:1;min-width:220px}.columns{display:grid;grid-template-columns:minmax(280px,36%) 1fr;gap:16px}.listing{max-height:700px;overflow:auto;border:1px solid #39546b;border-radius:12px}.listing button{width:100%;border:0;border-bottom:1px solid #30475d;background:#142238;color:#dce9f2;text-align:left;padding:10px 15px;cursor:pointer}.listing button:hover,.listing button.active{background:#22515a}.listing small{display:block;color:#8faebf}code{color:#8be9cf;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0e1a2b;padding:13px;border-radius:8px}ul{padding-left:21px}li{margin:4px 0}.caveat{border-left:3px solid #e5ae6c;padding:12px 16px;background:#282536}.asset-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}@media(max-width:750px){.columns{grid-template-columns:1fr}.listing{max-height:340px}}@media print{nav,.toolbar{display:none}body{background:white;color:#111}header,.step,.panel{color:#111;background:white}.diagram{page-break-inside:avoid}}
</style><header><div class="eyebrow">Vibe Rescue / Engineering map</div><h1>Source Atlas</h1><p class="lead">Từ entrypoint đến hàm, biến, prompt, scanner, evidence, owner gate và nhánh lỗi. Bản đồ hành vi được biên soạn từ source; chỉ mục hàm được trích xuất tĩnh, không chạy code target.</p><div class="meta"><span id="stats"></span><span id="fingerprint"></span><a href="../REPO_RUNTIME_ATLAS.md">Diễn giải, đánh giá và rủi ro</a><a href="../../LICENSE">MIT License</a></div></header>
<nav>__NAV__<a href="#functions">Toàn bộ hàm</a><a href="#assets">Config · prompts · tests</a></nav><main><aside class="caveat">Mũi tên trong SVG là luồng đọc source, không phải trace. `resolved` chỉ là tham chiếu Python tĩnh; `unresolved` gồm lệnh ngoài, callback, method động và call chưa phân giải. Xem Risk trong từng bước trước khi coi gate đã bảo vệ đủ.</aside>
__FLOWS__<section id="functions"><div class="section-head"><h2>Toàn bộ hàm Python</h2><span id="total"></span></div><p>Tìm bất kỳ hàm, file, call, biến hoặc tên field. Chọn một hàm để xem caller/callee, tham số, biến cục bộ, field và docstring. Source line là bằng chứng; không suy ra nhánh runtime từ graph.</p><div class="toolbar"><input id="find" placeholder="Tìm hàm, file, biến, call..."><select id="module"><option value="">Mọi module</option></select><select id="group"><option value="">Source + tests</option><option value="source">Runtime</option><option value="tests">Tests</option></select></div><div class="columns"><div id="listing" class="listing"></div><div id="detail" class="panel">Chọn hàm bên trái.</div></div></section>
<section id="assets"><h2>Config · prompts · rules · tests</h2><p>Inventory này lấy từ working tree khi sinh atlas. Mở file để kiểm chính xác nội dung và quyền thực thi; sự tồn tại của file không có nghĩa runtime đã gọi nó.</p><div id="asset-grid" class="asset-grid"></div></section></main>
<script type="application/json" id="data">__DATA__</script><script>
const data=JSON.parse(document.getElementById('data').textContent), fns=data.functions;
const el=(tag,txt)=>{const n=document.createElement(tag);n.textContent=txt;return n};
const link=(path,label)=>{const a=el('a',label||path);a.href='../../'+path.split(':')[0];return a};
document.getElementById('stats').textContent=`${data.files} Python files · ${fns.length} definitions`;
document.getElementById('fingerprint').textContent=`source SHA-256 ${data.fingerprint.slice(0,12)}`;
document.getElementById('total').textContent=fns.length+' indexed';
const mods=[...new Set(fns.map(x=>x.module))].sort();for(const m of mods){const o=el('option',m);o.value=m;document.getElementById('module').append(o)}
function show(x){const d=document.getElementById('detail');d.replaceChildren();d.append(el('h2',x.name));d.append(link(x.file+':'+x.line,x.file+':'+x.line+'–'+x.end));d.append(el('p','ID: '+x.id+' · '+x.kind));
 for(const [title,items] of [['Parameters',x.args],['Local variables',x.locals],['State fields',x.fields],['Calls resolved',x.resolved.map(c=>c.name+' → '+c.to+' @'+c.line)],['Calls unresolved',x.unresolved.map(c=>c.name+' @'+c.line)],['Called by',x.callers.map(c=>c.from+' @'+c.line)]]){d.append(el('h3',title+' ('+items.length+')'));const p=el('pre',items.length?items.join('\\n'):'—');d.append(p)}if(x.doc){d.append(el('h3','Docstring'));d.append(el('pre',x.doc))}}
function refresh(){const q=document.getElementById('find').value.toLowerCase().trim(),m=document.getElementById('module').value,g=document.getElementById('group').value,box=document.getElementById('listing');box.replaceChildren();let count=0;
 for(const x of fns){if(m&&x.module!==m)continue;if(g==='tests'&&!x.file.startsWith('tests/'))continue;if(g==='source'&&x.file.startsWith('tests/'))continue;const hay=[x.id,x.file,...x.args,...x.locals,...x.fields,...x.resolved.map(c=>c.name),...x.unresolved.map(c=>c.name)].join(' ').toLowerCase();if(q&&!hay.includes(q))continue;count++;const b=document.createElement('button');b.append(el('span',x.name),el('small',x.file+':'+x.line));b.onclick=()=>{box.querySelector('.active')?.classList.remove('active');b.classList.add('active');show(x)};box.append(b)}document.getElementById('total').textContent=count+'/'+fns.length+' shown'}
for(const id of ['find','module','group'])document.getElementById(id).addEventListener(id==='find'?'input':'change',refresh);refresh();
const grid=document.getElementById('asset-grid');for(const [name,files] of Object.entries(data.assets)){const box=el('div','');box.className='panel';box.append(el('h3',name+' ('+files.length+')'));const ul=el('ul','');for(const file of files){const li=el('li','');li.append(link(file));ul.append(li)}box.append(ul);grid.append(box)}for(const [name,sections] of Object.entries(data.configs)){const box=el('div','');box.className='panel';box.append(el('h3',name));box.append(link(name));box.append(el('p','Top-level TOML sections: '+sections.join(', ')));grid.append(box)}for(const [name,fields] of Object.entries(data.constants)){if(!fields.length)continue;const box=el('div','');box.className='panel';box.append(el('h3',name));box.append(el('pre','Module variables: '+fields.join(', ')));grid.append(box)}if(data.parse_errors.length){const box=el('div','');box.className='panel';box.append(el('h3','Parse errors'));for(const issue of data.parse_errors)box.append(el('p',issue.file+':'+issue.line+' '+issue.error));grid.prepend(box)}
</script></html>'''
    # Translate only the static shell. Journey text comes from the locale's JSON,
    # so a translation cannot accidentally change a source anchor or identifier.
    en_ui = {
        'lang="vi"': 'lang="en"',
        'Từ entrypoint đến hàm, biến, prompt, scanner, evidence, owner gate và nhánh lỗi. Bản đồ hành vi được biên soạn từ source; chỉ mục hàm được trích xuất tĩnh, không chạy code target.':
            'From entry points to functions, variables, prompts, scanners, evidence, owner approvals and failure paths. Workflows are traced from source; the function index is static and does not execute target code.',
        'Diễn giải, đánh giá và rủi ro': 'Walkthrough, assessment and risks (Vietnamese)',
        '<a href="#functions">Toàn bộ hàm</a>': '<a href="#functions">All functions</a>',
        'Mũi tên trong SVG là luồng đọc source, không phải trace. `resolved` chỉ là tham chiếu Python tĩnh; `unresolved` gồm lệnh ngoài, callback, method động và call chưa phân giải. Xem Risk trong từng bước trước khi coi gate đã bảo vệ đủ.':
            'SVG arrows show a source-reading path, not a runtime trace. `resolved` means a static Python reference; `unresolved` includes external commands, callbacks, dynamic methods and unlinked calls. Read each risk before relying on a gate.',
        '<h2>Toàn bộ hàm Python</h2>': '<h2>All Python functions</h2>',
        'Tìm bất kỳ hàm, file, call, biến hoặc tên field. Chọn một hàm để xem caller/callee, tham số, biến cục bộ, field và docstring. Source line là bằng chứng; không suy ra nhánh runtime từ graph.':
            'Search functions, files, calls, variables and fields. Select a function to inspect callers, callees, parameters, local variables, fields and its docstring. Source lines are evidence; the graph does not establish runtime branches.',
        'Tìm hàm, file, biến, call...': 'Search functions, files, variables, calls...',
        'Mọi module': 'All modules',
        'Chọn hàm bên trái.': 'Select a function on the left.',
        'Inventory này lấy từ working tree khi sinh atlas. Mở file để kiểm chính xác nội dung và quyền thực thi; sự tồn tại của file không có nghĩa runtime đã gọi nó.':
            'This inventory comes from the working tree at generation time. Open each file to inspect its contents and execution permissions; its presence does not prove runtime use.',
    }
    vi_ui = {
        '<title>Vibe Rescue Source Atlas · Codebase Map and Call Graph</title>':
            '<title>Vibe Rescue · Bản đồ mã nguồn và lời gọi</title>',
        'Vibe Rescue / Engineering map': 'Vibe Rescue / Bản đồ kỹ thuật',
        '<h1>Source Atlas</h1>': '<h1>Bản đồ mã nguồn</h1>',
        'Từ entrypoint đến hàm, biến, prompt, scanner, evidence, owner gate và nhánh lỗi. Bản đồ hành vi được biên soạn từ source; chỉ mục hàm được trích xuất tĩnh, không chạy code target.':
            'Từ điểm vào đến hàm, biến, chỉ dẫn agent, bộ quét, bằng chứng, phê duyệt của chủ sở hữu và nhánh lỗi. Sơ đồ được biên soạn từ mã nguồn; chỉ mục hàm là phân tích tĩnh, không chạy mã của repo đích.',
        'Mũi tên trong SVG là luồng đọc source, không phải trace. `resolved` chỉ là tham chiếu Python tĩnh; `unresolved` gồm lệnh ngoài, callback, method động và call chưa phân giải. Xem Risk trong từng bước trước khi coi gate đã bảo vệ đủ.':
            'Mũi tên trong SVG biểu diễn luồng đọc mã nguồn, không phải vết thực thi. `resolved` là tham chiếu Python tĩnh; `unresolved` gồm lệnh ngoài, hàm gọi lại, phương thức động và lời gọi chưa phân giải. Xem rủi ro từng bước trước khi tin rằng gate đã bảo vệ đủ.',
        'MIT License': 'Giấy phép MIT',
        'Python files ·': 'tệp Python ·',
        'definitions`': 'định nghĩa`',
        "+' indexed'": "+' đã lập chỉ mục'",
        "+' shown'": "+' hiển thị'",
        "['Parameters',": "['Tham số',",
        "['Local variables',": "['Biến cục bộ',",
        "['State fields',": "['Trường trạng thái',",
        "['Calls resolved',": "['Lời gọi xác định',",
        "['Calls unresolved',": "['Lời gọi chưa xác định',",
        "['Called by',": "['Được gọi bởi',",
        "'Docstring'": "'Chú thích hàm'",
        "'Top-level TOML sections: '": "'Mục TOML cấp cao: '",
        "'Module variables: '": "'Biến cấp module: '",
        "'Parse errors'": "'Lỗi phân tích cú pháp'",
    }
    for source, translation in (en_ui if lang == "en" else vi_ui).items():
        if source not in page:
            raise ValueError(f"missing {lang} UI text to translate: {source!r}")
        page = page.replace(source, translation)
    page = page.replace("__NAV__", "".join(flow_nav)).replace("__FLOWS__", "".join(flow_sections))
    page = page.replace("__DATA__", payload)
    output.write_text(page, encoding="utf-8")


def render_generic(data, root, output):
    """Offline, searchable source ledger for an arbitrary Python repository."""
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    prefix = os.path.relpath(root, output.parent).replace("\\", "/").rstrip("/") + "/"
    title = html.escape(root.name)
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Source Explorer · __TITLE__</title>
<style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#e7f0f6;font:15px/1.5 system-ui}
header{padding:25px 4vw;background:#15263a;border-bottom:1px solid #38516a}h1{margin:0 0 8px}p{color:#b6c9d7}
main{padding:22px 4vw;max-width:1800px;margin:auto}input{width:100%;padding:12px;background:#13243a;color:#fff;border:1px solid #507089;border-radius:8px}
.layout{display:grid;grid-template-columns:minmax(280px,34%) 1fr;gap:18px;margin-top:18px}.list{max-height:76vh;overflow:auto;border:1px solid #35506b;border-radius:10px}
.list button{display:block;width:100%;border:0;border-bottom:1px solid #30465b;background:#142237;color:#e7f0f6;text-align:left;padding:10px;cursor:pointer}
.list button:hover{background:#214657}.list small{display:block;color:#a7bfce}.detail{border:1px solid #35506b;border-radius:10px;padding:20px;overflow:auto}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#101d2e;padding:12px;border-radius:7px}a{color:#76e3c4}code{color:#9bead6}
.map{overflow:auto;border:1px solid #35506b;border-radius:10px;margin:14px 0;background:#0b1220}.map svg{display:block;min-width:1000px;width:100%}
.save{border:1px solid #509781;border-radius:7px;background:#173d40;color:#e7f0f6;padding:8px 12px;cursor:pointer}
@media(max-width:800px){.layout{grid-template-columns:1fr}.list{max-height:34vh}}</style>
<header><h1>Source Explorer · __TITLE__</h1><p id="stats"></p><p>Static Python syntax only. Guards and raises are syntactic locations, not proof of runtime behavior. Dynamic calls remain unresolved.</p></header>
<main><input id="search" placeholder="Search function, path, parameter, variable, field or call"><p id="count"></p>
<p id="map-note">Select a function for its static caller → function → callee SVG. All references remain in the detail panel.</p>
<button id="save-svg" class="save" hidden>Download selected SVG</button><div id="ego" class="map"></div>
<div class="layout"><div id="list" class="list"></div><div id="detail" class="detail">Select a function.</div></div></main>
<script type="application/json" id="data">__DATA__</script><script>
const data=JSON.parse(document.getElementById('data').textContent), fns=data.functions, prefix=__PREFIX__;
const el=(tag,value)=>{const node=document.createElement(tag);node.textContent=value;return node};
document.getElementById('stats').textContent=`${data.files} Python files · ${fns.length} definitions · ${data.parse_errors.length} parse errors · source SHA-256 ${data.fingerprint.slice(0,12)}`;
const byId=new Map(fns.map(x=>[x.id,x])), searchText=fns.map(x=>[x.id,x.file,...x.args,...x.locals,...x.fields,
 ...x.resolved.map(c=>c.name),...x.unresolved.map(c=>c.name)].join(' ').toLowerCase());
const svgNS='http://www.w3.org/2000/svg';let selectedSvg=null;
function svgEl(tag,attrs={},value){const n=document.createElementNS(svgNS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));
 if(value!==undefined)n.textContent=value;return n}
function renderEgo(x){const callers=[...new Set(x.callers.map(c=>c.from))],callees=[...new Set(x.resolved.map(c=>c.to))];
 const left=callers.slice(0,12),right=callees.slice(0,12),rows=Math.max(left.length,right.length,1),height=Math.max(330,80+rows*62);
 const svg=svgEl('svg',{viewBox:`0 0 1200 ${height}`,role:'img','aria-label':'Static caller to function to callee map'});
 svg.append(svgEl('rect',{width:1200,height,fill:'#0b1220'}));const defs=svgEl('defs'),marker=svgEl('marker',{id:'arrow',viewBox:'0 0 10 10',refX:9,refY:5,
 markerWidth:7,markerHeight:7,orient:'auto-start-reverse'});marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#67dfc1'}));defs.append(marker);svg.append(defs);
 svg.append(svgEl('text',{x:25,y:33,fill:'#b9d2e2','font-size':18},`CALLERS ${left.length}/${callers.length}`));
 svg.append(svgEl('text',{x:445,y:33,fill:'#b9d2e2','font-size':18},'SELECTED FUNCTION'));
 svg.append(svgEl('text',{x:825,y:33,fill:'#b9d2e2','font-size':18},`CALLEES ${right.length}/${callees.length}`));
 const box=(item,bx,by,width,active=false)=>{const group=svgEl('g');group.append(svgEl('rect',{x:bx,y:by,width,height:52,rx:8,
 fill:active?'#173e4a':'#192b43',stroke:active?'#67dfc1':'#557495','stroke-width':1.4}));
 group.append(svgEl('text',{x:bx+12,y:by+22,fill:'#f0f6fa','font-size':15,'font-weight':700},item.name.slice(0,43)));
 group.append(svgEl('text',{x:bx+12,y:by+41,fill:'#b3c8d8','font-size':12},`${item.file}:${item.line}`.slice(0,51)));svg.append(group)};
 const mid=height/2-26;box(x,415,mid,370,true);
 for(const [i,id] of left.entries()){const y=59+i*62,item=byId.get(id);if(!item)continue;box(item,20,y,365);
 svg.append(svgEl('path',{d:`M 385 ${y+26} L 415 ${mid+26}`,stroke:'#67dfc1','stroke-width':1.7,fill:'none','marker-end':'url(#arrow)'}))}
 for(const [i,id] of right.entries()){const y=59+i*62,item=byId.get(id);if(!item)continue;box(item,815,y,365);
 svg.append(svgEl('path',{d:`M 785 ${mid+26} L 815 ${y+26}`,stroke:'#67dfc1','stroke-width':1.7,fill:'none','marker-end':'url(#arrow)'}))}
 const note=`Static references · ${x.guards.length} guards · ${x.raises.length} raises · ${x.unresolved.length} unresolved calls`;
 svg.append(svgEl('text',{x:415,y:height-18,fill:'#e4b87e','font-size':13},note));
 const target=document.getElementById('ego');target.replaceChildren(svg);selectedSvg=svg;document.getElementById('save-svg').hidden=false;
 document.getElementById('map-note').textContent=`${x.id}: ${note}. Diagram shows at most 12 on each side; the detail panel lists all references.`}
document.getElementById('save-svg').onclick=()=>{if(!selectedSvg)return;const raw=new XMLSerializer().serializeToString(selectedSvg);
 const url=URL.createObjectURL(new Blob([raw],{type:'image/svg+xml'})),a=document.createElement('a');a.href=url;a.download='source-function-map.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
const detail=document.getElementById('detail');
function show(x){detail.replaceChildren();detail.append(el('h2',x.name));const a=el('a',x.file+':'+x.line);a.href=prefix+x.file;detail.append(a);
detail.append(el('p',`Lines ${x.line}–${x.end} · ${x.kind}`));
for(const [title,items] of [['Parameters',x.args],['Local variables',x.locals],['State fields',x.fields],
['Guards',x.guards.map(g=>g.line+' '+g.kind+' '+g.expression)],['Raises',x.raises.map(r=>r.line+' '+r.expression)],
['Calls resolved',x.resolved.map(c=>c.line+' '+c.name+' → '+c.to)],['Calls unresolved',x.unresolved.map(c=>c.line+' '+c.name)],
['Called by',x.callers.map(c=>c.from+' @'+c.line)]]){detail.append(el('h3',title+' ('+items.length+')'));detail.append(el('pre',items.length?items.join('\\n'):'—'))}
if(x.doc){detail.append(el('h3','Docstring'));detail.append(el('pre',x.doc))}renderEgo(x)}
const list=document.getElementById('list');function refresh(){const q=document.getElementById('search').value.toLowerCase().trim();list.replaceChildren();let hits=0;
for(let i=0;i<fns.length;i++){const x=fns[i];if(q&&!searchText[i].includes(q))continue;hits++;if(hits>200)continue;const b=el('button',x.name);b.append(el('small',x.file+':'+x.line));b.onclick=()=>show(x);list.append(b)}
document.getElementById('count').textContent=`${hits} matches · showing first ${Math.min(hits,200)}; narrow the search for more`}
document.getElementById('search').addEventListener('input',refresh);refresh();
const requested=new URLSearchParams(location.search).get('function');if(requested&&byId.has(requested)){
 document.getElementById('search').value=requested;refresh();show(byId.get(requested))}</script></html>'''
    output.write_text(page.replace("__TITLE__", title).replace("__DATA__", payload)
                      .replace("__PREFIX__", json.dumps(prefix)), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build offline source atlas for vibe_rescue")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--lang", choices=("en", "vi"), default="vi")
    parser.add_argument("--journeys", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", action="store_true", help="fail when committed atlas is stale")
    parser.add_argument("--generic", action="store_true", help="index an arbitrary Python target")
    parser.add_argument("--sources", nargs="+", help="source directories relative to --root (generic mode)")
    args = parser.parse_args(argv)
    if args.generic:
        if args.check:
            parser.error("--check is only available for the curated Vibe Rescue atlas")
        if not args.sources:
            parser.error("--generic requires --sources; choose approved source directories")
        root = args.root.resolve()
        sources = args.sources
        if any(not (root / source).resolve().is_relative_to(root) for source in sources):
            parser.error("--sources must stay inside --root")
        if any(not (root / source).is_dir() for source in sources):
            parser.error("every --sources entry must be an existing directory")
        output = args.out or ROOT / "reports" / "source-explorer.html"
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        data = index(root, sources=sources, asset_dirs=())
        output.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False),
                                               encoding="utf-8")
        render_generic(data, root, output)
        print(f"[EXPLORER] {data['files']} Python files, {len(data['functions'])} definitions "
              f"→ {output}")
        return 2 if data["parse_errors"] else 0
    args.journeys = args.journeys or ROOT / ("docs/repo_journeys.en.json" if args.lang == "en"
                                            else "docs/repo_journeys.json")
    args.out = args.out or ROOT / ("docs/assets/repo-explorer.en.html" if args.lang == "en"
                                  else "docs/assets/repo-explorer.html")
    data = index(args.root)
    flows = json.loads(args.journeys.read_text(encoding="utf-8"))
    ids = [flow["id"] for flow in flows]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"[a-z0-9_-]+", value) for value in ids):
        raise ValueError("journey id must be unique and filesystem-safe")
    for flow in flows:
        for step in flow["steps"]:
            path, _, line = step["source"].partition(":")
            source_file = args.root / path
            if (not line.isdigit() or not source_file.is_file() or source_file.is_symlink()
                    or not source_file.resolve().is_relative_to(args.root.resolve())):
                raise ValueError(f"invalid source anchor: {step['source']}")
            source_lines = source_file.read_text(encoding="utf-8").splitlines()
            if not 1 <= int(line) <= len(source_lines) or not source_lines[int(line) - 1].strip():
                raise ValueError(f"invalid source anchor: {step['source']}")
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp) / args.out.name
            render(data, flows, expected, args.lang)
            for generated in expected.parent.iterdir():
                actual = args.out.parent / generated.name
                if not actual.is_file() or actual.read_bytes() != generated.read_bytes():
                    print(f"[ATLAS] stale: {actual}; rerun scripts/repo_explorer.py")
                    return 2
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        render(data, flows, args.out, args.lang)
    print(f"[ATLAS] {data['files']} Python files, {len(data['functions'])} definitions, "
          f"{len(flows)} journeys → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

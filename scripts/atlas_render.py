"""Offline HTML/SVG/PDF views of evidence-labelled static code graphs."""
import html
import json
import math
import shutil
import subprocess
from pathlib import Path

MAX_NODES = 120


def _esc(value):
    return html.escape(str(value), quote=True)


def svg_for_graph(graph, title, page_nodes=None):
    nodes = graph.get("nodes", [])[:MAX_NODES] if page_nodes is None else page_nodes
    ids = {n["id"] for n in nodes}
    edges = [e for e in graph.get("edges", []) if e["source"] in ids and e["target"] in ids]
    columns, card_w, card_h, x_gap, y_gap = 3, 360, 84, 36, 38
    rows = math.ceil(len(nodes) / columns)
    width = 40 + columns * (card_w + x_gap)
    height = max(280, 140 + rows * (card_h + y_gap))
    positions = {n["id"]: (40 + (i % columns) * (card_w + x_gap),
                            100 + (i // columns) * (card_h + y_gap))
                 for i, n in enumerate(nodes)}
    parts = [(f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
              f'aria-label="{_esc(title)}" viewBox="0 0 {width} {height}" '
              f'width="{width}" height="{height}">'),
             ('<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
              'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
              '<path d="M 0 0 L 10 5 L 0 10 z" fill="#667a98"/></marker></defs>'),
             '<rect width="100%" height="100%" fill="#f5f7fb"/>',
             f'<text x="40" y="50" class="title">{_esc(title)}</text>']
    for edge in edges:
        x1, y1 = positions[edge["source"]]
        x2, y2 = positions[edge["target"]]
        sx, sy = x1 + card_w / 2, y1 + card_h
        tx, ty = x2 + card_w / 2, y2
        if ty <= sy:
            sx, sy, tx, ty = x1 + card_w, y1 + card_h / 2, x2, y2 + card_h / 2
        mid = (sy + ty) / 2
        parts.append(f'<path d="M {sx:.0f} {sy:.0f} C {sx:.0f} {mid:.0f}, '
                     f'{tx:.0f} {mid:.0f}, {tx:.0f} {ty:.0f}" class="edge" '
                     f'marker-end="url(#arrow)"><title>{_esc(edge.get("kind", "static edge"))}'
                     f' · {_esc(edge.get("file", ""))}:{_esc(edge.get("line", "?"))}'
                     '</title></path>')
    for node in nodes:
        x, y = positions[node["id"]]
        label = str(node.get("label", node["id"]))
        source = f'{node.get("file", "unknown")}:{node.get("line", "?")}'
        parts.append(f'<g class="node" data-label="{_esc(label.lower())}" '
                     f'data-source="{_esc(source.lower())}"><title>{_esc(label)} · '
                     f'{_esc(source)}</title><rect x="{x}" y="{y}" width="{card_w}" '
                     f'height="{card_h}" rx="12"/><text x="{x + 18}" y="{y + 34}" '
                     f'class="label">{_esc(label[:42])}</text><text x="{x + 18}" '
                     f'y="{y + 62}" class="source">{_esc(source[:52])}</text></g>')
    parts.append('<style>.title{font:700 25px system-ui;fill:#16253f}.node rect{fill:#fff;'
                 'stroke:#bccbde;stroke-width:1.5}.label{font:600 17px system-ui;fill:#14253f}'
                 '.source{font:13px ui-monospace,monospace;fill:#4b627f}.edge{fill:none;'
                 'stroke:#667a98;stroke-width:1.5;opacity:.66}.node.dim{opacity:.15}'
                 '@media print{.edge{stroke:#54657f}}</style></svg>')
    return "\n".join(parts), len(nodes), len(edges)


def _catalog(graph):
    """Complete searchable symbol/edge ledger, including nodes omitted from SVG."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    unknown = graph.get("unknown", [])
    by_id = {str(node.get("id")): node for node in nodes}
    incoming, outgoing = {}, {}
    for edge in edges:
        outgoing.setdefault(str(edge.get("source")), []).append(edge)
        incoming.setdefault(str(edge.get("target")), []).append(edge)

    def edge_items(items, other):
        if not items:
            return "<li>Không có cạnh tĩnh đã phân giải.</li>"
        parts = []
        for edge in items:
            symbol_id = str(edge.get(other, ""))
            symbol = by_id.get(symbol_id, {})
            label = symbol.get("label") or symbol_id
            evidence = f"{edge.get('file', '')}:{edge.get('line', '?')}"
            parts.append(f"<li><code>{_esc(label)}</code> · {_esc(edge.get('kind', 'static'))} "
                         f"· {_esc(evidence)}</li>")
        return "".join(parts)

    cards = []
    for node in nodes:
        symbol_id = str(node.get("id", ""))
        label = str(node.get("label", symbol_id))
        source = f"{node.get('file', 'unknown')}:{node.get('line', '?')}"
        search = f"{label} {source} {symbol_id}".lower()
        cards.append(f'<details class="symbol" data-search="{_esc(search)}">'
                     f'<summary><b>{_esc(label)}</b><small>{_esc(source)} · '
                     f'{_esc(node.get("kind", "symbol"))}</small></summary>'
                     f'<div class="edge-lists"><div><strong>Calls / imports → '
                     f'{len(outgoing.get(symbol_id, []))}</strong><ul>'
                     f'{edge_items(outgoing.get(symbol_id, []), "target")}</ul></div>'
                     f'<div><strong>Called / imported by ← '
                     f'{len(incoming.get(symbol_id, []))}</strong><ul>'
                     f'{edge_items(incoming.get(symbol_id, []), "source")}</ul></div></div>'
                     '</details>')
    unknown_items = [f'<li><code>{_esc(item.get("file", "unknown"))}:'
                     f'{_esc(item.get("line", "?"))}</code> · '
                     f'{_esc(item.get("call", item.get("import", "unknown")))} · '
                     f'{_esc(item.get("reason", "unresolved"))}</li>' for item in unknown]
    return (f'<section id="catalog" class="catalog"><h2>Full source catalog · {len(nodes)} symbols '
            f'· {len(edges)} static edges</h2><p>SVG được chia trang tối đa {MAX_NODES} node. '
            'Danh mục dưới đây giữ toàn bộ node/cạnh parser trả về; unknown vẫn ở cuối.</p>'
            '<input id="catalog-find" aria-label="Tìm toàn bộ symbol" '
            'placeholder="Tìm tên hàm, file hoặc ID...">'
            f'<div class="symbols">{"".join(cards)}</div>'
            f'<details class="unknown"><summary>Unknown / unresolved ({len(unknown)})</summary>'
            f'<ul>{"".join(unknown_items) or "<li>Không có unknown được parser báo.</li>"}</ul>'
            '</details></section>')


def write_graph(graph, title, outdir: Path, stem: str, pdf=False):
    outdir.mkdir(parents=True, exist_ok=True)
    nodes = graph.get("nodes", [])
    svg, shown_nodes, shown_edges = svg_for_graph(graph, title)
    svg_path = outdir / f"{stem}.svg"
    html_path = outdir / f"{stem}.html"
    svg_path.write_text(svg, encoding="utf-8")
    incomplete = len(nodes) > shown_nodes
    pages = [svg_path.name]
    visual_edges = shown_edges
    if incomplete:
        for start in range(MAX_NODES, len(nodes), MAX_NODES):
            page = outdir / f"{stem}-page-{start // MAX_NODES + 1:03d}.svg"
            page_svg, _, page_edges = svg_for_graph(
                graph, f"{title} · page {start // MAX_NODES + 1}",
                nodes[start:start + MAX_NODES])
            page.write_text(page_svg, encoding="utf-8")
            pages.append(page.name)
            visual_edges += page_edges
    page_links = "".join(
        f'<a href="{_esc(name)}">{idx + 1}: '
        f'{idx * MAX_NODES + 1}–{min((idx + 1) * MAX_NODES, len(nodes))}</a>'
        for idx, name in enumerate(pages))
    note = (f"SVG: {len(pages)} page(s), {len(nodes)}/{len(nodes)} symbol; "
            f"{visual_edges}/{len(graph.get('edges', []))} cạnh cùng trang. "
            f"Cạnh giữa các trang nằm trong catalog HTML; unknown: {len(graph.get('unknown', []))}. "
            "Mũi tên chỉ là bằng chứng phân tích tĩnh; cần test/trace để xác nhận runtime.")
    catalog = _catalog(graph)
    canvas = (f'<details class="diagram"><summary>Mở SVG preview ({shown_nodes} node)</summary>'
              f'<div class="canvas">{svg}</div></details>') if incomplete else f'<div class="canvas">{svg}</div>'
    page = f"""<!doctype html><html lang="vi"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title><style>
body{{margin:0;font:16px system-ui;background:#0b1220;color:#e2e8f0}}
header{{padding:20px 28px;background:linear-gradient(120deg,#123048,#17233a);color:white;display:flex;gap:20px;align-items:center;flex-wrap:wrap}}
header a{{color:#7de1c4}}
h1{{font-size:24px;margin:0}} button,input{{font:inherit;padding:8px 12px;border-radius:8px;border:1px solid #92a5bf}}
button{{cursor:pointer}} main{{padding:20px;max-width:1500px;margin:auto}} .notice{{background:#282536;border-left:3px solid #e5ae6c;padding:12px 16px;border-radius:8px}}
.canvas{{overflow:auto;max-height:620px;background:white;border-radius:12px;margin-top:16px}} .canvas svg{{max-width:none}}
.diagram{{margin-top:16px}}.diagram summary{{cursor:pointer;color:#7de1c4;font-weight:700}}
.pages{{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}} .pages a{{color:#7de1c4;padding:5px 8px;background:#17253c;border-radius:6px}}
.catalog{{margin-top:36px}}.catalog h2{{font-size:27px}}.catalog p{{color:#a9bdcd}}
#catalog-find{{width:min(100%,620px);background:#13243a;color:#e2e8f0;border-color:#4d6a82}}
.symbols{{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:9px;margin-top:16px}}
.symbol,.unknown{{background:#17253c;border:1px solid #3a5571;border-radius:9px;padding:10px 14px}}
.symbol summary,.unknown summary{{cursor:pointer}}.symbol small{{display:block;color:#92aec4}}
.symbol b{{color:#7de1c4}}.edge-lists{{display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:13px}}
.edge-lists ul,.unknown ul{{padding-left:18px;overflow-wrap:anywhere}}code{{color:#a8e9d7}}
.unknown{{margin-top:16px}}.symbol[hidden]{{display:none}}
@media print{{header button,header input{{display:none}} body{{background:white}} main{{padding:0}} .canvas{{overflow:visible;max-height:none}}}}
</style><header><h1>{_esc(title)}</h1><input id="find" aria-label="Tìm symbol hoặc file" placeholder="Tìm symbol/file">
<button id="save">Tải SVG</button><a href="#catalog">Danh mục đầy đủ</a>
<button onclick="window.print()">In / lưu PDF</button></header>
<main><p class="notice">{_esc(note)}</p><nav class="pages" aria-label="SVG pages">{page_links}</nav>{canvas}{catalog}</main>
<script>const input=document.getElementById('find');input.addEventListener('input',()=>{{
let q=input.value.toLowerCase().trim();for(let n of document.querySelectorAll('.node')){{
n.classList.toggle('dim',!!q&&!((n.dataset.label||'').includes(q)||(n.dataset.source||'').includes(q)));}}}});
document.getElementById('catalog-find').addEventListener('input',e=>{{
let q=e.target.value.toLowerCase().trim();for(let n of document.querySelectorAll('.symbol')){{
n.hidden=!!q&&!n.dataset.search.includes(q);}}}});
document.getElementById('save').addEventListener('click',()=>{{let s=document.querySelector('svg');
let b=new Blob([new XMLSerializer().serializeToString(s)],{{type:'image/svg+xml'}});
let a=document.createElement('a');a.href=URL.createObjectURL(b);a.download={json.dumps(stem + '.svg')};a.click();
setTimeout(()=>URL.revokeObjectURL(a.href),1000);}});</script></html>"""
    html_path.write_text(page, encoding="utf-8")
    result = {"html": html_path.name, "svg": svg_path.name,
              "shown_nodes": shown_nodes, "total_nodes": len(graph.get("nodes", [])),
              "shown_edges": shown_edges, "total_edges": len(graph.get("edges", [])),
              "catalog_nodes": len(graph.get("nodes", [])),
              "catalog_edges": len(graph.get("edges", [])),
              "svg_pages": pages,
              "visual_nodes": len(nodes),
              "visual_edges": visual_edges,
              "unknown": len(graph.get("unknown", [])), "truncated": incomplete}
    if pdf:
        pdf_path = outdir / f"{stem}.pdf"
        wkhtml = shutil.which("wkhtmltopdf")
        browser = shutil.which("chromium") or shutil.which("google-chrome")
        if wkhtml:
            cmd = [wkhtml, "--quiet", "--enable-local-file-access",
                   str(html_path), str(pdf_path)]
            renderer = "wkhtmltopdf"
        elif browser:
            cmd = [browser, "--headless", "--disable-gpu", "--no-sandbox",
                   f"--print-to-pdf={pdf_path}", html_path.as_uri()]
            renderer = "Chromium/Chrome"
        else:
            cmd, renderer = None, None
        if cmd:
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
            if run.returncode == 0 and pdf_path.is_file() and pdf_path.stat().st_size > 0:
                result["pdf"] = pdf_path.name
                result["pdf_renderer"] = renderer
            else:
                result["pdf_error"] = (run.stderr or "PDF export failed")[-300:]
        else:
            result["pdf_error"] = "wkhtmltopdf/Chromium/Chrome chưa cài; HTML có nút In / lưu PDF"
    return result

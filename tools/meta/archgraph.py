#!/usr/bin/env python3
# Chính sách noqa: parse 1 file hỏng phải bỏ qua, không được chết cả graph (RULES R11).
# ruff: noqa: BLE001
"""
archgraph.py — đọc cấu trúc import của repo Python (không LLM, evidence cho
auditor_architecture): cycles, hub/mang thôi module (fan-in/out), size modul.

JSON ra stdout: {"modules": [...], "cycles": [[...]], "summary": {...}}
Bỏ qua .git/.rescue/.ipynb_checkpoints/node_modules (dùng IGNORE_DIRS của context_pack).
"""
import ast
import json
import sys
from pathlib import Path

ROOT_EXC = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox",
            ".pytest_cache", ".mypy_cache", ".ipynb_checkpoints", "dist", "build",
            ".next", "target", ".idea", ".vscode", ".auditor_g6_sweep", "logs_audit",
            "bin", ".rescue"}


def walk_py(root: Path):
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root)
        if any(part in ROOT_EXC or part.startswith(".") for part in rel.parts):
            continue
        if ".ipynb_checkpoints" in rel.parts:
            continue
        yield rel


def module_of(root: Path, rel: Path):
    """Đường dẫn -> module name ('a/b.py' -> 'a.b', 'a/__init__.py' -> 'a')."""
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts) if parts else "__root__"


def resolve_imports(root: Path, mod_to_rel, tree, cur_mod):
    """Thu gọn imports về module nội bộ (bỏ ngoại vi — không phải cấu trúc code mình)."""
    out = set()
    cur_pkg = cur_mod.rsplit(".", 1)[0] if "." in cur_mod else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                base = a.name.split(".")[0]
                if any(m == a.name or m.startswith(a.name + ".") for m in mod_to_rel):
                    out.add(a.name)
                elif base in mod_to_rel:
                    out.add(base)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import
                parts = cur_pkg.split(".") if cur_pkg else []
                base = parts[: len(parts) - node.level + 1] + (node.module or "").split(".")
                cand = ".".join([x for x in base if x])
            else:
                cand = node.module or ""
            if not cand:
                continue
            if cand in mod_to_rel:
                out.add(cand)
            for alias in node.names:
                if alias.name == "*":
                    continue
                full = f"{cand}.{alias.name}"
                if full in mod_to_rel:
                    out.add(full)
            base = cand.split(".")[0]
            if base in mod_to_rel:
                out.add(base)
    return out


def scc_cycles(graph):
    """Tarjan SCC — chỉ lấy SCC > 1 module (cycle) hoặc self-edge."""
    index = {}
    low = {}
    onstack = set()
    stack = []
    result = []

    def strongconnect(v):
        index[v] = low[v] = len(index)
        stack.append(v)
        onstack.add(v)
        for w in graph.get(v, ()):
            if w not in index:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in onstack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                onstack.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or (len(comp) == 1 and comp[0] in graph.get(comp[0], ())):
                result.append(sorted(comp))

    for v in graph:
        if v not in index:
            strongconnect(v)
    return result


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    root = root.resolve()
    mod_to_rel = {}
    for rel in walk_py(root):
        mod_to_rel[module_of(root, rel)] = rel

    modules = []
    graph = {}
    size = {}
    for mod, rel in mod_to_rel.items():
        full = root / rel
        try:
            tree = ast.parse(full.read_text(errors="ignore"))
        except Exception:  # noqa: S112 — file hỏng bỏ qua, evidence vẫn chạy tiếp
            continue
        line_count = sum(1 for _ in full.open(errors="ignore"))
        size[mod] = line_count
        imports = sorted(resolve_imports(root, mod_to_rel, tree, mod))
        graph[mod] = imports
        modules.append({"module": mod, "path": str(rel), "lines": line_count,
                        "imports": imports})

    fan_in = {m: 0 for m in graph}
    for imps in graph.values():
        for i in imps:
            if i in fan_in:
                fan_in[i] += 1

    cycles = scc_cycles(graph)
    hub = sorted((m for m, n in fan_in.items() if n >= 5),
                 key=lambda m: (-fan_in[m], m))
    print(json.dumps({
        "modules": modules,
        "cycles": cycles,
        "fan_in": fan_in,
        "summary": {"modules": len(modules),
                    "cycles": len(cycles),
                    "max_fan_in": max(fan_in.values()) if fan_in else 0,
                    "hub_modules": [{"module": m, "fan_in": fan_in[m],
                                     "lines": size.get(m, 0)} for m in hub[:15]]},
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Syntax-only symbol and local-call map; parses source without executing it."""
from pathlib import Path

GRAMMARS = {
    "rust": "rust", "go": "go", "java": "java", "csharp": "csharp", "php": "php",
}
FRONTEND_GRAMMARS = {
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "tsx", ".ts": "typescript", ".tsx": "tsx",
}
DEFINITIONS = {
    "rust": {"function_item"},
    "go": {"function_declaration", "method_declaration"},
    "java": {"method_declaration", "constructor_declaration"},
    "csharp": {"method_declaration", "constructor_declaration"},
    "php": {"function_definition", "method_declaration"},
    "frontend": {"function_declaration", "method_definition", "variable_declarator"},
}
CALLS = {"call_expression", "invocation_expression", "function_call_expression",
         "member_call_expression", "scoped_call_expression", "method_invocation"}


def _name(node, source):
    field = node.child_by_field_name("name") or node.child_by_field_name("function")
    if field is None:
        field = next((c for c in node.children if c.type in ("identifier", "name")), None)
    if field is None:
        return None
    raw = source[field.start_byte:field.end_byte].decode("utf-8", errors="replace")
    return raw.rsplit("::", 1)[-1].rsplit(".", 1)[-1].strip()


def _definition(node, language):
    if node.type not in DEFINITIONS[language]:
        return False
    if language == "frontend" and node.type == "variable_declarator":
        value = node.child_by_field_name("value")
        return value is not None and value.type in {"arrow_function", "function_expression"}
    return True


def extract(target: Path, paths: list[Path], language: str, max_bytes=1_000_000):
    """Only same-file syntax calls are asserted; other calls stay unknown."""
    from tree_sitter_language_pack import get_parser

    parsers = {}
    nodes, edges, unknown = [], [], []
    for relative in paths:
        grammar = (FRONTEND_GRAMMARS.get(relative.suffix.lower()) if language == "frontend"
                   else GRAMMARS[language])
        if not grammar:
            unknown.append({"file": str(relative), "reason": "frontend syntax unsupported"})
            continue
        if grammar not in parsers:
            parsers[grammar] = get_parser(grammar)
        parser = parsers[grammar]
        path = target / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
            unknown.append({"file": str(relative), "reason": "symlink, missing or >1 MB"})
            continue
        source = path.read_bytes()
        tree = parser.parse(source)
        if tree.root_node.has_error:
            unknown.append({"file": str(relative), "reason": "syntax parse has error"})
        definitions = []
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            if _definition(node, language):
                name = _name(node, source)
                if name:
                    symbol_id = f"{relative}:{node.start_point.row + 1}:{name}"
                    definitions.append((node, name, symbol_id))
                    nodes.append({"id": symbol_id, "label": name,
                                  "file": str(relative), "line": node.start_point.row + 1,
                                  "kind": "function"})
            stack.extend(reversed(node.children))
        by_name = {}
        for _node, name, symbol_id in definitions:
            by_name.setdefault(name, []).append(symbol_id)
        for parent, _name_value, source_id in definitions:
            walk = list(parent.children)
            while walk:
                child = walk.pop()
                if child is not parent and _definition(child, language):
                    continue
                if child.type in CALLS:
                    name = _name(child, source)
                    direct = (language != "frontend" or (
                        (callee := child.child_by_field_name("function")) is not None
                        and callee.type == "identifier"))
                    matches = by_name.get(name or "", []) if direct else []
                    if len(matches) == 1:
                        edges.append({"source": source_id, "target": matches[0],
                                      "kind": "same-file direct call" if language == "frontend"
                                      else "same-file syntax call",
                                      "file": str(relative), "line": child.start_point.row + 1})
                    elif name:
                        unknown.append({"file": str(relative), "line": child.start_point.row + 1,
                                        "call": name, "reason": "member/dynamic call unresolved"
                                        if not direct else "target unresolved or ambiguous"})
                walk.extend(child.children)
    return {"nodes": nodes, "edges": edges, "unknown": unknown,
            "evidence": "tree-sitter syntax only; no runtime dispatch or cross-file resolution"}

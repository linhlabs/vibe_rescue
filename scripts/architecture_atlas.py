"""Evidence-graded architecture model for the generic Source Explorer.

Documentation is read locally from explicit source scopes. A documentation
claim and a statically resolved call remain different kinds of evidence.
"""

import ast
import hashlib
import html
import json
import os
import re
from collections import defaultdict
from pathlib import Path

try:
    from scripts.module_resolution import from_base, resolve_qualified, unique_suffixes
except ModuleNotFoundError:  # direct script entry point
    from module_resolution import from_base, resolve_qualified, unique_suffixes

CODE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java",
             ".php", ".cs", ".c", ".cc", ".cpp", ".h", ".hpp", ".kt",
             ".swift", ".rb", ".dart", ".sh"}
ASSET_EXTS = {".yaml", ".yml", ".toml", ".ini", ".json", ".txt", ".md"}
ASSET_WORDS = ("config", "prompt", "policy", "manifest", "schema", "workflow", "pipeline", "route")
DOC_NAMES = {"readme.md", "design.md", "architecture.md", "pipeline.md"}
SKIP_PARTS = {".git", "node_modules", "__pycache__", ".ipynb_checkpoints", ".venv", "venv", "archive",
              "audit_claude", "logs_audit", "test_e2e", "tokenizer", "corpora",
              "attachments", "artifacts", "evidence", "VIBE_RESCUE", ".rescue"}
RUN_PREFIXES = ("sota_run_", "sota_gemma_diag", "evidence_", "run_artifact")
SKIP_PARTS_LOWER = {name.lower() for name in SKIP_PARTS}
JOURNEY_WORDS = ("architecture", "pipeline", "workflow", "journey", "how it works",
                 "request flow", "data flow", "kiến trúc", "quy trình", "luồng",
                 "đường đi")
CONTROL_SPECS = (
    ("H01", "Intent and plan", "agent", ("intent", "planner", "plan"),
     "Trace input → structured intent/plan, including ambiguous and failed planning cases."),
    ("H02", "Tool authority and scope", "agent", ("tool_runner", "tool_call", "allowed_tool", "tool_permission"),
     "Prove each agent can call only approved tools and cannot escape its write scope."),
    ("H03", "Timeout, cancel and termination", "agent", ("timeout", "cancel", "termination", "deadline"),
     "Fault-inject timeout/cancel and prove a bounded terminal state with no orphan work."),
    ("H04", "Retry and budget", "agent", ("retry", "max_iters", "budget", "cost"),
     "Measure retry/token/cost bounds and prove failures do not loop or silently continue."),
    ("H05", "Evidence and final judge", "agent", ("evidence", "citation", "judge", "final_audit"),
     "Trace a claim from source evidence through writer to the final audit verdict."),
    ("H06", "Step audit trail", "agent", ("audit", "trace", "telemetry"),
     "Check every decision and failure emits a redacted, ordered audit event."),
    ("S01", "Swarm dispatch and concurrency", "swarm", ("swarm", "fanout", "gather", "executor", "dispatch"),
     "If parallel agents are intended, prove bounded fan-out, ordering and backpressure."),
    ("S02", "Swarm independent review", "swarm", ("reviewer", "challenger", "crosscheck", "self_approval"),
     "Show a distinct reviewer, disagreement handling and no self-approval path."),
    ("S03", "Swarm failure containment", "swarm", ("cancel", "timeout", "kill", "rollback"),
     "Kill one worker mid-task; prove siblings, shared state and final response fail safely."),
    ("P01", "Sensitive intake and classification", "pii", ("phi", "pii", "sensitive", "intake"),
     "Identify entrypoints and data classes without copying real personal data into reports."),
    ("P02", "Mask before provider egress", "pii", ("mask", "redact", "egress", "provider"),
     "Fault-inject the masker at every outbound boundary and prove no raw identifier leaves."),
    ("P03", "Storage, retention and consent", "pii", ("retention", "consent", "encrypt", "delete_subject"),
     "Prove subject consent, isolation, deletion/TTL and storage policy with focused tests."),
    ("P04", "Step and final audit redaction", "pii", ("audit", "redact", "final_audit", "log"),
     "Inspect step/final audit and telemetry with synthetic identifiers; require zero raw leaks."),
    ("M01", "Clinical evidence and citation", "medical", ("clinical", "citation", "evidence", "source_gate"),
     "Test no-source/conflicting-source medical turns; block invented numbers and citations."),
    ("M02", "Patient/subject isolation", "medical", ("subject", "patient", "profile", "memory"),
     "Test self/relative/unknown subject and prevent cross-person memory or personalization."),
    ("B01", "Billing authorization and idempotency", "billing", ("billing", "payment", "idempot", "authorize"),
     "Replay/duplicate a payment request and prove authorization plus one durable charge."),
    ("B02", "Billing ledger and reconciliation", "billing", ("ledger", "reconcil", "refund", "invoice"),
     "Prove transaction audit, reconciliation and compensating failure paths."),
)


def excluded_parts(parts):
    return any(part.lower() in SKIP_PARTS_LOWER or
               part.lower().startswith(RUN_PREFIXES) for part in parts)


def _safe_file(root, path):
    path = path if path.is_absolute() else root / path
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        return False
    parts = path.relative_to(root).parts
    if excluded_parts(parts):
        return False
    return not any(root.joinpath(*parts[:depth]).is_symlink() for depth in range(1, len(parts)))


def discover_docs(root, sources, extra=()):
    """Read only bounded, named documentation under approved paths."""
    candidates = {root / "README.md"}
    for source in sources:
        for path in (root / source).rglob("*.md"):
            if path.name.lower() in DOC_NAMES and _safe_file(root, path):
                candidates.add(path)
    for path in extra:
        candidate = root / path
        if not _safe_file(root, candidate):
            raise ValueError(f"documentation path is missing or unsafe: {path}")
        candidates.add(candidate)
    records, skipped = [], []
    for path in sorted(candidates):
        if not _safe_file(root, path):
            continue
        if path.stat().st_size > 96_000 or len(records) >= 100:
            skipped.append(path.relative_to(root).as_posix())
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        lines = raw.splitlines()
        title = next((line.lstrip("# ").strip() for line in lines if line.startswith("# ")), path.stem)
        intro, intro_line = "", 0
        in_code = False
        for n, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
            if (in_code or not stripped or stripped.startswith(("#", ">", "-", "*", "|", "![", "["))
                    or stripped[0].isdigit() and re.match(r"\d+[.)]", stripped)):
                continue
            if len(stripped) >= 25:
                intro, intro_line = stripped[:400], n
                break
        records.append({"path": path.relative_to(root).as_posix(), "title": title[:120],
                        "purpose": intro, "purpose_line": intro_line, "lines": lines})
    return records, skipped


def _code_files(root, sources):
    files = set()
    for source in sources:
        for path in (root / source).rglob("*"):
            if path.suffix.lower() in CODE_EXTS and _safe_file(root, path):
                files.add(path.relative_to(root).as_posix())
    return sorted(files)


def _context_assets(root, sources):
    assets = []
    for source in sources:
        for path in (root / source).rglob("*"):
            if not _safe_file(root, path) or path.suffix.lower() not in ASSET_EXTS:
                continue
            stem = path.stem.lower()
            if path.suffix.lower() in {".yaml", ".yml", ".toml", ".ini"} or any(
                    word in stem for word in ASSET_WORDS):
                role = "prompt" if "prompt" in stem else "config" if (
                    path.suffix.lower() in {".yaml", ".yml", ".toml", ".ini"} or "config" in stem
                ) else "policy/schema" if any(w in stem for w in ("policy", "schema", "manifest")) else "workflow"
                assets.append({"path": path.relative_to(root).as_posix(), "role": role})
    return sorted({item["path"]: item for item in assets}.values(), key=lambda item: item["path"])


def _blocks(files, sources, max_files=40):
    groups = []

    def add(prefix, paths, split=True):
        direct = [p for p in paths if Path(p).parent.as_posix() == prefix]
        children = defaultdict(list)
        for path in paths:
            rest = Path(path).relative_to(prefix).parts
            if len(rest) > 1:
                children[rest[0]].append(path)
        if split and children:
            if direct:
                groups.append((prefix, direct))
            for name, member in sorted(children.items()):
                child = (Path(prefix) / name).as_posix()
                add(child, member, split=len(member) > max_files)
        else:
            groups.append((prefix, paths))

    for source in sources:
        area = str(source).rstrip("/") or "."
        scoped = files if area == "." else [p for p in files if p.startswith(area + "/")]
        if scoped:
            add(area, scoped)
    # Overlapping --sources are allowed, but a file belongs to one block.
    unique, seen = [], set()
    for name, paths in sorted(groups):
        members = [p for p in paths if p not in seen]
        if members:
            unique.append((name, members))
            seen.update(members)
    return unique


def _label(path):
    if path == ".":
        return "Root"
    return path.split("/")[-1].replace("_", " ").replace("-", " ").title()


def _area_for_block(name, sources):
    for source in sources:
        area = str(source).rstrip("/") or "."
        if area == "." or name == area or name.startswith(area + "/"):
            return area
    return name


def _is_test_file(path):
    parts = Path(path).parts
    return any(part in {"tests", "test", "behavior"} for part in parts) or Path(path).name.startswith("test_")


def _purpose(block_id, docs, module_docs, members):
    candidates = [doc for doc in docs if Path(doc["path"]).parent.as_posix() == block_id
                  and doc["purpose"]]
    if candidates:
        doc = max(candidates, key=lambda item: len(Path(item["path"]).parts))
        return {"text": doc["purpose"], "state": "documented",
                "source": f"{doc['path']}:{doc['purpose_line']}"}
    local = [file for file in members if file in module_docs]
    local.sort(key=lambda file: (Path(file).parent.as_posix() != block_id,
                                 Path(file).name not in {"__init__.py", Path(block_id).name + ".py"}, file))
    if local:
        file = local[0]
        return {"text": module_docs[file]["text"], "state": "source_docstring",
                "source": f"{file}:{module_docs[file]['line']}"}
    candidates = [doc for doc in docs if block_id.startswith(Path(doc["path"]).parent.as_posix() + "/")
                  and doc["purpose"]]
    if candidates:
        doc = max(candidates, key=lambda item: len(Path(item["path"]).parts))
        return {"text": doc["purpose"], "state": "inherited_documentation",
                "source": f"{doc['path']}:{doc['purpose_line']}"}
    return {"text": "No purpose statement located in approved documentation or module docstrings.",
            "state": "unknown", "source": ""}


def _imports(root, index_data, file_to_block):
    modules = index_data["modules"]
    suffixes = unique_suffixes(modules)
    edges = []
    for module, file in modules.items():
        if file not in file_to_block:
            continue
        try:
            tree = ast.parse((root / file).read_bytes(), filename=file)
        except (SyntaxError, OSError):
            continue
        for node in tree.body:
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = from_base(module, node.module, node.level)
                names = [base, *(f"{base}.{alias.name}" for alias in node.names)]
            for name in names:
                resolved_name = resolve_qualified(name, suffixes)
                target = modules.get(resolved_name)
                if target and target in file_to_block and file_to_block[file] != file_to_block[target]:
                    edges.append((file_to_block[file], file_to_block[target],
                                  {"file": file, "line": node.lineno, "symbol": name,
                                   "resolution": "unique_module_suffix" if resolved_name != name else "exact_lexical"}))
    return edges


def _journeys(docs, index_data, file_to_block):
    by_name = defaultdict(list)
    by_file = defaultdict(list)
    for fn in index_data["functions"]:
        by_name[fn["name"].split(".")[-1]].append(fn["id"])
        by_file[fn["file"]].append(fn["id"])
    journeys = []

    def finish(doc, section, steps):
        if section and steps and len(journeys) < 30:
            journeys.append({"title": section[0], "source": f"{doc['path']}:{section[1]}",
                             "steps": steps[:15]})

    for doc in docs:
        section, steps = None, []
        for n, line in enumerate(doc["lines"], 1):
            heading = re.match(r"^#{2,4}\s+(.+)", line)
            if heading:
                finish(doc, section, steps)
                title = heading.group(1).strip()
                section = (title, n) if any(word in title.lower() for word in JOURNEY_WORDS) else None
                steps = []
                continue
            match = re.match(r"^\s*(\d{1,2})[.)]\s+(.+)", line)
            if not section or not match:
                continue
            refs, blocks = [], set()
            for token in re.findall(r"`([^`]+)`", match.group(2)):
                token = token.strip()
                for file in by_file:
                    if file == token or file.endswith("/" + token):
                        blocks.add(file_to_block[file])
                        refs.extend(by_file[file][:5])
                if len(by_name.get(token, [])) == 1:
                    refs.extend(by_name[token])
                    blocks.add(file_to_block[index_data["functions_by_id"][refs[-1]]["file"]])
            steps.append({"text": match.group(2).strip()[:500],
                          "source": f"{doc['path']}:{n}",
                          "functions": list(dict.fromkeys(refs))[:12],
                          "blocks": sorted(blocks),
                          "binding": "source_observed" if refs else "unknown"})
        finish(doc, section, steps)
    return journeys


def _control_hits(index_data, docs, controls, file_to_block):
    functions = index_data["functions"]
    for code, title, group, tokens, recommendation in CONTROL_SPECS:
        if group not in controls:
            continue
        hits = []
        for fn in functions:
            # Paths suggest the profile, but a module called "medical" or "agent_tools"
            # cannot be evidence for every control in that profile.
            hay = fn["name"].lower()
            if any(re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", hay) for token in tokens):
                is_test = _is_test_file(fn["file"])
                hits.append({"kind": "test_candidate" if is_test else "source_candidate",
                             "source": f"{fn['file']}:{fn['line']}", "symbol": fn["id"],
                             "block": file_to_block.get(fn["file"], "")})
        if not hits:
            for doc in docs:
                hay = (doc["title"] + " " + doc["purpose"]).lower()
                if any(re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", hay) for token in tokens):
                    hits.append({"kind": "documented", "source": f"{doc['path']}:{doc['purpose_line']}",
                                 "symbol": "", "block": ""})
        hits.sort(key=lambda h: (h["kind"] != "source_candidate", h["source"]))
        status = ("source_candidate" if any(h["kind"] == "source_candidate" for h in hits)
                  else "test_only" if hits and hits[0]["kind"] == "test_candidate"
                  else "documented_only" if hits else "not_located_in_scope")
        yield {"id": code, "title": title, "group": group, "status": status,
               "evidence": hits[:5], "candidate_count": len(hits),
               "recommendation": recommendation,
               "claim": "Names and syntax are leads; runtime, fail-closed behavior and production readiness unverified."}


def build(root, sources, index_data, extra_docs=(), profiles=()):
    root = Path(root).resolve()
    docs, skipped_docs = discover_docs(root, sources, extra_docs)
    files = _code_files(root, sources)
    context_assets = _context_assets(root, sources)
    groups = _blocks(files, sources)
    file_to_block = {file: name for name, members in groups for file in members}
    assets_by_block = defaultdict(list)
    for asset in context_assets:
        owner = max((name for name, _ in groups if name == "." or asset["path"].startswith(name + "/")),
                    key=len, default=None)
        if owner:
            assets_by_block[owner].append(asset)
    fn_by_id = {fn["id"]: fn for fn in index_data["functions"]}
    by_file = defaultdict(list)
    for fn in index_data["functions"]:
        by_file[fn["file"]].append(fn["id"])
    blocks = []
    for name, members in groups:
        functions = [fn for file in members for fn in by_file[file]]
        def lead_rank(identifier, block_name=name):
            fn = fn_by_id[identifier]
            runtime_callers = [fn_by_id.get(call["from"]) for call in fn["callers"]]
            cross = sum(bool(caller and not _is_test_file(caller["file"]) and
                             file_to_block.get(caller["file"]) != block_name) for caller in runtime_callers)
            leaf = fn["name"].split(".")[-1].lstrip("_")
            entry = leaf in {"main", "run", "dispatch", "handle", "serve", "stream"} or leaf.startswith(
                ("run_", "handle_", "serve_", "process_", "orchestrate_", "stream_"))
            return (not entry, -cross, fn["name"].split(".")[-1].startswith("_"),
                    fn["name"].count("."), -len(fn["callers"]), identifier)
        function_leads = sorted((fn for fn in functions if not _is_test_file(fn_by_id[fn]["file"])),
                                key=lead_rank)[:24]
        languages = defaultdict(int)
        for file in members:
            languages[Path(file).suffix.lower() or "other"] += 1
        blocks.append({"id": name, "label": _label(name), "area": _area_for_block(name, sources),
            "purpose": _purpose(name, docs, index_data.get("module_docs", {}), members),
            "files": members, "functions": functions, "function_leads": function_leads,
            "context_assets": assets_by_block[name],
            "languages": dict(languages)})
    edge_map = defaultdict(lambda: {"count": 0, "examples": []})
    for fn in index_data["functions"]:
        first = file_to_block.get(fn["file"])
        for call in fn["resolved"]:
            target = fn_by_id.get(call["to"])
            second = file_to_block.get(target["file"]) if target else None
            if not first or not second or first == second:
                continue
            edge = edge_map[(first, second, "test_call" if _is_test_file(fn["file"]) else "static_call")]
            edge["count"] += 1
            if len(edge["examples"]) < 5:
                edge["examples"].append({"source": f"{fn['file']}:{call['line']}",
                                         "from": fn["id"], "to": call["to"],
                                         "resolution": call["resolution"]})
    for first, second, example in _imports(root, index_data, file_to_block):
        edge = edge_map[(first, second, "test_import" if _is_test_file(example["file"]) else "import")]
        edge["count"] += 1
        if len(edge["examples"]) < 5:
            edge["examples"].append(example)
    edges = [{"from": first, "to": second, "kind": kind, **payload}
             for (first, second, kind), payload in sorted(edge_map.items())]
    doc_text = " ".join((d["title"] + " " + d["purpose"]).lower() for d in docs)
    code_names = " ".join(Path(p).stem.lower() for p in files)
    detected = set(profiles)
    if any(x in doc_text for x in ("agent", "harness", "orchestrat")) or "agent" in code_names:
        detected.update(("agent", "swarm"))
    if any(x in doc_text for x in ("phi", "pii", "patient", "bệnh nhân", "personal data")):
        detected.add("pii")
    if any(x in doc_text for x in ("medical", "clinical", "lâm sàng", "y khoa")):
        detected.add("medical")
    if any(x in doc_text for x in ("billing", "payment", "invoice", "thanh toán")):
        detected.add("billing")
    # The profile is a lead, never a classification of actual data handled.
    index_data = {**index_data, "functions_by_id": fn_by_id}
    journeys = _journeys(docs, index_data, file_to_block)
    controls = list(_control_hits(index_data, docs, detected, file_to_block))
    overview = next((d for d in docs if d["path"] == "README.md"), None)
    fingerprint = hashlib.sha256((index_data["fingerprint"] + "\n" + "\n".join(
        f"{d['path']}:{hashlib.sha256(chr(10).join(d['lines']).encode()).hexdigest()}" for d in docs)).encode()).hexdigest()
    return {"schema": 1, "repo": root.name, "fingerprint": fingerprint,
            "overview": {"title": overview["title"], "purpose": overview["purpose"],
                         "source": f"README.md:{overview['purpose_line']}"} if overview else
                        {"title": root.name, "purpose": "No root README in approved scope.", "source": ""},
            "sources": list(sources), "profiles_candidate": sorted(detected),
            "docs": [{k: v for k, v in doc.items() if k != "lines"} for doc in docs],
            "blocks": blocks, "edges": edges, "journeys": journeys, "controls": controls,
            "coverage": {"code_files": len(files), "python_functions": len(fn_by_id),
                         "context_assets": len(context_assets),
                         "documents_read": len(docs), "documents_skipped": skipped_docs,
                         "parse_errors": index_data["parse_errors"],
                         "journey_steps_unbound": sum(not step["functions"] for j in journeys for step in j["steps"]),
                         "non_python_files": sum(Path(p).suffix.lower() != ".py" for p in files)},
            "limits": ["Documentation claims may be stale.",
                       "Static calls/imports do not prove a runtime request path.",
                       "Unique module-suffix bindings assume one indexed local module; dynamic sys.path can load another module.",
                       "Function parameters/guards are indexed for Python only; other languages retain file-level blocks.",
                       "Control candidates are not a security or production-readiness verdict."]}


def render(model, root, output):
    template = Path(__file__).with_name("architecture_template.html").read_text(encoding="utf-8")
    payload = json.dumps(model, ensure_ascii=False).replace("<", "\\u003c")
    prefix = os.path.relpath(root, output.parent).replace("\\", "/").rstrip("/") + "/"
    page = (template.replace("__DATA__", payload)
            .replace("__TITLE__", html.escape(model["repo"], quote=True))
            .replace("__ROOT_PREFIX__", json.dumps(prefix)))
    output.write_text(page, encoding="utf-8")
    output.with_suffix(".json").write_text(json.dumps(model, ensure_ascii=False, indent=1),
                                          encoding="utf-8")

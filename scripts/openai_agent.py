#!/usr/bin/env python3
"""
openai_agent.py - run ONE harness AI task through ANY OpenAI-style chat server
(`/v1/chat/completions` with tool calling): open models you host yourself
(Gemma, Qwen, ...) or any cheap or strong hosted model.

Why it exists: the harness expects an AI *agent program* that can read files and
write its report itself (Claude Code, Codex). A plain model server cannot. This
adapter gives a plain server exactly the hands it needs, and nothing more:

  tools  : list_dir, read_file, grep (read only); write_file (confined, see below);
           git_diff (execute and verdict tasks only).
  no shell, no network except the one server you name. The harness itself runs the
  tests, scanners, scope check and delta gate; the model never runs commands.

What each task may write (everything else is refused):
  review     -> any file under $REVIEW_DIR
  crosscheck -> only $REVIEW_DIR/EVIDENCE/cross-check.md
  plan       -> nothing; the final answer is printed to stdout (the harness saves it)
  execute    -> files under $TARGET_WT (never inside .git)
  verdict    -> only $VERDICT_FILE

Settings (never put a key on the command line or in a file):
  --base-url / VIBE_AGENT_BASE_URL   server URL ending in /v1 (https, or http on loopback;
                                     other http needs --allow-http)
  --model    / VIBE_AGENT_MODEL      exact model id from the server's /v1/models
  --api-key-env NAME                 env var that holds the key (default VIBE_AGENT_API_KEY);
                                     empty or unset = no Authorization header (local servers)
  VIBE_AGENT_TASK                    set by the harness: review|crosscheck|plan|execute|verdict

Use it through config.toml:  [roles.audit] cli = "openai" ; model = "<id>" ;
extra_args = ["--base-url", "http://localhost:8000/v1"]

Exit codes: 0 done, 2 bad settings, 3 server/network failure, 4 step limit reached.
Page content that the model reads is redacted with tools/meta/redact.py before it is
sent (best effort, like the rest of the harness).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.meta.redact import mask_text

TASKS = ("review", "crosscheck", "plan", "execute", "verdict")
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
MAX_READ_CHARS = 60_000
MAX_TOOL_OUT = 20_000
MAX_WRITE_CHARS = 400_000
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".rescue"}
ENV_NAMES = ("TARGET_DIR", "TARGET_WT", "EVIDENCE_DIR", "REVIEW_DIR", "PLAN", "VERDICT_FILE")


class Refused(Exception):
    """A tool call that the policy does not allow; reported to the model, not fatal."""


def _env_path(name):
    value = os.environ.get(name)
    return Path(value).resolve() if value else None


def build_policy(task):
    """Return (read_roots, write_roots, exact_write_files). Roots may be dirs or files."""
    target, wt, ev, rv, plan, verdict = (_env_path(n) for n in ENV_NAMES)
    if task == "review":
        reads, writes, exact = [target, ev, rv], [rv], []
    elif task == "crosscheck":
        reads, writes = [target, ev, rv], []
        exact = [rv / "EVIDENCE" / "cross-check.md"] if rv else []
    elif task == "plan":
        reads, writes, exact = [target, ev], [], []
    elif task == "execute":
        reads, writes, exact = [wt, plan], [wt], []
    else:  # verdict
        reads, writes, exact = [wt, plan], [], [verdict]
    reads, writes, exact = ([p for p in group if p] for group in (reads, writes, exact))
    return reads, writes, exact


def _inside(path, root):
    return path == root or root in path.parents


def resolve(arg, roots, bases):
    """Resolve a model-supplied path; it must stay inside one of `roots` (symlinks followed)."""
    raw = Path(str(arg))
    candidates = [raw] if raw.is_absolute() else [b / raw for b in bases]
    for cand in candidates:
        real = cand.resolve()
        if any(_inside(real, r) for r in roots):
            return real
    raise Refused(f"path not allowed: {arg}")


class Tools:
    def __init__(self, task):
        self.task = task
        self.reads, self.writes, self.exact = build_policy(task)
        if not self.reads and not self.exact:
            raise SystemExit(f"[AGENT] task '{task}' has no usable directories in the environment")
        self.bases = [p for p in self.reads if p.is_dir()]
        self.wrote = []

    def schema(self):
        def tool(name, desc, props, req):
            return {"type": "function", "function": {
                "name": name, "description": desc,
                "parameters": {"type": "object", "properties": props, "required": req}}}
        path = {"type": "string", "description": "path inside the allowed folders"}
        out = [
            tool("list_dir", "List a folder (max 300 entries).", {"path": path}, ["path"]),
            tool("read_file", "Read a text file with line numbers.",
                 {"path": path, "start": {"type": "integer"}, "end": {"type": "integer"}}, ["path"]),
            tool("grep", "Find a literal text in files under a folder (max 100 hits).",
                 {"pattern": {"type": "string"}, "path": path}, ["pattern"]),
        ]
        if self.writes or self.exact:
            out.append(tool("write_file", "Create or overwrite one allowed file with the full content.",
                            {"path": path, "content": {"type": "string"}}, ["path", "content"]))
        if self.task in ("execute", "verdict"):
            out.append(tool("git_diff", "Show the change under review (read only).", {}, []))
        return out

    # -- read tools -------------------------------------------------------------------
    def list_dir(self, path="."):
        p = resolve(path, self.reads, self.bases)
        if not p.is_dir():
            raise Refused("not a folder")
        names = sorted(f"{c.name}/" if c.is_dir() else c.name for c in p.iterdir() if c.name != ".git")
        return "\n".join(names[:300]) + (f"\n... {len(names) - 300} more" if len(names) > 300 else "")

    def read_file(self, path, start=1, end=None):
        p = resolve(path, self.reads + self.exact, self.bases)
        if not p.is_file():
            raise Refused("not a file")
        data = p.read_bytes()[: MAX_READ_CHARS * 4]
        if b"\x00" in data[:8192]:
            raise Refused("binary file")
        lines = data.decode("utf-8", "replace").splitlines()
        start = max(1, int(start or 1))
        end = min(len(lines), int(end)) if end else len(lines)
        text = "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))
        return mask_text(text[:MAX_READ_CHARS])

    def grep(self, pattern, path="."):
        root = resolve(path, self.reads, self.bases)
        hits, files = [], 0
        walk = [root] if root.is_file() else sorted(root.rglob("*"))
        for f in walk:
            if any(part in SKIP_DIRS for part in f.parts) or not f.is_file():
                continue
            files += 1
            if files > 400 or f.stat().st_size > 1_000_000:
                continue
            try:
                for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern in line:
                        hits.append(f"{f}:{n}: {line.strip()[:200]}")
                        if len(hits) >= 100:
                            return mask_text("\n".join(hits))
            except (OSError, UnicodeDecodeError):
                continue
        return mask_text("\n".join(hits)) or "no match"

    def git_diff(self):
        wt = _env_path("TARGET_WT")
        if not wt:
            raise Refused("no worktree")
        args = ["git", "-C", str(wt), "diff"] + (["HEAD~1", "HEAD"] if self.task == "verdict" else [])
        r = subprocess.run(args, capture_output=True, text=True, timeout=120, check=False)
        return mask_text((r.stdout or r.stderr)[:MAX_READ_CHARS])

    # -- the only write tool -----------------------------------------------------------
    def write_file(self, path, content):
        if len(content) > MAX_WRITE_CHARS:
            raise Refused("file too large")
        p = resolve(path, self.writes + self.exact, self.writes[:1] + [x.parent for x in self.exact])
        if ".git" in p.parts:
            raise Refused("never inside .git")
        if not (p in self.exact or any(_inside(p, w) for w in self.writes)):
            raise Refused(f"writing here is not allowed for task '{self.task}': {path}")
        if p.is_dir():
            raise Refused("is a folder")
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp-agent")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, p)
        self.wrote.append(str(p))
        return f"wrote {len(content)} chars to {p}"

    def call(self, name, args):
        if name not in {t["function"]["name"] for t in self.schema()}:
            return f"error: unknown or disabled tool {name}"
        try:
            return str(getattr(self, name)(**args))[:MAX_TOOL_OUT]
        except Refused as exc:
            return f"refused: {exc}"
        except (TypeError, OSError, ValueError, subprocess.SubprocessError) as exc:
            return f"error: {type(exc).__name__}: {str(exc)[:200]}"


def chat(base_url, model, key, messages, tools, timeout, retries=2):
    body = {"model": model, "temperature": 0, "messages": messages}
    if tools:
        body["tools"] = tools
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    last = ""
    for attempt in range(retries + 1):
        req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions",
                                     data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)["choices"][0]["message"]
        except urllib.error.HTTPError as exc:
            detail = exc.read(300).decode("utf-8", "replace").replace("\n", " ")
            last = f"HTTP {exc.code}: {detail}".replace(key, "***") if key else f"HTTP {exc.code}: {detail}"
            if exc.code not in (408, 429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as exc:
            last = type(exc).__name__
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(last or "request failed")


def strip_fence(text):
    t = text.strip()
    if t.startswith("```") and t.endswith("```") and t.count("```") == 2:
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip() + "\n"


def extract_plan(text):
    """Keep exactly one plan: drop any narration before the first '# PLAN-' heading, any later
    second plan, and a closing code fence. Without a heading the text is returned unchanged."""
    heads = [m.start() for m in re.finditer(r"(?m)^# PLAN-", text)]
    if not heads:
        return strip_fence(text)
    end = heads[1] if len(heads) > 1 else len(text)
    body = text[heads[0]:end].rstrip()
    if body.endswith("```"):
        body = body[:-3].rstrip()
    return body + "\n"


def head_sha(path):
    if not path:
        return ""
    r = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                       timeout=30, check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def run(task, base_url, model, key, max_steps, timeout):
    tools = Tools(task)
    prompt = os.environ.get("PROMPT_AGENT", "")
    for name in ENV_NAMES:
        if os.environ.get(name):
            prompt = prompt.replace("$" + name, str(_env_path(name)))
    where = "\n".join(f"{n} = {_env_path(n)}" for n in ENV_NAMES if os.environ.get(n))
    allowed = [str(p) for p in tools.writes + tools.exact] or ["nothing (answer in your final message)"]
    messages = [
        {"role": "system", "content": prompt or "Do the task described by the user."},
        {"role": "user", "content": (
            f"Task: {task}.\nFolders you can read (use the tools):\n{where}\n"
            f"You may write only: {', '.join(allowed)}.\n"
            "You cannot run commands. Only use facts you read with the tools; "
            "if you do not know, say so. When finished, reply with a short final message."
            + (f"\nMachine receipts (run by the harness, not by you): {os.environ.get('VIBE_RECEIPTS')}\n"
               "You cannot run commands, so do not ask for them and do not claim you ran them: judge the diff "
               "with git_diff, check it matches the plan, and state clearly that you relied on these receipts."
               if task == "verdict" and os.environ.get("VIBE_RECEIPTS") else "")
            + (f"\nPlan rules: your final message is saved as the plan file. It must contain exactly ONE plan "
               f"whose first line is '# PLAN-001: <one outcome>', no text before it, and each file listed once "
               f"in Scope. Use this Plan SHA: {head_sha(_env_path('TARGET_DIR'))}." if task == "plan" else ""))},
    ]
    for _ in range(max_steps):
        msg = chat(base_url, model, key, messages, tools.schema(), timeout)
        calls = msg.get("tool_calls") or []
        if not calls:
            sys.stdout.write(extract_plan(msg.get("content") or "") if task == "plan" else (msg.get("content") or "") + "\n")
            return 0
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for c in calls:
            fn = c.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            result = tools.call(fn.get("name", ""), args if isinstance(args, dict) else {})
            messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": result})
    print(f"[AGENT] step limit ({max_steps}) reached", file=sys.stderr)
    return 4


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run one harness AI task via an OpenAI-style server")
    ap.add_argument("--task", default=os.environ.get("VIBE_AGENT_TASK"), choices=TASKS)
    ap.add_argument("--base-url", default=os.environ.get("VIBE_AGENT_BASE_URL"))
    ap.add_argument("--model", default=os.environ.get("VIBE_AGENT_MODEL"))
    ap.add_argument("--api-key-env", default="VIBE_AGENT_API_KEY")
    ap.add_argument("--allow-http", action="store_true", help="allow plain HTTP to a trusted non-loopback server")
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args(argv)
    if not (a.task and a.base_url and a.model):
        print("[AGENT] need a task (VIBE_AGENT_TASK), --base-url and --model", file=sys.stderr)
        return 2
    u = urllib.parse.urlparse(a.base_url)
    if u.scheme not in ("http", "https") or not u.netloc:
        print("[AGENT] invalid base URL", file=sys.stderr)
        return 2
    if u.scheme == "http" and u.hostname not in LOOPBACK and not a.allow_http:
        print("[AGENT] plain HTTP to a non-loopback server needs --allow-http", file=sys.stderr)
        return 2
    key = os.environ.get(a.api_key_env, "")
    try:
        return run(a.task, a.base_url, a.model, key, a.max_steps, a.timeout)
    except RuntimeError as exc:
        print(f"[AGENT] server failure: {str(exc).replace(key, '***') if key else exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

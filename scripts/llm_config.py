#!/usr/bin/env python3
"""
llm_config.py — nạp cấu hình LLM theo VAI TRÒ từ config.toml (không hardcode).

Vai trò: write (advisor+executor) · verify (reviewer 4-mắt) · audit (auditor review).
Cấu hình không chứa key — auth lấy từ env (~/.bashrc): ANTHROPIC_API_KEY,
OPENAI_API_KEY, KIMI_MODEL_API_KEY...

Overriding cho test/CI: env VIBE_LLM_CONFIG trỏ tới file config khác.
"""
import os
import shlex
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {
    "write": {"cli": "claude", "model": "", "extra_args": []},
    "verify": {"cli": "codex", "model": "", "extra_args": []},
    "audit": {"cli": "claude", "model": "", "extra_args": []},
}
CLI_TEMPLATES = {
    "claude": "{cli} -p {prompt} {args}",   # headless, print
    "codex": "{cli} exec {prompt} {args}",
}
# cli = "openai" runs scripts/openai_agent.py: ANY OpenAI-style server (open or hosted models),
# the prompt and paths arrive through the environment. See that file for settings.
# Other CLIs get only a generic prompt argument; this is not a validated adapter.
OPENAI_ADAPTER = ROOT / "scripts" / "openai_agent.py"


def config_path():
    return Path(os.environ.get("VIBE_LLM_CONFIG", str(ROOT / "config.toml")))


def load_config(path=None):
    """Đọc config.toml, merge lên DEFAULTS (role thiếu vẫn có default)."""
    p = Path(path) if path else config_path()
    raw = {}
    if p.exists():
        with open(p, "rb") as f:
            raw = tomllib.load(f)
    roles = {}
    for role, defaults in DEFAULTS.items():
        override = raw.get("roles", {}).get(role, {}) if isinstance(raw.get("roles"), dict) else {}
        roles[role] = {**defaults, **{k: v for k, v in override.items() if k in defaults}}
    return roles


def resolve_cli(cli):
    return shutil.which(cli) or cli


def build_cmd(role, roles=None):
    """Trả về chuỗi lệnh (dùng cho shell=False+shlex của rescue_loop/voyage):
    claude -> '<cli> -p "$PROMPT_AGENT" [--model X] [extra...]'
    codex  -> '<cli> exec "$PROMPT_AGENT" [--model X] [extra...]'
    khác   -> '<cli> "$PROMPT_AGENT" [extra...]'
    """
    roles = roles or load_config()
    r = roles[role]
    if r["cli"].lower() == "openai":
        cli = f"{shlex.quote(sys.executable)} {shlex.quote(str(OPENAI_ADAPTER))}"
    else:
        cli = shlex.quote(resolve_cli(r["cli"]))
    args = []
    if r.get("model"):
        args += ["--model", r["model"]]
    args += list(r.get("extra_args") or [])
    arg_str = " ".join(shlex.quote(a) for a in args)
    template = CLI_TEMPLATES.get(r["cli"].lower(), "{cli} {prompt} {args}")
    if r["cli"].lower() == "openai":
        template = "{cli} {args}"
    return template.format(cli=cli, prompt='"$PROMPT_AGENT"',
                           args=arg_str).replace("  ", " ").strip()


def describe(roles=None):
    """Dòng mô tả cho log — không lộ key."""
    roles = roles or load_config()
    return {role: {"cli": r["cli"] if r["cli"].lower() == "openai" else resolve_cli(r["cli"]),
                   "model": r.get("model", "")}
            for role, r in roles.items()}

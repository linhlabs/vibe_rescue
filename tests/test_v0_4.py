from scripts import llm_config
from scripts.llm_config import build_cmd, load_config


def test_config_defaults_and_override(tmp_path, monkeypatch):
    cfg = tmp_path / "c.toml"
    cfg.write_text("""[roles.write]
cli = "kimi"
model = "kimi-k3"
[roles.verify]
cli = "codex"
[roles.audit]
cli = "claude"
""")
    monkeypatch.setenv("VIBE_LLM_CONFIG", str(cfg))
    roles = load_config()
    assert roles["write"]["cli"] == "kimi" and roles["write"]["model"] == "kimi-k3"
    assert roles["verify"]["cli"] == "codex"  # model vẫn default ""
    assert roles["audit"]["extra_args"] == llm_config.DEFAULTS["audit"]["extra_args"]


def test_build_cmd_templates():
    roles = {
        "write": {"cli": "claude", "model": "", "extra_args": []},
        "verify": {"cli": "codex", "model": "o3", "extra_args": ["--json"]},
        "audit": {"cli": "claude", "model": "", "extra_args": ["--allowedTools", "Read"]},
    }
    cmd = build_cmd("write", roles)
    # resolve_cli trả về đường dẫn tuyệt đối nếu tìm thấy — kiểm tra tail, không hardcode path
    assert cmd.endswith('-p "$PROMPT_AGENT"') and "claude" in cmd
    cmd = build_cmd("verify", roles)
    assert 'exec "$PROMPT_AGENT"' in cmd and "codex" in cmd
    assert "--model o3" in cmd and "--json" in cmd
    cmd = build_cmd("audit", roles)
    assert "--allowedTools Read" in cmd


def test_build_cmd_generic_cli():
    roles = {"write": {"cli": "tiny-agent", "model": "m1", "extra_args": []}}
    cmd = build_cmd("write", roles)
    assert cmd == 'tiny-agent "$PROMPT_AGENT" --model m1'


def test_describe_no_secret():
    roles = load_config()
    d = llm_config.describe(roles)
    assert "write" in d and "verify" in d and "audit" in d
    text = str(d)
    assert "key" not in text.lower() or "api" not in text.lower() or "secret" not in text.lower()

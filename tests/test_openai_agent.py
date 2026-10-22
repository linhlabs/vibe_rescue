"""openai_agent.py: the adapter that lets any OpenAI-style server act as a harness agent.
A scripted fake server stands in for the model; no network, no real key."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from scripts import openai_agent
from scripts.llm_config import build_cmd

KEY = "k-test-0123456789-not-a-real-key"
FAKE_SECRET = "sk-" + "ABCDEFGH" + "IJKLMNOPQRSTUVWX" + "123456"  # built at run time: not a real key


class Fake:
    """Scripted chat server. `script` is a list of assistant messages (or an int HTTP error)."""

    def __init__(self, script):
        self.script, self.requests, self.auth = list(script), [], []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append(body)
                fake.auth.append(self.headers.get("Authorization"))
                step = fake.script.pop(0) if fake.script else {"content": "done"}
                if isinstance(step, int):
                    self.send_response(step)
                    self.end_headers()
                    return
                data = json.dumps({"choices": [{"message": step}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.srv = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_port}/v1"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()


def call(name, **args):
    return {"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def msg(*calls, content=""):
    return {"role": "assistant", "content": content, "tool_calls": list(calls)}


@pytest.fixture
def world(tmp_path, monkeypatch):
    dirs = {n: tmp_path / n for n in ("target", "session", "review", "wt")}
    for d in dirs.values():
        d.mkdir()
    (dirs["target"] / "app.py").write_text(f"print('hi')\nAPI_KEY = '{FAKE_SECRET}'\n")
    (dirs["wt"] / "a.py").write_text("x = 1\n")
    (tmp_path / "PLAN-001.md").write_text("# PLAN\n")
    for k in openai_agent.ENV_NAMES + ("VIBE_AGENT_TASK",):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TARGET_DIR", str(dirs["target"]))
    monkeypatch.setenv("EVIDENCE_DIR", str(dirs["session"]))
    monkeypatch.setenv("REVIEW_DIR", str(dirs["review"]))
    monkeypatch.setenv("TARGET_WT", str(dirs["wt"]))
    monkeypatch.setenv("PLAN", str(tmp_path / "PLAN-001.md"))
    monkeypatch.setenv("VERDICT_FILE", str(tmp_path / "verdict.md"))
    monkeypatch.setenv("PROMPT_AGENT", "You are an auditor. Write into $REVIEW_DIR.")
    monkeypatch.setenv("VIBE_AGENT_API_KEY", KEY)
    return {**dirs, "tmp": tmp_path}


def run(fake, task, *extra):
    return openai_agent.main(["--task", task, "--base-url", fake.url, "--model", "m", *extra])


def tool_results(fake):
    return [m["content"] for r in fake.requests for m in r["messages"] if m["role"] == "tool"]


def test_review_writes_report_files(world, capsys):
    f = Fake([msg(call("write_file", path="README.md", content="# ok\n"),
                  call("write_file", path=str(world["review"] / "PROPOSALS.md"), content="# p\n")),
              {"content": "finished"}])
    assert run(f, "review") == 0
    f.close()
    assert (world["review"] / "README.md").read_text() == "# ok\n"
    assert (world["review"] / "PROPOSALS.md").exists()
    assert f.auth[0] == "Bearer " + KEY
    assert str(world["review"]) in f.requests[0]["messages"][0]["content"]  # $REVIEW_DIR expanded
    assert KEY not in capsys.readouterr().out


def test_review_cannot_write_target_or_escape(world):
    f = Fake([msg(call("write_file", path=str(world["target"] / "app.py"), content="pwn"),
                  call("write_file", path="../escape.md", content="pwn")), {"content": "x"}])
    run(f, "review")
    f.close()
    assert "pwn" not in (world["target"] / "app.py").read_text()
    assert not (world["review"].parent / "escape.md").exists()
    assert all(r.startswith("refused") for r in tool_results(f))


def test_reads_are_confined_and_secrets_masked(world, tmp_path):
    (tmp_path / "outside.txt").write_text("top secret outside")
    (world["target"] / "link.txt").symlink_to(tmp_path / "outside.txt")
    f = Fake([msg(call("read_file", path="app.py"), call("read_file", path="link.txt"),
                  call("read_file", path="../outside.txt")), {"content": "x"}])
    run(f, "review")
    f.close()
    out = tool_results(f)
    assert FAKE_SECRET not in out[0] and "print('hi')" in out[0]
    assert out[1].startswith("refused") and out[2].startswith("refused")
    assert "top secret" not in json.dumps(f.requests)


def test_plan_prints_unfenced_answer_and_cannot_write(world, capsys):
    f = Fake([msg(call("write_file", path="x.md", content="no")),
              {"content": "```markdown\n# PLAN-001: demo\n```"}])
    assert run(f, "plan") == 0
    f.close()
    assert capsys.readouterr().out == "# PLAN-001: demo\n"
    assert "write_file" not in [t["function"]["name"] for t in f.requests[0]["tools"]]
    assert tool_results(f)[0].startswith("error: unknown or disabled tool")


def test_extract_plan_keeps_one_plan_without_narration():
    text = ("I read the files.\n\n```\n# PLAN-002: first\nScope: [a.py]\n```\n"
            "\n# PLAN-003: second\nScope: [b.py]\n")
    out = openai_agent.extract_plan(text)
    assert out == "# PLAN-002: first\nScope: [a.py]\n"
    assert openai_agent.extract_plan("no heading here") == "no heading here\n"


def test_plan_task_message_carries_the_sha(world):
    import subprocess
    t = world["target"]
    for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.email=a@b", "-c", "user.name=n", "commit", "-qm", "i"]):
        subprocess.run(["git", "-C", str(t), *cmd], check=True, capture_output=True)
    sha = subprocess.run(["git", "-C", str(t), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    f = Fake([{"content": "# PLAN-001: x\n"}])
    run(f, "plan")
    f.close()
    assert sha in f.requests[0]["messages"][1]["content"] and "ONE plan" in f.requests[0]["messages"][1]["content"]


def test_verdict_message_carries_receipts(world, monkeypatch):
    monkeypatch.setenv("VIBE_RECEIPTS", "probe [pytest] identical before and after")
    f = Fake([{"content": "ok"}])
    run(f, "verdict")
    f.close()
    text = f.requests[0]["messages"][1]["content"]
    assert "probe [pytest] identical" in text and "relied on these receipts" in text


def test_execute_writes_in_worktree_but_not_git(world):
    (world["wt"] / ".git").mkdir()
    f = Fake([msg(call("write_file", path="a.py", content="x = 2\n"),
                  call("write_file", path=".git/config", content="bad"),
                  call("write_file", path=str(world["target"] / "app.py"), content="bad")), {"content": "x"}])
    run(f, "execute")
    f.close()
    assert (world["wt"] / "a.py").read_text() == "x = 2\n"
    assert not (world["wt"] / ".git" / "config").exists()
    assert "bad" not in (world["target"] / "app.py").read_text()


def test_verdict_and_crosscheck_write_only_their_one_file(world):
    f = Fake([msg(call("write_file", path=str(world["tmp"] / "verdict.md"), content="Result: APPROVE\n"),
                  call("write_file", path="a.py", content="bad")), {"content": "x"}])
    run(f, "verdict")
    f.close()
    assert (world["tmp"] / "verdict.md").read_text() == "Result: APPROVE\n"
    assert (world["wt"] / "a.py").read_text() == "x = 1\n"
    g = Fake([msg(call("write_file", path=str(world["review"] / "EVIDENCE" / "cross-check.md"),
                       content="CROSSCHECK: CLEAN\n"),
                  call("write_file", path=str(world["review"] / "README.md"), content="bad")), {"content": "x"}])
    run(g, "crosscheck")
    g.close()
    assert (world["review"] / "EVIDENCE" / "cross-check.md").exists()
    assert not (world["review"] / "README.md").exists()


def test_server_failure_exits_3_without_leaking_key(world, capsys, monkeypatch):
    monkeypatch.setattr(openai_agent.time, "sleep", lambda s: None)
    f = Fake([500, 500, 500])
    assert run(f, "review") == 3
    f.close()
    cap = capsys.readouterr()
    assert KEY not in cap.out + cap.err and "HTTP 500" in cap.err


def test_step_limit(world):
    f = Fake([msg(call("list_dir", path=".")) for _ in range(5)])
    assert run(f, "review", "--max-steps", "3") == 4
    f.close()


def test_plain_http_to_remote_host_is_refused(world):
    assert openai_agent.main(["--task", "plan", "--base-url", "http://example.com/v1", "--model", "m"]) == 2
    assert openai_agent.main(["--task", "plan", "--base-url", "ftp://x/v1", "--model", "m"]) == 2


def test_no_key_means_no_auth_header(world, monkeypatch):
    monkeypatch.delenv("VIBE_AGENT_API_KEY")
    f = Fake([{"content": "ok"}])
    assert run(f, "plan") == 0
    f.close()
    assert f.auth == [None]


def test_config_openai_role_builds_adapter_command(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[roles.audit]\ncli = "openai"\nmodel = "my/model"\n'
                   'extra_args = ["--base-url", "http://localhost:8000/v1"]\n')
    from scripts.llm_config import load_config
    cmd = build_cmd("audit", load_config(cfg))
    assert "openai_agent.py" in cmd and "--model my/model" in cmd and "--base-url" in cmd
    assert "$PROMPT_AGENT" not in cmd and os.path.exists(openai_agent.__file__)

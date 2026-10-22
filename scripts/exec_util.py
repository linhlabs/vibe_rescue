#!/usr/bin/env python3
"""
exec_util.py — DUY NHẤT chỗ định nghĩa "chạy lệnh con" cho toàn repo (H5, audit v0.3.5).

Trước đây sh()/run() chép 3 bản (rescue_voyage, rescue_loop, scan) với timeout trôi dạt.
Giờ:
  - sh(*argv, ...)        : argv list, KHÔNG shell, KHÔNG expand env — voyage/fanout dùng.
                            Cần shell (pipe/redirect) -> tự truyền "bash", "-c", "cmd > f".
  - sh_expand(cmd_str,..) : chuỗi lệnh, expand $VAR/${VAR} theo env truyền vào, shlex.split,
                            shell=False — rescue_loop dùng (an toàn theo semgrep B602).

Quy ước chung: KHÔNG BAO GIỜ raise khi rc != 0 — caller đọc returncode và quyết
(fail-loud nằm ở caller, không ở runner). Lỗi thật (FileNotFoundError/timeout) vẫn raise.
"""
import re
import shlex
import subprocess

DEFAULT_TIMEOUT = 1800


def sh(*argv, cwd=None, env=None, timeout=DEFAULT_TIMEOUT):
    return subprocess.run([str(a) for a in argv], cwd=cwd, capture_output=True,
                          text=True, timeout=timeout, check=False, env=env)


def sh_expand(cmd, cwd=None, env=None):
    """Chuỗi lệnh -> expand $VAR/${VAR} theo {os.environ, env} -> shlex.split -> chạy."""
    merged = {**__import__("os").environ, **(env or {})}

    def repl(m):
        return merged.get(m.group(1) or m.group(2), m.group(0))
    cmd = re.sub(r"\$(\w+)|\$\{(\w+)\}", repl, cmd) if isinstance(cmd, str) else cmd
    argv = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          check=False, env=merged)

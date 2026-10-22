#!/usr/bin/env python3
"""
dialogue.py — giao thức hỏi-đáp với OWNER (không bao giờ tự quyết thay owner).

Hai chế độ:
  interactive : in câu hỏi ra tty, đọc input() (người dùng có mặt).
  file        : viết QUESTION-<id>.json rồi chờ ANSWER-<id>.json (như vậy
                một LLM agent / automator khác có thể đọc và trả lời theo
                protocol — xem docs/OWNER_PACT.md).

Quy tắc: nếu không nhận được câu trả lời hợp lệ trong timeout -> HARNH
dừng phiên (fail-closed, RULES R11). KHÔNG có chế độ "auto-approve".

Usage (import):
  from scripts.dialogue import Dialogue
  d = Dialogue(mode="file", dir=Path(...))
  choice, note = d.ask("plan", "OK plan?", ["accept", "reject"])
"""
import hashlib
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path


class DialogueReject(Exception):
    """Owner từ chối (choice='reject') — caller dừng bước đó, không tự ý làm tiếp."""


class DialogueTimeout(Exception):
    """Không nhận được answer trong timeout — fail-closed."""


def parse_answer(data, options, question):
    """Only accept an answer bound to the exact outstanding question."""
    if not isinstance(data, dict) or not data.get("choice"):
        raise ValueError("answer thiếu 'choice'")
    for field in ("id", "nonce", "binding"):
        if data.get(field) != question[field]:
            raise ValueError(f"answer {field} không khớp câu hỏi hiện tại")
    choice = str(data["choice"]).strip().lower()
    if choice not in options:
        raise ValueError(f"choice '{choice}' không nằm trong options {options}")
    return choice, str(data.get("note") or "")


class Dialogue:
    def __init__(self, mode="interactive", directory=None):
        self.mode = mode
        self.dir = Path(directory) if directory else Path(".")
        self.dir.mkdir(parents=True, exist_ok=True)
        self._n = 0

    def ask(self, phase, question, options, context=None, timeout=300, id=None):
        """Trả (choice, note). Chỉ trả hợp lệ; reject -> raise DialogueReject."""
        options = [o.lower() for o in options]
        prefix = id or f"Q{self._n:03d}"
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", prefix):
            raise ValueError("question id không hợp lệ")
        qid = f"{prefix}-{secrets.token_hex(12)}"
        self._n += 1
        nonce = secrets.token_hex(16)
        binding = hashlib.sha256(json.dumps(
            {"id": qid, "phase": phase, "question": question,
             "options": options, "context": context or {}},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        payload = {"id": qid, "phase": phase, "question": question,
                   "options": options, "context": context or {},
                   "nonce": nonce, "binding": binding,
                   "answer_file": f"ANSWER-{qid}.json"}
        if self.mode == "interactive":
            return self._ask_interactive(payload, options)
        return self._ask_file(payload, options, timeout)

    # ---------- interactive ----------
    def _ask_interactive(self, payload, options):
        print(f"\n[OWNER:{payload['phase']}] {payload['question']}")
        print(f"  options: {options}")
        sys.stdout.flush()
        for _ in range(3):
            line = input("  > ").strip().lower()
            if line in options:
                return line, ""
            if line in ("quit", "abort"):
                raise DialogueReject("owner abort")
            print("  (nhập một trong:", ", ".join(options), ")")
        raise DialogueTimeout("3 lần nhập sai — dừng phiên (fail-closed)")

    # ---------- file ----------
    def _ask_file(self, payload, options, timeout):
        if timeout <= 0:
            raise ValueError("file dialogue cần timeout dương")
        qpath = self.dir / f"QUESTION-{payload['id']}.json"
        apath = self.dir / f"ANSWER-{payload['id']}.json"
        temporary = qpath.with_name(qpath.name + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
        os.replace(temporary, qpath)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if apath.exists():
                try:
                    data = json.loads(apath.read_text())
                    choice, note = parse_answer(data, options, payload)
                    apath.unlink()  # one-time answer; never replay it in another ask
                    return choice, note
                except (ValueError, json.JSONDecodeError):
                    apath.unlink(missing_ok=True)  # stale/invalid -> wait for a fresh answer
                except DialogueReject:
                    raise
            time.sleep(0.1)
        raise DialogueTimeout(f"hết hạn {timeout}s chờ {apath.name}")

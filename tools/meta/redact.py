#!/usr/bin/env python3
"""
redact.py — che giá trị bí mật (khóa API / token) trong mọi artifact do harness ghi ra.

Vì sao tồn tại: harness quét target có thể chạm khóa thật (file .env, model_inventory,
báo cáo gitleaks gốc...). Nếu giữ nguyên giá trị trong evidence thì harness tự nhân rộng
rò rỉ mà nó đang đi tìm (audit v0.3.5 — phát hiện H1). Nguyên tắc: **che ở nguồn**, mọi
tầng ghi artifact đều gọi bộ pattern DUY NHẤT ở đây:
  - tools/meta/scan.py::emit()      -> raw/<tool>.json
  - scripts/merge_findings.py       -> findings.json / findings.sarif
  - tools/meta/context_pack.py      -> context.txt

Phạm vi: che theo lớp CƠ KHÍ (regex trên giá trị kiểu khóa) — đúng tầng cơ khí được
phép dùng regex (RULES R6), không đụng nội dung có ý nghĩa pháp lý. Che giá trị, GIỮ tên
biến (OPENAI_API_KEY=[REDACTED]) để evidence vẫn đọc hiểu được.

CLI dùng lại cho từng file có sẵn:
  python3 tools/meta/redact.py FILE...   # che NGAY TRONG file (dùng để dọn artifact cũ)
"""
import re
import sys
from pathlib import Path

PLACEHOLDER = "[REDACTED]"

# Pattern giá trị key-like — bảo thủ: chỉ bắt định dạng khóa phổ biến, không bắt chuỗi
# hex/base64 chung chung (tránh xóa nhầm sha256, id máy... trong evidence).
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_\-]{12,}",                                      # OpenAI-style
    r"AKIA[0-9A-Z]{16}",                                            # AWS access key id
    r"ghp_[A-Za-z0-9]{20,}",                                        # GitHub PAT (cổ)
    r"github_pat_[A-Za-z0-9_]{20,}",                                # GitHub PAT (fine-grained)
    r"xox[baprs]-[A-Za-z0-9\-]{10,}",                               # Slack token
    r"AIza[0-9A-Za-z_\-]{30,}",                                     # Google API key
    r"dapi[0-9a-f]{28,}",                                           # Databricks token
    r"glpat-[A-Za-z0-9_\-]{15,}",                                   # GitLab PAT
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
]
_ASSIGN_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|passwd|password)\b(\s*[:=]\s*['\"]?)([^\s'\"]{8,})")
_COMPILED = [re.compile(p) for p in SECRET_PATTERNS]
MAX_REDACT_FILE_BYTES = 64 * 1024 * 1024


def mask_text(s):
    """Che mọi giá trị key-like trong chuỗi. Chuỗi thường (code, md5, sha256) giữ nguyên."""
    if not s:
        return s
    for rx in _COMPILED:
        s = rx.sub(PLACEHOLDER, s)
    return _ASSIGN_RE.sub(lambda m: m.group(1) + m.group(2) + PLACEHOLDER, s)


def mask_obj(o):
    """Đệ quy qua dict/list/tuple — che mọi giá trị str (JSON tùy chỉnh an toàn)."""
    if isinstance(o, str):
        return mask_text(o)
    if isinstance(o, dict):
        return {k: mask_obj(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return type(o)(mask_obj(v) for v in o)
    return o


def mask_findings(findings):
    """Che evidence/message của list findings chuẩn (rule/severity/file/line/...)."""
    for f in findings or []:
        if isinstance(f, dict):
            for k in ("evidence", "message"):
                if isinstance(f.get(k), str):
                    f[k] = mask_text(f[k])
    return findings


def mask_file(p):
    """Che NGAY TRONG file văn bản. Trả về True nếu có thay đổi."""
    p = Path(p)
    if not p.exists() or p.stat().st_size > MAX_REDACT_FILE_BYTES:
        return False
    text = p.read_text(errors="ignore")
    masked = mask_text(text)
    if masked != text:
        p.write_text(masked)
        return True
    return False


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    for a in argv:
        p = Path(a)
        if not p.exists():
            print(f"[WARN] bỏ qua (không tồn tại): {p}")
            continue
        if p.stat().st_size > MAX_REDACT_FILE_BYTES:
            print(f"[WARN] bỏ qua (file > 64MB): {p}")
            continue
        print(("[REDACT] " if mask_file(p) else "[clean]  ") + str(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())

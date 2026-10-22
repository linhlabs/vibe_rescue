# Fixture semgrep — chứa vi phạm (để test rule pack bắt được; KHÔNG phải code chạy)
import subprocess
import tarfile

PHONE = "0391234567"
CCCD = "079123456789"


def run_shell(cmd):
    return subprocess.run(cmd, check=False, shell=True)  # noqa: PLW1510 - fixture chủ đích


def run_eval(expr):
    return eval(expr)  # violation: security-eval-exec


def load_pickle(p):
    import pickle
    return pickle.loads(p)  # violation: security-pickle-insecure


def unpack(a):
    return tarfile.extractall(a)  # violation: security-archive-extract


KEY = "sk-ABCDEFGHIJKLMNOPQRSTUVWX123456"  # violation: security-hardcoded-secret

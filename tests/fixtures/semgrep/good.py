# Fixture sạch — không được có finding (trừ khi rule quá tham)
import subprocess

if __name__ == "__main__":
    r = subprocess.run(["echo", "ok"], capture_output=True, text=True, check=False)
    assert r.returncode == 0

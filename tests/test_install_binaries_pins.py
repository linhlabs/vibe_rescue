"""The binary installer must verify pinned archive bytes before extraction."""
import hashlib
import io

import pytest

from scripts import install_binaries


def test_binary_archive_checksum_mismatch_never_installs(tmp_path, monkeypatch):
    conf = {"url": "https://github.com/google/osv-scanner/releases", "tag": "v1",
            "asset": "osv-scanner_linux_amd64", "sha256": "0" * 64}
    release = {"tag_name": "v1", "assets": [{"name": conf["asset"],
                                            "browser_download_url": "https://example.test/file"}]}
    monkeypatch.setattr(install_binaries, "pinned_release", lambda *_: release)
    monkeypatch.setattr(install_binaries.urllib.request, "urlopen", lambda *_args, **_kw: io.BytesIO(b"bad"))
    with pytest.raises(ValueError, match="checksum"):
        install_binaries.install_one("osv-scanner", conf, tmp_path, dry=False)
    assert not (tmp_path / "osv-scanner").exists()


def test_binary_pin_installs_exact_verified_raw_asset(tmp_path, monkeypatch):
    payload = b"#!/bin/sh\nexit 0\n"
    conf = {"url": "https://github.com/google/osv-scanner/releases", "tag": "v1",
            "asset": "osv-scanner_linux_amd64", "sha256": hashlib.sha256(payload).hexdigest()}
    release = {"tag_name": "v1", "assets": [{"name": conf["asset"],
                                            "browser_download_url": "https://example.test/file"}]}
    monkeypatch.setattr(install_binaries, "pinned_release", lambda *_: release)
    monkeypatch.setattr(install_binaries.urllib.request, "urlopen", lambda *_args, **_kw: io.BytesIO(payload))
    install_binaries.install_one("osv-scanner", conf, tmp_path, dry=False)
    assert (tmp_path / "osv-scanner").read_bytes() == payload

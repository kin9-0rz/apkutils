import os
import zipfile

import pytest

from apkutils._certificates import CertificateError, Certificates

FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))
ANDROID_DEBUG = "C=US, O=Android, CN=Android Debug"


def _entries(fixture):
    with zipfile.ZipFile(os.path.join(FIXTURES, fixture)) as zf:
        return [
            (name, zf.read(name))
            for name in zf.namelist()
            if name.startswith("META-INF/") and name.endswith((".DSA", ".RSA"))
        ]


def test_empty_entries_yield_no_certs():
    assert Certificates([]).content == []


def test_text_signature_files_are_skipped():
    assert Certificates([("META-INF/notes.txt", b"hello")]).content == []


def test_reads_cert_with_each_hash():
    entries = _entries("kotlin-app.zip")

    assert Certificates(entries, _hash="md5").content == [
        (ANDROID_DEBUG, "ea9596d642069cfac0a1b99df3ea9f38")
    ]
    assert Certificates(entries, _hash="sha1").content == [
        (ANDROID_DEBUG, "73c066b2205e938e2a9e25eb81849c02a0565441")
    ]
    assert Certificates(entries, _hash="sha256").content == [
        (
            ANDROID_DEBUG,
            "299d8de477962c781714eaab76a90c287bb67123cd2909de0f743838cad264e4",
        )
    ]


def test_broken_signature_raises():
    with zipfile.ZipFile(os.path.join(FIXTURES, "kotlin-app.zip")) as zf:
        truncated = zf.read("META-INF/CERT.RSA")[:40]

    with pytest.raises(CertificateError):
        Certificates([("META-INF/BROKEN.RSA", truncated)])

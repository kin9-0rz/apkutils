import os
import zipfile

import pytest

from apkutils._manifest import ManifestError, ManifestReader

FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))


def _manifest_bytes(fixture):
    with zipfile.ZipFile(os.path.join(FIXTURES, fixture)) as zf:
        return zf.read("AndroidManifest.xml")


def test_absent_manifest_keeps_defaults():
    m = ManifestReader()

    assert m.axml is None
    assert m.raw == ""
    assert m.package_name == ""
    assert m.version_name == ""
    assert m.version_code is None
    assert m.min_sdk_version == 1
    assert m.target_sdk_version == 1
    assert m.max_sdk_version == 0xFF
    assert m.main_activities == []
    assert m.application == ""
    assert m.application_icon_addr == ""
    assert m.application_label_id == ""
    assert m.activities_icon_addrs == []


@pytest.mark.parametrize("bad", [b"not an axml", b"", b"\x03\x00\x08\x00"])
def test_unparsable_manifest_raises(bad):
    with pytest.raises(ManifestError):
        ManifestReader(bad)


def test_reads_package_version_and_launcher():
    m = ManifestReader(_manifest_bytes("test.zip"))

    assert m.package_name == "com.example.hellojni"
    assert m.version_name == "1.0"
    assert m.version_code == "1"
    assert m.main_activities == ["com.example.hellojni.MainActivity"]
    assert m.application == ""
    assert m.application_icon_addr == "0x7f020000"
    assert m.application_label_id == "0x7f050000"
    assert m.axml is not None
    assert "com.example.hellojni" in m.raw


def test_reads_application_name_and_missing_target_sdk():
    m = ManifestReader(_manifest_bytes("test_am_0908.zip"))

    assert m.package_name == "bsp.yzxnk.qwolcp.ZHQ2017_001"
    assert m.application == "myyt.Vrp9hm9sc2t4fox981tqjz83ho7juoxq"
    assert m.min_sdk_version == "9"
    # 清单没写 maxSdkVersion / targetSdkVersion 时回落到默认值
    assert m.target_sdk_version == -1
    assert m.max_sdk_version == 0xFF


def test_reads_relative_launcher_name():
    m = ManifestReader(_manifest_bytes("kotlin-app.zip"))

    assert m.package_name == "com.example.kotlinapp"
    assert m.main_activities == ["com.example.kotlinapp.MainActivity"]
    assert m.target_sdk_version == "28"

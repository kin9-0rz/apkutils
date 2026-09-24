import logging
import os
import zipfile

import pytest

from apkutils._manifest import ManifestError, ManifestReader, _as_label
from apkutils.axml import AXMLPrinter

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


def test_as_label_normalizes_ref_but_keeps_literal():
    # 资源引用归一成小写地址
    assert _as_label("@7F050000") == "0x7f050000"
    # 字面字符串（含大小写）原样保留，不能被小写化
    assert _as_label("米兰") == "米兰"
    assert _as_label("MyApp") == "MyApp"
    assert _as_label("") == ""
    assert _as_label(None) == ""


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


def test_packed_trap_attributes_are_dropped_quietly(caplog):
    """百度加固（np_trap）注入的 decoy 属性：安静丢弃，且不影响正常字段。

    回归：这类清单曾对每个 decoy 属性打 3 条 warning（近 2000 行），
    并把属性名改写成 ``________manifest____android_name`` 之类的垃圾。
    """
    data = _manifest_bytes("packed_trap.zip")

    with caplog.at_level(logging.WARNING, logger="axml"):
        m = ManifestReader(data)

    assert m.package_name == "singansfg.lwecthodnj.sdancsuhsfj"
    assert m.version_code == "172"
    assert m.version_name == "1.0.0"
    assert m.min_sdk_version == "21"
    assert m.target_sdk_version == "28"

    # decoy 属性被丢弃，不再以垃圾名写进清单
    assert "____" not in m.raw

    # 不再产生“无效名字/未知命名空间”告警
    trap_records = [
        r
        for r in caplog.records
        if "Invalid start for name" in r.getMessage()
        or "contains invalid characters" in r.getMessage()
        or "unknown namespace prefix" in r.getMessage()
    ]
    assert trap_records == []

    # 丢弃 decoy 不等于放过加固文件：仍需标记为 packed
    assert AXMLPrinter(data, True).is_packed() is True

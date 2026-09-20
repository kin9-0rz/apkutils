import io
import os
import zipfile

import pytest

from apkutils import APK
from apkutils._dex import DexError
from apkutils._manifest import ManifestError
from apkutils._resources import ResourceTableError


class TestAPK(object):
    def setup_class(self):
        file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "fixtures", "test.zip")
        )
        self.apk = APK.from_file(file_path).parse_dex().parse_resource()

    def teardown_class(self):
        self.apk.close()

    def test_manifest(self):
        assert '".MainActivity"' in self.apk.get_manifest()
        assert self.apk.get_package_name() == "com.example.hellojni"
        assert self.apk.get_manifest_application() == ""
        assert self.apk.get_manifest_main_activities() == [
            "com.example.hellojni.MainActivity"
        ]

    def test_get_strings(self):
        assert len(self.apk.get_dex_strings()) == 8594

    def test_get_subfiles(self):
        for item in self.apk.get_subfiles():
            if item.get("crc") == "FA974826":
                assert "AndroidManifest.xml" in item.get("name")
                break

    def test_get_dex_opcodes(self):
        for item in self.apk.get_dex_opcodes():
            class_name = item.get("class_name")
            method_name = item.get("method_name")
            opcodes = item.get("opcodes")

            if (
                class_name == "com/example/hellojni/MainActivity"
                and method_name == "onCreate"
            ):
                assert opcodes == "6F156E0E"
                break

    def test_get_app_icon(self):
        icons = self.apk.get_app_icons()
        assert "res/drawable-xxhdpi-v4/ic_launcher.png" in icons

    def test_app_name(self):
        assert self.apk.app_name == "hellojni"


def test_instances_do_not_share_archive():
    # 先打开 A、再打开 B，随后读 A 必须仍读到 A 自己的归档。
    # 旧实现把 ZipFile 存在类属性上，A 会读到 B 的包名。
    fixtures = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))
    apk_a = APK.from_file(os.path.join(fixtures, "test.zip"))
    apk_b = APK.from_file(os.path.join(fixtures, "test_am_0908.zip"))
    try:
        assert apk_a.parse_resource().get_package_name() == "com.example.hellojni"
        assert (
            apk_b.parse_resource().get_package_name()
            == "bsp.yzxnk.qwolcp.ZHQ2017_001"
        )
    finally:
        apk_a.close()
        apk_b.close()


def _apk_bytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_default_swallows_manifest_error():
    data = _apk_bytes({"AndroidManifest.xml": b"not an axml"})
    with APK.from_bytes(data) as apk:
        assert apk.parse_resource().get_manifest() == ""


def test_strict_surfaces_manifest_error():
    data = _apk_bytes({"AndroidManifest.xml": b"not an axml"})
    with APK.from_bytes(data, strict=True) as apk:
        with pytest.raises(ManifestError):
            apk.parse_resource()


def test_default_swallows_resource_error():
    data = _apk_bytes({"resources.arsc": b"not an arsc"})
    with APK.from_bytes(data) as apk:
        assert apk.parse_resource().get_arsc() is None


def test_strict_surfaces_resource_error():
    data = _apk_bytes({"resources.arsc": b"not an arsc"})
    with APK.from_bytes(data, strict=True) as apk:
        with pytest.raises(ResourceTableError):
            apk.parse_resource()


def test_default_swallows_dex_error():
    data = _apk_bytes({"classes.dex": b"dex\n035\x00"})
    with APK.from_bytes(data) as apk:
        assert apk.parse_dex().get_dex_strings() == []


def test_strict_surfaces_dex_error():
    data = _apk_bytes({"classes.dex": b"dex\n035\x00"})
    with APK.from_bytes(data, strict=True) as apk:
        with pytest.raises(DexError):
            apk.parse_dex()


def test_close_is_safe_without_archive():
    apk = APK()
    apk.close()
    apk.close()


def test_failures_are_recorded_not_printed(capsys):
    data = _apk_bytes(
        {"AndroidManifest.xml": b"not an axml", "resources.arsc": b"not an arsc"}
    )

    with APK.from_bytes(data) as apk:
        apk.parse_resource()
        assert {err.part for err in apk.errors} == {"manifest", "arsc"}

    assert capsys.readouterr().out == ""


def test_strict_records_the_error_before_raising():
    data = _apk_bytes({"AndroidManifest.xml": b"not an axml"})

    with APK.from_bytes(data, strict=True) as apk:
        with pytest.raises(ManifestError):
            apk.parse_resource()

    assert [err.part for err in apk.errors] == ["manifest"]


def test_no_manifest_is_only_parsed_once(monkeypatch):
    with APK.from_bytes(_apk_bytes({"dummy.txt": b"x"})) as apk:
        calls = []
        original = apk._init_manifest

        def spy():
            calls.append(1)
            return original()

        monkeypatch.setattr(apk, "_init_manifest", spy)

        assert apk.get_manifest() == ""
        assert apk.get_manifest() == ""
        assert apk.get_manifest() == ""

        assert len(calls) == 1

import os
import zipfile

import pytest

from apkutils._manifest import ManifestReader
from apkutils._metadata import AppMetadata, AppMetadataError
from apkutils._resources import ResourceTable

FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))


def _inputs(fixture):
    """用一个真实 APK 造出 AppMetadata 需要的三样输入。"""
    with zipfile.ZipFile(os.path.join(FIXTURES, fixture)) as zf:
        manifest = ManifestReader(zf.read("AndroidManifest.xml"))
        resources = ResourceTable(zf.read("resources.arsc"))
        subfiles = [{"name": name} for name in zf.namelist()]
    return manifest, resources, subfiles


def test_derives_icons_and_app_name():
    manifest, resources, subfiles = _inputs("test.zip")

    meta = AppMetadata(manifest, resources, subfiles)

    assert "res/drawable-xxhdpi-v4/ic_launcher.png" in meta.icons
    assert meta.app_name == "hellojni"


def test_no_resource_table_means_empty():
    meta = AppMetadata(ManifestReader(), ResourceTable(), [])

    assert meta.icons == []
    assert meta.app_name is None


def test_bad_icon_address_raises():
    manifest, resources, subfiles = _inputs("test.zip")
    manifest.application_icon_addr = "0xdeadbeef"

    with pytest.raises(AppMetadataError):
        AppMetadata(manifest, resources, subfiles)

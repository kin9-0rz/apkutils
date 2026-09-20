import os
import zipfile
from types import SimpleNamespace

from apkutils._subfiles import Subfiles

FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))


def test_lists_every_entry_with_type_time_crc():
    with zipfile.ZipFile(os.path.join(FIXTURES, "test.zip")) as zf:
        names = zf.namelist()
        items = Subfiles(zf).items

    assert len(items) == 14
    assert [item["name"] for item in items] == names
    assert items[0] == {
        "name": "AndroidManifest.xml",
        "type": "application/vnd.android.arsc",
        "time": "20170813184636",
        "crc": "627E516B",
    }


def test_crc_is_always_eight_hex_digits():
    with zipfile.ZipFile(os.path.join(FIXTURES, "kotlin-app.zip")) as zf:
        items = Subfiles(zf).items

    assert items
    assert all(len(item["crc"]) == 8 for item in items)


class _FakeArchive:
    """只实现 Subfiles 需要的 handle interface，用来触发逐条失败。"""

    def namelist(self):
        return ["good.txt", "bad.txt"]

    def read(self, name):
        if name == "bad.txt":
            raise ValueError("无法读取")
        return b"hello"

    def getinfo(self, name):
        return SimpleNamespace(date_time=(2020, 1, 2, 3, 4, 5), CRC=0xAB)


def test_skipped_entries_are_collected_not_dropped():
    subfiles = Subfiles(_FakeArchive())

    assert [item["name"] for item in subfiles.items] == ["good.txt"]
    assert [name for name, _ in subfiles.skipped] == ["bad.txt"]
    assert isinstance(subfiles.skipped[0][1], ValueError)

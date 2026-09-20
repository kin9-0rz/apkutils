import os
import zipfile

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

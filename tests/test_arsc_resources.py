import hashlib
import os
import zipfile

import pytest

from apkutils.axml import ARSCParser, Resource

FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))

KINDS = ["public", "string", "id", "bool", "integer", "color", "dimen"]

# 8 个 emitter 的输出指纹。7 个扁平 emitter 收敛到同一个 formatter 时，
# 用这些值守住"输出字节完全不变"。改格式必须是有意的，并同步更新这里。
GOLDEN = {
    "test.zip": {
        "public": "9d2918969211f6be4a1706918416886e",
        "string": "d57f95d69d18e40b9d80e37f20005b04",
        "id": "30eace6bc047936bf0772ef75da0b335",
        "bool": "143e12f5606a1da161adb7cb7fa6aa92",
        "integer": "143e12f5606a1da161adb7cb7fa6aa92",
        "color": "143e12f5606a1da161adb7cb7fa6aa92",
        "dimen": "5a0492ac8636244cbeb73211ea953c0b",
        "strings": "7865decac6c0859dd263fb8e1dba52d8",
    },
    "kotlin-app.zip": {
        "public": "038ce2b8f7c9d7aaca4727299ef34e9a",
        "string": "813928333622302289cdba4be8544312",
        "id": "3b09e9f36d5fca1d4f77cd8836cbdf85",
        "bool": "73fc41b2c7c1fd8a138f11d78fba0442",
        "integer": "54c82f55a3f88724d039d64100d0010b",
        "color": "5268149b9ffc38b3477b87c57fede9d3",
        "dimen": "7aba31da2251fb84c126a0d1cc76b971",
        "strings": "0e1ab88ff110639ae2d422b9017926f8",
    },
}


def _parser(fixture):
    with zipfile.ZipFile(os.path.join(FIXTURES, fixture)) as zf:
        return ARSCParser(zf.read("resources.arsc"))


def _emit(parser, package, kind):
    if kind == "strings":
        return parser.get_strings_resources()
    return getattr(parser, "get_%s_resources" % kind)(package)


@pytest.mark.parametrize("fixture", sorted(GOLDEN))
def test_emitter_output_is_byte_stable(fixture):
    parser = _parser(fixture)
    package = parser.get_packages_names()[0]

    actual = {
        kind: hashlib.md5(_emit(parser, package, kind)).hexdigest()
        for kind in KINDS + ["strings"]
    }

    assert actual == GOLDEN[fixture]


def test_flat_emitters_have_expected_content():
    parser = _parser("test.zip")
    package = parser.get_packages_names()[0]

    assert b'<string name="app_name">hellojni</string>' in _emit(
        parser, package, "string"
    )
    assert (
        b'<item type="id" name="action_settings">false</item>'
        in _emit(parser, package, "id")
    )
    assert (
        b'<public type="drawable" name="ic_launcher" id="0x7f020000" />'
        in _emit(parser, package, "public")
    )
    assert (
        b'<dimen name="activity_horizontal_margin">16.0dip</dimen>'
        in _emit(parser, package, "dimen")
    )


def test_emitters_that_have_no_data_still_emit_empty_resources():
    parser = _parser("test.zip")
    package = parser.get_packages_names()[0]

    for kind in ("bool", "integer", "color"):
        assert _emit(parser, package, kind) == (
            '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n</resources>\n'
        ).encode("utf-8")


def test_get_resources_public_records():
    parser = _parser("test.zip")
    package = parser.get_packages_names()[0]

    records = parser.get_resources(package, "public")

    # public 的 kind 是条目的真实资源类型，id 是资源 id
    assert Resource("drawable", "ic_launcher", None, 0x7F020000) in records


def test_get_resources_typed_records():
    parser = _parser("test.zip")
    package = parser.get_packages_names()[0]

    assert Resource("string", "app_name", "hellojni", None) in parser.get_resources(
        package, "string"
    )
    assert Resource("id", "action_settings", "false", None) in parser.get_resources(
        package, "id"
    )


def test_get_resources_unknown_kind_or_package_is_empty():
    parser = _parser("test.zip")
    package = parser.get_packages_names()[0]

    assert parser.get_resources(package, "no_such_kind") == []
    assert parser.get_resources("com.no.such.package", "string") == []

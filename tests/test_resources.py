import os
import zipfile

import pytest

from apkutils._resources import ResourceTable, ResourceTableError

FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))
PACKAGE = "com.example.hellojni"


def _arsc_bytes(fixture):
    with zipfile.ZipFile(os.path.join(FIXTURES, fixture)) as zf:
        return zf.read("resources.arsc")


def test_absent_table_returns_none():
    t = ResourceTable()

    assert t.parser is None
    assert t.package_name == ""
    assert t.resolve_reference(PACKAGE, "0x7f020000") is None
    assert t.string_by_name(PACKAGE, "app_name") is None


@pytest.mark.parametrize("bad", [b"not an arsc", b"", b"\x02\x00\x0c\x00"])
def test_unparsable_table_raises(bad):
    with pytest.raises(ResourceTableError):
        ResourceTable(bad)


def test_resolves_address_to_name_and_type():
    t = ResourceTable(_arsc_bytes("test.zip"))

    assert t.package_name == PACKAGE
    assert t.resolve_reference(PACKAGE, "0x7f020000") == ("ic_launcher", "drawable")
    assert t.resolve_reference(PACKAGE, "0x7f050000") == ("app_name", "string")


def test_reads_string_by_name():
    t = ResourceTable(_arsc_bytes("test.zip"))

    assert t.string_by_name(PACKAGE, "app_name") == "hellojni"


def test_unknown_lookups_return_none():
    t = ResourceTable(_arsc_bytes("test.zip"))

    assert t.resolve_reference(PACKAGE, "0xdeadbeef") is None
    assert t.resolve_reference(PACKAGE, "") is None
    assert t.resolve_reference("com.other.package", "0x7f020000") is None
    assert t.string_by_name(PACKAGE, "no_such_name") is None

"""2.0.5 的 dex 缓存属性（``opcodes`` / ``strings_refx`` / ``dex_files``）以只读 property 保留。

这三个属性在 2.0.5 里是 ``APK.__init__`` 赋的普通属性，缓存随后移进了私有 ``DexReader``。
顶住旧形状，是为了让读属性的下游拿到值而不是 ``AttributeError``；写属性则不再支持。
"""

import os

import pytest

from apkutils import APK

FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))


def _from_fixture(name):
    return APK.from_file(os.path.join(FIXTURES, name))


def test_unparsed_dex_keeps_2_0_5_defaults():
    with _from_fixture("test.zip") as apk:
        assert apk.opcodes is None
        assert apk.strings_refx is None
        assert apk.dex_files == []


def test_properties_mirror_getters():
    with _from_fixture("test.zip") as apk:
        opcodes = apk.get_dex_opcodes()
        strings_refx = apk.get_dex_strings_refx()
        dex_files = apk.get_dex_files()

        # 同一对象：旧版属性就是 getter 写回的缓存，下游的别名观察不到差别
        assert apk.opcodes is opcodes
        assert apk.strings_refx is strings_refx
        assert apk.dex_files == dex_files


def test_properties_never_trigger_parsing():
    with _from_fixture("i15.zip") as apk:
        # 只读属性沿用旧版语义：不解析 dex（2.0.5 的 opcodes 初值就是 None）
        assert apk.opcodes is None
        assert apk.strings_refx is None


def test_properties_are_read_only():
    with _from_fixture("test.zip") as apk:
        with pytest.raises(AttributeError):
            apk.opcodes = []
        with pytest.raises(AttributeError):
            apk.strings_refx = {}

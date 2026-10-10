import logging
import os
import zipfile

import pytest
from bs4 import BeautifulSoup

from apkutils._manifest import (
    ManifestError,
    ManifestReader,
    _as_label,
    _attr,
    _expand_name,
    _has_launcher_filter,
    _is_disabled,
)
from apkutils.axml import AXMLPrinter

FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))

_NS = 'xmlns:android="http://schemas.android.com/apk/res/android"'


def _manifest_bytes(fixture):
    with zipfile.ZipFile(os.path.join(FIXTURES, fixture)) as zf:
        return zf.read("AndroidManifest.xml")


def _component(xml):
    """把单个 activity / activity-alias 片段套进最小 manifest，返回该 Tag。"""
    soup = BeautifulSoup(
        '<manifest {}><application>{}</application></manifest>'.format(_NS, xml),
        "lxml-xml",
    )
    return soup.application.find()


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
    assert m.aliases == {}
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


def test_expand_name_rules():
    # 以 . 开头 → 包名 + 名字
    assert _expand_name("com.foo", ".Main") == "com.foo.Main"
    # 不含 . → 包名 + . + 名字
    assert _expand_name("com.foo", "Main") == "com.foo.Main"
    # 已含 . 但不是 . 开头 → 原样
    assert _expand_name("com.foo", "com.foo.Main") == "com.foo.Main"
    assert _expand_name("com.foo", "other.pkg.Main") == "other.pkg.Main"
    # 缺失 → None，调用方据此跳过
    assert _expand_name("com.foo", None) is None
    assert _expand_name("com.foo", "") is None


def test_launcher_filter_requires_main_and_launcher_in_same_filter():
    assert _has_launcher_filter(
        _component(
            '<activity android:name=".A"><intent-filter>'
            '<action android:name="android.intent.action.MAIN"/>'
            '<category android:name="android.intent.category.LAUNCHER"/>'
            "</intent-filter></activity>"
        )
    )


def test_launcher_filter_split_across_filters_is_not_launcher():
    # 两个 intent-filter 各声明一个：Android 语义下不是启动入口
    assert not _has_launcher_filter(
        _component(
            '<activity android:name=".A">'
            '<intent-filter><action android:name="android.intent.action.MAIN"/></intent-filter>'
            '<intent-filter><category android:name="android.intent.category.LAUNCHER"/></intent-filter>'
            "</activity>"
        )
    )


def test_launcher_filter_requires_both_parts():
    assert not _has_launcher_filter(
        _component(
            '<activity android:name=".A"><intent-filter>'
            '<action android:name="android.intent.action.MAIN"/>'
            "</intent-filter></activity>"
        )
    )
    assert not _has_launcher_filter(
        _component(
            '<activity android:name=".A"><intent-filter>'
            '<category android:name="android.intent.category.LAUNCHER"/>'
            "</intent-filter></activity>"
        )
    )
    assert not _has_launcher_filter(_component('<activity android:name=".A"/>'))


def test_launcher_filter_matches_action_name_exactly():
    # 子串法会误命中 android.intent.action.MAIN_KILL
    assert not _has_launcher_filter(
        _component(
            '<activity android:name=".A"><intent-filter>'
            '<action android:name="android.intent.action.MAIN_KILL"/>'
            '<category android:name="android.intent.category.LAUNCHER"/>'
            "</intent-filter></activity>"
        )
    )


def test_is_disabled_reads_string_value():
    assert _is_disabled(
        _component('<activity android:name=".A" android:enabled="false"/>')
    )
    assert not _is_disabled(
        _component('<activity android:name=".A" android:enabled="true"/>')
    )
    assert not _is_disabled(_component('<activity android:name=".A"/>'))


def test_attr_tolerates_stripped_namespace_prefix():
    # 没有 xmlns:android 声明时 lxml 会把 android: 前缀剥掉，key 变成无前缀
    soup = BeautifulSoup(
        '<manifest package="com.foo"><application>'
        '<activity name=".A" enabled="false"/>'
        "</application></manifest>",
        "lxml-xml",
    )
    item = soup.activity
    assert _attr(item, "name") == ".A"
    assert _attr(item, "enabled") == "false"


def test_attr_tolerates_renamed_namespace_prefix():
    """前缀被改名时（``ns0:``）仍能取到属性值。

    回归：加固工具抹掉字符串池里的 ``android`` 前缀字符串后，lxml 会自己另起
    一个编号不定的前缀。``_attr`` 只认 ``android:`` / 无前缀，于是 versionCode、
    versionName、minSdkVersion 全部读成 ``None``，回落到默认值 1 / -1。
    """
    soup = BeautifulSoup(
        '<manifest xmlns:ns0="http://schemas.android.com/apk/res/android" '
        'ns0:versionCode="114"><application>'
        '<activity ns0:name=".A" ns0:enabled="false"/>'
        "</application></manifest>",
        "lxml-xml",
    )
    item = soup.activity
    assert _attr(item, "name") == ".A"
    assert _attr(item, "enabled") == "false"
    assert _attr(soup.manifest, "versionCode") == "114"
    assert _attr(item, "missing") is None


def test_main_activities_preserve_document_order():
    """入口判定对 activity / activity-alias 一视同仁，输出保持文档序。

    回归：曾按 ("activity", "activity-alias") 两轮遍历，alias 排在 activity
    前面时输出会被重排成 activity 组 → alias 组。
    """
    m = ManifestReader()
    m.package_name = "com.foo"
    soup = BeautifulSoup(
        '<manifest {}><application>'
        '<activity-alias android:name=".Alias" android:targetActivity=".Real">'
        '<intent-filter><action android:name="android.intent.action.MAIN"/>'
        '<category android:name="android.intent.category.LAUNCHER"/></intent-filter>'
        '</activity-alias>'
        '<activity android:name=".First">'
        '<intent-filter><action android:name="android.intent.action.MAIN"/>'
        '<category android:name="android.intent.category.LAUNCHER"/></intent-filter>'
        '</activity>'
        '</application></manifest>'.format(_NS),
        "lxml-xml",
    )
    m._find_activities(soup)

    assert m.main_activities == ["com.foo.Alias", "com.foo.First"]


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


def test_youtube_alias_target_is_not_expanded_into_main_activities():
    m = ManifestReader(_manifest_bytes("youtube.zip"))

    # 入口只保留别名本身，targetActivity 不展开
    assert m.main_activities == [
        "com.google.android.youtube.app.honeycomb.Shell$HomeActivity"
    ]
    # 别名映射覆盖全部 activity-alias（含非入口的），target 补全为全限定名
    assert m.aliases["com.google.android.youtube.app.honeycomb.Shell$HomeActivity"] == (
        "com.google.android.apps.youtube.app.application.Shell$HomeActivity"
    )
    assert m.aliases["com.google.android.youtube.UrlActivity"] == (
        "com.google.android.apps.youtube.app.application.Shell$UrlActivity"
    )
    assert len(m.aliases) == 5


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


def test_reads_manifest_with_inflated_chunk_headers(caplog):
    """kiwisec 加固：chunk 头被调大并塞入填充数据，清单仍应完整读出。

    回归：这份清单曾以 "AndroidManifest.xml 解析为空" 失败，包名、版本、
    启动 Activity 全部读不出来。加固手法有四处：

    1. AXML 根 chunk ``headerSize`` 8→16，头部后面插 8 字节填充；
    2. 字符串池 ``headerSize`` 28→32，头部末尾插 4 字节填充，
       且 ``stringsStart`` 只补了这 4 字节——偏移数组之后另插的 12 字节没补，
       因此字符串数据并不紧跟在偏移数组后面，必须按 chunk 起点换算；
    3. 资源映射表 ``headerSize`` 8→24，ID 之前插 16 字节填充；
    4. namespace chunk ``size`` 被调大，固定字段之后挂了 20 字节垃圾。

    第 4 点曾让解析游标错位 20 字节：namespace chunk 读完 prefix/uri 后直接
    ``continue``，没有对齐到 chunk 末尾，之后每个 chunk 都从垃圾里读头。
    """
    data = _manifest_bytes("packed_kiwisec.zip")

    with caplog.at_level(logging.WARNING, logger="axml"):
        m = ManifestReader(data)

    assert m.package_name == "com.hnmtd.clean"
    assert m.version_code == "114"
    assert m.version_name == "1.1.4"
    # 不再回落到 1 / -1 的默认值
    assert m.min_sdk_version == "24"
    assert m.target_sdk_version == "34"

    assert m.application == "com.kiwivm.security.StubApplication"
    assert m.application_label_id == "0x7f120058"
    assert m.application_icon_addr == "0x7f0f01f5"

    # 唯一带 MAIN + LAUNCHER 的入口，以及两个 activity-alias
    assert m.main_activities == ["com.cssq.clear.ui.activity.SplashActivity"]
    assert set(m.aliases) == {
        "com.hnmtd.clean.wxapi.WXEntryActivity",
        "com.hnmtd.clean.wxapi.WXPayEntryActivity",
    }

    # 字符串池完整解开（451 条），不是解析到一半就放弃
    printer = AXMLPrinter(data, True)
    assert len(printer.axml.sb) == 451
    assert printer.axml.sb[0] == "theme"
    assert printer.axml.sb[450] == "KWS_MAIN_APP"

    # 资源映射表的 ID 与字符串池前几项对齐
    assert printer.axml.m_resourceIDs[:3] == [0x01010000, 0x01010001, 0x01010002]

    # 填充数据要留痕，但不能降级成“解析失败”
    assert any("填充数据" in r.getMessage() for r in caplog.records)

"""AndroidManifest.xml 读取。

`ManifestReader` 的 interface 只吃 AndroidManifest.xml 的原始 bytes，
吐出一个可查询的清单模型：包名、版本、SDK 区间、启动 Activity、别名映射、
application 的 name / icon / label 资源地址。

它不碰 zip，也不碰 ARSC —— 那些是 facade 与其它 module 的事。
"""

import re

from bs4 import BeautifulSoup
from lxml import etree

from apkutils.axml import AXMLPrinter

MANIFEST_NAME = "AndroidManifest.xml"

MAIN_ACTION = "android.intent.action.MAIN"
LAUNCHER_CATEGORY = "android.intent.category.LAUNCHER"


class ManifestError(Exception):
    """AndroidManifest.xml 无法解析。"""


def _attr(tag, name):
    """取 ``android:<name>`` 属性值，兼容类名前缀被剥落的清单。

    清单缺少 ``xmlns:android`` 声明时，``lxml-xml`` 会把 ``android:x`` 的
    前缀剥掉（key 变成 ``x``）；两种 key 都尝试，缺失返回 ``None``。
    """
    value = tag.get("android:" + name)
    if value is None:
        value = tag.get(name)
    return value


def _expand_name(package_name, name):
    """按 Android 规则把组件名展开成全限定名。

    ``.`` 开头 → ``包名 + 名字``；不含 ``.`` → ``包名 + "." + 名字``；
    否则原样。缺失（``None`` / 空串）返回 ``None``，调用方据此跳过。
    """
    if not name:
        return None
    if name.startswith("."):
        return package_name + name
    if "." not in name:
        return package_name + "." + name
    return name


def _is_disabled(tag):
    """组件是否显式声明 ``android:enabled="false"``。"""
    return str(_attr(tag, "enabled") or "").lower() == "false"


def _has_launcher_filter(item):
    """同一 intent-filter 内是否同时声明 MAIN 与 LAUNCHER。

    两个 intent-filter 各声明一个的拆分写法不构成启动入口。
    """
    for intent_filter in item.find_all("intent-filter"):
        actions = {_attr(node, "name") for node in intent_filter.find_all("action")}
        categories = {
            _attr(node, "name") for node in intent_filter.find_all("category")
        }
        if MAIN_ACTION in actions and LAUNCHER_CATEGORY in categories:
            return True
    return False


class ManifestReader:
    """读取 AndroidManifest.xml。

    传入 ``None`` 表示归档里没有清单：所有字段保持默认值，
    caller 不必额外判空。
    """

    def __init__(self, data=None):
        self.axml = None
        self.raw = ""
        self.package_name = ""
        self.version_code = None
        self.version_name = ""
        self.min_sdk_version = 1
        self.target_sdk_version = 1
        self.max_sdk_version = 0xFF
        self.main_activities = []
        self.aliases = {}
        self.application = ""
        self.application_icon_addr = ""
        self.application_label_id = ""
        self.activities_icon_addrs = []

        if data is not None:
            self._parse(data)

    def _parse(self, data):
        try:
            axml = AXMLPrinter(data, True).get_xml_obj()
        except Exception as e:
            raise ManifestError("AndroidManifest.xml 解析失败") from e

        if axml is None:
            raise ManifestError("AndroidManifest.xml 解析为空")

        buff = etree.tostring(axml, pretty_print=True, encoding="utf-8")
        if buff is None:
            raise ManifestError("AndroidManifest.xml 序列化失败")

        self.axml = axml
        # 某些混淆工具会把 name 属性写成无前缀形式，这里补回 android: 前缀
        self.raw = re.sub(
            r'\s:(="[\w]*?\.[\.\w]*")', r" android:name\1", buff.decode("UTF-8")
        )
        self._read_fields()

    def _read_fields(self):
        soup = BeautifulSoup(self.raw, "lxml-xml")

        manifest_tag = soup.manifest
        if manifest_tag is not None:
            self.package_name = str(_attr(manifest_tag, "package") or "")
            self.version_code = _attr(manifest_tag, "versionCode")
            self.version_name = _attr(manifest_tag, "versionName")

        uses_sdk = soup.select_one("uses-sdk")
        if uses_sdk is None:
            uses_sdk = {}
        self.min_sdk_version = _attr(uses_sdk, "minSdkVersion")
        if self.min_sdk_version is None:
            self.min_sdk_version = 1
        self.target_sdk_version = _attr(uses_sdk, "targetSdkVersion")
        if self.target_sdk_version is None:
            self.target_sdk_version = -1
        self.max_sdk_version = _attr(uses_sdk, "maxSdkVersion")
        if self.max_sdk_version is None:
            self.max_sdk_version = 0xFF

        application_tag = soup.application
        if application_tag is None:
            return

        self.application = _attr(application_tag, "name") or ""
        self.application_icon_addr = _as_res_addr(_attr(application_tag, "icon"))
        self.application_label_id = _as_label(_attr(application_tag, "label"))

        self._find_activities(soup)

    def _find_activities(self, soup):
        seen = set()
        for tag in ("activity", "activity-alias"):
            for item in soup.find_all(tag):
                name = _expand_name(self.package_name, _attr(item, "name"))
                if name is None or _is_disabled(item):
                    continue
                if not _has_launcher_filter(item):
                    continue
                if name in seen:
                    continue
                seen.add(name)
                self.main_activities.append(name)

                addr = _as_res_addr(_attr(item, "icon"))
                if addr:
                    self.activities_icon_addrs.append(addr)

        # 别名映射覆盖全部 activity-alias，与入口判定无关。
        for item in soup.find_all("activity-alias"):
            name = _expand_name(self.package_name, _attr(item, "name"))
            if name is None:
                continue
            self.aliases[name] = _expand_name(
                self.package_name, _attr(item, "targetActivity")
            )


def _as_res_addr(value):
    """把 ``@0x7f…`` 资源引用归一成小写 ``0x7f…``；缺失时返回空串。"""
    return str(value or "").lower().replace("@", "0x")


def _as_label(value):
    """归一 label：``@0x7f…`` 资源引用转成小写 ``0x7f…``；字面字符串原样保留。

    与 `_as_res_addr` 的区别在于字面量不能被小写化——
    ``android:label`` 允许直接写字符串（如 ``MyApp``），那本身就是应用名。
    """
    raw = str(value or "")
    if raw.startswith("@"):
        return "0x" + raw[1:].lower()
    return raw

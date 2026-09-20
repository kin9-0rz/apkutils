"""AndroidManifest.xml 读取。

`ManifestReader` 的 interface 只吃 AndroidManifest.xml 的原始 bytes，
吐出一个可查询的清单模型：包名、版本、SDK 区间、启动 Activity、
application 的 name / icon / label 资源地址。

它不碰 zip，也不碰 ARSC —— 那些是 facade 与其它 module 的事。
"""

import re

from bs4 import BeautifulSoup
from lxml import etree

from apkutils.axml import AXMLPrinter

MANIFEST_NAME = "AndroidManifest.xml"


class ManifestError(Exception):
    """AndroidManifest.xml 无法解析。"""


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
            self.package_name = str(manifest_tag.get("package", ""))
            self.version_code = manifest_tag.get("android:versionCode")
            self.version_name = manifest_tag.get("android:versionName")

        uses_sdk = soup.select_one("uses-sdk")
        if uses_sdk is None:
            uses_sdk = {}
        self.min_sdk_version = uses_sdk.get("android:minSdkVersion", 1)
        self.target_sdk_version = uses_sdk.get("android:targetSdkVersion", -1)
        self.max_sdk_version = uses_sdk.get("android:maxSdkVersion", 0xFF)

        application_tag = soup.application
        if application_tag is None:
            return

        self.application = application_tag.get("android:name", "")
        self.application_icon_addr = _as_res_addr(application_tag.get("android:icon"))
        self.application_label_id = _as_res_addr(application_tag.get("android:label"))

        self._find_activities(soup)

    def _find_activities(self, soup):
        for tag in ("activity", "activity-alias"):
            for item in soup.select(tag):
                name = str(item.get("android:name", "none"))
                if name.startswith("."):
                    name = self.package_name + name

                if item.get("android:enabled", True) is False:
                    continue

                content = item.encode_contents().decode("utf-8")
                if "android.intent.action.MAIN" not in content:
                    continue
                if "android.intent.category.LAUNCHER" not in content:
                    continue

                self.main_activities.append(name)

                addr = _as_res_addr(item.get("android:icon"))
                if addr:
                    self.activities_icon_addrs.append(addr)

                target_activity = item.get("android:targetActivity", None)
                if target_activity:
                    self.main_activities.append(target_activity)


def _as_res_addr(value):
    """把 ``@0x7f…`` 资源引用归一成小写 ``0x7f…``；缺失时返回空串。"""
    return str(value or "").lower().replace("@", "0x")

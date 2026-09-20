"""resources.arsc 读取。

`ResourceTable` 的 interface 只吃 resources.arsc 的原始 bytes，
并提供两个查询：资源地址 → (name, type)，资源名 → 字符串值。

它直接读 `ARSCParser.get_resources()` 的结构化记录——
不经过"先渲染成 XML 再用 BeautifulSoup 解析回来"的往返。
"""

from apkutils.axml import ARSCParser

ARSC_NAME = "resources.arsc"


class ResourceTableError(Exception):
    """resources.arsc 无法解析。"""


class ResourceTable:
    """解析 resources.arsc，并提供地址/名称查询。

    传入 ``None`` 表示归档里没有资源表：``parser`` 为 ``None``，
    所有查询返回 ``None``，caller 不必额外判空。
    """

    def __init__(self, data=None):
        self.parser = None
        self.package_name = ""
        self._public = {}
        self._strings = {}

        if data is not None:
            self._parse(data)

    def _parse(self, data):
        try:
            self.parser = ARSCParser(data)
        except Exception as e:
            raise ResourceTableError("resources.arsc 解析失败") from e

        names = self.parser.get_packages_names()
        if names:
            self.package_name = names[0]

    def resolve_reference(self, package, addr):
        """把 ``0x7f…`` 资源地址解析成 ``(name, type)``；找不到返回 ``None``。"""
        if self.parser is None or not addr:
            return None

        for res in self._public_resources(package):
            if "0x{:08x}".format(res.id) == addr:
                return res.name, res.kind
        return None

    def string_by_name(self, package, name):
        """按资源名读出字符串资源的值；找不到返回 ``None``。"""
        if self.parser is None or not name:
            return None

        for res in self._string_resources(package):
            if res.name == name:
                return res.value or None
        return None

    def _public_resources(self, package):
        if package not in self._public:
            self._public[package] = self.parser.get_resources(package, "public")
        return self._public[package]

    def _string_resources(self, package):
        if package not in self._strings:
            self._strings[package] = self.parser.get_resources(package, "string")
        return self._strings[package]

"""从清单 + 资源表 + 子文件列表推出应用图标与应用名。

`AppMetadata` 的 interface 只吃三个已解析的东西：
清单模型、资源表、子文件列表。构造即算出 ``icons`` 与 ``app_name``。

清单里存的是资源地址（``0x7f020000``），资源表把地址翻成
``(name, type)``，子文件列表把 name/type 对上真实文件名——
这条编排链整个藏在构造里。
"""


class AppMetadataError(Exception):
    """应用图标或应用名无法解析。"""


class AppMetadata:
    """应用图标与应用名。"""

    def __init__(self, manifest, resources, subfiles):
        self.icons = []
        self.app_name = None
        self._read(manifest, resources, subfiles)

    def _read(self, manifest, resources, subfiles):
        if resources.parser is None:
            return

        addr = manifest.application_icon_addr
        if addr == "":
            if manifest.activities_icon_addrs == []:
                return
            addr = manifest.activities_icon_addrs[0]

        package = manifest.package_name

        ref = resources.resolve_reference(package, addr)
        if ref is None:
            raise AppMetadataError(f"图标地址错误: {addr}")

        icon_name, icon_path = ref
        for item in subfiles:
            name = item["name"]
            if icon_name in name and icon_path in name:
                self.icons.append(name)

        ref = resources.resolve_reference(package, manifest.application_label_id)
        if ref is None:
            return

        label = ref[0] or ""
        if isinstance(label, list):
            label = ",".join(label)

        self.app_name = resources.string_by_name(package, label)

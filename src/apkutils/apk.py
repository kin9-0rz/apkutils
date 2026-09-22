import dataclasses
import io
import logging

import pyftype

from apkutils import _apkfile
from apkutils._certificates import (
    META_INF_PREFIX,
    SIGNATURE_SUFFIXES,
    CertificateError,
    Certificates,
)
from apkutils._dex import DexError, DexReader
from apkutils._dex import convert_proto_string as _convert_proto_string
from apkutils._manifest import MANIFEST_NAME, ManifestError, ManifestReader
from apkutils._metadata import AppMetadata, AppMetadataError
from apkutils._resources import ARSC_NAME, ResourceTable, ResourceTableError
from apkutils._subfiles import Subfiles

log = logging.getLogger("apkutils")

NS_ANDROID_URI = "http://schemas.android.com/apk/res/android"
NS_ANDROID = "{{{}}}".format(NS_ANDROID_URI)  # Namespace as used by etree


@dataclasses.dataclass(frozen=True)
class PartError:
    """一次解析失败：哪个部分、哪个文件（若有）、原始异常。"""

    part: str
    error: Exception
    name: str | None = None


class APK:
    def __init__(self, strict=False):
        self.apk_path = None
        self.afile = None
        self.strict = strict
        self.errors: list[PartError] = []
        self.children = []
        self.manifest: str = ""
        self.axml = None
        self._manifest = ManifestReader()
        self._manifest_loaded = False
        self._resources = ResourceTable()
        self._dex = None
        self._certs = {}
        self.arsc = None
        self._app_icons: list | None = None
        self._app_name = None
        self.trees = None  # 代码结构序列字典
        """应用名的KEY"""

    @classmethod
    def from_file(cls, path, strict=False):
        apk = cls.from_io(path, strict=strict)
        apk.apk_path = path
        return apk

    @classmethod
    def from_bytes(cls, _bytes, strict=False):
        return cls.from_io(io.BytesIO(_bytes), strict=strict)

    @classmethod
    def from_io(cls, _io, strict=False):
        apk = cls(strict=strict)
        apk.afile = _apkfile.ZipFile(_io, "r")
        return apk

    def parse_resource(self):
        """解析资源文件，包括AndroidManifest.xml、resource.arsc，图标、应用名

        Returns:
            _type_: _description_
        """
        self._init_manifest()
        self._init_arsc()
        self._init_app_metadata()  # 依赖 manifest, arsc, 子文件列表
        return self

    def parse_dex(self):
        self._ensure_dex().strings()
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        if self.afile is not None:
            self.afile.close()

    # * -------------------------- 失败记录 ----------------------------------

    def _fail(self, part, error, name=None, summary=None):
        """记下一次失败。

        默认模式：只记进 ``self.errors`` 并写日志，不打断调用方。
        ``strict=True``：向外抛出（``summary`` 用于把多个明细合成一个异常）。
        """
        self.errors.append(PartError(part, error, name))

        if self.strict:
            raise summary if summary is not None else error

        log.warning(
            "[%s] %s 解析失败: %s",
            part,
            name or self.apk_path,
            error,
            exc_info=error,
        )

    # * -------------------------- 清单 --------------------------------------

    def get_manifest(self):
        if self.manifest == "" and not self._manifest_loaded:
            self._init_manifest()
        return self.manifest

    def _init_manifest(self):
        if self._manifest_loaded:
            return
        self._manifest_loaded = True

        data = None
        try:
            if MANIFEST_NAME in self.afile.namelist():
                data = self.afile.read(MANIFEST_NAME)
        except Exception as e:
            self._fail("manifest", e)
            return

        try:
            self._manifest = ManifestReader(data)
        except ManifestError as e:
            self._fail("manifest", e)
            self._manifest = ManifestReader()

        self.axml = self._manifest.axml
        self.manifest = self._manifest.raw

    @property
    def package_name(self):
        return self._manifest.package_name

    def get_package_name(self):
        return self._manifest.package_name

    def get_manifest_main_activities(self):
        return self._manifest.main_activities

    def get_manifest_application(self):
        return self._manifest.application

    @property
    def version_name(self):
        return self._manifest.version_name

    @property
    def min_sdk_version(self):
        return self._manifest.min_sdk_version

    @property
    def target_sdk_version(self):
        return self._manifest.target_sdk_version

    @property
    def max_sdk_version(self):
        return self._manifest.max_sdk_version

    # * -------------------------- DEX --------------------------------------

    def _ensure_dex(self):
        if self._dex is None:
            self._init_dex_files()
        return self._dex

    def _init_dex_files(self):
        blobs = []
        try:
            for name in self.afile.namelist():
                data = self.afile.read(name)
                if (
                    name.startswith("classes")
                    and name.endswith(".dex")
                    and pyftype.guess(data).EXTENSION == "dex"
                ):
                    blobs.append(data)
        except Exception as e:
            self._fail("dex", e)
            return

        self._dex = DexReader(blobs)

        if self._dex.skipped:
            summary = DexError("{} 个 DEX 解析失败".format(len(self._dex.skipped)))
            for err in self._dex.skipped:
                self._fail("dex", err, summary=summary)

    @property
    def dex_files(self):
        return self._dex.dex_files if self._dex is not None else []

    @property
    def opcodes(self):
        """兼容 2.0.5 的 ``opcodes`` 缓存属性（只读），即 ``get_dex_opcodes()`` 的结果。

        与 2.0.5 的差别只有一处：dex 已解析但未调用过 ``get_dex_opcodes()`` 时，
        这里返回结果而非 ``None``。
        """
        if self._dex is None:
            return None
        return self._dex.opcodes_list()

    @property
    def strings_refx(self):
        """兼容 2.0.5 的 ``strings_refx`` 缓存属性（只读），即 ``get_dex_strings_refx()`` 的结果。

        与 2.0.5 的差别只有一处：dex 已解析但未调用过 ``get_dex_strings_refx()`` 时，
        这里返回结果而非 ``None``。
        """
        if self._dex is None:
            return None
        return self._dex.strings_refx_index()

    def get_dex_classes(self):
        return self._ensure_dex().classes()

    def get_dex_methods(self):
        return self._ensure_dex().methods()

    def get_dex_method_strings(self, mtd):
        return self._ensure_dex().method_strings(mtd)

    def xref(self, _mtd):
        return self._ensure_dex().xref(_mtd)

    def get_dex_strings_refx(self):
        return self._ensure_dex().strings_refx_index()

    def get_dex_methods_refx(self):
        return self._ensure_dex().methods_refx_index()

    def get_dex_files(self):
        return self._ensure_dex().files()

    def get_dex_strings(self):
        return self._ensure_dex().strings()

    def get_dex_hex_strings(self):
        if self._dex is None:
            return None
        return self._dex.hex_strings()

    def get_dex_opcodes(self):
        return self._ensure_dex().opcodes_list()

    @staticmethod
    def convert_proto_string(return_type, param_types):
        return _convert_proto_string(return_type, param_types)

    # * -------------------------- 子文件 --------------------------------------

    def get_subfiles(self) -> list:
        """获取子文件

        :return: 子文件列表
        :rtype: _type_
        """
        if self.children == []:
            self._init_children()
        return self.children

    def _init_children(self):
        try:
            subfiles = Subfiles(self.afile)
        except Exception as e:
            self._fail("subfiles", e)
            return

        self.children = subfiles.items
        for name, err in subfiles.skipped:
            self._fail("subfiles", err, name)

    def _init_arsc(self):
        data = None
        try:
            if ARSC_NAME in self.afile.namelist():
                data = self.afile.read(ARSC_NAME)
        except Exception as e:
            self._fail("arsc", e)
            return

        try:
            self._resources = ResourceTable(data)
        except ResourceTableError as e:
            self._fail("arsc", e)
            self._resources = ResourceTable()

        # FIXME: 这个包名可能与清单的不一样
        self.arsc = self._resources.parser

    def get_arsc(self):
        return self.arsc

    def get_app_icons(self):
        return self._app_icons

    @property
    def app_name(self):
        return self._app_name

    def _init_app_metadata(self):
        try:
            meta = AppMetadata(self._manifest, self._resources, self.get_subfiles())
        except AppMetadataError as e:
            self._fail("metadata", e)
            return

        self._app_icons = meta.icons
        self._app_name = meta.app_name

    def get_certs(self, _hash="md5"):
        if _hash not in self._certs:
            self._init_certs(_hash)
        return self._certs.get(_hash, [])

    def _init_certs(self, _hash):
        try:
            entries = [
                (name, self.afile.read(name))
                for name in self.afile.namelist()
                if name.startswith(META_INF_PREFIX) and name.endswith(SIGNATURE_SUFFIXES)
            ]
        except Exception as e:
            self._fail("certs", e)
            return

        try:
            self._certs[_hash] = Certificates(entries, _hash=_hash).content
        except CertificateError as e:
            self._fail("certs", e)

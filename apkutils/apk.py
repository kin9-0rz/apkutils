import binascii
import hashlib
import io
import re
import traceback
import xml
from xml.parsers.expat import ExpatError

import pyftype
from bs4 import BeautifulSoup
from lxml import etree

from apkutils import apkfile
from apkutils.axml import ARSCParser, AXMLPrinter
from apkutils.cert import Certificate
from apkutils.dex.dalvik import OPCODES
from apkutils.dex.dexparser import DexFile

# 6E invoke-virtual 110
# 6F invoke-supper
# 70 invoke-direct
# 71 invoke-static
# 72 invoke-interface
# 74 invoke-virtual/range
# 75 invoke-supper/range
# 76 invoke-direct/range
# 77 invoke-static/range
# 78 invoke-interface-range
INVOKE_OPCODES = {0x6E, 0x6F, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76, 0x77, 0x78}

NS_ANDROID_URI = "http://schemas.android.com/apk/res/android"
NS_ANDROID = "{{{}}}".format(NS_ANDROID_URI)  # Namespace as used by etree


class APK:
    def __init__(self):
        self.apk_path = None
        self.dex_files = None
        self.children = None
        self.manifest = None
        self._dex_strings = None  # 字符串
        self._dex_hex_strings = None  # 16进制字符串
        self.opcodes = None
        self.certs = {}
        self.arsc = None
        self.strings_refx = None
        self._app_icons = []
        self._methods = None
        self.trees = None  # 代码结构序列字典
        self._classes = None
        self._methods_refx = None
        self._package_name = None  # 包名
        self._app_name = None
        self._application_icon_addr = None

    @classmethod
    def from_file(cls, path):
        cls.apk_path = path
        return cls.from_io(path)

    @classmethod
    def from_bytes(cls, _bytes):
        return cls.from_io(io.BytesIO(_bytes))

    @classmethod
    def from_io(cls, _io):
        cls.afile = apkfile.ZipFile(_io, "r")
        return cls()

    def parse_resouce(self):
        """解析资源文件，包括AndroidManifest.xml、resource.arsc，图标、应用名

        Returns:
            _type_: _description_
        """
        self._init_manifest()
        self._init_arsc()
        self._init_app_icons()
        self._init_app_name()
        return self
    
    def parse_dex(self):
        self._init_dex_strings()
        return self
    
    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        self.afile.close()

    # * -------------------------- 清单 --------------------------------------

    def get_manifest(self):
        return self.manifest

    def _init_manifest(self):
        ANDROID_MANIFEST = "AndroidManifest.xml"
        try:
            if ANDROID_MANIFEST in self.afile.namelist():
                data = self.afile.read(ANDROID_MANIFEST)
                try:
                    self.axml = AXMLPrinter(data, True).get_xml_obj()
                    if self.axml is None:
                        return
                    buff = etree.tostring(
                        self.axml, pretty_print=True, encoding="utf-8"
                    )
                    if buff is None:
                        return
                    self.manifest = buff.decode("UTF-8")
                except Exception:
                    traceback.print_exc()
                    return
        except Exception:
            traceback.print_exc()
            return

        # fix manifest
        self.manifest = re.sub(
            r'\s:(="[\w]*?\.[\.\w]*")', r" android:name\1", self.manifest
        )

        soup = BeautifulSoup(self.manifest, "lxml-xml")
        self._package_name = soup.manifest.get("package", "")
        self._version_code = soup.manifest.get("android:versionCode")
        self._version_name = soup.manifest.get("android:versionName")

        uses_sdk = soup.select_one("uses-sdk")
        if uses_sdk is None:
            uses_sdk = {}
        self._min_sdk_version = uses_sdk.get("android:minSdkVersion", 1)
        self._target_sdk_version = uses_sdk.get("android:targetSdkVersion", -1)
        self._max_sdk_version = uses_sdk.get("android:maxSdkVersion", 0xFF)
        self._main_activities = []

        application_tag = soup.application
        if application_tag is None:
            return
        self._application = application_tag.get("android:name", "")
        self._application_icon_addr = (
            application_tag.get("android:icon", "").lower().replace("@", "0x")
        )
        self._application_label_id = (
            application_tag.get("android:label", "").lower().replace("@", "0x")
        )

        self._activities_icon_addrs = []

        def find_activities(tag):
            for item in soup.select(tag):
                name = item.get("android:name", "none")
                if name.startswith("."):
                    name = self._package_name + name

                enabled = item.get("android:enabled", True)
                if enabled is False:
                    continue

                content = item.renderContents().decode("utf-8")
                if "android.intent.action.MAIN" not in content:
                    continue
                if "android.intent.category.LAUNCHER" not in content:
                    continue
                self._main_activities.append(name)
                if addr := item.get("android:icon"):
                    self._activities_icon_addrs.append(addr.lower().replace("@", "0x"))

                ta = item.get("android:targetActivity", None)
                if ta:
                    self._main_activities.append(ta)

        find_activities("activity")
        find_activities("activity-alias")

    @property
    def package_name(self):
        return self._package_name

    def get_package_name(self):
        return self._package_name

    def get_manifest_main_activities(self):
        return self._main_activities

    def get_manifest_application(self):
        return self._application

    # * -------------------------- DEX --------------------------------------

    def get_dex_classes(self):
        if self._classes is None:
            self._init_classes()
        return self._classes

    def _init_classes(self):
        classes = set()
        if not self.dex_files:
            self._init_dex_files()

        for dex_file in self.dex_files:
            for dexClass in dex_file.classes:
                classes.add(dexClass.name)
        self._classes = sorted(classes)

    def get_dex_methods(self):
        """获取所有方法路径 com/a/b/mtd_name

        Returns:
            TYPE: set
        """
        if self._methods is None:
            self._init_dex_methods()
        return self._methods

    def _init_dex_methods(self):
        """初始化方法

        如果类和方法超过1W的时候，速度非常慢。
        TODO 等待优化。
        TODO 也许需要C/C++或者Rust等方式生成so，给Python调用，才能提升这个性能。

        Returns:
            TYPE: 方法集合
        """
        methods = set()
        if not self.dex_files:
            self._init_dex_files()

        def process_dex_class(dexClass):
            try:
                dexClass.parseData()
            except IndexError as e:
                print(e)
                return
            for method in dexClass.data.methods:
                clsname = method.id.cname.decode()
                mtdname = method.id.name.decode()
                methods.add(clsname + "/" + mtdname)

        for dex_file in self.dex_files:
            for dex_class in dex_file.classes:
                process_dex_class(dex_class)

    def get_dex_method_strings(self, mtd):
        """获取某个方法中的所有字符串

        Args:
            cname (str): _description_
            mname (str): _description_
        """
        arr = mtd.split("->")
        cname = arr[0].encode("utf-8")
        arr = arr[1].split("(")
        mname = arr[0].encode("utf-8")
        desc = ("(" + arr[1]).encode("utf-8")

        if not self.dex_files:
            self._init_dex_files()

        strings = set()
        for dex_file in self.dex_files:
            for dexClass in dex_file.classes:
                if dexClass.name == cname:
                    try:
                        dexClass.parseData()
                    except IndexError:
                        continue
                    for method in dexClass.data.methods:
                        if method.id.name != mname:
                            continue
                        if desc != method.id.desc:
                            continue
                        if not method.code:
                            continue

                        for bc in method.code.bytecode:
                            if bc.opcode not in {26, 27}:
                                continue
                            strings.add(dex_file.string(bc.args[1]).decode("utf-8"))
                    break
        return strings

    def xref(self, mtd: str):
        """获取所有的引用方法 pkg/cls->mtd()

        Args:
            mtd (str): _description_
        """
        mtd = mtd.encode("utf-8")

        if not self.dex_files:
            self._init_dex_files()

        mtds = set()
        for dex_file in self.dex_files:
            for dexClass in dex_file.classes:
                try:
                    dexClass.parseData()
                except IndexError:
                    continue

                for method in dexClass.data.methods:
                    if not method.code:
                        continue

                    for bc in method.code.bytecode:
                        if bc.opcode not in INVOKE_OPCODES:
                            continue

                        method_id = dex_file.method_id(bc.args[0])
                        dexstr = (
                            method_id.cname + b"->" + method_id.name + method_id.desc
                        )

                        if mtd == dexstr:
                            m = (
                                method.id.cname
                                + b"->"
                                + method.id.name
                                + method.id.desc
                            )
                            mtds.add(m)
        return mtds

    def _init_dex_strings_refx(self):
        # TODO 开启线程池
        if not self.dex_files:
            self._init_dex_files()

        self.strings_refx = {}
        for dex_file in self.dex_files:
            for dexClass in dex_file.classes:
                try:
                    dexClass.parseData()
                except IndexError:
                    continue

                for method in dexClass.data.methods:
                    if not method.code:
                        continue

                    for bc in method.code.bytecode:
                        # 1A const-string
                        # 1B const-string-jumbo
                        if bc.opcode not in {26, 27}:
                            continue

                        if method.id.cname is None:
                            continue

                        clsname = method.id.cname.decode()
                        mtdname = method.id.name.decode()
                        dexstr = dex_file.string(bc.args[1])
                        if clsname in self.strings_refx:
                            if mtdname in self.strings_refx[clsname]:
                                self.strings_refx[clsname][mtdname].add(dexstr)
                            else:
                                self.strings_refx[clsname][mtdname] = set()
                                self.strings_refx[clsname][mtdname].add(dexstr)
                        else:
                            self.strings_refx[clsname] = {}
                            self.strings_refx[clsname][mtdname] = set()
                            self.strings_refx[clsname][mtdname].add(dexstr)

    def get_dex_strings_refx(self):
        """获取字符串索引，即字符串被那些类、方法使用了。

        :return: 字符串索引
        :rtype: [dict]
        """
        if self.strings_refx is None:
            self._init_dex_strings_refx()
        return self.strings_refx

    def get_dex_methods_refx(self):
        """获取方法索引，即方法被那些类、方法使用了。

        :return: 方法索引
        :rtype: [dict]
        """
        if self._methods_refx is None:
            self._init_methods_refx()
        return self._methods_refx

    def _init_dex_methods_refx(self):
        if not self.dex_files:
            self._init_dex_files()

        self._methods_refx = {}
        for dex_file in self.dex_files:
            for dexClass in dex_file.classes:
                try:
                    dexClass.parseData()
                except IndexError:
                    continue

                for method in dexClass.data.methods:
                    if not method.code:
                        continue

                    for bc in method.code.bytecode:
                        if bc.opcode not in INVOKE_OPCODES:
                            continue
                        clsname = method.id.cname.decode()
                        mtdname = method.id.name.decode()

                        method_id = dex_file.method_id(bc.args[0])
                        mtd_name = method_id.name
                        mtd_cname = method_id.cname
                        dexstr = mtd_cname + b"->" + mtd_name
                        if clsname in self._methods_refx:
                            if mtdname in self._methods_refx[clsname]:
                                self._methods_refx[clsname][mtdname].add(dexstr)
                            else:
                                self._methods_refx[clsname][mtdname] = set()
                                self._methods_refx[clsname][mtdname].add(dexstr)
                        else:
                            self._methods_refx[clsname] = {}
                            self._methods_refx[clsname][mtdname] = set()
                            self._methods_refx[clsname][mtdname].add(dexstr)

    def get_dex_files(self):
        if not self.dex_files:
            self._init_dex_files()
        return self.dex_files

    def _init_dex_files(self):
        self.dex_files = []
        try:
            for name in self.afile.namelist():
                data = self.afile.read(name)
                if (
                    name.startswith("classes")
                    and name.endswith(".dex")
                    and pyftype.guess(data).EXTENSION == "dex"
                ):
                    dex_file = DexFile(data)
                    self.dex_files.append(dex_file)
        except Exception as e:
            print(self.apk_path)
            print(e)

    def get_dex_strings(self):
        return self._dex_strings

    def _init_dex_strings(self):
        if not self.dex_files:
            self._init_dex_files()

        str_set = set()
        hex_str_set = set()
        for dex_file in self.dex_files:
            for i in range(dex_file.string_ids.size):
                ostr = dex_file.string(i)
                str_set.add(ostr)
                hex_str_set.add(binascii.hexlify(ostr).decode())

        self._dex_strings = list(str_set)
        self._dex_hex_strings = list(hex_str_set)

    def get_dex_hex_strings(self):
        return self._dex_hex_strings

    def get_dex_opcodes(self):
        if not self.opcodes:
            self._init_dex_opcodes()
        return self.opcodes

    def _init_dex_opcodes(self):
        if not self.dex_files:
            self._init_dex_files()
        self.opcodes = []
        for dex_file in self.dex_files:
            for dexClass in dex_file.classes:
                try:
                    dexClass.parseData()
                except IndexError:
                    continue
                for method in dexClass.data.methods:
                    opcodes = ""
                    if method.code:
                        for bc in method.code.bytecode:
                            opcode = str(hex(bc.opcode)).upper()[2:]
                            if len(opcode) == 2:
                                opcodes = opcodes + opcode
                            else:
                                opcodes = opcodes + "0" + opcode

                    proto = self.convert_proto_string(
                        method.id.return_type, method.id.param_types
                    )

                    item = {}
                    item["super_class"] = dexClass.super.decode()
                    item["class_name"] = method.id.cname.decode()
                    item["method_name"] = method.id.name.decode()
                    item["method_desc"] = method.id.desc.decode()
                    item["proto"] = proto
                    item["opcodes"] = opcodes
                    self.opcodes.append(item)

    @staticmethod
    def convert_proto_string(return_type, param_types):
        proto = return_type.decode()
        if len(proto) > 1:
            proto = "L"

        for item in param_types:
            param_type = item.decode()
            proto += "L" if len(param_type) > 1 else param_type

        return proto

    # * -------------------------- 子文件 --------------------------------------

    def get_subfiles(self):
        """获取子文件

        :return: 子文件列表
        :rtype: _type_
        """
        if not self.children:
            self._init_children()
        return self.children

    def _init_children(self):
        self.children = []
        try:
            for name in self.afile.namelist():
                try:
                    data = self.afile.read(name)
                    mine = pyftype.guess(data).MIME
                    info = self.afile.getinfo(name)
                except Exception as ex:
                    print(name, ex)
                    continue
                item = {}
                item["name"] = name
                item["type"] = mine
                item["time"] = "%d%02d%02d%02d%02d%02d" % info.date_time
                crc = str(hex(info.CRC)).upper()[2:]
                crc = "0" * (8 - len(crc)) + crc
                item["crc"] = crc
                # item["sha1"] = ""
                self.children.append(item)
        except Exception:
            traceback.print_exc()

    def _init_arsc(self):
        ARSC_NAME = "resources.arsc"
        try:
            if ARSC_NAME in self.afile.namelist():
                data = self.afile.read(ARSC_NAME)
                self.arsc = ARSCParser(data)
                self.package = self.arsc.get_packages_names()[0]
        except Exception as e:
            print(self.apk_path)
            print(e)

    def get_arsc(self):
        return self.arsc

    def get_app_icons(self):
        if self._app_icons is []:
            return self._app_icons
        self._init_app_icons()
        return self._app_icons

    def _init_app_icons(self):
        """仅获取Appliction的图标"""
        if self.arsc is None:
            return
        
        self._string_res_app_name = ""

        files = self.get_subfiles()

        addr = self._application_icon_addr
        if addr == "":
            if self._activities_icon_addrs == []:
                return
            addr = self._activities_icon_addrs[0]

        try:
            soup = BeautifulSoup(
                self.arsc.get_public_resources(self._package_name), "lxml-xml"
            )
            public_tag = soup.select_one('public[id="{}"]'.format(addr))

            icon_name = public_tag.get("name")
            icon_path = public_tag.get("type")
            for f in files:
                name = f["name"]
                if icon_name in name and icon_path in name:
                    self._app_icons.append(name)

            public_tag = soup.select_one(
                'public[id="{}"]'.format(self._application_label_id)
            )
            if public_tag is None:
                return
            self._string_res_app_name = public_tag.get("name")
        except Exception as e:
            print(self.apk_path)
            print(e)

    @property
    def app_name(self):
        if self._app_name is None:
            self._init_app_name()
        return self._app_name

    def _init_app_name(self):
        if self.arsc is None:
            return
        
        try:
            soup = BeautifulSoup(
                self.arsc.get_string_resources(self._package_name), "lxml-xml"
            )
            tag = soup.select_one('string[name="{}"]'.format(self._string_res_app_name))
            self._app_name = tag.text

        except Exception as e:
            print(self.apk_path)
            print(e)

    def get_certs(self, _hash="md5"):
        if _hash not in self.certs:
            self._init_certs(_hash)
        return self.certs[_hash]

    def _init_certs(self, _hash):
        try:
            for name in self.afile.namelist():
                if name.startswith("META-INF/") and name.endswith((".DSA", ".RSA")):
                    data = self.afile.read(name)
                    kind = pyftype.guess(data)
                    mine = kind.EXTENSION
                    if mine != "txt":
                        cert = Certificate(data, _hash=_hash)
                        self.certs[_hash] = cert.get()
        except Exception as e:
            print(self.apk_path)
            print(e)

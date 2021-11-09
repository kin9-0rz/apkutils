import binascii
import hashlib
import io
import re
import xml
from xml.parsers.expat import ExpatError

import pyftype
import xmltodict
from anytree import Node, RenderTree
from anytree.resolver import Resolver
from bs4 import BeautifulSoup
from lxml import etree

from apkutils import apkfile
from apkutils.axml import ARSCParser, AXMLPrinter
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
        self.dex_strings = None  # 16进制字符串
        self.opcodes = None
        self.certs = {}
        self.arsc = None
        self.strings_refx = None
        self.app_icon = None
        self.methods = None
        self.trees = None  # 代码结构序列字典
        self.application = None
        self.main_activity = None
        self.mini_mani = None
        self.classes = None
        self.methods_refx = None

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

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        self.afile.close()

    # TODO -------------------------- 解析清单 -------------------------------------- 


    def get_manifest(self):
        if not self.manifest:
            self._init_manifest()
        return self.manifest

    def _init_manifest(self):
        ANDROID_MANIFEST = "AndroidManifest.xml"
        try:
            if ANDROID_MANIFEST in self.afile.namelist():
                data = self.afile.read(ANDROID_MANIFEST)
                try:
                    self.axml = AXMLPrinter(data).get_xml_obj()
                    buff = etree.tostring(
                        self.axml, pretty_print=True, encoding="utf-8"
                    )
                    self.manifest = buff.decode("UTF-8")

                except Exception as e:
                    raise e
        except Exception as e:
            print(self.apk_path)
            print(e)

        # fix manifest
        self.manifest = re.sub(
            r'\s:(="[\w]*?\.[\.\w]*")', r" android:name\1", self.manifest
        )

    def get_main_activities(self):
        x = set()
        y = set()

        activities_and_aliases = self.axml.findall(".//activity") + self.axml.findall(
            ".//activity-alias"
        )

        for item in activities_and_aliases:
            # Some applications have more than one MAIN activity.
            # For example: paid and free content
            activityEnabled = item.get(self._ns("enabled"))
            if activityEnabled == "false":
                continue

            for sitem in item.findall(".//action"):
                val = sitem.get(self._ns("name"))
                if val == "android.intent.action.MAIN":
                    activity = item.get(self._ns("name"))
                    if activity is not None:
                        x.add(item.get(self._ns("name")))
                    else:
                        print("Main activity without name")

            for sitem in item.findall(".//category"):
                val = sitem.get(self._ns("name"))
                if val == "android.intent.category.LAUNCHER":
                    activity = item.get(self._ns("name"))
                    if activity is not None:
                        y.add(item.get(self._ns("name")))
                    else:
                        print("Launcher activity without name")

        return x.intersection(y)

    @staticmethod
    def _ns(name):
        """
        return the name including the Android namespace URI
        """
        return NS_ANDROID + name

    def get_manifest_tag_numbers(self):
        """统计清单标签的个数"""
        if not self.manifest:
            self._init_manifest()
        if self.manifest is None:
            print(self.apk_path, "无法解析清单")
            return

        tag_reg = r"<([\w\-\:]+)\s"
        tag_reg = r'<([\w\-\:]+)\s[^>]*?:name="([^"]*?)"'
        tag_ptn = re.compile(tag_reg)
        result = {
            "uses-permission": 0,
            "activity": 0,
            "receiver": 0,
            "service": 0,
            "provider": 0,
            "version_code": 0,
        }

        perms = set()
        for item in tag_ptn.finditer(self.manifest):
            name, value = item.groups()
            if name == "uses-permission":
                if value.startswith("android.permission"):
                    perms.add(value)
            elif "activity" in name and name != "activity-alias":
                result["activity"] += 1
            elif "receiver" in name:
                result["receiver"] += 1
            elif "service" in name:
                result["service"] += 1
            elif "provider" in name:
                result["provider"] += 1

        result["uses-permission"] = len(perms)

        ptn = re.compile(r'android:versionCode="(\d+?)"')
        for item in ptn.finditer(self.manifest):
            value = item.groups()[0]
            if value.isdigit():
                result["version_code"] = int(value)

        api = 4
        target_sdk_ptn = re.compile(r'android:targetSdkVersion="(\d+?)"')
        match = target_sdk_ptn.search(self.manifest)
        if match:
            api = int(match.groups()[0])
        else:
            min_sdk_ptn = re.compile(r'android:minSdkVersion="(\d+?)"')
            match = min_sdk_ptn.search(self.manifest)
            if match:
                api = int(match.groups()[0])

        if api <= 3:
            #  If both your minSdkVersion and targetSdkVersion values are set to 3 or lower,
            # the system implicitly grants your app these permissions
            if "android.permission.READ_PHONE_STATE" in self.manifest:
                result["uses-permission"] += 1
            if "android.permission.WRITE_EXTERNAL_STORAGE" in self.manifest:
                result["uses-permission"] += 1
        return result
    # TODO 需要优化
    def get_main_activity(self):
        if not self.main_activity:
            self._init_main_activity()
        return self.main_activity

    def _init_main_activity(self):
        # TODO 使用BS解析清单信息，原始清单，清单信息
        mani = self.get_mini_mani()
        ptn = r'<activity(.*?)android:name="([^"]*?)"[^<>]*?>.*?<action android:name="android.intent.action.MAIN">.*?</activity>'
        result = re.search(ptn, mani)
        if result:
            self.main_activity = result.groups()[1]

    def get_application(self):
        if not self.application:
            self._init_application()
        return self.application

    def _init_application(self):
        mani = self.get_mini_mani()
        if not mani:
            return
        ptn = r'<application[^<>]*?:name="([^<>"]*?)"[^<>]*?>'
        result = re.search(ptn, mani)
        if result:
            self.application = result.groups()[0]

   


    # TODO DEX解析
    def get_classes(self):
        if self.classes is None:
            self._init_classes()
        return self.classes

    def _init_classes(self):
        classes = set()
        if not self.dex_files:
            self._init_dex_files()

        for dex_file in self.dex_files:
            for dexClass in dex_file.classes:
                classes.add(dexClass.name)
        self.classes = sorted(classes)

    def get_methods(self, limit=10000):
        """获取所有方法路径 com/a/b/mtd_name

        Returns:
            TYPE: set
        """
        if self.methods is None:
            self._init_methods(limit)
        return self.methods

    def _init_methods(self, limit=10000):
        """初始化方法

        某些APK可能存在大量的方法，可能会相当耗时，根据情况加限制

        Args:
            limit (int, optional): 方法数量限制，超过该值，则不获取方法

        Returns:
            TYPE: 方法集合
        """
        methods = set()
        if not self.dex_files:
            self._init_dex_files()

        count = 0
        for dex_file in self.dex_files:
            count += dex_file.method_ids.size
        if limit < count:
            return

        for dex_file in self.dex_files:
            for dexClass in dex_file.classes:
                try:
                    dexClass.parseData()
                except IndexError:
                    continue

                for method in dexClass.data.methods:
                    clsname = method.id.cname.decode()
                    mtdname = method.id.name.decode()
                    methods.add(clsname + "/" + mtdname)
        self.methods = sorted(methods)

    def _init_strings_refx(self):
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

    def get_strings_refx(self):
        """获取字符串索引，即字符串被那些类、方法使用了。

        :return: 字符串索引
        :rtype: [dict]
        """
        if self.strings_refx is None:
            self._init_strings_refx()
        return self.strings_refx

    def get_methods_refx(self):
        """获取方法索引，即方法被那些类、方法使用了。

        :return: 方法索引
        :rtype: [dict]
        """
        if self.methods_refx is None:
            self._init_methods_refx()
        return self.methods_refx

    def _init_methods_refx(self):
        if not self.dex_files:
            self._init_dex_files()

        self.methods_refx = {}
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
                        if clsname in self.methods_refx:
                            if mtdname in self.methods_refx[clsname]:
                                self.methods_refx[clsname][mtdname].add(dexstr)
                            else:
                                self.methods_refx[clsname][mtdname] = set()
                                self.methods_refx[clsname][mtdname].add(dexstr)
                        else:
                            self.methods_refx[clsname] = {}
                            self.methods_refx[clsname][mtdname] = set()
                            self.methods_refx[clsname][mtdname].add(dexstr)

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
        if not self.dex_strings:
            self._init_dex_strings()
        return self.dex_strings

    def _init_dex_strings(self):
        if not self.dex_files:
            self._init_dex_files()

        str_set = set()
        for dex_file in self.dex_files:
            for i in range(dex_file.string_ids.size):
                ostr = dex_file.string(i)
                str_set.add(binascii.hexlify(ostr).decode())

        self.dex_strings = list(str_set)

    def get_files(self):
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
        except Exception as e:
            print(self.apk_path)
            print(e)


    def _init_arsc(self):
        ARSC_NAME = "resources.arsc"
        try:
            if ARSC_NAME in self.afile.namelist():
                data = self.afile.read(ARSC_NAME)
                self.arsc = ARSCParser(data)
        except Exception as e:
            print(self.apk_path)
            print(e)

    def get_arsc(self):
        if not self.arsc:
            self._init_arsc()

        return self.arsc

    def get_opcodes(self):
        if not self.opcodes:
            self._init_opcodes()
        return self.opcodes

    def _init_opcodes(self):
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

                    proto = self.get_proto_string(
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
    def get_proto_string(return_type, param_types):
        proto = return_type.decode()
        if len(proto) > 1:
            proto = "L"

        for item in param_types:
            param_type = item.decode()
            proto += "L" if len(param_type) > 1 else param_type

        return proto


    def get_app_icon(self):
        if self.app_icon:
            return self.app_icon
        self._init_app_icon()
        return self.app_icon

    def _init_app_icon(self):
        files = self.get_files()
        result = re.search(r':icon="@(.*?)"', self.get_manifest())
        ids = "0x" + result.groups()[0].lower()
        try:
            data = self.afile.read("resources.arsc")
            self.arscobj = ARSCParser(data)
            self.package = self.arscobj.get_packages_names()[0]
            datas = xmltodict.parse(self.arscobj.get_public_resources(self.package))
            for item in datas["resources"]["public"]:
                if ids != item["@id"]:
                    continue
                for f in files:
                    name = f["name"]
                    if item["@type"] in name and item["@name"] in name:
                        self.app_icon = name
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
                        from apkutils.cert import Certificate

                        cert = Certificate(data, _hash=_hash)
                        self.certs[_hash] = cert.get()
        except Exception as e:
            print(self.apk_path)
            print(e)

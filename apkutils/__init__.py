# coding: utf-8
import binascii
import xml
import zipfile

import xmltodict
from cigam import Magic

from apkutils import apkfile
from apkutils.axml.axmlparser import AXML
from apkutils.dex.dexparser import DexFile
from apkutils.manifest import Manifest
from apkutils.axml.arscparser import ARSCParser


class APK:

    def __init__(self, apk_path):
        self.apk_path = apk_path
        self.dex_files = None
        self.children = None
        self.org_manifest = None
        self.strings = None
        self.org_strings = None
        self.opcodes = None
        self.certs = []
        self._manifest = None

    def get_dex_files(self):
        if not self.dex_files:
            self._init_dex_files()
        return self.dex_files

    def _init_dex_files(self):
        self.dex_files = []
        try:
            with apkfile.ZipFile(self.apk_path, 'r') as z:
                for name in z.namelist():
                    data = z.read(name)
                    if name.startswith('classes') and name.endswith('.dex') \
                            and Magic(data).get_type() == 'dex':
                        dex_file = DexFile(data)
                        self.dex_files.append(dex_file)
        except Exception as ex:
            raise ex

    def get_strings(self):
        if not self.strings:
            self._init_strings()
        return self.strings

    def get_org_strings(self):
        if not self.org_strings:
            self._init_strings()
        return self.org_strings

    def _init_strings(self):
        if not self.dex_files:
            self._init_dex_files()

        str_set = set()
        org_str_set = set()
        for dex_file in self.dex_files:
            for i in range(dex_file.string_ids.size):
                ostr = dex_file.string(i)
                org_str_set.add(ostr)
                str_set.add(binascii.hexlify(ostr).decode())

        self.strings = list(str_set)
        self.org_strings = list(org_str_set)

    def get_files(self):
        if not self.children:
            self._init_children()
        return self.children

    def _init_children(self):
        self.children = []
        try:
            with apkfile.ZipFile(self.apk_path, mode="r") as zf:
                for name in zf.namelist():
                    try:
                        data = zf.read(name)
                        mine = Magic(data).get_type()
                        info = zf.getinfo(name)
                    except Exception as ex:
                        print(name, ex)
                        continue
                    item = {}
                    item["name"] = name
                    item["type"] = mine
                    item["time"] = "%d%02d%02d%02d%02d%02d" % info.date_time
                    crc = str(hex(info.CRC)).upper()[2:]
                    crc = '0' * (8 - len(crc)) + crc
                    item["crc"] = crc
                    # item["sha1"] = ""
                    self.children.append(item)
        except Exception as e:
            raise e

    def get_org_manifest(self):
        if not self.org_manifest:
            self._init_manifest()
        return self.org_manifest

    @property
    def resources(self):
        with zipfile.ZipFile(self.apk_path, mode="r") as zf:
            data = zf.read('resources.arsc')
            return ARSCParser(data)

    def _init_org_manifest(self):
        ANDROID_MANIFEST = "AndroidManifest.xml"
        try:
            with apkfile.ZipFile(self.apk_path, mode="r") as zf:
                if ANDROID_MANIFEST in zf.namelist():
                    data = zf.read(ANDROID_MANIFEST)
                    try:
                        axml = AXML(data)
                        if axml.is_valid:
                            self.org_manifest = axml.get_xml()
                    except Exception as e:
                        raise e
        except Exception as e:
            raise e

    def get_manifest(self):
        if not self._manifest:
            self._init_manifest()
        return self._manifest

    @property
    def manifest(self):
        return Manifest(self.get_org_manifest())

    def _init_manifest(self):
        if not self.org_manifest:
            self._init_org_manifest()

        if self.org_manifest:
            try:
                self._manifest = xmltodict.parse(
                    self.org_manifest, False)['manifest']
            except xml.parsers.expat.ExpatError as e:
                pass
            except Exception as e:
                raise e

    def get_certs(self):
        if not self.certs:
            self._init_certs()
        return self.certs

    def _init_certs(self):
        try:
            with apkfile.ZipFile(self.apk_path, mode="r") as zf:
                for name in zf.namelist():
                    if 'META-INF' in name:
                        data = zf.read(name)
                        mine = Magic(data).get_type()
                        if mine != 'txt':
                            from apkutils.cert import Certificate
                            cert = Certificate(data)
                            self.certs = cert.get()
        except Exception as e:
            raise e

    def get_opcodes(self):
        if not self.dex_files:
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
                        method.id.return_type, method.id.param_types)

                    item = {}
                    item['super_class'] = dexClass.super.decode()
                    item['class_name'] = method.id.cname.decode()
                    item['method_name'] = method.id.name.decode()
                    item['method_desc'] = method.id.desc.decode()
                    item['proto'] = proto
                    item['opcodes'] = opcodes
                    self.opcodes.append(item)

    @staticmethod
    def get_proto_string(return_type, param_types):
        proto = return_type.decode()
        if len(proto) > 1:
            proto = 'L'

        for item in param_types:
            param_type = item.decode()
            proto += 'L' if len(param_type) > 1 else param_type

        return proto

import binascii

import xmltodict
from cigam import Magic

from . import mzipfile as zipfile
from .axml.axmlparser import AXML
from .dex.dexparser import DexFile


class APK:

    def __init__(self, apk_path):
        self.apk_path = apk_path
        self.dex_files = None
        self.children = None
        self.manifest = None
        self.org_manifest = None
        self.strings = None
        self.opcodes = None

    def get_dex_files(self):
        if not self.dex_files:
            self._init_dex_files()
        return self.dex_files

    def _init_dex_files(self):
        self.dex_files = []
        try:
            with zipfile.ZipFile(self.apk_path, 'r') as z:
                for name in z.namelist():
                    # zipinfo = z.getinfo(name)
                    # zipinfo.flag_bits = 0
                    data = z.read(name)
                    if name.startswith('classes') and name.endswith('.dex'):
                        dex_file = DexFile(data)
                        self.dex_files.append(dex_file)
        except Exception as ex:
            raise ex

    def get_strings(self):
        if not self.strings:
            self._init_strings()
        return self.strings

    def _init_strings(self):
        if not self.dex_files:
            self._init_dex_files()

        str_set = set()
        for dex_file in self.dex_files:
            for i in range(dex_file.string_ids.size):
                str_set.add(binascii.hexlify(dex_file.string(i)).decode())

        self.strings = list(str_set)

    def get_files(self):
        if not self.children:
            self._init_children()
        return self.children

    def _init_children(self):
        self.children = []
        try:
            with zipfile.ZipFile(self.apk_path, mode="r") as zf:
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

    def get_manifest(self):
        if not self.manifest:
            self._init_manifest()
        return self.manifest

    def get_org_manifest(self):
        if not self.org_manifest:
            self._init_manifest()
        return self.org_manifest

    def _init_manifest(self):
        ANDROID_MANIFEST = "AndroidManifest.xml"
        try:
            with zipfile.ZipFile(self.apk_path, mode="r") as zf:
                if ANDROID_MANIFEST in zf.namelist():
                    zipinfo = zf.getinfo(ANDROID_MANIFEST)
                    zipinfo.flag_bits = 0
                    data = zf.read(ANDROID_MANIFEST)
                    try:
                        axml = AXML(data)
                        if axml.is_valid:
                            self.org_manifest = axml.get_xml()
                            self.manifest = xmltodict.parse(
                                self.org_manifest)['manifest']
                    except Exception as e:
                        raise e
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

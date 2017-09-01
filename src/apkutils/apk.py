import json
import xml
import zipfile
import traceback
import binascii

import xmltodict
from cigam import Magic

from .axml.axmlparser import AXML
from .dex.dexparser import DexFile


class APK:

    def __init__(self, apk_path):
        self.apk_path = apk_path
        self.dex_files = None
        self.children = None
        self.manifest = None
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
                    data = z.read(name)
                    if name.startswith('classes') and name.endswith('.dex'):
                        dex_file = DexFile(data)
                        self.dex_files.append(dex_file)
        except Exception:
            traceback.print_exc()

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
                    except:
                        traceback.print_exc()
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
        except Exception:
            traceback.print_exc()

    def get_manifest(self):
        if not self.manifest:
            self._init_manifest()
        return self.manifest

    def _init_manifest(self):
        ANDROID_MANIFEST = "AndroidManifest.xml"
        try:
            with zipfile.ZipFile(self.apk_path, mode="r") as zf:
                if ANDROID_MANIFEST in zf.namelist():
                    data = zf.read(ANDROID_MANIFEST)
                    try:
                        axml = AXML(data)
                        if axml.is_valid:
                            try:
                                self.manifest = xmltodict.parse(
                                    axml.get_xml())['manifest']
                            except xml.parsers.expat.ExpatError:
                                print('AndroidManifest Exception', end=' ')
                    except:
                        traceback.print_exc()
        except:
            traceback.print_exc()

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

                    proto = get_proto_string(
                        method.id.return_type, method.id.param_types)

                    item = {}
                    item['super_class'] = dexClass.super.decode()
                    item['class_name'] = method.id.cname.decode()
                    item['method_name'] = method.id.name.decode()
                    item['method_desc'] = method.id.desc.decode()
                    item['proto'] = proto
                    item['opcodes'] = opcodes
                    self.opcodes.append(item)


def get_files(apk_path):
    files = list()
    if zipfile.is_zipfile(apk_path):
        try:
            with zipfile.ZipFile(apk_path, mode="r") as zf:
                for name in zf.namelist():
                    try:
                        data = zf.read(name)
                        mine = Magic(data).get_mime()
                        info = zf.getinfo(name)
                    except:
                        traceback.print_exc()
                        continue
                    item = {}
                    item["name"] = name
                    item["type"] = mine
                    item["time"] = "%d%02d%02d%02d%02d%02d" % info.date_time
                    item["crc"] = ""
                    item["sha1"] = ""
                    files.append(item)

        except:
            traceback.print_exc()

    return files


def get_manifest(apk_path):
    ANDROID_MANIFEST = "AndroidManifest.xml"
    if zipfile.is_zipfile(apk_path):
        try:
            with zipfile.ZipFile(apk_path, mode="r") as zf:
                if ANDROID_MANIFEST in zf.namelist():
                    data = zf.read(ANDROID_MANIFEST)
                    try:
                        axml = AXML(data)
                        if axml.is_valid:
                            try:
                                return xmltodict.parse(axml.get_xml())['manifest']
                            except xml.parsers.expat.ExpatError:
                                print('AndroidManifest Exception', end=' ')
                    except:
                        traceback.print_exc()
        except:
            traceback.print_exc()

    return {}


def get_dex_files(apk_path):
    dex_files = []
    if zipfile.is_zipfile(apk_path):
        try:
            with zipfile.ZipFile(apk_path, 'r') as z:
                for name in z.namelist():
                    data = z.read(name)
                    if name.startswith('classes') and name.endswith('.dex'):
                        dex_file = DexFile(data)
                        dex_files.append(dex_file)
        except:
            traceback.print_exc()

    return dex_files


def get_strs(dex_files):
    str_set = set()
    for dex_file in dex_files:
        for i in range(dex_file.string_ids.size):
            str_set.add(binascii.hexlify(dex_file.string(i)).decode())

    return list(str_set)


def get_opcodes(dex_files):
    opcodes_list = []
    for dex_file in dex_files:
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

                proto = get_proto_string(
                    method.id.return_type, method.id.param_types)

                item = {}
                item['super_class'] = dexClass.super.decode()
                item['class_name'] = method.id.cname.decode()
                item['method_name'] = method.id.name.decode()
                item['method_desc'] = method.id.desc.decode()
                item['proto'] = proto
                item['opcodes'] = opcodes
                opcodes_list.append(item)

    return opcodes_list


def get_proto_string(return_type, param_types):
    proto = return_type.decode()
    if len(proto) > 1:
        proto = 'L'

    for item in param_types:
        param_type = item.decode()
        proto += 'L' if len(param_type) > 1 else param_type

    return proto


def get_dex_infos(apk_path, string_flag=True, opcodes_flag=True):
    """
    包含的信息

    {
        dex_header_infos: {
            class_num:
            str_num:
            ...
        }
        strings:[]
        datas:[
                {
                    super_class:
                    class_name:
                    method_name:
                    proto:
                    opcode:
                }
                {...}
        ]
    }
    """
    dex_infos = {}

    dex_files = get_dex_files(apk_path)
    if not dex_files:
        return dex_infos

    if string_flag:
        dex_infos["strings"] = get_strs(dex_files)
    if opcodes_flag:
        dex_infos["opcodes"] = get_opcodes(dex_files)

    return dex_infos


def get_elf_infos(apk_path):
    from .elf import elfparser
    elf_infos = []
    elf_datas = elfparser.get_elf_files(apk_path)
    for elf_name, elf_data, elf_file in elf_datas:
        item = {}
        item["name"] = elf_name
        item["strings"] = elfparser.get_rodata_strings(elf_file)
        item["dynsym"] = elfparser.get_dynsym_datas(elf_data, elf_file)

        elf_infos.append(item)

    return elf_infos


def get_resource_infos(apk_path):
    from .axml.arscparser import ARSCParser
    RESOURCES_ARSC = "resources.arsc"
    if zipfile.is_zipfile(apk_path):
        try:
            with zipfile.ZipFile(apk_path, mode="r") as zf:
                if "resources.arsc" in zf.namelist():
                    data = zf.read("resources.arsc")
                    try:
                        arscobj = ARSCParser(data)
                        package = arscobj.get_packages_names()[0]
                        return arscobj.get_string_resources(package)
                    except:
                        traceback.print_exc()
        except:
            traceback.print_exc()


def get_infos(apk_path):
    infos = {}

    infos["files"] = get_files(apk_path)
    infos["manifest"] = get_manifest(apk_path)
    infos["dex"] = get_dex_infos(apk_path)
    infos["elf"] = get_elf_infos(apk_path)

    return infos

"""DEX 读取：类、方法、字符串、交叉引用、opcode。

`DexReader` 持有一组已加载的 DEX 字节。

* `classes()` / `strings()` / `hex_strings()` 各自独立。
* `methods()` / `strings_refx_index()` / `methods_refx_index()` /
  `opcodes_list()` 共享同一个遍历骨架 `_iter_parsed_classes()`，
  但各自 lazy、各自缓存，互不触发。
* `method_strings()` / `xref()` 是定向查询，有 early-break，不走骨架。

归档扫描（找 classes*.dex）与 I/O 是 facade 的事；这里只吃字节。
坏 blob 逐个跳过并记进 `skipped`，不牵连其余 blob。
"""

import binascii

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

# 1A const-string / 1B const-string-jumbo
CONST_STRING_OPCODES = {26, 27}


class DexError(Exception):
    """DEX 无法解析。"""


class DexReader:
    """一组 DEX 文件的只读视图。"""

    def __init__(self, blobs=()):
        self.dex_files = []
        self.skipped = []
        for blob in blobs:
            try:
                self.dex_files.append(DexFile(blob))
            except Exception as e:
                self.skipped.append(e)

        self._classes = None
        self._methods = None
        self._strings_refx = None
        self._methods_refx = None
        self._opcodes = None
        self._dex_strings = []
        self._dex_hex_strings = None

    def files(self):
        return self.dex_files

    def _iter_parsed_classes(self):
        """所有解析成功的 ``(dex_file, dex_class)``。

        唯一的遍历骨架：先 `parseData()`（`DexClass` 自己会缓存），
        坏类跳过。四个索引视图都从这里出发。
        """
        for dex_file in self.dex_files:
            for dex_class in dex_file.classes:
                try:
                    dex_class.parseData()
                except IndexError:
                    continue
                yield dex_file, dex_class

    # --- 类 ---------------------------------------------------------------

    def classes(self):
        if self._classes is None:
            classes = set()
            for dex_file in self.dex_files:
                for dex_class in dex_file.classes:
                    classes.add(dex_class.name)
            self._classes = sorted(classes)
        return self._classes

    # --- 四个独立 lazy 视图 -----------------------------------------------

    def methods(self):
        """所有方法，形如 ``pkg/cls/mtd_name``。"""
        if self._methods is None:
            methods = set()
            for _, dex_class in self._iter_parsed_classes():
                for method in dex_class.data.methods:
                    cname = method.id.cname
                    if cname is None:
                        continue
                    methods.add(cname.decode() + "/" + method.id.name.decode())
            self._methods = methods
        return self._methods

    def strings_refx_index(self):
        """字符串被哪些类、方法使用。"""
        if self._strings_refx is None:
            index = {}
            for dex_file, dex_class in self._iter_parsed_classes():
                for method in dex_class.data.methods:
                    if not method.code or method.id.cname is None:
                        continue
                    clsname = method.id.cname.decode()
                    mtdname = method.id.name.decode()
                    for bc in method.code.bytecode:
                        if bc.opcode not in CONST_STRING_OPCODES:
                            continue
                        dexstr = dex_file.string(bc.args[1])
                        bucket = index.setdefault(clsname, {})
                        bucket.setdefault(mtdname, set()).add(dexstr)
            self._strings_refx = index
        return self._strings_refx

    def methods_refx_index(self):
        """方法被哪些类、方法引用。"""
        if self._methods_refx is None:
            index = {}
            for dex_file, dex_class in self._iter_parsed_classes():
                for method in dex_class.data.methods:
                    if not method.code or method.id.cname is None:
                        continue
                    clsname = method.id.cname.decode()
                    mtdname = method.id.name.decode()
                    for bc in method.code.bytecode:
                        if bc.opcode not in INVOKE_OPCODES:
                            continue
                        method_id = dex_file.method_id(bc.args[0])
                        dexstr = method_id.cname + b"->" + method_id.name
                        bucket = index.setdefault(clsname, {})
                        bucket.setdefault(mtdname, set()).add(dexstr)
            self._methods_refx = index
        return self._methods_refx

    def opcodes_list(self):
        """每个方法的 opcode 串、proto 与所属类。"""
        if self._opcodes is None:
            opcodes = []
            for _, dex_class in self._iter_parsed_classes():
                super_name = dex_class.super and dex_class.super.decode()
                for method in dex_class.data.methods:
                    cname = method.id.cname
                    if cname is None:
                        continue

                    opcode_text = ""
                    if method.code:
                        for bc in method.code.bytecode:
                            opcode = str(hex(bc.opcode)).upper()[2:]
                            opcode_text += (
                                opcode if len(opcode) == 2 else "0" + opcode
                            )

                    opcodes.append(
                        {
                            "super_class": super_name,
                            "class_name": cname.decode(),
                            "method_name": method.id.name.decode(),
                            "method_desc": method.id.desc.decode(),
                            "proto": convert_proto_string(
                                method.id.return_type, method.id.param_types
                            ),
                            "opcodes": opcode_text,
                        }
                    )
            self._opcodes = opcodes
        return self._opcodes

    # --- 定向查询（不走骨架） ---------------------------------------------

    def method_strings(self, mtd):
        """某个方法里所有 ``const-string`` 字符串。"""
        arr = mtd.split("->")
        cname = arr[0].encode("utf-8")
        arr = arr[1].split("(")
        mname = arr[0].encode("utf-8")
        desc = ("(" + arr[1]).encode("utf-8")

        strings = set()
        for dex_file in self.dex_files:
            for dex_class in dex_file.classes:
                if dex_class.name == cname:
                    try:
                        dex_class.parseData()
                    except IndexError:
                        continue
                    for method in dex_class.data.methods:
                        if method.id.name != mname:
                            continue
                        if desc != method.id.desc:
                            continue
                        if not method.code:
                            continue
                        for bc in method.code.bytecode:
                            if bc.opcode not in CONST_STRING_OPCODES:
                                continue
                            strings.add(dex_file.string(bc.args[1]).decode("utf-8"))
                    break
        return strings

    def xref(self, mtd):
        """所有引用 ``pkg/cls->mtd()`` 的方法。"""
        mtd = mtd.encode("utf-8")

        mtds = set()
        for dex_file in self.dex_files:
            for dex_class in dex_file.classes:
                try:
                    dex_class.parseData()
                except IndexError:
                    continue

                for method in dex_class.data.methods:
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

    # --- 字符串池 ---------------------------------------------------------

    def strings(self):
        if self._dex_strings == []:
            self._init_strings()
        return self._dex_strings

    def _init_strings(self):
        str_set = set()
        hex_str_set = set()
        for dex_file in self.dex_files:
            for i in range(dex_file.string_ids.size):
                ostr = dex_file.string(i)
                str_set.add(ostr)
                hex_str_set.add(binascii.hexlify(ostr).decode())

        self._dex_strings = list(str_set)
        self._dex_hex_strings = list(hex_str_set)

    def hex_strings(self):
        return self._dex_hex_strings


def convert_proto_string(return_type, param_types):
    proto = return_type.decode()
    if len(proto) > 1:
        proto = "L"

    for item in param_types:
        param_type = item.decode()
        proto += "L" if len(param_type) > 1 else param_type

    return proto

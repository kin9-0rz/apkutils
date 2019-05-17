import binascii
import re
import xml

import xmltodict
from anytree import Node, RenderTree
from anytree.resolver import Resolver
from apkutils import apkfile
from apkutils.axml.arscparser import ARSCParser
from apkutils.axml.axmlparser import AXML
from apkutils.dex.dexparser import DexFile
from cigam import Magic
from TextWizard import hash

__VERSION__ = '0.6.6'

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
INVOKE_OPCODES = {0x6e, 0x6f, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76, 0x77, 0x78}


class APK:

    def __init__(self, apk_path):
        self.apk_path = apk_path
        self.dex_files = None
        self.children = None
        self.manifest = None
        self.org_manifest = None
        self.strings = None     # 16进制字符串
        self.org_strings = None  # 原始字符串
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

    @staticmethod
    def serialize_xml(org_xml):
        if not org_xml:
            return None
        _xml = re.sub(r'\n', ' ', org_xml)
        _xml = re.sub(r'"\s+?>', '">', _xml)
        _xml = re.sub(r'>\s+?<', '><', _xml)
        return _xml

    def get_mini_mani(self):
        if not self.mini_mani:
            self.mini_mani = self.serialize_xml(self.get_org_manifest())
        return self.mini_mani

    def get_main_activity(self):
        if not self.main_activity:
            self._init_main_activity()
        return self.main_activity

    def _init_main_activity(self):
        mani = self.get_mini_mani()
        ptn = r'<activity android:name="([^"]*?)"[^<>]*?>.*?<action android:name="android.intent.action.MAIN">.*?</activity>'
        result = re.search(ptn, mani)
        if result:
            self.main_activity = result.groups()[0]

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

    def get_app_icon(self):
        if self.app_icon:
            return self.app_icon
        self._init_app_icon()
        return self.app_icon

    def _init_app_icon(self):
        files = self.get_files()
        result = re.search(r':icon="@(.*?)"', self.get_org_manifest())
        ids = '0x' + result.groups()[0].lower()
        try:
            with apkfile.ZipFile(self.apk_path, 'r') as z:
                data = z.read('resources.arsc')
                self.arscobj = ARSCParser(data)
                self.package = self.arscobj.get_packages_names()[0]
                datas = xmltodict.parse(
                    self.arscobj.get_public_resources(self.package))
                for item in datas['resources']['public']:
                    if ids != item['@id']:
                        continue
                    for f in files:
                        name = f['name']
                        if item['@type'] in name and item['@name'] in name:
                            self.app_icon = name
        except Exception as ex:
            raise ex

    def get_trees(self, height=2, limit=5000):
        if self.trees is None:
            self._init_trees(height, limit)
        return self.trees

    @staticmethod
    def pretty_print(node):
        """漂亮地打印一个节点

        Args:
            node (TYPE): Description
        """
        for pre, _, node in RenderTree(node):
            print('{}{}'.format(pre, node.name))

    def _init_trees(self, height, limit):
        if self.methods is None:
            self._init_methods(limit)
        if not self.methods:
            return

        root = Node('root')
        r = Resolver(pathattr='name')

        def find_node(path):
            """查找节点

            Args:
                root (TYPE): Description
                path (TYPE): Description

            Returns:
                TYPE: Description
            """
            try:
                return r.glob(root, path)[0]
            except Exception:
                return None

        def to_nodes(mtd):
            """把一个方法，转化成节点

            Args:
                root (TYPE): 根节点
                mtd (TYPE): Description

            Returns:
                TYPE: Node
            """
            current = root
            node_path = '/root'
            for item in mtd.split('/'):
                node_path = node_path + '/' + item
                tnode = find_node(node_path)
                if tnode:
                    current = tnode
                else:
                    current = Node(item, parent=current)

        count = 0
        # TODO  节点插入的顺序，决定了树的遍历顺序，及其计算结果
        # 假设2个结构一样，但是，因为名字顺序不一样，导致插入顺序不一致
        # 有可能导致一样的结构不一样的结果。
        for mtd in self.methods:
            count += 1
            to_nodes(mtd)

        def serialize_node(root_node):
            snum = ''
            for pre, _, node in RenderTree(root_node):
                snum = snum + str(node.height)
            return snum

        self.trees = {}
        for pre, _, node in RenderTree(root):
            if node.height > height:
                key = hash.hash(serialize_node(node), 'md5')
                if key in self.trees:
                    self.trees[key].append(node)
                else:
                    self.trees[key] = [node]

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
                    methods.add(clsname + '/' + mtdname)
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
                        dexstr = mtd_cname + b'->' + mtd_name
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
        if not self.manifest:
            self._init_manifest()
        return self.manifest

    def _init_manifest(self):
        if not self.org_manifest:
            self._init_org_manifest()

        if self.org_manifest:
            try:
                self.manifest = xmltodict.parse(
                    self.org_manifest, False)['manifest']
            except xml.parsers.expat.ExpatError as e:
                pass
            except Exception as e:
                raise e

    def _init_arsc(self):
        ARSC_NAME = 'resources.arsc'
        try:
            with apkfile.ZipFile(self.apk_path, mode="r") as zf:
                if ARSC_NAME in zf.namelist():
                    data = zf.read(ARSC_NAME)
                    self.arsc = ARSCParser(data)
        except Exception as e:
            raise e

    def get_arsc(self):
        if not self.arsc:
            self._init_arsc()

        return self.arsc

    def get_certs(self, digestalgo='md5'):
        if digestalgo not in self.certs:
            self._init_certs(digestalgo)
        return self.certs[digestalgo]

    def _init_certs(self, digestalgo):
        try:
            with apkfile.ZipFile(self.apk_path, mode="r") as zf:
                for name in zf.namelist():
                    if name.startswith('META-INF/') and name.endswith(('.DSA', '.RSA')):
                        data = zf.read(name)
                        mine = Magic(data).get_type()
                        if mine != 'txt':
                            from apkutils.cert import Certificate
                            cert = Certificate(data, digestalgo=digestalgo)
                            self.certs[digestalgo] = cert.get()
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

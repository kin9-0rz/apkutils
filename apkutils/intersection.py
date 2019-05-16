import re


class APK_Intersection:

    def __init__(self, apks):
        self.apks = apks

        permission_pattern1 = r'uses-permission\s+?.*?:name="([^"]+?)"'
        permission_pattern2 = r'android:permission="([^"]+?)"'
        self.perm1_matcher = re.compile(permission_pattern1)
        self.perm2_matcher = re.compile(permission_pattern2)

        action_pattern = r'action\s+?.*?:name="([^"]+?)"'
        self.action_matcher = re.compile(action_pattern)

    def get_permissions(self, mani):
        perms = set()
        iter = self.perm1_matcher.finditer(mani)
        for item in iter:
            perms.add(item.groups()[0])

        iter = self.perm2_matcher.finditer(mani)
        for item in iter:
            perms.add(item.groups()[0])
        return perms

    def get_actions(self, mani):
        actions = set()
        iter = self.action_matcher.finditer(mani)
        for item in iter:
            actions.add(item.groups()[0])
        return actions

    def serialize_xml(self, org_xml):
        _xml = re.sub(r'\n', ' ', org_xml)
        _xml = re.sub(r'"\s+?>', '">', _xml)
        _xml = re.sub(r'>\s+?<', '><', _xml)
        return _xml

    def common(self, one, two):
        """清单内容交集，不一样的地方用*号表示。
        注：只是简单的匹配，可能不如人意。
        Args:
            one (TYPE): 第一个清单
            two (TYPE): 第二个清单

        Returns:
            TYPE: 清单交集
        """
        import difflib
        from difflib import SequenceMatcher as SM
        s = SM(None, one, two)
        r = s.ratio()
        if r == 1.0:
            return one

        d = difflib.Differ()
        sss = ''
        for item in list(d.compare(one, two)):
            if item.startswith(' '):
                sss += item[2:]
            elif not sss.endswith('*'):
                sss += '*'
        return sss

    def intersect_manifest(self):
        """清单交集

        - 权限
        - actions
        - 清单内容交集

        Returns:
            TYPE: (权限, actions, 清单内容交集)
        """
        flag = True  # 第一次
        aflag = True
        perms = set()
        actions = set()

        same = None
        for apk in self.apks:
            mani = apk.get_org_manifest()
            if not mani:
                print('not mani')
                continue
            mani = self.serialize_xml(mani)

            if flag:
                perms = self.get_permissions(mani)
                flag = False
            else:
                perms = perms & self.get_permissions(mani)

            if aflag:
                actions = self.get_actions(mani)
                aflag = False
            elif not actions:
                actions = None
            else:
                actions = actions & self.get_actions(mani)

            if not same:
                same = mani
            else:
                same = self.common(same, mani)

        result = ''
        if same:
            result = re.sub(r'"[^"]+?\*[^"]+?"', '"[^"]+?"', same)

        return (sorted(perms), sorted(actions), [result])

    def intersect_dex_string_refx(self):
        """字符串交集

        真正的字符串，不包含类名、方法命。
        特征方法中定义的、使用的字符串。
        """
        def to_set(data):
            strs = set()
            for key, value in data.items():
                for _, v in value.items():
                    strs.update(v)
            return strs

        flag = True
        strings = set()
        for apk in self.apks:
            if flag:
                strings = to_set(apk.get_strings_refx())
                flag = False
            else:
                strings = strings & to_set(apk.get_strings_refx())
        return sorted(strings)

    def intersect_dex_apis(self):
        """api字符串交集

        真正的字符串不包含类名、方法名。
        特征方法中定义的、使用的字符串。
        """
        def to_set(data):
            strs = set()
            for key, value in data.items():
                # print(key, value)
                for _, v in value.items():
                    strs.update(v)
            return strs

        flag = True
        strings = set()
        for apk in self.apks:
            if flag:
                strings = to_set(apk.get_methods_refx())
                flag = False
            else:
                strings = strings & to_set(apk.get_methods_refx())
        return sorted(strings)

    def intersect_dex_string(self):
        flag = True
        strings = set()
        for apk in self.apks:
            if flag:
                strings = set(apk.get_strings())
                flag = False
            else:
                strings = strings & set(apk.get_strings())

        return sorted(strings)

    def intersect_dex_opcode(self):
        pass

    def intersect_arsc(self):
        pass

    def intersect_mf(self):
        pass

    def intersect_dex_tree(self):
        md5s = set()
        flag = True
        ftree = None
        for apk in self.apks:
            result = apk.get_trees()
            if flag:
                ftree = result
            if not result:
                continue

            if flag:
                md5s = result.keys()
                flag = False
            else:
                md5s = md5s & result.keys()

        return (ftree, md5s)

    def intersect_apis(self):
        for apk in self.apks:
            print(apk.get_methods_refx())
            return

    def intersect_resources(self):
        flag1 = True
        files = set()
        for apk in self.apks:
            if flag1:
                for item in apk.get_files():
                    files.add(item.get('name'))
                flag1 = False
                continue
            tmps = set()
            for item in apk.get_files():
                tmps.add(item.get('name'))
            files = files & tmps
        print('res = [')
        for item in sorted(files):
            print("    '{}',".format(item))
        print(']')

import os.path
import re

from apkutils import wildcard


class APK_Intersection:

    def __init__(self, apks):
        self.apks = apks

        permission_pattern1 = r'uses-permission\s+?.*?:name="([^"]+?)"'
        permission_pattern2 = r'android:permission="([^"]+?)"'
        self.perm1_matcher = re.compile(permission_pattern1)
        self.perm2_matcher = re.compile(permission_pattern2)

        action_pattern = r'action\s+?.*?:name="([^"]+?)"'
        self.action_matcher = re.compile(action_pattern)

        category_pattern = r'<category\s[^>]*?:name="([^"]+?)"'
        self.category_matcher = re.compile(category_pattern)

        uses_feature_pattern = r'<uses-feature\s[^>]*?:name="([^"]+?)"'
        self.uses_feature_matcher = re.compile(uses_feature_pattern)

        activity_pattern = r'<activity\s[^>]*?:name="([^"]*?)"'
        self.activity_matcher = re.compile(activity_pattern)

        activity_alias_pattern = r'<activity-alias\s[^>]*?:name="([^"]*?)"'
        self.activity_alias_matcher = re.compile(activity_alias_pattern)

        receiver_pattern = r'<receiver\s[^>]*?:name="([^"]*?)"'
        self.receiver_matcher = re.compile(receiver_pattern)

        service_pattern = r'<service\s[^>]*?:name="([^"]*?)"'
        self.service_matcher = re.compile(service_pattern)

        provider_pattern = r'<provider\s[^>]*?:name="([^"]*?)"'
        self.provider_matcher = re.compile(provider_pattern)

        meta_name_pattern = r'<meta-data\s[^>]*?:name="([^"]*?)"'
        self.meta_name_matcher = re.compile(meta_name_pattern)

        meta_value_pattern = r'<meta-data\s[^>]*?:value="([^"]*?)"'
        self.meta_value_matcher = re.compile(meta_value_pattern)

        label_pattern = r'android:label="([^"]+?)"'
        self.label_matcher = re.compile(label_pattern)

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

    def intersect_manifest_tag_num(self):
        result = {
            # min max
            'uses-permission': [0xFF, 0],
            'activity': [0xFF, 0],
            'receiver': [0xFF, 0],
            'service': [0xFF, 0],
            'provider': [0xFF, 0],
            'version_code': [0xFF, 0],
        }
        for item in self.apks:
            nums = item.get_manifest_tag_numbers()
            if nums is None:
                continue
            for key, value in nums.items():
                mm = result.get(key)
                if mm[0] > value:
                    mm[0] = value
                if mm[1] < value:
                    mm[1] = value
                result[key] = mm

        return result, nums

    @staticmethod
    def gen_words(s):
        words = set()
        size = len(s)

        for offset in range(1, size+1):
            for i in range(0, size+1-offset):
                word = '.'.join(s[i:i+offset])
                start = ''
                end = ''
                if i > 0:
                    start = '*.'
                if size - offset > i:
                    end = '.*'
                words.add(start + word + end)
        return words

    def intersect_manifest(self):
        """清单交集

        Returns:
            TYPE: 清单内容交集
        """
        nums = {
            # min max
            'uses-permission': [0xFF, 0],
            'activity': [0xFF, 0],
            'receiver': [0xFF, 0],
            'service': [0xFF, 0],
            'provider': [0xFF, 0],
            'version_code': [0xFF, 0],
        }

        import jieba

        is_first = True
        words = {
            'uses-permission': set(),
            'application': set(),
            'activity': set(),
            'activity-alias': set(),
            'receiver': set(),
            'service': set(),
            'provider': set(),
            'action': set(),
            'meta-data:name': set(),
            'meta-data:value': set(),
            'label': set(),

        }

        same = None
        for apk in self.apks:
            mani = apk.get_org_manifest()
            if not mani:
                print(apk.apk_path, 'no mani')
                continue

            application = apk.get_application()
            app_words = set()
            if application:
                app_words = APK_Intersection.gen_words(application.split('.'))
            if is_first:
                words['application'] = app_words
            else:
                words['application'] &= app_words

            mani = self.serialize_xml(mani)
            pieces = set()
            for item in self.perm1_matcher.finditer(mani):
                pieces.add(item.groups()[0])
            if is_first:
                words['uses-permission'] = pieces
            else:
                words['uses-permission'] &= pieces

            pieces = set()
            for item in self.uses_feature_matcher.finditer(mani):
                pieces.add(item.groups()[0])
            if is_first:
                words['uses-feature'] = pieces
            else:
                words['uses-feature'] &= pieces

            pieces = set()
            for item in self.action_matcher.finditer(mani):
                pieces.add(item.groups()[0])
            if is_first:
                words['action'] = pieces
            else:
                words['action'] &= pieces

            pieces = set()
            for item in self.category_matcher.finditer(mani):
                pieces.add(item.groups()[0])
            if is_first:
                words['category'] = pieces
            else:
                words['category'] &= pieces

            pieces = set()
            for item in self.label_matcher.finditer(mani):
                pieces.add(item.groups()[0])
            if is_first:
                words['label'] = pieces
            else:
                words['label'] &= pieces

            pieces = set()
            for item in self.meta_name_matcher.finditer(mani):
                pieces.add(item.groups()[0])
            if is_first:
                words['meta-data:name'] = pieces
            else:
                words['meta-data:name'] &= pieces

            pieces = set()
            for item in self.meta_value_matcher.finditer(mani):
                pieces.add(item.groups()[0])
            if is_first:
                words['meta-data:value'] = pieces
            else:
                words['meta-data:value'] &= pieces

            pieces = set()
            for item in self.activity_matcher.finditer(mani):
                piece = APK_Intersection.gen_words(item.groups()[0].split('.'))
                pieces |= piece
            if is_first:
                words['activity'] = pieces
            else:
                words['activity'] &= pieces

            pieces = set()
            for item in self.receiver_matcher.finditer(mani):
                piece = APK_Intersection.gen_words(item.groups()[0].split('.'))
                pieces |= piece
            if is_first:
                words['receiver'] = pieces
            else:
                words['receiver'] &= pieces

            pieces = set()
            for item in self.service_matcher.finditer(mani):
                piece = APK_Intersection.gen_words(item.groups()[0].split('.'))
                pieces |= piece
            if is_first:
                words['service'] = pieces
            else:
                words['service'] &= pieces

            pieces = set()
            for item in self.provider_matcher.finditer(mani):
                piece = APK_Intersection.gen_words(item.groups()[0].split('.'))
                pieces |= piece
            if is_first:
                words['provider'] = pieces
            else:
                words['provider'] &= pieces

            if is_first:
                is_first = False

            if not same:
                same = mani
            else:
                same = self.common(same, mani)

            mtn = apk.get_manifest_tag_numbers()
            if mtn is None:
                continue
            for key, value in mtn.items():
                mm = nums.get(key)
                if mm[0] > value:
                    mm[0] = value
                if mm[1] < value:
                    mm[1] = value
                nums[key] = mm

        return words, nums

    def intersect_dex_string_refx(self, filters):
        """字符串交集

        真正的字符串，不包含类名、方法命。
        特征方法中定义的、使用的字符串。
        """
        def to_set(data):
            """通过类名，过滤不必要的字符串

            Args:
                data ([type]): [description]

            Returns:
                [type]: [description]
            """
            strs = set()
            for key, value in data.items():
                skip = False
                for item in filters:
                    if item in key:
                        skip = True
                        break
                if skip:
                    continue

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

    def intersect_dex_opcode(self, is_wildcard, is_obj):
        """[summary]

        Args:
            is_wildcard (bool): 是否通配
            is_obj (bool): 父类是否为Object

        Returns:
            [type]: [description]
        """
        ops_set = set()
        fuzzy_ops_set = set()
        method_dict = dict()
        is_first = True

        common_opcodes = []

        for apk in self.apks:
            opcodes = apk.get_opcodes()
            if is_first:
                for item in opcodes:
                    super_class = item['super_class']
                    if is_obj and super_class != 'java/lang/Object':
                        continue
                    if not is_obj and super_class == 'java/lang/Object':
                        continue
                    common_opcodes.append(item)
                is_first = False
                continue

            next_common_opcodes = []
            for item1 in opcodes:
                sup1 = item1['super_class']
                if is_obj and sup1 != 'java/lang/Object':
                    continue
                if not is_obj and sup1 == 'java/lang/Object':
                    continue

                proto1 = item1['proto']
                opcs1 = item1['opcodes']
                len1 = len(opcs1)

                if len1 < 10:
                    continue

                max_item = None
                max_ratio = 0
                max_len = 0
                for item2 in common_opcodes:
                    sup2 = item2['super_class']
                    proto2 = item2['proto']
                    opcs2 = item2['opcodes']

                    if (sup1, proto1, opcs1) == (sup2, proto2, opcs2):
                        if item2 not in next_common_opcodes:
                            next_common_opcodes.append(item2)
                        break

                    if is_wildcard and (sup1, proto1) == (sup2, proto2):
                        len2 = len(opcs2)
                        ratio = wildcard.get_ratio(opcs1, opcs2, 2)
                        if ratio > max_ratio:
                            max_ratio = ratio
                            max_item = item2

                if max_ratio:
                    com_opcs = wildcard.get_wildcards(
                        opcs1, max_item['opcodes'])
                    len2 = len(com_opcs)
                    if len1 > len2:
                        max_len = len1
                    else:
                        max_len = len2

                    max_item['max_len'] = max_len
                    max_item['opcodes'] = com_opcs
                    next_common_opcodes.append(max_item)

            common_opcodes = next_common_opcodes

        return common_opcodes

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

    def intersect_arsc(self):
        flag = True
        result = set()
        for apk in self.apks:
            arsc = apk.get_arsc()
            pns = arsc.get_packages_names()

            tmps = set()
            for item in pns:
                for sr in arsc.get_string_resources(item):
                    tmps.add((sr['name'], sr['value']))

            if flag:
                flag = False
                result = tmps
            else:
                result = result & tmps

        return result

    def intersect_files(self):
        flag1 = True
        files1 = set()
        for apk in self.apks:
            tmps = set()
            for item in apk.get_files():
                tmps.add((item['name'], item['crc']))

            if flag1:
                files1 = tmps
                flag1 = False
            else:
                files1 = files1 & tmps

        flag1 = True
        files2 = set()
        for apk in self.apks:
            tmps = set()
            for item in apk.get_files():
                tmps.add(item.get('name'))

            if flag1:
                files2 = tmps
                flag1 = False
            else:
                files2 = files2 & tmps

        flag1 = True
        files3 = set()
        for apk in self.apks:
            tmps = set()
            for item in apk.get_files():
                tmps.add(item['crc'])

            if flag1:
                files3 = tmps
                flag1 = False
            else:
                files3 = files3 & tmps

        return sorted(files1), sorted(files2), sorted(files3)

    def intersect_certs(self):
        for apk in self.apks:
            print(apk.get_certs())

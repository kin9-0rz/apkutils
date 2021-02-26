from difflib import Differ, SequenceMatcher


def get_max_len(wildcards):
    '''
        find the max length from wildcards.
    '''
    mlen = 0
    for item in wildcards.split('*'):
        length = len(item)
        if length > mlen:
            mlen = length


# FIXME 直接生成*.*.*.*， 或者，compare的顺序相反？但是仍然不能避免。
def get_wildcards(str1, str2, min_length=0):
    '''
        获取2个字符串的通配符字符串,
        length，2个*之间的字符串的最小长度，默认为0。
        如果小于这个长度，那么会变成*；如果min_length=1，*a* -> *
    '''
    if not str1 or not str2:
        return None

    num1 = str1.count('.')
    num2 = str2.count('.')

    if num2 < num1:
        num1 = num2

    diff = Differ().compare(str1, str2)
    diff = Differ().compare(str2, str1)
    # print('-' * 100)
    # print(str1, str2)
    # print(num1, num2)
    wildcards = ''
    for item in list(diff):
        if '-' in item or '+' in item:
            if not wildcards.endswith('*'):
                wildcards = wildcards + '*'
        else:
            wildcards = wildcards + item.strip()

    if not wildcards:
        return wildcards

    result = ''
    if min_length > 0:
        if wildcards[0] == '*':
            result = '*'
        is_first = True
        for item in wildcards.split('*'):
            if is_first:
                is_first = False
                if len(item) < min_length and not result.endswith('*'):
                    result = result + '*'
            elif not result.endswith('*'):
                result = result + '*'

            if len(item) > min_length:
                result = result + item
            elif '.' in item:
                result = result + '.'
    else:
        result = wildcards

    return result


def get_wildcards_in_list(str_list, min_length=0):
    '''
        获取一个通配字符串，可以通配符该列表里面所有的字符串。
    '''
    wildcards = str_list[0]
    str_list.remove(wildcards)
    for item in str_list:
        wildcards = get_wildcards(wildcards, item, min_length)

    return wildcards


def get_best_wildcard_from_list(str1, str_list, min_length=0):
    '''
        从列表str_list中，找出一个与str最相似的通配字符串。
    '''
    best_radio = 0.0
    best_str = ''
    for sss in str_list:
        radio = get_ratio(str1, sss)
        if best_radio < radio:
            best_radio = radio
            best_str = sss

    return get_wildcards(str1, best_str, min_length)


def get_ratio(str1, str2, weight=3):
    len1 = len(str1)
    len2 = len(str2)
    if len1 < weight or len2 < weight:
        return 0
    # print(int(len1 / len2 + len2 / len1))
    if int(len1 / len2 + len2 / len1) >= weight:
        return 0
    return SequenceMatcher(None, str1, str2).ratio()


def gen_wildcard_str(str1, str2, min_length=0):
    '''
        get commom opcode
    '''
    result = ''
    fcp = find_common_opcodes(str1, str2)
    for key, value in fcp[0]:
        if key and len(value) > min_length:
            result = result + value + '*'

    result = result.replace('**', '*')
    if result.endswith('*'):
        return result[:-1]
    return result


def longest_common_subopcode(s1, s2):
    '''
        如果是2个普通串还好，但是，如果里面包含*，这种符号，那就完蛋了
    '''
    m = [[0] * (1 + len(s2)) for i in range(1 + len(s1))]
    longest, x_longest = 0, 0
    for x in range(1, 1 + len(s1)):
        for y in range(1, 1 + len(s2)):
            if s1[x - 1] == s2[y - 1]:
                m[x][y] = m[x - 1][y - 1] + 1
                if m[x][y] > longest:
                    longest = m[x][y]
                    x_longest = x
            else:
                m[x][y] = 0

    if '*' not in s1:
        end = x_longest & ~1
        longest = longest - (x_longest - end)
        start = end - (longest & ~1)
        subopcode = s1[start:end]
    else:
        start = x_longest - longest
        end = x_longest
        subopcode = s1[start:end]
        if subopcode.startswith('*') and len(subopcode) % 2 == 0:
            subopcode = subopcode[0:-1]
    return subopcode


def find_common_opcodes(s1, s2):  # used recursively
    if s1 == '' or s2 == '':
        return [], []
    com = longest_common_subopcode(s1, s2)
    if len(com) < 2:
        return ([(0, s1)], [(0, s2)])
    s1_bef, _, s1_aft = s1.partition(com)
    s2_bef, _, s2_aft = s2.partition(com)
    before = find_common_opcodes(s1_bef, s2_bef)
    after = find_common_opcodes(s1_aft, s2_aft)
    return (before[0] + [(1, com)] + after[0],
            before[1] + [(1, com)] + after[1])


def longest_common_substring(s1, s2):
    m = [[0] * (1 + len(s2)) for i in range(1 + len(s1))]
    longest, x_longest = 0, 0
    for x in range(1, 1 + len(s1)):
        for y in range(1, 1 + len(s2)):
            if s1[x - 1] == s2[y - 1]:
                m[x][y] = m[x - 1][y - 1] + 1
                if m[x][y] > longest:
                    longest = m[x][y]
                    x_longest = x
            else:
                m[x][y] = 0
    return s1[x_longest - longest:x_longest]


def find_common_patterns(s1, s2):  # used recursively
    if s1 == '' or s2 == '':
        return [], []
    com = longest_common_substring(s1, s2)
    if len(com) < 2:
        return ([(0, s1)], [(0, s2)])
    s1_bef, _, s1_aft = s1.partition(com)
    s2_bef, _, s2_aft = s2.partition(com)
    before = find_common_patterns(s1_bef, s2_bef)
    after = find_common_patterns(s1_aft, s2_aft)
    return (before[0] + [(1, com)] + after[0],
            before[1] + [(1, com)] + after[1])

# 将opcode 分成opcode数组，然后，再diff，也许效果会好一些，只要有差异就不接受？


if __name__ == '__main__':
    print('hello')
    a = '*o*.*.*.*m*'
    c = '*.*o*.*.*m'
    b = 'mb.cvf.jt.jge.pt.oirg'
    d = 'com.android.dyad.MyApplication'

    d2 = 'com.system.activity.MyApplication'
    e = 'com.wjbl.mio.efj.ycgh.rywy.prl'
    print(get_wildcards(a, b))
    print(gen_wildcard_str(d, d2))
    print(get_wildcards(c, b))
    print(get_wildcards(d, e, 1))

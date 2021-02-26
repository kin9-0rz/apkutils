import binascii
import os

from apkutils import APK

file_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", 'data', 'test'))
apk = APK(file_path)

org_strs = apk.get_org_strings()  # the strings from all of classes\d*.dex
for item in org_strs:
    if 'helloword' in item.decode('utf-8'):
        print(item)

strs = apk.get_strings()  # the strings from all of classes\d*.dex
for item in strs:
    s = binascii.unhexlify(item).decode('utf-8', errors='ignore')
    if 'helloword' in s:
        print(s)

result = apk.get_strings_refx()
for clsname in result:
    for mtdname in result[clsname]:
        if b'hellojni' in result[clsname][mtdname]:
            print(clsname, mtdname, result[clsname][mtdname])
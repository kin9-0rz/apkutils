import binascii
import os

from apkutils import APK

file_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "test")
)
apk = APK.from_file(file_path).parse_dex()

org_strs = apk.get_dex_strings()  # the strings from all of classes\d*.dex
for item in org_strs:
    if "helloword" in item.decode("utf-8"):
        print(item)

strs = apk.get_dex_hex_strings()  # the strings from all of classes\d*.dex
for item in strs:
    s = binascii.unhexlify(item).decode("utf-8", errors="ignore")
    if "helloword" in s:
        print(s)

result = apk.get_dex_strings_refx()
for clsname in result:
    for mtdname in result[clsname]:
        if b"hellojni" in result[clsname][mtdname]:
            print(clsname, mtdname, result[clsname][mtdname])

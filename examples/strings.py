import binascii
import os

from apkutils import APK

file_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", 'data', 'test'))
apk = APK(file_path)

strs = apk.get_strings()  # the strings from all of classes\d*.dex
for item in strs:
    s = binascii.unhexlify(item).decode('utf-8', errors='ignore')
    if 'hello' in s:
        print(s)

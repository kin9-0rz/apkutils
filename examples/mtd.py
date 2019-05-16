import os

from apkutils import APK

file_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", 'data', 'test'))
apk = APK(file_path)

res = apk.get_methods_refx()
for item in res:
    print(item, res[item])

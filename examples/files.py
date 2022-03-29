import os

from apkutils import APK

file_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "test")
)
apk = APK.from_file(file_path)

files = apk.get_files()
for item in files:
    print(item["name"])

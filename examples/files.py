import os

from apkutils import APK

file_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "test")
)
apk = APK.from_file(file_path)

files = apk.get_subfiles()
for item in files:
    print(item["name"])

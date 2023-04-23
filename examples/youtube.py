import os

from apkutils import APK

file_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "youtube.zip")
)

# TODO 解析还不够完美
apk = APK.from_file(file_path).parse_resouce()
arsc = apk.get_arsc()
package = arsc.get_packages_names()[0]
print(package)

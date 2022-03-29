import os
import zipfile
from collections import OrderedDict

import xmltodict
from apkutils import APK

file_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "test")
)
apk = APK.from_file(file_path)
icon_id = apk.get_manifest().get("application", {}).get("@android:icon", None)
if not icon_id:
    exit()
icon_id = icon_id[1:].lower()

# ! 不再使用xmltodict处理XML，而是使用 BeautifulSoup
datas = xmltodict.parse(apk.get_arsc().get_public_resources(apk.package_name))


def get_icon_path():
    for item in datas["resources"]["public"]:
        if icon_id not in item.get("@id"):
            break
        return (item.get("@type"), item.get("@name"))


icon = get_icon_path()
for item in apk.get_files():
    name = item.get("name")
    if icon[0] in name and icon[1] in name:
        print(name)

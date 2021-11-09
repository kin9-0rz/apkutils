import os
import unittest
import zipfile
from collections import OrderedDict

import xmltodict
from apkutils.axml.arscparser import ARSCParser

import os

from apkutils import APK

file_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", 'data', 'test'))
apk = APK.from_file(file_path)

package = apk.get_manifest().get('@package', None)
if not package:
    exit()

icon_id = apk.get_manifest().get('application', {}).get('@android:icon', None)
if not icon_id:
    exit()

icon_id = icon_id[1:].lower()
datas = xmltodict.parse(
    apk.get_arsc().get_public_resources(package))

def get_icon_path():
    for item in datas['resources']['public']:
        if icon_id not in item.get('@id'):
            break
        return (item.get('@type'), item.get('@name'))

icon = get_icon_path()
for item in apk.get_files():
    name = item.get('name')
    if icon[0] in name and icon[1] in name:
        print(name)

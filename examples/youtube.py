import os
import os
import unittest
import zipfile
from collections import OrderedDict

import xmltodict
from apkutils.axml.arscparser import ARSCParser

from apkutils import APK

file_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", 'data', 'youtube.zip'))


# file_path = os.path.abspath(os.path.join(
#     os.path.dirname(__file__), "..", 'data', 'i15.zip'))
apk = APK(file_path)

arsc = apk.get_arsc()

# file_path = os.path.abspath(os.path.join(
#     os.path.dirname(__file__), "..", 'data', 'youtube.zip'))

# with zipfile.ZipFile(file_path, mode="r") as zf:
#     data = zf.read('resources.arsc')
#     arscobj = ARSCParser(data)

# apk = apkutils.APK(file_path)
# arsc = apk.get_asrc()
package = arsc.get_packages_names()[0]
print(package)
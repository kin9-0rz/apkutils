import os
import zipfile
from collections import OrderedDict

import xmltodict
from apkutils.axml.arscparser import ARSCParser

from apkutils import APK

file_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", 'data', 'youtube.zip'))

apk = APK(file_path)
arsc = apk.get_arsc()
package = arsc.get_packages_names()[0]


def test_get_packages_names():
    assert package == 'com.google.android.youtube'

# def test_get_strings_resources():
#     print(str(arsc.get_strings_resources()))
#     datas = xmltodict.parse(
#         arsc.get_strings_resources())['packages']['package']
#     assert datas['@name'] == 'com.google.android.youtube'

    # strs = datas['locale']['resources']['string']

    # assert OrderedDict([('@name', 'app_name'), ('#text', 'hellojni')]) in strs
    # assertIn(OrderedDict(
    #     [('@name', 'hello_world'), ('#text', 'Hello world!')]), strs)
    # assertIn(OrderedDict(
    #     [('@name', 'action_settings'), ('#text', 'Settings')]), strs)

# def test_get_id_resources(self):
#     datas = xmltodict.parse(
#         arsc.get_id_resources(package))
#     assert OrderedDict(
#         [('@type', 'id'), ('@name', 'action_settings'), ('#text', 'false')]), datas['resources']['item'])

# def test_get_public_resources(self):
#     datas = xmltodict.parse(
#         arsc.get_public_resources(package))

#     app_name = OrderedDict(
#         [('@type', 'string'), ('@name', 'app_name'), ('@id', '0x7f050000')])
#     assertIn(app_name, datas['resources']['public'])

#     main = OrderedDict(
#         [('@type', 'menu'), ('@name', 'main'), ('@id', '0x7f070000')])
#     assertIn(main, datas['resources']['public'])

# def test_others(self):
#     datas = xmltodict.parse(
#         arsc.get_public_resources(package))
#     for item in datas['resources']['public']:
#         if "0x7f020000" == item['@id']:
#             assert item['@type'], 'drawable')
#             assert item['@name'], 'ic_launcher')
#             break

# def test_get_bool_resources(self):
#     buff = minidom.parseString(
#         arsc.get_bool_resources(package)).toprettyxml()
#     print(buff)

# def test_get_integer_resources(self):
#     buff = minidom.parseString(
#         arsc.get_integer_resources(package)).toprettyxml()
#     print(buff)

# def test_get_color_resources(self):
#     buff = minidom.parseString(
#         arsc.get_color_resources(package)).toprettyxml()
#     print(buff)

# def test_get_dimen_resources(self):
#     datas = xmltodict.parse(
#         arsc.get_dimen_resources(package))
#     ahm = OrderedDict(
#         [('@name', 'activity_horizontal_margin'), ('#text', '16.0dip')])

#     assertIn(ahm, datas['resources']['dimen'])



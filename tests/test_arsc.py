import os
import unittest
import zipfile
from xml.dom import minidom
import xmltodict
from collections import OrderedDict


from apkutils import apk
from apkutils.axml.arscparser import ARSCParser


class TestAPK(unittest.TestCase):

    def setUp(self):
        file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", 'data', 'test'))
        with zipfile.ZipFile(file_path, mode="r") as zf:
            data = zf.read('resources.arsc')
            self.arscobj = ARSCParser(data)

        self.package = self.arscobj.get_packages_names()[0]

    def test_get_packages_names(self):
        self.assertEqual(self.package, 'com.example.hellojni')

    def test_get_strings_resources(self):
        datas = xmltodict.parse(
            self.arscobj.get_strings_resources())['packages']['package']
        self.assertEqual(datas['@name'], 'com.example.hellojni')

        strs = datas['locale']['resources']['string']

        self.assertIn(OrderedDict(
            [('@name', 'app_name'), ('#text', 'hellojni')]), strs)
        self.assertIn(OrderedDict(
            [('@name', 'hello_world'), ('#text', 'Hello world!')]), strs)
        self.assertIn(OrderedDict(
            [('@name', 'action_settings'), ('#text', 'Settings')]), strs)

    def test_get_id_resources(self):
        datas = xmltodict.parse(
            self.arscobj.get_id_resources(self.package))
        self.assertEqual(OrderedDict(
            [('@type', 'id'), ('@name', 'action_settings'), ('#text', 'false')]), datas['resources']['item'])

    def test_get_public_resources(self):
        datas = xmltodict.parse(
            self.arscobj.get_public_resources(self.package))

        app_name = OrderedDict(
            [('@type', 'string'), ('@name', 'app_name'), ('@id', '0x7f050000')])
        self.assertIn(app_name, datas['resources']['public'])

        main = OrderedDict(
            [('@type', 'menu'), ('@name', 'main'), ('@id', '0x7f070000')])
        self.assertIn(main, datas['resources']['public'])

    # def test_get_bool_resources(self):
    #     buff = minidom.parseString(
    #         self.arscobj.get_bool_resources(self.package)).toprettyxml()
    #     print(buff)

    # def test_get_integer_resources(self):
    #     buff = minidom.parseString(
    #         self.arscobj.get_integer_resources(self.package)).toprettyxml()
    #     print(buff)

    # def test_get_color_resources(self):
    #     buff = minidom.parseString(
    #         self.arscobj.get_color_resources(self.package)).toprettyxml()
    #     print(buff)

    def test_get_dimen_resources(self):
        datas = xmltodict.parse(
            self.arscobj.get_dimen_resources(self.package))
        ahm = OrderedDict(
            [('@name', 'activity_horizontal_margin'), ('#text', '16.0dip')])

        self.assertIn(ahm, datas['resources']['dimen'])

if __name__ == "__main__":
    unittest.main()

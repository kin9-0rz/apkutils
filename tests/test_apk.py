import os
import unittest

from apkutils import APK


class TestAPK(unittest.TestCase):

    def setUp(self):
        file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", 'data', 'test'))
        self.apk = APK(file_path)

    def test_get_manifest(self):
        self.assertIn('com.example', self.apk.get_manifest().get('@package'))

    def test_get_strings(self):
        self.assertEqual(len(self.apk.get_strings()), 8594)

    def test_get_files(self):
        for item in self.apk.get_files():
            if item.get('crc') == 'FA974826':
                self.assertIn('AndroidManifest.xml', item.get('name'))
                break

    def test_get_opcodes(self):
        for item in self.apk.get_opcodes():
            class_name = item.get('class_name')
            method_name = item.get('method_name')
            opcodes = item.get('opcodes')

            if class_name == 'com/example/hellojni/MainActivity' and method_name == 'onCreate':
                self.assertEqual(opcodes, '6F156E0E')
                break


if __name__ == "__main__":
    unittest.main()

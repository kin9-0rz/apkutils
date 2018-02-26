import os
import unittest

from apkutils import APK


class TestAPK(unittest.TestCase):

    def setUp(self):
        file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", 'data', 'test_zip_fake_pwd'))
        self.apk = APK(file_path)

    def test_get_manifest(self):
        self.apk.get_manifest()

    def test_get_strings(self):
        self.apk.get_strings()

    def test_get_files(self):
        self.apk.get_files()

    def test_get_opcodes(self):
        self.apk.get_opcodes()

if __name__ == "__main__":
    unittest.main()

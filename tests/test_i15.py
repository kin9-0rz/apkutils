import os
import unittest

from apkutils import APK


class TestAPK(unittest.TestCase):

    def setUp(self):
        file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", 'data', 'i15.zip'))
        self.apk = APK(file_path)

    def test_get_strings_refx(self):
        result = self.apk.get_strings_refx()
        self.assertEqual(len(result), 1477)


if __name__ == "__main__":
    unittest.main()

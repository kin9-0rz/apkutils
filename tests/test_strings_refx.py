import os
import unittest

from apkutils import APK


class TestAPK(unittest.TestCase):

    def setUp(self):
        file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", 'data', 'test'))
        self.apk = APK(file_path)

    def test_get_strings_refx(self):
        result = self.apk.get_strings_refx()
        for clsname in result:
            for mtdname in result[clsname]:
                if b'hellojni' in result[clsname][mtdname]:
                    print(clsname, mtdname, result[clsname][mtdname])


if __name__ == "__main__":
    unittest.main()

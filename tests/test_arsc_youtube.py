import os

from apkutils import APK


class TestZipFakePWD(object):
    def setup_class(self):
        file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "fixtures", "youtube.zip")
        )
        self.apk = APK.from_file(file_path)

        self.arsc = self.apk.get_arsc()
        self.package = self.arsc.get_packages_names()[0]

    def teardown_class(self):
        self.apk.close()

    def test_get_packages_names(self):
        assert self.package == "com.google.android.youtube"

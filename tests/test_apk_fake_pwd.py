import os

from apkutils import APK


class TestZipFakePWD(object):
    def setup_class(self):
        file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "fixtures", "test_zip_fake_pwd")
        )
        self.apk = APK.from_file(file_path)

    def teardown_class(self):
        self.apk.close()

    def test_get_manifest(self):
        assert "xml" in self.apk.get_manifest()

    def test_get_strings(self):
        assert "7265737020726573756c74206572726f72202564" in self.apk.get_dex_strings()

    def test_get_files(self):
        assert len(self.apk.get_files()) == 30

    def test_get_opcodes(self):
        assert self.apk.get_opcodes() != None
        assert len(self.apk.get_opcodes()) == 940

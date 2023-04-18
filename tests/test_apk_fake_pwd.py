import os

from apkutils import APK


class TestZipFakePWD(object):
    def setup_class(self):
        file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "fixtures", "test_zip_fake_pwd")
        )
        self.apk = APK.from_file(file_path).parse_manifest().parse_dex()

    def teardown_class(self):
        self.apk.close()

    def test_get_manifest(self):
        assert "xml" in self.apk.get_manifest()

    def test_get_strings(self):
        assert b'writeLong' in self.apk.get_dex_strings()

    def test_get_subfiles(self):
        assert len(self.apk.get_subfiles()) == 30

    def test_get_dex_opcodes(self):
        assert self.apk.get_dex_opcodes() is not None
        assert len(self.apk.get_dex_opcodes()) == 940

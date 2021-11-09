import os

from apkutils import APK

class TestAPK(object):
    def setup_class(self):
        file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "fixtures", "test")
        )
        self.apk = APK.from_file(file_path)

    def teardown_class(self):
        self.apk.close()

    def test_get_manifest(self):
        assert "com.example" in self.apk.get_manifest()

    def test_get_strings(self):
        assert len(self.apk.get_dex_strings()) == 8594

    def test_get_files(self):
        for item in self.apk.get_files():
            if item.get("crc") == "FA974826":
                assert "AndroidManifest.xml" in item.get("name")
                break

    def test_get_opcodes(self):
        for item in self.apk.get_opcodes():
            class_name = item.get("class_name")
            method_name = item.get("method_name")
            opcodes = item.get("opcodes")

            if (
                class_name == "com/example/hellojni/MainActivity"
                and method_name == "onCreate"
            ):
                assert opcodes == "6F156E0E"
                break

    def test_get_app_icon(self):
        path = self.apk.get_app_icon()
        assert path == "res/drawable-xxhdpi-v4/ic_launcher.png"

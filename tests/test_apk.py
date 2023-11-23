import os

from apkutils import APK


class TestAPK(object):
    def setup_class(self):
        file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "fixtures", "test.zip")
        )
        self.apk = APK.from_file(file_path).parse_dex().parse_resouce()

    def teardown_class(self):
        self.apk.close()

    def test_manifest(self):
        assert '".MainActivity"' in self.apk.get_manifest()
        assert self.apk.get_package_name() == "com.example.hellojni"
        assert self.apk.get_manifest_application() == ""
        assert self.apk.get_manifest_main_activities() == [
            "com.example.hellojni.MainActivity"
        ]

    def test_get_strings(self):
        assert len(self.apk.get_dex_strings()) == 8594

    def test_get_subfiles(self):
        for item in self.apk.get_subfiles():
            if item.get("crc") == "FA974826":
                assert "AndroidManifest.xml" in item.get("name")
                break

    def test_get_dex_opcodes(self):
        for item in self.apk.get_dex_opcodes():
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
        icons = self.apk.get_app_icons()
        assert "res/drawable-xxhdpi-v4/ic_launcher.png" in icons

    def test_app_name(self):
        assert self.apk.app_name == "hellojni"

import os

from apkutils import APK


class TestZipFakePWD(object):
    def setup_class(self):
        file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "fixtures", "youtube.zip")
        )
        self.apk = APK.from_file(file_path).parse_manifest()

    def teardown_class(self):
        self.apk.close()

    def test_manifest(self):
        assert self.apk.get_package_name() == "com.google.android.youtube"
        assert len(self.apk.get_manifest_main_activities()) == 2
        assert (
            self.apk.get_manifest_application()
            == "com.google.android.apps.youtube.app.YouTubeApplication"
        )

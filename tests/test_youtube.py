import os

from apkutils import APK


class TestZipFakePWD(object):
    def setup_class(self):
        file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "fixtures", "youtube.zip")
        )
        self.apk = APK.from_file(file_path).parse_resource()

    def teardown_class(self):
        self.apk.close()

    def test_manifest(self):
        assert self.apk.get_package_name() == "com.google.android.youtube"
        assert self.apk.get_manifest_main_activities() == [
            "com.google.android.youtube.app.honeycomb.Shell$HomeActivity"
        ]
        aliases = self.apk.get_manifest_activity_aliases()
        assert aliases[
            "com.google.android.youtube.app.honeycomb.Shell$HomeActivity"
        ] == "com.google.android.apps.youtube.app.application.Shell$HomeActivity"
        # 非入口别名同样在映射里，供逆向追踪实现类
        assert aliases["com.google.android.youtube.UrlActivity"] == (
            "com.google.android.apps.youtube.app.application.Shell$UrlActivity"
        )
        assert len(aliases) == 5
        assert (
            self.apk.get_manifest_application()
            == "com.google.android.apps.youtube.app.YouTubeApplication"
        )

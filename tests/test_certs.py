import os

from apkutils import APK


def test_youtube():
    file_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "fixtures", "youtube.zip")
    )
    apk = APK.from_file(file_path)

    certs = [
        (
            "CN=Unknown, OU=Google, Inc, O=Google, Inc, L=Mountain View, ST=CA, C=US",
            "d046fc5d1fc3cd0e57c5444097cd5449",
        )
    ]

    assert certs == apk.get_certs()

    certs = [
        (
            "CN=Unknown, OU=Google, Inc, O=Google, Inc, L=Mountain View, ST=CA, C=US",
            "24bb24c05e47e0aefa68a58a766179d9b613a600",
        )
    ]
    assert certs == apk.get_certs("sha1")

    certs = [
        (
            "CN=Unknown, OU=Google, Inc, O=Google, Inc, L=Mountain View, ST=CA, C=US",
            "3d7a1223019aa39d9ea0e3436ab7c0896bfb4fb679f4de5fe7c23f326c8f994a",
        )
    ]
    assert certs == apk.get_certs("sha256")

    apk.close()

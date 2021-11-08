import os

from apkutils import APK

file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "test"))
apk = APK(file_path)


def test_get_manifest():
    assert "com.example" in apk.get_manifest().get("@package")


def test_get_strings():
    assert len(apk.get_strings()) == 8594


def test_get_files():
    for item in apk.get_files():
        if item.get("crc") == "FA974826":
            assert "AndroidManifest.xml" in item.get("name")
            break


def test_get_opcodes():
    for item in apk.get_opcodes():
        class_name = item.get("class_name")
        method_name = item.get("method_name")
        opcodes = item.get("opcodes")

        if (
            class_name == "com/example/hellojni/MainActivity"
            and method_name == "onCreate"
        ):
            assert opcodes == "6F156E0E"
            break


def test_get_app_icon():
    path = apk.get_app_icon()
    assert path == "res/drawable-xxhdpi-v4/ic_launcher.png"

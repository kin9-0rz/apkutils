import os

from apkutils import APK

file_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "fixtures", "i15.zip")
)
apk = APK(file_path)


def test_get_strings_refx():
    result = apk.get_strings_refx()
    assert len(result) == 1477

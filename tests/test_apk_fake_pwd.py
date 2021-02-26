import os
from apkutils import APK

file_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", 'data', 'test_zip_fake_pwd'))
apk = APK(file_path)

def test_get_manifest():
    assert "xml" in apk.get_org_manifest()

def test_get_strings():
    assert "7265737020726573756c74206572726f72202564" in apk.get_strings()

def test_get_files():
    assert len(apk.get_files()) == 30

def test_get_opcodes():
    assert apk.get_opcodes() != None
    assert len(apk.get_opcodes()) == 940


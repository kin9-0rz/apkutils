import os

from apkutils import APK


file_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", 'data', 'test'))
apk = APK(file_path)

def test_get_strings_refx():
    result = apk.get_strings_refx()
    for clsname in result:
        for mtdname in result[clsname]:
            if b'hellojni' in result[clsname][mtdname]:
                print(clsname, mtdname, result[clsname][mtdname])



import os

from apkutils import APK


def test_get_dex_strings_refx():
    file_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "fixtures", "test.zip")
    )

    with APK.from_file(file_path).parse_dex() as apk:
        result = apk.get_dex_strings_refx()
        for clsname in result:
            for mtdname in result[clsname]:
                if b"hellojni" in result[clsname][mtdname]:
                    assert clsname == "com/example/hellojni/MainActivity"
                    assert mtdname == "<clinit>"
                    # print(clsname, mtdname, result[clsname][mtdname])


def test_get_dex_strings_refx2():
    file_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "fixtures", "i15.zip")
    )

    with APK.from_file(file_path).parse_dex() as apk:
        result = apk.get_dex_strings_refx()
        assert len(result) == 1477

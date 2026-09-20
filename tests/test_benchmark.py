import os
import zipfile

from apkutils._dex import DexReader

FIXTURES = os.path.dirname(os.path.abspath(__file__)) + "/fixtures"


def test_01(benchmark):
    @benchmark
    def do():
        import time

        time.sleep(0.1)


def test_0001(benchmark):
    @benchmark
    def do():
        import time

        time.sleep(0.001)


def test_apk(benchmark):
    file_path = os.path.join(FIXTURES, "youtube.zip")
    with zipfile.ZipFile(file_path) as zf:
        blobs = [
            zf.read(name)
            for name in zf.namelist()
            if name.startswith("classes") and name.endswith(".dex")
        ]

    @benchmark
    def do():
        DexReader(blobs).strings_refx_index()


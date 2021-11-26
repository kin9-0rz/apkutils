import os

import pyftype
from apkutils import APK

FIXTURES = os.path.dirname(os.path.abspath(__file__)) + '/fixtures'


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
    file_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "fixtures", "youtube.zip")
            )
    apk = APK.from_file(file_path)
    @benchmark
    def do():
        apk._init_dex_methods()
    
    apk.close()
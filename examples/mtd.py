import os
import time

from apkutils import APK

file_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "youtube.zip")
)
apk = APK.from_file(file_path)
start = time.time()
# 获取所有的dex方法，非常耗时，25秒。
apk._init_dex_methods()
end = time.time()
print(end - start)
apk.close()

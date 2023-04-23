import json
import os

from apkutils import APK

file_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "test")
)
apk = APK.from_file(file_path).parse_resouce()

m_xml = apk.get_manifest()
# 只返回原始的xml，使用xml2dict，BeautifulSoup 处理都可以。
print(m_xml)

x = apk.get_dex_strings()
print(x)


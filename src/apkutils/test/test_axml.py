# -*- coding: utf-8 -*-
import zipfile
from apkutils.axml.axmlparser import AXML
import traceback

if __name__ == "__main__":
    apk_path = "E:\\samples\\vt\\apks\\ae697a0045bc1eafd716d268a802918c.apk"

    ANDROID_MANIFEST = "AndroidManifest.xml"
    if zipfile.is_zipfile(apk_path):
        try:
            with zipfile.ZipFile(apk_path, mode="r") as zf:
                if ANDROID_MANIFEST in zf.namelist():
                    data = zf.read(ANDROID_MANIFEST)
                    try:
                        axml = AXML(data)
                        # print(axml.get_xml())
                        import xmltodict
                        import json
                        buff = axml.get_buff()
                        import chardet
                        # print(type(buff))
                        # bytess = buff.encode('utf-8')
                        with open("test.xml", "w", encoding="utf-8") as fd:
                            fd.write(buff.replace("\0", ""))
                        # print(chardet.detect(bytess))
                        # print(bytess)
                        with open("test.xml", mode='r', encoding="utf-8", errors=None, newline=None, closefd=True) as f:
                            with open("test.json", "w", encoding="utf-8") as fd:
                                fd.write(str(xmltodict.parse(f.read().encode('utf-8'), encoding='utf-8')))
                    except:
                        traceback.print_exc()
        except:
            traceback.print_exc()

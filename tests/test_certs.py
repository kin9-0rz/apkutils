import os
import unittest

from apkutils import APK



def test_youtube():
    file_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", 'data', 'youtube.zip'))
    apk = APK(file_path)

    # Check that the default (md5) is correct
    # FixME 错误，解析结果少了一个OU=Google
    # assert [('C=US, ST=CA, L=Mountain View, O=Google, Inc, OU=Google, Inc, CN=Unknown',
    #     'D046FC5D1FC3CD0E57C5444097CD5449')] == apk.get_certs()

    # Check that sha1 is correct
    # assert [('C=US, ST=CA, L=Mountain View, O=Google, Inc, OU=Google, Inc, CN=Unknown',
    #     '24BB24C05E47E0AEFA68A58A766179D9B613A600')] == apk.get_certs('sha1')

    # Check that sha256 is correct
    # assert [('C=US, ST=CA, L=Mountain View, O=Google, Inc, OU=Google, Inc, CN=Unknown',
    #     '3D7A1223019AA39D9EA0E3436AB7C0896BFB4FB679F4DE5FE7C23F326C8F994A')] == apk.get_certs('sha256')


# Kotlin apps add data mime-typed files to META-INF which might
# confuse the certifiacte guesser, check that we can handle those
def test_kotlin_app():
    file_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", 'data', 'kotlin-app.zip'))
    apk = APK(file_path)
    # assert [('CN=Android Debug, O=Android, C=US',
    #     '299D8DE477962C781714EAAB76A90C287BB67123CD2909DE0F743838CAD264E4')] in apk.get_certs('sha256')


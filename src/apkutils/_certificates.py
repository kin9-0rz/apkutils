"""APK 签名证书读取。

`Certificates` 的 interface 只吃 caller 从归档里挑出的 ``(name, data)`` 对，
负责识别哪些是签名文件、按给定哈希算出 ``(subject, fingerprint)`` 列表。

挑文件（META-INF/*.DSA|.RSA）与读字节是 facade 的 I/O；
识别与解析藏在这里。
"""

import pyftype

from apkutils.cert import Certificate

SIGNATURE_SUFFIXES = (".DSA", ".RSA")
META_INF_PREFIX = "META-INF/"


class CertificateError(Exception):
    """签名证书无法解析。"""


class Certificates:
    """从签名文件读出证书列表。"""

    def __init__(self, entries, _hash="md5"):
        self.content = []
        self._parse(entries, _hash)

    def _parse(self, entries, _hash):
        for name, data in entries:
            if pyftype.guess(data).EXTENSION == "txt":
                continue
            try:
                cert = Certificate(data, _hash=_hash)
            except Exception as e:
                raise CertificateError(f"{name}: 证书解析失败") from e
            self.content = cert.get()

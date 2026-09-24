import re
import warnings

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs7

# 加固工具（如百度加固）签名的测试证书常带违反 X.520 的 subject 属性：
# 例如 countryName (C) 要求恰好 2 字符，样本里却是 "test"。
# cryptography 解析这类 subject 时会打 UserWarning，但属性值仍可正常读出，
# 因此只静音这条已知无害的告警，不向调用方刷屏。
_INVALID_ATTR_LENGTH_WARNING = r"Attribute's length must be"


class Certificate:
    def __init__(self, buff, _hash="md5"):
        self.content = []
        self._parse(buff, _hash)

    def get(self):
        return self.content

    def _parse(self, buff, _hash):
        h = hashes.MD5()
        if _hash == "sha256":
            h = hashes.SHA256()
        elif _hash == "sha1":
            h = hashes.SHA1()

        certificates = pkcs7.load_der_pkcs7_certificates(buff)

        for item in certificates:
            # 见模块级 _INVALID_ATTR_LENGTH_WARNING 的说明
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=_INVALID_ATTR_LENGTH_WARNING,
                    category=UserWarning,
                )
                name = item.subject.rfc4514_string()
            name = re.sub(r",(\w{1,2}\=)", r", \1", name).replace("\\", "")
            fingerprint = item.fingerprint(h).hex()
            self.content.append((name, fingerprint))

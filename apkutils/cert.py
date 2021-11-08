import re

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs7


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
            name = item.subject.rfc4514_string()
            name = re.sub(r",(\w{1,2}\=)", r", \1", name).replace("\\", "")
            fingerprint = item.fingerprint(h).hex()
            self.content.append((name, fingerprint))

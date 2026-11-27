import os
import zipfile

import pytest
from bs4 import BeautifulSoup

from apkutils.axml import ARSCParser, ResParserError


class TestARSC(object):
    def setup_class(self):
        file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "fixtures", "test.zip")
        )

        with zipfile.ZipFile(file_path, mode="r") as zf:
            data = zf.read("resources.arsc")
            self.arsc = ARSCParser(data)

        self.package = self.arsc.get_packages_names()[0]

    def test_get_packages_names(self):
        assert self.package == "com.example.hellojni"

    def test_get_strings_resources(self):
        str_res = self.arsc.get_strings_resources()
        soup = BeautifulSoup(str_res, "lxml-xml")

        packages = soup.packages
        assert packages is not None
        package = packages.select_one("package")
        assert package is not None
        assert package["name"] == "com.example.hellojni"
        assert package.get("name") == "com.example.hellojni"

        package_node = soup.select_one("package")
        assert package_node is not None
        assert package_node["name"] == "com.example.hellojni"

        setting = soup.select_one('string[name="action_settings"]')
        assert setting is not None
        assert setting.string == "Settings"

    def test_get_id_resources(self):
        res = self.arsc.get_id_resources(self.package)

        assert b'name="action_settings">false</item>' in res

    def test_get_public_resources(self):
        res = self.arsc.get_public_resources(self.package)
        assert b'name="ic_launcher" id="0x7f020000" ' in res

    def test_get_dimen_resources(self):
        res = self.arsc.get_dimen_resources(self.package)
        assert b'name="activity_horizontal_margin">16.0dip</dimen>' in res


def test_invalid_arsc_raises_typed_error():
    with pytest.raises(ResParserError):
        ARSCParser(b"\x00" * 4)

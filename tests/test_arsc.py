import os
import zipfile

from apkutils.axml import ARSCParser
from bs4 import BeautifulSoup


class TestARSC(object):
    def setup_class(self):
        file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "fixtures", "test")
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

        assert soup.packages.package["name"] == "com.example.hellojni"
        assert soup.packages.package.get("name") == "com.example.hellojni"
        assert soup.select_one("package")["name"] == "com.example.hellojni"

        assert soup.select_one('string[name="action_settings"]').string == "Settings"

    def test_get_id_resources(self):
        res = self.arsc.get_id_resources(self.package)

        assert b'name="action_settings">false</item>' in res

    def test_get_public_resources(self):
        res = self.arsc.get_public_resources(self.package)
        assert b'name="ic_launcher" id="0x7f020000" ' in res

    def test_get_dimen_resources(self):
        res = self.arsc.get_dimen_resources(self.package)
        assert b'name="activity_horizontal_margin">16.0dip</dimen>' in res

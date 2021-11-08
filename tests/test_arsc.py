import os
import unittest
import zipfile
from collections import OrderedDict

import xmltodict
from apkutils.axml import ARSCParser

file_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "test")
)
with zipfile.ZipFile(file_path, mode="r") as zf:
    data = zf.read("resources.arsc")
    arscobj = ARSCParser(data)

package = arscobj.get_packages_names()[0]


def test_get_packages_names():
    assert package == "com.example.hellojni"


def test_get_strings_resources():
    datas = xmltodict.parse(arscobj.get_strings_resources())["packages"]["package"]
    assert datas["@name"] == "com.example.hellojni"

    strs = datas["locale"]["resources"]["string"]

    assert OrderedDict([("@name", "app_name"), ("#text", "hellojni")]) in strs
    assert OrderedDict([("@name", "hello_world"), ("#text", "Hello world!")]) in strs
    assert OrderedDict([("@name", "action_settings"), ("#text", "Settings")]) in strs


def test_get_id_resources():
    datas = xmltodict.parse(arscobj.get_id_resources(package))
    assert (
        OrderedDict([("@type", "id"), ("@name", "action_settings"), ("#text", "false")])
        == datas["resources"]["item"]
    )


def test_get_public_resources():
    datas = xmltodict.parse(arscobj.get_public_resources(package))

    app_name = OrderedDict(
        [("@type", "string"), ("@name", "app_name"), ("@id", "0x7f050000")]
    )

    assert app_name in datas["resources"]["public"]

    main = OrderedDict([("@type", "menu"), ("@name", "main"), ("@id", "0x7f070000")])
    assert main in datas["resources"]["public"]


def test_others():
    datas = xmltodict.parse(arscobj.get_public_resources(package))
    for item in datas["resources"]["public"]:
        if "0x7f020000" == item["@id"]:
            assert item["@type"] == "drawable"
            assert item["@name"] == "ic_launcher"
            break


def test_get_dimen_resources():
    datas = xmltodict.parse(arscobj.get_dimen_resources(package))
    ahm = OrderedDict([("@name", "activity_horizontal_margin"), ("#text", "16.0dip")])

    assert ahm in datas["resources"]["dimen"]

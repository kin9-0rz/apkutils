
from struct import unpack, pack
import collections

from xml.dom import minidom
import codecs

from apkutils.axml.arscparser import ARSCParser


def read(filename, binary=True):
    with open(filename, 'rb' if binary else 'r') as f:
        return f.read()


if __name__ == "__main__":
    arscobj = ARSCParser(read("E:\\samples\\base\\resources.arsc"))

    print(arscobj.get_resolved_res_configs(0x7F070028))

    package = arscobj.get_packages_names()[0]

    buff = minidom.parseString(arscobj.get_strings_resources()).toprettyxml()
    with open("strings.xml", "w", encoding="utf-8") as fd:
        fd.write(buff)

    buff = minidom.parseString(arscobj.get_id_resources(package)).toprettyxml()
    with open("id.xml", "w") as fd:
        fd.write(buff)

    buff = minidom.parseString(arscobj.get_public_resources(package)).toprettyxml()
    with open("public.xml", "w") as fd:
        fd.write(buff)

    buff = minidom.parseString(arscobj.get_bool_resources(package)).toprettyxml()
    with open("bool.xml", "w") as fd:
        fd.write(buff)

    buff = minidom.parseString(arscobj.get_integer_resources(package)).toprettyxml()
    with open("integer.xml", "w") as fd:
        fd.write(buff)

    buff = minidom.parseString(arscobj.get_color_resources(package)).toprettyxml()
    with open("color.xml", "w") as fd:
        fd.write(buff)

    buff = minidom.parseString(arscobj.get_dimen_resources(package)).toprettyxml()
    with open("dimen.xml", "w") as fd:
        fd.write(buff)

"""Console script for apkutils."""
import binascii
import sys

import click
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers import get_lexer_by_name

from apkutils import APK, __version__


@click.group()
@click.version_option(__version__)
def main():
    pass


@main.command()
@click.argument("path")
def manifest(path):
    """打印清单"""
    apk = APK.from_file(path)

    sys.stdout.write(
        highlight(apk.get_manifest(), get_lexer_by_name("xml"), TerminalFormatter())
    )

    print(apk.get_manifest_main_activities())


@main.command()
@click.argument("path")
@click.option(
    "--res_type",
    type=click.Choice(
        ["string", "strings", "bool", "id", "color", "dimen", "integer", "public"]
    ),
)
def arsc(path, res_type):
    """打印arsc"""
    apk = APK.from_file(path)
    arsc = apk.get_arsc()

    keys = arsc.packages.keys()
    if len(keys) == 0:
        return

    package = list(keys)[0]

    data = ""

    if res_type == "string":
        data = arsc.get_string_resources(package)
    elif res_type == "bool":
        data = arsc.get_bool_resources(package)
    elif res_type == "id":
        data = arsc.get_id_resources(package)
    elif res_type == "color":
        data = arsc.get_color_resources(package)
    elif res_type == "dimen":
        data = arsc.get_dimen_resources(package)
    elif res_type == "integer":
        data = arsc.get_integer_resources(package)
    elif res_type == "public":
        data = arsc.get_public_resources(package)
    elif res_type == "strings":
        data = arsc.get_strings_resources()
    else:
        data = arsc.get_string_resources(package)
    sys.stdout.write(highlight(data, get_lexer_by_name("xml"), TerminalFormatter()))


@main.command()
@click.argument("path")
def strings(path):
    """打印Dex中的字符串"""
    apk = APK.from_file(path)
    s = sorted(apk.get_dex_strings())
    for item in s:
        print(item)


@main.command()
@click.argument("path")
def files(path):
    """打印文件"""
    apk = APK.from_file(path)
    for item in apk.get_subfiles():
        print(item)


@main.command()
@click.argument("path")
def certs(path):
    """打印证书"""
    apk = APK.from_file(path)
    for item in apk.get_certs():
        print(item)


if __name__ == "__main__":
    sys.exit(main())

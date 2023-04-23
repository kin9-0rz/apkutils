"""Console script for apkutils."""
import sys

import click
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers import get_lexer_by_name

from apkutils import APK, __version__, apkfile


@click.group()
@click.version_option(__version__)
def main():
    pass

# TODO 增加解压命令
@main.command()
@click.argument("path", type=click.Path(exists=True))
# @click.option("-l", is_flag=True, help="Show listing of a zipfile")
@click.option("-t", is_flag=True, help="Test if a zipfile is valid")
@click.option("-e", is_flag=True, help="Extract zipfile into target dir")
@click.option("-o", "--output", default="out", help="Output directory")
def unzip(path, t, e, output):
    """解压文件，默认显示zip文件"""
    if e:
        with apkfile.ZipFile(path, "r") as zf:
            zf.extractall(output)
    elif t:
        with apkfile.ZipFile(path, "r") as zf:
            badfile = zf.testzip()
        if badfile:
            print("The following enclosed file is corrupted: {!r}".format(badfile))
        print("Done testing")
    else:
        with apkfile.ZipFile(path, "r") as zf:
            zf.printdir()
    

@main.command()
@click.argument("path")
def manifest(path):
    """打印清单"""
    apk = APK.from_file(path).parse_resouce()
    manifest = apk.get_manifest()
    if manifest is None:
        print("Manifest is None!")
        return

    sys.stdout.write(
        highlight(manifest, get_lexer_by_name("xml"), TerminalFormatter())
    )
    
    print("\nPackage: {}".format(apk.get_package_name()))
    print("Main Activities:")
    for item in apk.get_manifest_main_activities():
        print(" - {}".format(item))

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
    apk = APK.from_file(path).parse_resouce()
    arsc = apk.get_arsc()
    if arsc is None:
        print("ARSC解析失败")
        return

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
    # print(data.decode("utf-8"))
    sys.stdout.write(highlight(data, get_lexer_by_name("xml"), TerminalFormatter()))


@main.command()
@click.argument("path")
def strings(path):
    """打印Dex中的字符串"""
    apk = APK.from_file(path).parse_dex()
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


@main.command()
@click.argument("path")
@click.option(
    "-m",
    "--method",
    help="指定方法，如 top/cls->mtd(Landroid/app/Application;Ljava/lang/String;Ljava/lang/String;)V",
)
def mtds(path, method):
    """获取指定方法中的所有字符串"""
    apk = APK.from_file(path).parse_dex()
    strs = apk.get_dex_method_strings(method)
    if strs is None:
        return

    for item in strs:
        print(item)


@main.command()
@click.argument("path")
@click.option(
    "-m",
    "--method",
    help="指定方法，如 top/cls->mtd(Landroid/app/Application;Ljava/lang/String;Ljava/lang/String;)V",
)
def xref(path, method):
    """获取方法的引用方法"""
    apk = APK.from_file(path).parse_dex()
    strs = apk.xref(method)
    if strs is None:
        return

    for item in strs:
        print(item)


if __name__ == "__main__":
    sys.exit(main())

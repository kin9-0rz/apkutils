"""Console script for apkutils."""
import binascii
import sys

import click

from apkutils import APK, __version__


@click.group()
@click.version_option(__version__)
def main():
    pass


@main.command()
@click.argument('path')
def manifest(path):
    """打印清单"""
    apk = APK(path)
    print(apk.get_org_manifest())


@main.command()
@click.argument('path')
def strings(path):
    """打印Dex中的字符串"""
    apk = APK(path)
    s = sorted(apk.get_strings())
    for item in s:
        print(binascii.unhexlify(item).decode(errors='ignore'))

@main.command()
@click.argument('path')
def files(path):
    """打印文件"""
    apk = APK(path)
    for item in apk.get_files():
        print(item)

@main.command()
@click.argument('path')
def certs(path):
    """打印证书"""
    apk = APK(path)
    for item in apk.get_certs():
        print(item)



if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover

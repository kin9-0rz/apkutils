# apkutils

![PyPI](https://img.shields.io/pypi/v/apkutils?style=for-the-badge) ![PyPI - Status](https://img.shields.io/pypi/status/apkutils?style=for-the-badge) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/apkutils?style=for-the-badge)  ![PyPI - Downloads](https://img.shields.io/pypi/dw/apkutils?style=for-the-badge) ![PyPI - License](https://img.shields.io/pypi/l/apkutils?style=for-the-badge)

#### Description

A Parser for APK, Dex, ARSC, AXML, ELF.


#### Installation

```
❯ pip install apkutils

❯ apkutils
Usage: apkutils [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  arsc      打印arsc
  certs     打印证书
  files     打印文件
  manifest  打印清单
  mtds      获取指定方法中的所有字符串
  strings   打印Dex中的字符串
  unzip     解压文件，默认显示zip文件
  xref      获取方法的引用方法
```

#### Usage

```python
from apkutils import APK

# NOTE 按需解析，这里仅仅解析清单，不解析dex、图标。
apk = APK.from_file(file_path).parse_manifest()
manifest = apk.get_manifest()
apk.close()

# or 
with APK.from_file(file_path) as apk:
    apk.get_manifest()
```
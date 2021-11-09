# apkutils

![PyPI](https://img.shields.io/pypi/v/apkutils?style=for-the-badge) ![PyPI - Status](https://img.shields.io/pypi/status/apkutils?style=for-the-badge) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/apkutils?style=for-the-badge)  ![PyPI - Downloads](https://img.shields.io/pypi/dw/apkutils?style=for-the-badge) ![PyPI - License](https://img.shields.io/pypi/l/apkutils?style=for-the-badge)

#### 介绍

一个用于解析APK、Dex、AXML、ARSC、ELF的库。

#### 安装教程

```
❯ pip install apkutils

❯ apkutils --help
Usage: apkutils [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  arsc      打印arsc
  certs     打印证书
  files     打印文件
  manifest  打印清单
  strings   打印Dex中的字符串
```

#### 用法

```python
from apkutils import APK

apk = APK.from_file(file_path)
manifest = apk.get_manifest()
apk.close()

# or 
with APK.from_file(file_path) as apk:
    apk.get_manifest()
```
请参考`examples`目录使用。
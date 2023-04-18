# apkutils

[![PyPI](https://img.shields.io/pypi/v/apkutils?style=for-the-badge)](https://pypi.org/project/apkutils/) ![PyPI - Status](https://img.shields.io/pypi/status/apkutils?style=for-the-badge) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/apkutils?style=for-the-badge)  ![PyPI - Downloads](https://img.shields.io/pypi/dw/apkutils?style=for-the-badge) ![PyPI - License](https://img.shields.io/pypi/l/apkutils?style=for-the-badge)

#### 介绍

一个用于解析APK、Dex、AXML、ARSC、ELF的库。

#### 安装教程

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

#### 用法

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
请参考 `examples` 目录。

#### 备注

从 `1.3.0` 开始，默认不解析清单、不解析图标、不解析Dex，而是按需解析。


#### TODO

```
开始安装应用 ./2620fe8f3ae3314039f36aa28da1267a.apk... OK
Declared filesize (49112) is smaller than total file size (61400). Was something appended to the file? Trying to parse it anyways.
The Resource file seems to have data appended to it. Filesize: 3573752, declared size: 3561464
Invalid chunk found! It is larger than the outer chunk: <ARSCHeader idx='0x003656a0' type='35811' header_size='58030' size='2346950801'>


开始安装应用 ./3ca75ba49cfe20f94dd87375502e8ee2.apk... OK
Name 'http://schemas.android.com/apk/res/android' contains invalid characters!
Traceback (most recent call last):
    uri, name = self._fix_name(uri, self.axml.getAttributeName(i))
    attr = self.m_resourceIDs[name]
IndexError: list index out of range
Unknown chunk type encountered: <ARSCHeader idx='0x0000000c' type='0' header_size='8' size='264'>
None
res0 must be always zero!
包名 None


开始解析APK..../0792403520cb9911be9df9b78c609e58.apk
Name 'http://schemas.android.com/apk/res/android' contains invalid characters!
Traceback (most recent call last):
  File "/home/king/Sources/qfrida/.venv/lib/python3.10/site-packages/apkutils/apk.py", line 111, in _init_manifest
    self.axml = AXMLPrinter(data, True).get_xml_obj()
  File "/home/king/Sources/qfrida/.venv/lib/python3.10/site-packages/apkutils/axml/__init__.py", line 1050, in __init__
    uri, name = self._fix_name(uri, self.axml.getAttributeName(i))
  File "/home/king/Sources/qfrida/.venv/lib/python3.10/site-packages/apkutils/axml/__init__.py", line 903, in getAttributeName
    attr = self.m_resourceIDs[name]
IndexError: list index out of range
Unknown chunk type encountered: <ARSCHeader idx='0x0000000c' type='0' header_size='8' size='264'>
None
res0 must be always zero!

开始解析APK..../1feddcf02b8d88fedb5b2a2b118d35cf.apk
Name 'http://schemas.android.com/apk/res/android' contains invalid characters!
Traceback (most recent call last):
  File "/home/king/Sources/qfrida/.venv/lib/python3.10/site-packages/apkutils/apk.py", line 111, in _init_manifest
    self.axml = AXMLPrinter(data, True).get_xml_obj()
  File "/home/king/Sources/qfrida/.venv/lib/python3.10/site-packages/apkutils/axml/__init__.py", line 1050, in __init__
    uri, name = self._fix_name(uri, self.axml.getAttributeName(i))
  File "/home/king/Sources/qfrida/.venv/lib/python3.10/site-packages/apkutils/axml/__init__.py", line 903, in getAttributeName
    attr = self.m_resourceIDs[name]
IndexError: list index out of range
Unknown chunk type encountered: <ARSCHeader idx='0x0000000c' type='0' header_size='8' size='264'>
None
res0 must be always zero!


开始解析APK..../75a7dd8d4f02f64fe2fffcb79ce8441c.apk
Declared filesize (47840) is smaller than total file size (60962). Was something appended to the file? Trying to parse it anyways.
The Resource file seems to have data appended to it. Filesize: 3556894, declared size: 3543772

开始解析APK..../821587c17205d5049e2b63437d49f1d2.apk
Declared filesize (49544) is smaller than total file size (62666). Was something appended to the file? Trying to parse it anyways.
The Resource file seems to have data appended to it. Filesize: 3715414, declared size: 3702292

开始解析APK..../8b07d39a412caad7fa5371024639682d.apk
The Resource file seems to have data appended to it. Filesize: 3576634, declared size: 3542344

```


#### 模拟点击

- 28837840c67e3ee763cd5bb2e25776c5，验证码识别，自动输入。
- 086e40e0880995c2fb3200f418cb96a3，免注册登陆，增加模拟点击。（强制启动activity）
- 自动点击，模拟输入数据。
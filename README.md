# apkutils [![PyPI version](https://badge.fury.io/py/apkutils.svg)](https://badge.fury.io/py/apkutils) [![GitHub license](https://img.shields.io/github/license/mikusjelly/apkutils.svg)](https://github.com/mikusjelly/apkutils/blob/master/LICENSE)


A library that gets infos from APK.

### Install

```
$ pip install apkutils
```

### Options

```
$ python3 -m apkutils -h
usage: apkutils [-h] [-m] [-s] [-f] [-c] [-V] p

positional arguments:
  p              path

optional arguments:
  -h, --help     show this help message and exit
  -m             Show manifest
  -s             Show strings
  -f             Show files
  -c             Show certs
  -V, --version  show program's version number and exit

```

### Usage

```python
import binascii

from apkutils import __VERSION__, APK
apk = APK('test.apk')
```

Get AndroidManifest.json.
```python
if apk.get_manifest():
    print(json.dumps(apk.get_manifest(), indent=1))
elif apk.get_org_manifest():
    print(apk.get_org_manifest())
```

Get strings defined in APK.
```python
for item in apk.get_strings():
    print(binascii.unhexlify(item).decode(errors='ignore'))
```

Get files in APK.
```python
for item in apk.get_files():
    print(item)
```
```
{'name': 'res/layout/action_bar_item.xml', 'type': 'axml', 'time': '14300101000000', 'crc': '27FA35BC'}
...
```

Get certificates defined in APK.
```python
for item in apk.get_certs():
    print(item)
```

### Reference
- apkutils\axml from [mikusjelly/axmlparser](https://github.com/mikusjelly/axmlparser) ![Project unmaintained](https://img.shields.io/badge/project-unmaintained-red.svg)
- apkutils\dex from [google/enjarify](https://github.com/google/enjarify)

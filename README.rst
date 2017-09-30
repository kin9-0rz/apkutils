apkutils
=======================

This module help me to get infos from APK.

- apkutils\axml from [mikusjelly/axmlparser](https://github.com/mikusjelly/axmlparser)(No maintenance)
- apkutils\dex from [google/enjarify](https://github.com/google/enjarify)


### Install

```
pip install apkutils
```


### Usage

```python
from apkutils.apk import APK

apk = APK('test.apk')
apk.get_manifest()
apk_obj.get_strings()
apk.get_files()
apk_obj.get_dex_files()

# elf
from apkutils.apk import get_elf_infos
get_elf_infos("test.apk")
```


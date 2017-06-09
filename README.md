#apkutils

### Install 

```
pip install apkutils
```



### Usage

```python
from apkutils.apk import APK

apk = APK('test.apk')
get_manifest()
apk_obj.get_strings()
apk.get_files()
apk_obj.get_dex_files()

# elf
get_elf_infos("test.apk")
```


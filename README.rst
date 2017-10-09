========
apkutils
========

This module help me to get infos from APK.

- apkutils\axml from `mikusjelly/axmlparser(No maintenance) <https://github.com/mikusjelly/axmlparser>`_
- apkutils\dex from `google/enjarify <https://github.com/google/enjarify>`_

------
Install
------

::

  $ pip install apkutils


------
Usage
------

- Command Line:

::

  $ python -m apkutils.apk -h
  usage: adog [-h] [-m] [-s] [-f] p

  positional arguments:
    p           path

  optional arguments:
    -h, --help  show this help message and exit
    -m          Show manifest
    -s          Show strings
    -f          Show files


- Code
::

  from apkutils.apk import APK

  apk = APK('test.apk')
  apk.get_manifest()
  apk_obj.get_strings()
  apk.get_files()
  apk_obj.get_dex_files()

  # elf
  from apkutils.apk import get_elf_infos
  get_elf_infos("test.apk")



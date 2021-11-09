
apkutils
========


.. image:: https://img.shields.io/pypi/v/apkutils?style=for-the-badge
   :target: https://img.shields.io/pypi/v/apkutils?style=for-the-badge
   :alt: PyPI
 
.. image:: https://img.shields.io/pypi/status/apkutils?style=for-the-badge
   :target: https://img.shields.io/pypi/status/apkutils?style=for-the-badge
   :alt: PyPI - Status
 
.. image:: https://img.shields.io/pypi/pyversions/apkutils?style=for-the-badge
   :target: https://img.shields.io/pypi/pyversions/apkutils?style=for-the-badge
   :alt: PyPI - Python Version
  
.. image:: https://img.shields.io/pypi/dw/apkutils?style=for-the-badge
   :target: https://img.shields.io/pypi/dw/apkutils?style=for-the-badge
   :alt: PyPI - Downloads
 
.. image:: https://img.shields.io/pypi/l/apkutils?style=for-the-badge
   :target: https://img.shields.io/pypi/l/apkutils?style=for-the-badge
   :alt: PyPI - License


介绍
~~~~

一个用于解析APK、Dex、AXML、ARSC、ELF的库。

安装教程
~~~~~~~~

.. code-block::

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

用法
~~~~

.. code-block:: python

   from apkutils import APK

   apk = APK.from_file(file_path)
   manifest = apk.get_manifest()
   apk.close()

   # or 
   with APK.from_file(file_path) as apk:
       apk.get_manifest()

请参考\ ``examples``\ 目录使用。

注意
^^^^


* 1.0.0 之后的接口不兼容之前的版本。

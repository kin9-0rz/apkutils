# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
['apkutils',
 'apkutils.axml',
 'apkutils.dex',
 'apkutils.dex.jvm',
 'apkutils.dex.jvm.constants',
 'apkutils.dex.jvm.optimization',
 'apkutils.dex.typeinference',
 'apkutils.elf']

package_data = \
{'': ['*']}

install_requires = \
['Pygments>=2.12.0,<3.0.0',
 'beautifulsoup4>=4.10.0,<5.0.0',
 'click>=8.0.3,<9.0.0',
 'cryptography>=35.0.0,<36.0.0',
 'lxml>=4.6.4,<5.0.0',
 'pyelftools>=0.27,<0.28',
 'pyftype>=1.2.4,<2.0.0']

entry_points = \
{'console_scripts': ['apkutils = apkutils.cli:main']}

setup_kwargs = {
    'name': 'apkutils',
    'version': '1.0.5',
    'description': '一个APK解析库',
    'long_description': None,
    'author': 'kin9-0rz',
    'author_email': 'kin9-0rz@outlook.com',
    'maintainer': None,
    'maintainer_email': None,
    'url': 'https://gitee.com/kin9-0rz/apkutils',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'entry_points': entry_points,
    'python_requires': '>=3.8',
}


setup(**setup_kwargs)


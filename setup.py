#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

requirements = [
    'Click>=7.0', 
    "anytree",
    "cigam",
    "pyelftools",
    "pyopenssl",
    "xmltodict",
    "beautifulsoup4",
    "petty",
    "lxml",
]

setup_requirements = ['pytest-runner', ]

test_requirements = ['pytest>=3', ]

setup(
    author="King Orz",
    author_email='kin9-0rz@outlook.com',
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="a parser for apk, dex, axml, arsc",
    entry_points={
        'console_scripts': [
            'apkutils=apkutils.cli:main',
        ],
    },
    install_requires=requirements,
    license="MIT license",
    long_description=readme,
    include_package_data=True,
    keywords='apkutils',
    name='apkutils',
    packages=find_packages(include=['apkutils', 'apkutils.*']),
    package_data={"apkutils.axml": ['public.xml']},
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://gitee.com/kin9-0rz/apkutils',
    version='0.10.1',
    zip_safe=False,
)

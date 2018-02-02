from os import path

from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

with open('README.rst', 'r') as f:
    long_description = f.read()

setup(
    name="apkutils",

    version="0.1.3",

    description=("Utils for parsing apk."),
    long_description=long_description,

    url="https://github.com/mikusjelly/apkutils",

    author="mikusjelly",
    author_email="mikusjelly@gmail.com",

    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3 :: Only",
    ],

    keywords="apk dex axml",

    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    install_requires=[
        "pyelftools",
        "cigam",
        "xmltodict",
    ],
)

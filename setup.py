import os.path

from apkutils import __VERSION__
from setuptools import find_packages, setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="apkutils",

    version=__VERSION__,

    description=("Utils for parsing apk."),
    long_description=read('README.rst'),

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
        "anytree",
        "TextWizard"
    ],
)

import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="dexlib",
    version="0.0.1",
    author="acgmohu",
    author_email="acgmohu@gmail.com",
    description=("A parser for .dex(Android Dalvik EXecutable) files."),
    license="Apache",
    keywords="dex",
    url="https://github.com/acgmohu/dexlib",
    packages=['dexlib'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Utilities",
    ],
)

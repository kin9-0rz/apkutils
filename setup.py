from setuptools import setup


if __name__ == "__main__":

    with open('README.rst', 'r') as f:
        long_description = f.read()

    # def read(fname):
    #     return open(os.path.join(os.path.dirname(__file__), fname)).read()

    setup(
        name="apkutils",
        version="0.0.8",
        description=("apkutils"),
        install_requires=[
            "pyelftools",
            "cigam",
            "xmltodict",
        ],
        packages=[
            "apkutils",
            "apkutils.axml",
            "apkutils.dex",
            "apkutils.elf",
            "apkutils.test",
        ],
        package_dir={"": "src"},

        keywords="",
        license="Apache",
        classifiers=[
            "Development Status :: 4 - Beta",
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python :: 3 :: Only",
            "Topic :: Utilities",
        ],

        author="mikusjelly",
        author_email="mikusjelly@gmail.com",
        url="https://github.com/mikusjelly/apkutils",

    )

# `python -m apkutils` 的入口垫片：逻辑主体在 cli.py，这里只负责转发。
# 别把它整个注释掉——那样 `python -m apkutils` 会静默 exit 0（什么都不做），
# tests/test_readme_cli.py 的 python_dash_m 测试会变红。
import sys

from apkutils.cli import main

if __name__ == "__main__":
    sys.exit(main())
"""axml 解析器的类型化异常。

独立成叶子模块，而不是留在 `axml/__init__.py`：`public.py` 在 import 期
就要抛它，那时包入口还没执行到类定义，从入口取会形成循环导入。
"""


class ResParserError(Exception):
    """AXML / ARSC 二进制结构无法解析，或内置资源表缺失。"""

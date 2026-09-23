"""打包 metadata 的契约测试。

`pyproject.toml` 里的 license / classifiers 除了给人看，还是 shields.io 徽章的
数据来源：`pypi/status`、`pypi/pyversions`、`pypi/l` 分别读 PyPI metadata 的
`Development Status ::` classifier、`Programming Language :: Python :: 3.x`
classifier、license 表达式——取不到就渲染成 unknown / missing。这些字段缺失时
本地构建、安装、跑测试都不会报错，只有发版之后徽章变灰才会被发现，所以在这里
把契约钉住。

注意：shields.io 读的是 PyPI 上**已发布**版本的 metadata，本测试只能保证下一次
上传会带上正确字段，无法验证线上徽章本身。
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"

# shields pypi/pyversions 只认带 minor 的版本 classifier，「3 :: Only」不算
PYTHON_MINOR_CLASSIFIER = re.compile(
    r"^Programming Language :: Python :: (\d+)\.(\d+)$"
)
# requires-python 的下限，例如 ">=3.10"、">=3.10,<4"；同时留住运算符，
# 因为只有含下限的运算符才能断言「下限版本本身必须被声明」
REQUIRES_PYTHON_FLOOR = re.compile(r"(>=|>|~=|==)\s*(\d+)\.(\d+)")


def _load_pyproject():
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10 没有 tomllib，而 tomli 不在依赖里
        pytest.skip("Python 3.10 无 tomllib：本契约由 CI 的 3.13 job 覆盖")
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_pyproject_declares_an_spdx_license():
    """uv_build 只接受 PEP 639 的字符串形式，退回 {text = ...} 会构建失败。

    同时也是 shields pypi/l 的首选数据源（license-expression）。
    """
    project = _load_pyproject()["project"]

    license = project.get("license")
    assert isinstance(license, str) and license.strip(), (
        "project.license 必须是非空 SPDX 字符串（PEP 639），"
        "否则 shields pypi/l 显示 missing、且 uv_build 拒绝构建"
    )


def test_pyproject_ships_the_license_file():
    """让 LICENSE 进 wheel/sdist，PyPI 才会给出 License-File 元数据。"""
    project = _load_pyproject()["project"]

    assert "LICENSE" in project.get("license-files", []), (
        "project.license-files 需要包含 LICENSE，否则产物里带不上许可证文件"
    )


def test_pyproject_declares_development_status():
    """shields pypi/status 的唯一数据源。"""
    classifiers = _load_pyproject()["project"].get("classifiers", [])

    assert any(c.startswith("Development Status :: ") for c in classifiers), (
        "缺少 Development Status classifier，shields pypi/status 会渲染成 unknown"
    )


def test_python_version_classifiers_cover_the_lower_bound():
    """classifiers 与 requires-python 必须一致，否则 pypi/pyversions 会说谎。"""
    project = _load_pyproject()["project"]

    classifiers = project.get("classifiers", [])
    declared = [
        (int(m.group(1)), int(m.group(2)))
        for c in classifiers
        if (m := PYTHON_MINOR_CLASSIFIER.match(c))
    ]
    assert declared, (
        "没有任何 Programming Language :: Python :: 3.x classifier，"
        "shields pypi/pyversions 会渲染成 missing"
    )

    floor = REQUIRES_PYTHON_FLOOR.search(project["requires-python"])
    assert floor, f"无法从 requires-python 解析下限：{project['requires-python']!r}"
    operator, major, minor = floor.groups()
    floor_version = (int(major), int(minor))

    too_low = [v for v in declared if v < floor_version]
    assert not too_low, (
        f"classifier 声明了低于 requires-python 下限 {floor_version} 的版本 "
        f"{too_low}：这些版本装不上，会被 pypi/pyversions 广告出去"
    )
    # ">3.10" 这类排他下限不要求声明 3.10 本身，含下限的运算符才要求
    if operator in (">=", "~=", "=="):
        assert floor_version in declared, (
            f"requires-python 下限 {floor_version} 没有对应的 classifier："
            "下限版本明明可装，徽章上却不会出现"
        )

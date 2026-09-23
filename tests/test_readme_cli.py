"""README 里的 `apkutils --help` 快照必须等于真实输出。

这个快照曾经长期与代码脱节：README 里列着一个早已被删除的 `--version` 选项和
一份缺少 `info` / `packages` 的命令列表，而当时没有任何东西会因此变红。这里把
顶层 help 钉成契约——命令、选项或短帮助一改，本测试就会失败，提醒同步
README.md 与 README.en.md。

只钉顶层 help。子命令自己的 help 不写进 README，也就没有可漂移的地方。
"""

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from apkutils.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
README_FILES = ["README.md", "README.en.md"]

# 匹配 `❯ apkutils --help` 之后的围栏代码块（快照本身以 Usage 行开头）
HELP_BLOCK = re.compile(
    r"^```[a-z]*\n❯ apkutils --help\n"
    r"(?P<body>Usage: apkutils \[OPTIONS\] COMMAND \[ARGS\]\.\.\..*?)^```$",
    re.MULTILINE | re.DOTALL,
)


def _live_help():
    result = CliRunner().invoke(main, ["--help"], prog_name="apkutils")
    assert result.exit_code == 0, result.output
    return result.output.rstrip("\n")


def _snapshot(name):
    match = HELP_BLOCK.search((REPO_ROOT / name).read_text(encoding="utf-8"))
    assert match, (
        f"{name} 里找不到 `apkutils --help` 的快照代码块："
        "要么被删了，要么不再是 `❯ apkutils --help` + 真实 help 输出的形式"
    )
    return match.group("body").rstrip("\n")


def test_help_snapshot_starts_a_block_in_every_readme():
    """两个 README 都得有快照，避免只更新其中一份。"""
    assert {name for name in README_FILES if HELP_BLOCK.search(
        (REPO_ROOT / name).read_text(encoding="utf-8")
    )} == set(README_FILES)


@pytest.mark.parametrize("name", README_FILES)
def test_readme_help_snapshot_matches_cli(name):
    assert _snapshot(name) == _live_help(), (
        f"{name} 里的 `apkutils --help` 快照与真实输出不一致，请同步"
    )

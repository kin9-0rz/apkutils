# 运行时版本号来自 importlib.metadata，库不导出 `__version__`

`apkutils --version` 读的是打包元数据：真源始终是 `pyproject.toml` 的 `[project].version`，运行时经 `importlib.metadata.version("apkutils")` 取，且刻意放在 flag 的 callback 里惰性求值，不在 `apkutils.cli` 的模块导入期。同一个数字不需要第二份拷贝——`docs/agents/release.md` 的发布冒烟检查早就在用这条路径。

库因此**不**提供 `apkutils.__version__`。它看起来只是少写四行，实际后果有三层：版本号会变成 `pyproject.toml`、`uv.lock`、源码里的字面量三处需要同步的拷贝，而 CI 的 `uv lock --check`（`.github/workflows/ci.yml`）只校验前两处，第三处会静默腐烂直到有人拿它做判断；按 ADR-0006（public 成员只增不减），它一旦发布就永远删不掉；下一次有人看到 `src/apkutils/__init__.py` 里没有 `__version__`、又看到 README 里的 `--version`，最自然的反应就是「顺手补上」——而那正是本 ADR 拒绝的方案。惰性求值是同一条约束的另一半：未安装的源码树下 `import apkutils.cli` 必须照常可用，失败只应该发生在真的敲了 `--version` 的时候。

`18e58b3` 曾把 `--version` 与 `__version__` 一起删掉（清理提交，未记录理由），而 README 继续宣传着这个已不存在的选项，直到 `61b70f1` 修好快照。这次的结论是只加回前者：CLI 报告自己的版本是合理的用户需求，而库再维护一份版本字面量不是。

## Considered Options

- **恢复 `apkutils.__version__` 字面量**：`import` 期绝对安全，但引入 CI 抓不到的第三处版本号，且受 ADR-0006 永久保护。
- **运行时读 `pyproject.toml`**：真源唯一，但 `requires-python = ">=3.10"` 而 `tomllib` 是 3.11+；要么抬高 `requires-python`，要么加一个 tomllib 降级依赖。
- **交给 click 自动探测**（`version_option()` 不传 version）：底层就是 `importlib.metadata`，但 `pyproject.toml` 声明 `click>=8.0.3` 而 CI 的 `lowest-direct` job 正好钉在下限，等于把跨 click 版本的行为差异纳入自己的测试面。
- **手写 click 装饰器而非 `click.version_option()`**：内置 `version_option` 在装饰时求值（导入期），与惰性求值冲突，因此改为一个 `is_eager` + `expose_value=False` 的 flag 与 callback；help 文本沿用 click 内置措辞 `Show the version and exit.`，以便日后若改回内置实现，快照不需要重录。

## Consequences

- 改版本号只改 `pyproject.toml` 与 `uv.lock` 两处，流程与 `docs/agents/release.md` 一致；`--version` 自动跟着变。
- 未安装（`PYTHONPATH=src` 的裸 checkout）时敲 `--version` 会得到 `PackageNotFoundError`。这是**有意的**：CI 四个 job 全部走 `uv run`（会安装项目），开发走 `.venv`，发布冒烟也走已安装的 venv，「未安装即不支持」是被接受的立场，不加 `unknown` 之类的兜底。
- `tests/test_readme_cli.py` 用「输出版本 == `importlib.metadata` 读到的版本」锁住这个 flag，而不是把它做成 README 快照：版本号每次发版都变，快照会让每次发版多两处手改。`--version` 的输出是打包元数据的回显，不是需要逐字稳定的用户契约。

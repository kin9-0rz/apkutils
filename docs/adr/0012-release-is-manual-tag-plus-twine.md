# 发布是手工流程：annotated tag + uv build + twine，并同时提供 sdist

发布没有一个 release workflow：版本号提升走普通 PR，合并后在 `master` 上打 annotated tag `vX.Y.Z`，再由维护者在本机构建并用 `twine` 上传；凭据放在 `~/.pypirc` 的 `[pypi]` 段。也不建 GitHub Release。

决策：**保持手工发布，并把完整流程（含验证步骤）写进 `docs/agents/release.md`。**

理由：

- 发布是**不可逆**的动作——同一个版本号不能重传，传错只能 yank 后另发一个号。把最不可逆的动作交给无人值守的路径，收益（省几条命令）与风险（一次错误的自动发布）不成比例；本仓库过去一年只发布了 4 次（`2.0.4`、`2.0.5`、`2.1.0`、`2.1.1`）。
- 自动发布要引入两样本仓库现在没有的东西：tag 触发的 workflow，以及 PyPI 侧的 trusted publishing 配置。前者在 `master` 之外多出一条带写权限的路径，后者把发布身份从「维护者本机的 token」换成「仓库的 CI 身份」。对一人维护、发布频率如此低的仓库，这两样都是纯负担。
- 流程里真正容易错的不是命令，而是**意识**：漏掉 `uv.lock` 里的版本号、用 `--wheel` 只构建一半、没验证就上传。这些由文档里的清单和 CI 现有的 `uv lock --check` 覆盖，比自动化更直接。

## 发布物：从 2.1.1 起同时给 sdist

`2.1.0` 及以前在 PyPI 上只有 wheel，因为 `make build` 写的是 `uv build --wheel`，而它正是发布时用的命令。该目标已修正为 `uv build`（默认同时构建 wheel 与 sdist），所以 `2.1.1` 是第一个带 sdist 的版本。

这改变了 ADR-0011 的实际暴露面：构建后端的上限 `uv_build>=0.12.18,<0.13` 现在随 sdist 一起发布，从 sdist 构建的人会受它约束——ADR-0011 里「本仓库当前只发 wheel，所以这条决策的实际暴露面很小」的说法不再成立。该 ADR 记录的是当时的事实，故不改写它；`build-backend` 那个金丝雀则从「理论上该有」变成真的在保护一条发布路径。

## Considered Options

**tag 触发的 CI 自动发布（trusted publishing）**被拒绝：见上——收益是把三条命令挪进 YAML，代价是给不可逆动作加一条无人值守路径，并要求在 PyPI 侧新增 publisher 配置。

**用 `make publish` 封装上传**被拒绝：现有 `Makefile` 在维护者本机并不可用（没有 `make`），封装出的目标没人验证，等于把一个未测试的脚本当成发布入口；文档里的命令反而能被逐条复制执行。**这里有一个被接受的例外**：去掉 `make build` 里的 `--wheel`——那是修一个会产出错误发布物的既有目标，不是新增发布入口。

**继续只发 wheel（`uv build --wheel`）**被拒绝：sdist 是 Python 打包生态的常规产物，也是下游与发行版审计、自行构建的入口；ADR-0011 写下「对一个已发布的 sdist 而言」时已经预期了它。代价是多一份需要维护的产物面。

## Consequences

- 发布是**维护者本机的动作**，本机环境因此会渗进流程：Windows 的 GBK 控制台会让 `twine` 的进度条崩溃，必须带 `PYTHONIOENCODING=utf-8` 与 `--disable-progress-bar`（见 `docs/agents/release.md`）。
- tag 约定是 annotated `vX.Y.Z`，打在合并后的 `master` 上；仓库**没有** GitHub Release。
- 徽章的可见变化滞后于发布：shields.io 对 `pypi/status`、`pypi/l`、`pypi/pyversions` 的缓存是 86400 秒，GitHub 的 camo 还有一层。判断发布是否成功应以 PyPI 的 JSON API 为准，而不是 README 上的徽章。
- `dist/` 被 gitignore，发布产物不进仓库；发布历史的事实来源是 PyPI 与 git tag。
- 这条决策是可复审的：一旦发布频率上升，或仓库引入多人协作与 CI 发布身份，原本被拒绝的 trusted publishing 就该重新评估。

# 发布：手工 tag + uv build + twine upload

发布是**手工流程**：没有 release workflow，也没有 trusted publishing；`make build` / `make publish` 只是命令别名，发布正确性由本文这份人工验证清单保证。为什么这样，见 `docs/adr/0012-release-is-manual-tag-plus-twine.md`。

「改动走 branch + PR」的前提见 `git-workflow.md`；发布是在 merge 之后追加的一步。

## 发布物

**同时提供 wheel 与 sdist**（从 `2.1.1` 起；此前只发 wheel）。所以构建必须用 `uv build`——`uv build --wheel` 只出 wheel。历史上 `make build` 写的就是 `--wheel`，而它正是发布时用的命令，因此 `2.1.0` 及以前的所有版本在 PyPI 上都没有 sdist。这个目标已经修好（见 ADR-0012）。

附带后果：sdist 会带着构建后端上限 `uv_build>=0.12.18,<0.13` 一起发布，于是 ADR-0011 的金丝雀门禁从此真的在保护一条发布路径。

## 流程

### 1. 版本号

从 `master` 切 `release/X.Y.Z`，改**两处**，缺一不可：

- `pyproject.toml` 的 `[project].version`
- `uv.lock`：editable 自引用（`source = { editable = "." }`）也带版本号，跑一次 `uv lock` 更新它

只改 `pyproject.toml` 会让 CI 的 `uv lock --check` 变红。

### 2. PR 与合并

照 `git-workflow.md` 走 branch + PR，等 4 个必需检查（`test (3.10)`、`test (3.13)`、`lowest-direct`、`build-backend`）变绿后合并。

### 3. 打 tag

先例 `v2.1.0`、`v2.1.1` 都是 **annotated tag、打在合并后的 `master` 上，且不建 GitHub Release**：

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

### 4. 构建与验证（上传前必做）

**上传不可逆**：同一个版本号不能重传，传错只能 yank 后另发一个号。所以先把验证做满：

```bash
make build                       # = rm -rf dist && uv build，同时产出 wheel 与 sdist
uv run --with twine twine check dist/*
```

再解包核对 METADATA：`Version`、`License-Expression`、`License-File`、全部 `Classifier:` 行、`Project-URL`。最后把 wheel 装进一个干净 venv 跑冒烟：

```bash
SMOKE="$TEMP/smoke"                      # POSIX 下：SMOKE=/tmp/smoke
uv venv "$SMOKE"
uv pip install --python "$SMOKE" dist/*.whl   # 传 venv 目录，uv 自己找解释器
"$SMOKE/Scripts/python" -c "from importlib.metadata import version; print(version('apkutils'))"   # POSIX 下："$SMOKE/bin/python"
"$SMOKE/Scripts/apkutils" --help              # 顺带验证 console script 也装上了
```

再用 `tests/fixtures/test.zip` 解析一遍并确认 `apk.errors` 为空。这一步刻意**不用** `uv run`：要验证的是**装出来的 wheel**，而不是工作区的 editable 安装。

### 5. 上传

```bash
make publish                     # = make build + twine upload，已带 UTF-8 与禁进度条两个 flag
```

它展开成的就是下面这一条：

```bash
PYTHONIOENCODING=utf-8 uv run --with twine twine upload --non-interactive --disable-progress-bar dist/*
```

凭据读 `~/.pypirc` 的 `[pypi]` 段（`pypi-` 开头的 token）。

### 6. 核对线上

```bash
curl -s https://pypi.org/pypi/apkutils/X.Y.Z/json        # classifiers / license_expression / project_urls
curl -s "https://pypi.org/pypi/apkutils/json?ts=$(date +%s)"   # 主端点有 CDN 缓存，带参数绕开它
```

## 坑

- **twine 在 Windows 的 GBK 控制台上会崩**：rich 的进度条抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2022'`，上传中断。`make publish` 已经带上 `PYTHONIOENCODING=utf-8` 与 `--disable-progress-bar`；手工敲命令时要自己加。判断这次到底传上去了没有，要查**版本专属**端点（`/pypi/apkutils/X.Y.Z/json`），别信主端点——它有 CDN 缓存，发布后一段时间仍在报旧版本。
- **`uv.lock` 也带版本号**：见流程第 1 步。
- **徽章滞后不是故障**：shields.io 对 `pypi/status`、`pypi/l`、`pypi/pyversions` 的 `_cacheLength` 是 86400 秒，GitHub 的 camo 图片代理还有一层缓存，README 上的徽章最长滞后 24 小时。想立刻确认 shields 的上游数据是否已更新，给 URL 加一个无关查询参数换出未缓存的 URL：
  `https://img.shields.io/pypi/l/apkutils?style=for-the-badge&probe=1`
- **本仓库没有 GitHub Release**（现状只有 tag），发布说明目前只存在于 commit 与 PR 描述里。

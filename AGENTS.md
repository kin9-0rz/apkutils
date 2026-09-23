## Agent skills

### Python 环境

本项目用 **uv** 管理开发环境与依赖：一律 `uv sync` / `uv run ...` / `uv build`，**不要**使用系统 Python（本机 PATH 上的 `python` 是 scoop shim，会间歇性以 exit code 49 静默失败）。需要额外工具时用 `uv run --with <pkg> <cmd>`，不要全局安装。CI 同理：用 `astral-sh/setup-uv` 选择解释器，没有 `setup-python`。

### Issue tracker

Issues 存放在 GitHub Issues（`kin9-0rz/apkutils`），通过 `gh` CLI 操作。详见 `docs/agents/issue-tracker.md`。

### Triage labels

使用五个 canonical triage roles，label string 与 role name 相同。详见 `docs/agents/triage-labels.md`。

### Domain docs

Single-context 布局：repo root 的 `CONTEXT.md` + `docs/adr/`。详见 `docs/agents/domain.md`。

### Git 工作流

`master` 受分支保护且 `enforce_admins` 已启用，改动走 **branch + PR**，不直推。详见 `docs/agents/git-workflow.md`。

### 发布

发版是手工流程：annotated tag `vX.Y.Z` + `uv build` + `twine upload`，没有 CI 自动发布。详见 `docs/agents/release.md`。

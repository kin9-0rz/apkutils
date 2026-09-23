## Agent skills

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

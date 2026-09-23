# Git 工作流：master 受保护，改动走分支 + PR

`master` 是受保护分支，且 `enforce_admins` 已启用 —— **admin 也不能绕过**。因此任何改动都不能直推 `master`，agent 也不例外。

## 分支保护的约束

- **必需检查**（4 个，缺一不可）：`test (3.10)`、`test (3.13)`、`lowest-direct`、`build-backend`
- **禁止**：推送未通过必需检查的提交、force push、删除该分支
- `strict`（要求分支与 master 同步后再合并）当前为 `false`

规则的唯一事实来源是 GitHub 仓库设置；本文只解释它、以及 agent 该怎么配合，不复制完整配置。

## Agent 应走的流程

1. 从 `master` 切一个分支（例如 `fix/...`、`docs/...`）
2. 提交并推送该分支（`git push -u origin <branch>`）
3. 开 PR（`gh pr create`）
4. 等 4 个必需检查在 PR 上变绿（`gh pr checks --watch`）
5. merge（仓库允许 squash 与 merge commit；`delete_branch_on_merge` 已开）

发版不在这个流程里：它是在 merge 之后追加的手工步骤（annotated tag + 构建 + 上传），见 `release.md`。

若尝试直推 `master`，push 会被拒绝并提示 `Protected branch update failed` / `required status checks are expected`。看到这个**不要**用 `--force`、也不要去关分支保护——改成走上面的 PR 流程。

## `build-backend` 金丝雀变红时怎么办

`build-backend` 校验构建后端 pin 是否与当前 uv 版本匹配（见 `docs/adr/0011-build-backend-version-ceiling.md`）。它在 **uv 发布新 minor 时变红**，这是设计意图，不是故障。

处理：按 uv CHANGELOG 的提示，把 `pyproject.toml` 中 `[build-system].requires` 的上限 bump 到下一个 minor（例如 `<0.13` → `<0.14`），然后走上面的 PR 流程。因为它是必需检查，变红期间所有 PR 都合不了，所以应尽快处理。

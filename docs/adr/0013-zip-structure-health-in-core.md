# ZIP 结构层体检与修复进 core，android-reverse-maid 改依赖本包

android-reverse-maid 的 unpacking 技能自带 `zip_health.py`（ZIP 结构层对抗体检 + 修复）与 `zip_decrypt.py`（宽容读取器）两个脚本，而它们是围绕 `_apkfile` 的容忍规则长出来的姊妹物——同一批结构知识被两个仓库各维护一份，`_apkfile` 的容忍规则一改，两处判定就会漂移。决策：把能力迁进公开模块 `apkutils.ziphealth`（`check` / `repair` + 宽容读取），技能侧改为 import 本包，scripts 目录不再维护这两个文件。

## Considered Options

- **在技能侧保留脚本**——被拒：同一 ZIP 结构知识散在两仓库，容忍规则与体检判据必然漂移。
- **vendor 进 core 包原样保留**——被拒（ADR-0008）：包内会出现第二套与 `_apkfile` 并行的 ZIP 解析器；迁入即按 deep module 重组，而非复制。
- **检测复用 `_apkfile.ZipInfo`、修复另写一套**——被拒：名字一致性、LFH 侧标志、`cd_damaged` 判定本就必须读原始字节，最终收敛为一个字节级私有 deep module，兼作体检、修复与宽容读取。

## Consequences

- 库首次获得**写路径**：`repair` 产出干净副本。ADR-0003（库不写 stdout）仍成立——输出只在 CLI。
- 依赖方向反转：android-reverse-maid → apkutils；技能侧删两脚本，`static_triage.py` / `jiagu_unpacker.py` 改 import。
- 破坏性 CLI 变更：`unzip` 移入新的 `zip` 子命令组且不留别名。`unzip` 命中 ADR-0007 判据（README 点名 + 测试锁定），故只在 3.0 窗口内执行（ADR-0006）。
- 修复的版本归一化修正上游怪癖：`46`（bzip2）/`63`（lzma）是合法所需版本，不再被重置为 `20`。

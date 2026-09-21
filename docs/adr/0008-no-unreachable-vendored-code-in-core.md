# core 包不停放无入口的 vendored 代码

apkutils 的 core 包里长期躺着两批 vendored 第三方代码：`gdiff.py`（Google diff-match-patch 的 Python 移植）与 `dex/jvm` + `dex/typeinference`（enjarify，一个 DEX→JVM 字节码翻译器，约 69.5k 行）。它们没有入口——从 `APK`、CLI 出发均不可达，从未进过任何发布版的 `__all__`，文档未点名，无测试锁定。ADR-0007 的判据只能说清它们「不是 public surface」，说不出它们「为何不该待在包里」。

规则：**core 包只装被 facade 触达的实现。** 一段 vendored 第三方代码若在包里没有入口，就不留在 core：

- 想要那个能力对外提供 → 拆成独立 distribution，自带依赖声明与测试；
- 只是将来可能用到 → 删除，届时重新 vendor 上游最新版本，而不是复活一份无测试的旧副本。

## Considered Options

「先留着，等接线时再用」被拒绝：没人能"用"一份没有入口、没有测试的源码，它只会随 Python 版本与上游演进而腐烂；而重新 vendor 上游比修复旧副本更便宜。

「只从 wheel 排除、源码留在仓库」（`tool.uv.build-backend.wheel-exclude`）被拒绝：它能止住向用户投送垃圾，却减不掉认知负担——源码仍会被 grep 与 agent 读到、仍会被误当成现有能力。

## Consequences

判据是**入口可达性**：从 `APK`、`apkutils.cli`、`apkutils.__main__` 三个入口做可达性分析，包内不应存在不可达文件。这条检查是可机械执行的，应当作为大清理的验收条件。

2026-09 实测：`dex/jvm` 与 `dex/typeinference` 互引成环、无任何外部引用者（`flags.py`、`treelist.py` 只被该环引用），占 wheel 解压体积的 82.0%；据此删除。

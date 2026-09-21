# 已发布的 module path 只在曾是 surface 时才算公开

ADR-0006 说「public 成员只增不减」，但没说清一条 importable path 何时算 public。缺了判据，「这个模块随包发布过」会被读成「永远不能删」，死代码因此获得永久居留权。

判据：一条 importable path 算「已发布的 public surface」，当且仅当满足以下**至少一条**——

1. 出现在某个发布版的 `__all__`；
2. 被 `README.md` / `README.en.md` / `docs/` **点名**（泛指的能力词不算）；
3. 有测试锁定。

三条皆无 = 从未公开，可自由删除或改名，不必等下一个 major。

## Consequences

ADR-0006 的硬约束据此适用于 `APK` 的 public 成员与上述已发布 path。两处既有改动由此判为合规：`apkfile.py` → `_apkfile.py`（1.5.x 曾在 `__all__`，2.0 major 已移除），以及随后删除的 `gdiff` / `wildcard` / `intersection` / `elf` 四个零 importer 孤岛（从未进过任何发布版的 `__all__`，未被文档点名，无测试锁定）。

「(2) 必须点名」是刻意的窄口径：README 只写能力词（如「解析 ELF」）不能把某条具体 path 救成 surface，否则一个泛指词就能让死代码不可删。反过来，若某能力真要对外承诺，就得在文档里点名并给出测试——这也是把它从「从未公开」升格为 surface 的唯一途径。

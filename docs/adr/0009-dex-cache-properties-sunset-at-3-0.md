# 2.0.5 的 dex 缓存属性以只读 property 顶到 3.0，不再新增同类垫片

ADR-0007 的三条判据把 `APK.dex_files`、`APK.opcodes`、`APK.strings_refx` 都判为「从未公开」（ADR-0006 的硬约束因此不拦）——没进过 `__all__`、文档未点名、无测试锁定。但「合规」不等于「值得」：删掉意味着仍在读它们的下游拿到 `AttributeError`，而一个几行的 property 就能避免这种硬失败。

决策：三个名字都以只读 property 留在 facade 上，形状统一——

- 不触发解析（2.0.5 的属性也只是读缓存），未解析 dex 时 `opcodes`/`strings_refx` 为 `None`、`dex_files` 为 `[]`；
- 返回 `DexReader` 缓存的同一对象，因此 `apk.opcodes is apk.get_dex_opcodes()` 成立，别名观察不到差别；
- 不支持写入；
- 与 ADR-0005 相容：读属性只取一个视图，不触发其他视图，也不触发解析。

代价是**这三个名字据此升格为 surface**（判据第 3 条：`tests/test_apk_compat.py` 锁定），再删就要等下一个 major。所以期限写死：**只在 2.x 有效，3.0 连同 `dex_files` 一并删除**——3.0 是唯一的删除窗口，谁都不该把它们读成历史契约。

两处与 2.0.5 的刻意差异：dex 已解析但未调用过对应 getter 时，垫片返回结果而非 `None`；写入不再支持（2.0.5 是普通属性）。

## Consequences

这是特例，不是先例：判据仍是 ADR-0007，默认动作仍是删除。补垫片的门槛写成两条——删除会让下游**读属性硬失败**（而非只是行为差异），且垫片成本只有几行。两条不齐就别补，先删。

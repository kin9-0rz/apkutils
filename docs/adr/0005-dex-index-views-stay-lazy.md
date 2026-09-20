# DEX 索引视图保持按需构建，不合并为单次全量遍历

`methods()`、`strings_refx_index()`、`methods_refx_index()`、`opcodes_list()` 共享同一个遍历骨架 `_iter_parsed_classes()`，直觉上应合并为「一次遍历建全部索引」。我们保持四者各自 lazy、各自缓存、互不触发。

实测与直觉相反：i15.zip 上四视图合计 4401ms，合并为单次遍历后 4656ms（+5.8%），单独取一个视图则劣化 +58%。多数调用方只用一两个视图，合并会强迫它们为不用的视图付费。

## Consequences

要推翻这条结论，先复现那次测量，不要凭直觉「优化」。

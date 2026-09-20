# APK 是 facade，解析知识藏在私有 deep modules

`APK` 曾是 681 行的 god class，知道每种格式的解析细节。我们把它收缩为瘦 facade——只负责归档 I/O、按需触发解析、汇总失败——每个解析领域（manifest、resources、metadata、certificates、subfiles、dex）移进 `src/apkutils/_*.py` 私有 module，以小 interface 暴露实现。私有 `_` 前缀是刻意的：这些不是 API，可以自由演化，公开边界因此不必随重构变大，向后兼容只需守住 `APK`。

## Considered Options

平铺为 public module（`apkutils.manifest` 等）——被拒绝，因为那会固化更多 API 表面，与「public 成员只增不减」的硬约束直接冲突。

## Consequences

解析路径多一层间接，且 facade 需要为每个 module 写薄转发方法；新增解析领域时按同一形状落地。

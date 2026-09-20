# 解析失败默认收集，strict=True 才外抛

各解析 module 在内部诚实地 raise 自己的类型化异常（`ManifestError`、`ResourceTableError`、`AppMetadataError`、`CertificateError`、`DexError`）。facade 默认捕获它们，记进 `APK.errors: list[PartError]` 并写 `apkutils` logger，调用不被打断；`strict=True` 时改为向外抛。

保留旧的「部分结果、不抛异常」行为是 backward-compat 的要求，但旧行为让调用方无从发现失败，`APK.errors` 补上了这个信号，被跳过的条目则记入 `skipped`。

## Consequences

默认吞异常是刻意的——不要在后续重构中把它「修正」成默认 raise。`strict=True` 是唯一的向外抛出路径，也是新测试断言失败的推荐入口。

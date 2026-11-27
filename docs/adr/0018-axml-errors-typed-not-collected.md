# axml 抛类型化异常；参数校验不算解析失败

`apkutils.axml` 是 ADR-0001 意义上的 deep module：它内部的失败形状由自己的异常决定，`_resources.ResourceTable` 再把它包装成 `ResourceTableError`，交给 facade 记入 `APK.errors`（ADR-0002）。ruff 0.17.0 审计里剩下的那几条 `TRY002` / `TRY004` 就是拿这条链路做判断的。

结论三条：

1. **结构解析失败统一抛 `ResParserError`。** 它本来就在，只是混着两处裸 `Exception`——`axml/public.py` 的 import 期缺 `public.xml`、`ResTable_map_entry` 的越界。类定义因此从 `axml/__init__.py` 移到叶子模块 `axml/errors.py`：前一处发生在包入口执行到类定义之前，从入口 import 会成环。`apkutils.axml.ResParserError` 仍可 import，re-export 保住路径。
2. **`get_res_*` 的 `rid` 参数校验保持 `ValueError`。** 缺失或非 `int` 是调用方的编程错误，不是解析失败，不进入 ADR-0002 的收集面；`TRY004` 建议的 `TypeError` 更合语言习惯，但会让现有 `except ValueError` 的调用方失效，收益只在 lint 口味上，不做。
3. **同一条件不重复记日志。** `ResTable_map_entry` 越界处原来的 `log.error` 与紧随的异常是同一件事的两次表达；按 ADR-0002，由 facade 在收集/降级时记日志，模块内只负责抛出。

## Considered Options

- **新增 `PublicResourcesError` 区分「打包缺失」与「解析失败」**：语义更细，但多一个异常类；调用方想「axml 失败就换条路径」时得枚举两个类型，收益小于成本。
- **在 `__init__.py` 保留 `ResParserError`，`public.py` 首次使用时才抛**：绕开循环导入，但把打包错误从 `import` 推迟到第一次解析，失败点离原因更远。
- **`TRY004` 改抛 `TypeError`**：语言习惯正确，但对已发布版本是破坏性变更（ADR-0006），要么等 major，要么不做；只为 lint 不划算。

## Consequences

- 异常类型是**收窄**：原先 `except Exception` 的调用方照常捕获；`except ResParserError` 现在覆盖 axml 全部结构失败。
- `_resources.ResourceTable` 继续宽捕获并转 `ResourceTableError`——那是 PartError 收集点，见 `docs/agents/static-analysis.md` 的 BLE001 段落，本 ADR 不改。
- axml 的异常类 `__module__` 变为 `apkutils.axml.errors`，`repr` 里的限定名随之变化；路径 `apkutils.axml` 上的可用性由 re-export 保持不变。

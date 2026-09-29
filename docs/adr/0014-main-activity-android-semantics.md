# Main activity 判定按 Android 语义，且不展开 activity-alias

`get_manifest_main_activities` 的语义是"清单里可启动 APK 的入口组件"：要求 `MAIN` 与 `LAUNCHER` 出现在**同一个** `intent-filter` 内，action/category 名精确匹配；`activity-alias` 以别名自身计入，其 `targetActivity` 是实现细节、不展开；`enabled="false"` 的组件排除。

## Considered Options

- **子串扫描 `encode_contents()`（原实现）**：会把分散在两个 `intent-filter` 中的 `MAIN` 与 `LAUNCHER` 拼成一个入口，也会误命中 `android.intent.action.MAIN_*` 这类自定义 action。
- **展开 `activity-alias` 的 `targetActivity`（原实现）**：结果混入实现类，调用方无法区分"可启动组件名"与"别名背后的实现类"；`youtube.zip` 实测因此返回两个条目。

## 补充

`targetActivity` 不参与入口判定，但逆向追踪需要它：由独立的 `get_manifest_activity_aliases()` 返回**全部** `activity-alias` 的 `name→targetActivity` 映射（target 按相对名规则补全，缺失为 `None`），与入口列表解耦。

# 公开访问器即请求：每个访问器自己触发对应部分的按需解析

「按需解析」（见 CONTEXT.md 的「入口与解析」）要求调用方请求某一部分时才解析该部分。落到代码上就是：`APK` 的每个 public 访问器都是对某一部分的请求，必须自己经 `_ensure_<part>()` 触发解析，不能直接读惰性字段。

3.1.0 及以前有 12 个访问器违反了这条：`package_name`、`version_name`、`min_sdk_version`、`target_sdk_version`、`max_sdk_version`、`get_package_name()`、`get_manifest_main_activities()`、`get_manifest_activity_aliases()`、`get_manifest_application()` 直接返回 `self._manifest.*`，而它只是 `__init__` 里的空壳；`get_arsc()`、`get_app_icons()`、`app_name` 同样直接读 `self.arsc` / `self._app_icons` / `self._app_name`。真正会解析的只有 `get_manifest()` 与 `parse_resource()`。

失败是静默的：README 里「只要清单就不必先调 `parse_resource()`」的示例打印 `'' ''`，而 `APK.errors` 是空的——不是「失败了没记」，而是压根没发起解析，ADR-0002 允诺的「失败可经 `APK.errors` 查询」在这里无处施力。测试也没抓到：`tests/test_apk.py` 的夹具先调了 `parse_resource()`，把要测的行为遮住了。

现在每个惰性部分都有 `_ensure_<part>()` 守门（`_ensure_manifest()`、`_ensure_arsc()`、`_ensure_app_metadata()`、`_ensure_dex()`），访问器只从它取数；有依赖的 part 由 ensure 链补齐依赖（应用元数据依赖清单、资源表与子文件列表），`parse_resource()` 退化为按顺序 ensure 的糖。部分是否加载过由显式标志（`_manifest_loaded`、`_arsc_loaded`、`_app_metadata_loaded`、`self._dex is None`）记录，不用「结果是不是 `None`」判断——`None` / `''` / `[]` 都是合法的成功结果（归档没有资源表、清单里没有应用名）。

已知的例外只有 ADR-0009 那三个 2.0.5 垫片（`dex_files`、`opcodes`、`strings_refx`）：它们按设计不触发解析，且已约好随 3.0 删除。除它们之外的 public 访问器都受这条约束。

## Considered Options

- **只在 README 里补一句「先调 `get_manifest()`」**：文档能自洽，但这些 public 成员已经被下游直接调用（ADR-0006），靠文档缩小它们的语义不算修好。
- **未解析时抛异常**：把静默失败换成显式失败，但破坏「默认容忍、失败可查」（ADR-0002），且 2.0.5 时这些属性是急切解析、直接给值的，抛异常是倒退。
- **照 ADR-0005 让每个视图各自 lazy、互不触发**：那条针对 DEX 内部索引视图（同一次遍历的不同产物），与这里的 part 边界不是一回事——part 之间是有向依赖，访问器触发的是被依赖的 part。

## Consequences

新增 part 或给 part 加访问器时：先加 `_ensure_<part>()`，别直接读惰性字段；回归测试要从没调过 `parse_resource()` / `parse_dex()` 的干净实例起手，否则测不出这条约束。
默认模式下解析失败仍只记进 `APK.errors`；`strict=True` 下访问器会抛出对应异常，包括以前静默返回空值的 `apk.package_name`、`apk.get_arsc()`、`apk.app_name`。

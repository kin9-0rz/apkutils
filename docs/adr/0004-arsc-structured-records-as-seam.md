# ARSC 以结构化记录为 seam，XML 输出收敛为单一 formatter

ARSC 解析器曾同时是 XML 渲染器，上层 `_resources` 需要「渲染成 XML 再用 BeautifulSoup 解析回来」。现在 `ARSCParser.get_resources()` 返回结构化 `Resource` 记录（kind/name/value/id），XML 输出与上层资源查询都从这同一份结构化数据出发，XML 往返与 bs4 依赖随之消失。

7 个扁平 emitter（public/string/id/bool/integer/color/dimen）收敛为 `_emit_resources()` + `_FLAT_FORMATTERS`；`get_strings_resources` 的 packages/locale 嵌套形状确实不同，保持独立。

## Consequences

签名与输出字节不变，并由 `tests/test_arsc_resources.py` 的 golden md5 锁定 8 个 emitter 的输出指纹——改动 ARSC XML 格式必须是有意的。

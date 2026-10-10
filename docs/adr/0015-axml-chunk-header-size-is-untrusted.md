# AXML chunk 头的 headerSize 不可信：按声明跳过填充，失效只告警

AXML 解析不再把 `headerSize` 当成可信校验值、也不因它偏离默认值就判定文件无效。规则改为：

- **chunk 体从 `chunk_start + headerSize` 开始**。`ResChunkHeader` 固定只读 8 字节，超出部分是被当作掩护的填充数据，解析前按声明长度跳过。
- **字符串池的 `stringsStart` 相对 chunk 起点**（与 aapt 的 `mStringData = (const char*)header + header->stringsStart` 一致），不是"偏移数组读完后的当前位置"。偏移数组之后可能还有填充，两者不等价。
- **XML 节点 chunk 的固定字段仍在 8 字节通用头之后**的标准位置。`headerSize` 偏大只告警、不跳位。
- **每个 chunk 处理完对齐到 `chunk_end`**：`size` 同样可能被调大并在尾部挂垃圾，读完固定字段不代表读完 chunk。

这样加固清单能完整读出，同时每次跳填充都留 warning。

## 为什么不能选"一律按 headerSize 跳位"

同一个文件里，`headerSize` 被调大的语义**不一致**：`com.hnmtd.clean.apk` 实测中，AXML 根 chunk、字符串池、资源映射表的头部真的插了填充数据（必须跳过），而 XML 节点 chunk（含 namespace）只把数字调大、字段仍在标准位置（跳了就错位）。

加固工具只保证 `headerSize` 不小于真实头部，不保证它描述的字节真的存在。因此"按声明跳位"只对**头部之后紧接不定长数据**的 chunk 成立（根 chunk 后面跟下一个 chunk、资源映射表后面跟 ID 数组），对**头部里已含全部固定字段**的 chunk 不成立。

## Considered Options

- **硬失败（原实现）**：`header_size != 8` / `!= 0x1C` / `!= 0x10` 一律 `_valid = False`。被加固的清单因此完全读不出来，`APK.errors` 记 `manifest` 部分失败，包名、版本、启动 Activity 全部退化成默认值。
- **`headerSize` 只做告警、完全不用**：字符串池与资源映射表会从填充数据里开始读，读出随机值，失败从"明确报错"退化成"静默读出垃圾"——比硬失败更糟。
- **按 `headerSize` 跳位并用字段取值范围反推真实布局**：namespace chunk 的 prefix/uri 是字符串索引、资源映射表的 ID 有无符号约定，都缺乏可自校验的不变式，反推规则会变成一堆特例判断。

# apkutils

apkutils 解析 Android 安装包（APK）及其内嵌产物——清单、资源表、DEX、签名、子文件——对外只暴露一个 `APK` 入口对象。

## Language

### 入口与解析

**APK**：
一个 Android 安装包 zip 归档，也是 apkutils 的公开入口对象。打开归档不解析任何内容，解析按需发生。
_Avoid_：安装包文件、archive、apk 实例

**按需解析（on-demand parsing）**：
只有调用方请求某一部分时才解析该部分；未被请求的部分永不解析。自 1.3.0 起为默认行为。
_Avoid_：lazy loading、延迟解析、预解析

### 失败处理

**部分（part）**：
一次解析的独立组成单元，也是失败归属的单位：`manifest`、`arsc`、`dex`、`subfiles`、`metadata`、`certs`。
_Avoid_：阶段、stage、section

**PartError**：
记录某一部分解析失败的值对象，含部分名、原始异常与可选文件名；收集在 `APK.errors` 中。
_Avoid_：解析错误、error

**strict 模式**：
失败处理模式。默认下失败被收集进 `APK.errors` 并写日志，调用不中断；`strict=True` 时失败向外抛出。
_Avoid_：严格模式、fail-fast、raise 模式

**跳过（skip）**：
放弃单个坏条目（某个 DEX blob 或某个 zip 条目）而继续解析其余条目；被跳过的条目记入 `skipped`。
_Avoid_：忽略、丢弃、silent failure

### APK 产物

**清单（manifest）**：
以 AXML 二进制编码的 `AndroidManifest.xml`；包名、版本、SDK、启动 Activity 的来源。
_Avoid_：AndroidManifest、meta

**资源表（ARSC / resource table）**：
APK 内的二进制资源索引。它的结构化记录是 XML 输出与上层资源查询的共同来源。
_Avoid_：resources.arsc、arsc 文件

**DEX**：
APK 内的 Dalvik 可执行代码，一个包可含多个。类、方法、字符串、交叉引用（xref）、opcode 等索引视图按需构建。
_Avoid_：dex 文件、代码

# 库代码不写 stdout，诊断走 logging

apkutils 作为库被嵌进他人的进程，写 stdout 会污染调用方的输出。约定：库代码一律不 `print`；诊断走 `logging.getLogger("apkutils")`（DEX 子 logger 为 `apkutils.dex`，AXML 为 `axml`）；只有 CLI（`cli.py`）负责面向用户的输出。

## Consequences

vendored `apkfile.py` 中残留的读路径 print（超长文件名跳过提示、`_extract_member` 的遗留 debug）是待清理项，不构成反例。

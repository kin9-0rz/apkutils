# android-reverse-maid 切换清单：zip_health / zip_decrypt → apkutils.ziphealth

本清单是 apkutils 3.0.0 交付物的一部分。目标：`android-reverse-maid` 的 unpacking
技能不再维护 `scripts/zip_health.py` 与 `scripts/zip_decrypt.py`，改为直接调用
`apkutils.ziphealth`（决策见 ADR-0013）。**本文件的改动不包含在 3.0.0 发布里**，
由 android-reverse-maid 仓库按此清单执行。

## 前置

- 环境依赖 apkutils `>=3.0.0`（本次是 3.0.0，`zip` 子组为破坏性变更，旧版无
  `apkutils.ziphealth`）。
- 兼容保证：`check()` / `repair()` 的返回 dict 形状、宽容读取函数的签名与返回
  均与旧脚本一致；`CentralEntry` 只增 `extract_version` 字段（zip_health 原先
  从原始字节反推版本号的 hack 随之消失）。

## API 映射

| 旧（scripts/ 下） | 新（apkutils.ziphealth） | 差异 |
| --- | --- | --- |
| `zip_health.check(path)` | `check(path)` | 返回 dict 形状不变 |
| `zip_health.repair(path, dir)` | `repair(path, dir)` | 返回 dict 形状不变；版本归一化修正（46/63 不再被重置） |
| `zip_health.human(report)` | `human(report)` | 不变 |
| `zip_decrypt.read_file_fully(path)` | `read_file_fully(path)` | 不变 |
| `zip_decrypt.parse_central_directory(data)` | `parse_central_directory(data)` | 条目新增 `extract_version` 字段 |
| `zip_decrypt.find_local_entries(data)` | `find_local_entries(data)` | 不变 |
| `zip_decrypt.extract_entry(path, name)` | `extract_entry(path, name)` | 不变；`BadZipError` 同由 `apkutils.ziphealth` 导出 |
| `zip_decrypt.get_dex_data(path)` | `get_dex_data(path)` | 不变（失败仍返回 `b""`） |
| `zip_decrypt.list_entries(path)` | `list_entries(path)` | 不变 |
| `zip_decrypt.clear_encryption_bit(...)` / `iter_cdfh_offsets(...)` / `find_eocd` / `locate_central_directory` | 不公开（实现细节在 `apkutils._ziphealth`） | 无外部消费者，无需迁移 |

## 改动步骤

1. **删除** `skills/engineering/unpacking/scripts/zip_health.py` 与
   `zip_decrypt.py`。

2. **`static_triage.py`**（`skills/engineering/unpacking/scripts/`）：
   - `import zip_health as zh` → `from apkutils import ziphealth as zh`
   - `import zip_decrypt as zd` → `from apkutils import ziphealth as zd`
   - import 的 try/except 降级结构保留（`zh = None` / `zd = None` 时照旧降级；
     except 分支的报错文案可改为「apkutils 不可用」）。
   - `row["tools_used"]` 里的 `"zip_health"` / `"zip_decrypt"` 字符串可保留，
     语料索引行形状不变。

3. **`jiagu_unpacker.py`**：
   - `from zip_decrypt import get_dex_data` → `from apkutils.ziphealth import get_dex_data`
   - 函数内 fallback 报错文案对应更新。

4. **`SKILL.md`（unpacking）**：
   - 第 8.1 节 L2 脚本资产列表移除 `zip_health.py`、`zip_decrypt.py`，补一句
     「ZIP 结构层体检/修复改由 `apkutils.ziphealth` 提供（依赖 apkutils>=3.0.0）」。
   - 检索全文 `zip_health` / `zip_decrypt` 引用并更新。
   - android-reverse-maid 的 ADR-0004（vendor zip_decrypt）标记为 superseded，
     指向本清单。

## 验证

- `python -m apkutils zip health <对抗样本>` 与旧 `zip_health.py` 输出 verdict 一致。
- `python -m apkutils zip repair <对抗样本> -o clean/` 产物可被 jadx/apktool 打开。
- 跑一遍 `static_triage.py` 单样本，确认 `zip_health` / `zip_repair` 列非空且
  `zip_decrypt` 列正常（宽容读取路径走 `central_directory` 或 `local_headers`）。
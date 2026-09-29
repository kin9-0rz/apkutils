# apkutils

[![PyPI](https://img.shields.io/pypi/v/apkutils?style=for-the-badge)](https://pypi.org/project/apkutils/) ![PyPI - Status](https://img.shields.io/pypi/status/apkutils?style=for-the-badge) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/apkutils?style=for-the-badge) ![PyPI - License](https://img.shields.io/pypi/l/apkutils?style=for-the-badge)

简体中文 | [English](README.en.md)

## 介绍

一个用于解析APK、Dex、AXML、ARSC的库。

## 安装教程

```bash
❯ pip install apkutils
```

```bash
❯ apkutils --help
Usage: apkutils [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  arsc      打印arsc
  certs     打印证书
  files     打印文件
  info      打印包名、应用名、版本号、SDK与证书
  manifest  打印清单
  mtds      获取指定方法中的所有字符串
  packages  列出所有的包
  strings   打印Dex中的字符串
  xref      获取方法的引用方法
  zip       ZIP 容器层：解压、结构体检、对抗修复
```

| 命令       | 用途                                            | 选项                                                                                                 |
| ---------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `arsc`     | 打印 arsc 资源                                  | `--res_type`：`string`（默认）/ `strings` / `bool` / `id` / `color` / `dimen` / `integer` / `public` |
| `certs`    | 打印证书                                        |                                                                                                      |
| `files`    | 打印归档内的文件                                |                                                                                                      |
| `info`     | 打印包名、应用名、版本号、SDK 与证书            |                                                                                                      |
| `manifest` | 打印清单原文，并列出 Package、Main Activities 与 Activity Aliases |                                                                                                      |
| `mtds`     | 获取指定方法中的所有字符串                      | `-m` / `--method`                                                                                    |
| `packages` | 列出所有的包                                    |                                                                                                      |
| `strings`  | 打印 Dex 中的字符串                             |                                                                                                      |
| `xref`     | 获取方法的引用方法                              | `-m` / `--method`                                                                                    |
| `zip`      | ZIP 容器层子命令：`unzip` / `health` / `repair` | 见下方 `zip --help`                                                                                 |

`mtds` / `xref` 的 `-m` 形如 `top/cls->mtd(Landroid/app/Application;Ljava/lang/String;Ljava/lang/String;)V`。

### `zip` 子命令

```
❯ apkutils zip --help
Usage: apkutils zip [OPTIONS] COMMAND [ARGS]...

  ZIP 容器层：解压、结构体检、对抗修复

Options:
  --help  Show this message and exit.

Commands:
  health  ZIP 结构层对抗体检（标准工具能否信任）
  repair  清除 ZIP 结构层对抗，产出干净副本（标准工具可直接消费）
  unzip   解压文件，默认显示zip文件
```

| 子命令   | 用途                                       | 选项                                                                                           |
| -------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `unzip`  | 解压文件，默认列出 zip 内容                | `-t` 校验完整性，`-e` 解压到目录，`-o` / `--output` 指定输出目录（默认 `out`）                 |
| `health` | ZIP 结构层对抗体检（标准工具能否信任）     | `--json` 输出 JSON；有对抗/损坏时退出码 `2`                                                     |
| `repair` | 清除 ZIP 结构层对抗，产出干净副本          | `-o` / `--out` 输出目录（默认 `clean/`）；成功输出 JSON，失败退出码 `2`                        |

`health` / `repair` 的库 API 见 [`apkutils.ziphealth`](#ziphealth)。

## 用法

```python
from apkutils import APK

# 按需解析：这里解析清单、arsc、应用名与图标，不碰 dex
apk = APK.from_file(file_path).parse_resource()
manifest = apk.get_manifest()
app_name = apk.app_name
icons = apk.get_app_icons()
apk.close()

# 只要清单的话不必先调 parse_resource()，get_manifest() 自己会解析
with APK.from_file(file_path) as apk:
    print(apk.package_name, apk.version_name)

# dex 走 parse_dex()：字符串、类、方法、xref 都在这里
with APK.from_file(file_path) as apk:
    strings = apk.parse_dex().get_dex_method_strings(mtd)

# 除 from_file 外，还有 from_bytes / from_io
apk = APK.from_bytes(data)
```

请参考 `examples` 目录。

## ziphealth（ZIP 结构层：体检、修复与宽容读取）

`apkutils.ziphealth` 回答一个问题：**标准 ZIP 工具能不能信任这个文件？** 它体检的是 ZIP 结构层对抗手法（伪造加密标志、CRC 抹除、版本字段抬高、CD/LFH 名字不一致、CD 损坏），与内容层的加壳正交——`_apkfile` 对这类手法一律容忍，因此「本库可读」不代表「apktool/jadx/标准 `zipfile` 可读」。

```python
from apkutils import ziphealth

report = ziphealth.check(file_path)
# report = {"path": ..., "verdict": "ok|has_flags|cd_damaged|not_a_zip|error",
#           "findings": [...], "info": {...}, "sha256": ..., "size": ...}

result = ziphealth.repair(file_path, "clean")
# 清 CDFH/LFH 的对抗标志位（bit0/5/6）+ 归一化异常版本号，产出干净副本，
# 并以标准库 zipfile 验证（verified="testzip"）；不破解密码学。
```

宽容读取对同一批对抗样本照常读出内容：`read_file_fully` / `parse_central_directory` / `find_local_entries` / `list_entries` / `extract_entry` / `get_dex_data`。

详见 [ADR-0013](docs/adr/0013-zip-structure-health-in-core.md)。

## 失败处理

自 `2.1.0` 起，单个部分（`manifest`、`arsc`、`dex`、`subfiles`、`metadata`、`certs`）解析失败**不会**中断调用：失败被记进 `apk.errors`（`PartError`，含部分名、原始异常与可选文件名）并写 `apkutils` logger；部分内的坏条目（某个 DEX blob、某个 zip 条目）会被跳过，同样记进 `apk.errors`。

```python
apk = APK.from_file(file_path).parse_resource()
for err in apk.errors:
    print(err.part, err.name, err.error)

# 需要失败向外抛出时用 strict=True
apk = APK.from_file(file_path, strict=True).parse_resource()
```

库代码不写 stdout，诊断只走 `logging.getLogger("apkutils")`，面向用户的输出都在 CLI。详见 [ADR-0002](docs/adr/0002-errors-collected-by-default-strict-opts-out.md) 与 [ADR-0003](docs/adr/0003-library-never-writes-stdout.md)。

## 备注

从 `1.3.0` 开始默认按需解析：打开归档不解析任何内容，由 `parse_resource()`（清单 + arsc + 应用名/图标）与 `parse_dex()`（dex）按需触发。

## License

MIT License，见 [LICENSE](LICENSE)。

## 感谢

- [Storyyeller/enjarify](https://github.com/Storyyeller/enjarify)
- [androguard/androguard](https://github.com/androguard/androguard)

# apkutils

[![PyPI](https://img.shields.io/pypi/v/apkutils?style=for-the-badge)](https://pypi.org/project/apkutils/) ![PyPI - Status](https://img.shields.io/pypi/status/apkutils?style=for-the-badge) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/apkutils?style=for-the-badge) ![PyPI - Downloads](https://img.shields.io/pypi/dw/apkutils?style=for-the-badge) ![PyPI - License](https://img.shields.io/pypi/l/apkutils?style=for-the-badge)

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
  info      打印清单
  manifest  打印清单
  mtds      获取指定方法中的所有字符串
  packages  列出所有的包
  strings   打印Dex中的字符串
  unzip     解压文件，默认显示zip文件
  xref      获取方法的引用方法
```

| 命令 | 用途 | 选项 |
| --- | --- | --- |
| `arsc` | 打印 arsc 资源 | `--res_type`：`string`（默认）/ `strings` / `bool` / `id` / `color` / `dimen` / `integer` / `public` |
| `certs` | 打印证书 | |
| `files` | 打印归档内的文件 | |
| `info` | 打印包名、应用名、版本号、minSdk / targetSdk 与证书 | |
| `manifest` | 打印清单原文，并列出 Package 与 Main Activities | |
| `mtds` | 获取指定方法中的所有字符串 | `-m` / `--method` |
| `packages` | 列出所有的包 | |
| `strings` | 打印 Dex 中的字符串 | |
| `unzip` | 解压文件，默认列出 zip 内容 | `-t` 校验完整性，`-e` 解压到目录，`-o` / `--output` 指定输出目录（默认 `out`） |
| `xref` | 获取方法的引用方法 | `-m` / `--method` |

`mtds` / `xref` 的 `-m` 形如 `top/cls->mtd(Landroid/app/Application;Ljava/lang/String;Ljava/lang/String;)V`。

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

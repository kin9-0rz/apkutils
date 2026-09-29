# apkutils

[![PyPI](https://img.shields.io/pypi/v/apkutils?style=for-the-badge)](https://pypi.org/project/apkutils/) ![PyPI - Status](https://img.shields.io/pypi/status/apkutils?style=for-the-badge) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/apkutils?style=for-the-badge) ![PyPI - License](https://img.shields.io/pypi/l/apkutils?style=for-the-badge)

[简体中文](README.md) | English

## Description

A parser for APK, Dex, AXML and ARSC.

## Installation

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

The CLI itself is Chinese-only, hence the help text above is shown verbatim.

| Command | Purpose | Options |
| --- | --- | --- |
| `arsc` | Print arsc resources | `--res_type`: `string` (default) / `strings` / `bool` / `id` / `color` / `dimen` / `integer` / `public` |
| `certs` | Print certificates | |
| `files` | Print the files inside the archive | |
| `info` | Print package name, app name, version, SDK and certificates | |
| `manifest` | Print the raw manifest, plus Package, Main Activities and Activity Aliases | |
| `mtds` | Print every string inside a given method | `-m` / `--method` |
| `packages` | List all packages | |
| `strings` | Print the strings in the Dex | |
| `xref` | Print the methods referencing a given method | `-m` / `--method` |
| `zip` | ZIP container subcommands: `unzip` / `health` / `repair` | see `zip --help` below |

The `-m` argument of `mtds` / `xref` looks like `top/cls->mtd(Landroid/app/Application;Ljava/lang/String;Ljava/lang/String;)V`.

### `zip` subcommands

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

| Subcommand | Purpose | Options |
| --- | --- | --- |
| `unzip` | Unzip, or list the zip contents by default | `-t` test integrity, `-e` extract, `-o` / `--output` output directory (`out` by default) |
| `health` | ZIP structure-level evasion check (can standard tools trust it?) | `--json` JSON output; exit code `2` when evasive/damaged |
| `repair` | Strip ZIP structure-level evasion, write a clean copy | `-o` / `--out` output dir (`clean/` by default); JSON output, exit `2` on failure |

The `health` / `repair` library API is `apkutils.ziphealth`, documented below.

## Usage

```python
from apkutils import APK

# On-demand parsing: this parses the manifest, arsc, app name and icons, never the dex
apk = APK.from_file(file_path).parse_resource()
manifest = apk.get_manifest()
app_name = apk.app_name
icons = apk.get_app_icons()
apk.close()

# The manifest alone needs no parse_resource(): get_manifest() parses it lazily
with APK.from_file(file_path) as apk:
    print(apk.package_name, apk.version_name)

# The dex is reached through parse_dex(): strings, classes, methods and xref live there
with APK.from_file(file_path) as apk:
    strings = apk.parse_dex().get_dex_method_strings(mtd)

# Besides from_file there are from_bytes / from_io
apk = APK.from_bytes(data)
```

See the `examples` directory.

## ziphealth (ZIP structure layer: check, repair, tolerant read)

`apkutils.ziphealth` answers one question: **can standard ZIP tools trust this file?** It checks ZIP structure-level evasion (fake encryption flags, zeroed CRC, raised version fields, CD/LFH name mismatch, damaged central directory), which is orthogonal to content-layer packing — `_apkfile` tolerates all of it, so "this library can read it" does not mean "apktool/jadx/stdlib `zipfile` can".

```python
from apkutils import ziphealth

report = ziphealth.check(file_path)
# report = {"path": ..., "verdict": "ok|has_flags|cd_damaged|not_a_zip|error",
#           "findings": [...], "info": {...}, "sha256": ..., "size": ...}

result = ziphealth.repair(file_path, "clean")
# Clears the anti-analysis flag bits (bit0/5/6) in CDFH/LFH and normalizes odd
# version fields, then verifies the copy with the stdlib zipfile (verified="testzip").
# It does not crack encryption.
```

Tolerant reads work on the same evasive samples: `read_file_fully` / `parse_central_directory` / `find_local_entries` / `list_entries` / `extract_entry` / `get_dex_data`.

See [ADR-0013](docs/adr/0013-zip-structure-health-in-core.md).

## Error handling

Since `2.1.0`, a failing part (`manifest`, `arsc`, `dex`, `subfiles`, `metadata`, `certs`) does **not** interrupt the call: the failure is recorded in `apk.errors` (`PartError`, carrying the part name, the original exception and an optional file name) and logged to the `apkutils` logger. Bad entries inside a part (a single DEX blob, a single zip entry) are skipped and recorded in `apk.errors` as well.

```python
apk = APK.from_file(file_path).parse_resource()
for err in apk.errors:
    print(err.part, err.name, err.error)

# Pass strict=True to let failures propagate instead
apk = APK.from_file(file_path, strict=True).parse_resource()
```

The library never writes to stdout — diagnostics go to `logging.getLogger("apkutils")` only, and all user-facing output lives in the CLI. See [ADR-0002](docs/adr/0002-errors-collected-by-default-strict-opts-out.md) and [ADR-0003](docs/adr/0003-library-never-writes-stdout.md).

## Notes

Since `1.3.0` everything is parsed on demand: opening an archive parses nothing, and `parse_resource()` (manifest + arsc + app name/icons) and `parse_dex()` (dex) trigger the parsing.

## License

MIT License, see [LICENSE](LICENSE).

## Credits

- [Storyyeller/enjarify](https://github.com/Storyyeller/enjarify)
- [androguard/androguard](https://github.com/androguard/androguard)

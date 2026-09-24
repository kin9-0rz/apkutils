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
  unzip     解压文件，默认显示zip文件
  xref      获取方法的引用方法
```

The CLI itself is Chinese-only, hence the help text above is shown verbatim.

| Command | Purpose | Options |
| --- | --- | --- |
| `arsc` | Print arsc resources | `--res_type`: `string` (default) / `strings` / `bool` / `id` / `color` / `dimen` / `integer` / `public` |
| `certs` | Print certificates | |
| `files` | Print the files inside the archive | |
| `info` | Print package name, app name, version, SDK and certificates | |
| `manifest` | Print the raw manifest, plus Package and Main Activities | |
| `mtds` | Print every string inside a given method | `-m` / `--method` |
| `packages` | List all packages | |
| `strings` | Print the strings in the Dex | |
| `unzip` | Unzip, or list the zip contents by default | `-t` test integrity, `-e` extract, `-o` / `--output` output directory (`out` by default) |
| `xref` | Print the methods referencing a given method | `-m` / `--method` |

The `-m` argument of `mtds` / `xref` looks like `top/cls->mtd(Landroid/app/Application;Ljava/lang/String;Ljava/lang/String;)V`.

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

# 静态分析：本仓库不设 lint 门禁，ruff 报告不可按建议执行

本仓库**没有** ruff / flake8 或任何 linter 配置，CI 也没有 lint job——`.github/workflows/ci.yml` 的四个必需检查是 `test (3.10)`、`test (3.13)`、`lowest-direct`、`build-backend`。历史上存在过 flake8 配置（`setup.cfg` 的 `[flake8]`，随 1a4c87e 删除）与 `tox.ini`（随 edc2d08 删除），两者都**从未进入 CI**：配置存在过，但没有被强制力。

所以 agent 若在 code review 或重构中自行运行 ruff，得到的结论**不能照做**。本页记录本仓库的具体反例。`ruff check .`（ruff 0.17.0，无任何配置）共 246 条 finding，其中以下 16 条按建议修改会引入缺陷或破坏测试。

ruff 的规则是形状匹配，不理解领域约束。`DexParser` 用一个共享流顺序读取字节流、`ZipFile` 持有文件句柄直到对象终结、测试故意不检查子进程退出码——这三种情况在 ruff 眼里都长得像「忘了用返回值」或「忘了用 context manager」。

## DEX 解析路径：读取即副作用

`src/apkutils/dex/dexparser.py` 的 5 条 F841（unused variable）**全部不可删除**。

`DexParser` 全程使用**一个共享的 `stream` 对象顺序读取**。`CodeItem.__init__` 里的字段偏移，靠这些「没人读的 `u16` / `u32`」推进：

```python
self.nregs = registers_size = stream.u16()   # 局部名未用，u16() 必须执行
ins_size  = stream.u16()                      # 完全未用，读取动作必须发生
outs_size = stream.u16()                      # 同上
tries_size = stream.u16()                     # 用了
debug_off = stream.u32()                      # 未用，u32() 必须执行
self.insns_size = stream.u32()                # 依赖上面 5 次读取已把指针推到位
```

删掉任何一行，`insns_size` 就从错误偏移读出，后续 `insns` 列表与 `tries` 解析整体错位。

| 位置 | 变量 | 不可删的原因 |
| --- | --- | --- |
| `MethodId.__init__` | `shorty_idx` | `stream2.u32()` 三连读的第一个；`return_idx`、`parameters_off` 都被使用 |
| `CodeItem.__init__` | `registers_size` | 链式赋值 `self.nregs = registers_size = ...`，值已存入 `self` |
| `CodeItem.__init__` | `ins_size` | 读取动作是必需的 |
| `CodeItem.__init__` | `outs_size` | 读取动作是必需的 |
| `CodeItem.__init__` | `debug_off` | 读取动作是必需的 |

**不要为了消音而改名。** 把它们改成 `_ins_size` 之类的确能让规则不再报，但那会让「这行读取必须发生」这个事实彻底消失——下一个看到未使用变量的人（和下一个 agent）反而更有理由删掉它。消音是把最危险的信号关掉。

## ZipFile 持有句柄直到对象终结

`src/apkutils/_apkfile.py` 的 `ZipFile.__init__` 里裸 `io.open(file, "rb")` 触发 SIM115（`open` without context manager）。

这是**误报**。`ZipFile` 把句柄作为对象生命周期的一部分持有，配有 `_fileRefCnt` / `_fpclose` / `__exit__`；改成 `with` 会在退出块时关闭仍然需要的句柄。

## 测试故意不检查子进程退出码

`tests/test_readme_cli.py` 的 `_run_dash_m` 里 `subprocess.run(...)` 触发 PLW1510（`subprocess.run` without `check`）。

这是**误报**，且改动会撞上 ADR-0010 的下限契约。该测试调用裸 `python -m apkutils`（无参数）并只断言 `Usage:` 出现在输出中，不锁定退出码——docstring 写明 click 8.0.3 是 exit 0 + stdout、8.3.x 是 exit 2 + stderr，两者都算「没静默」，而 `lowest-direct` job 把 click 钉在声明下限。加上 `check=True` 会让该测试在下限版本上直接失败。

## 盲 except 是设计意图，不是疏忽

ruff 默认规则集含 BLE001（blind except），在本仓库报 9 处：`apk.py`（5）、`_ziphealth.py`（2）、`_subfiles.py`、`_dex.py`。

它们全部是 **PartError 收集点**——捕获 `Exception`、包装成 `PartError`、记入 `APK.errors` 并继续。这正是 `docs/adr/0002-errors-collected-by-default-strict-opts-out.md` 记录的设计。不要改成窄异常，也不要加 `per-file-ignores` 悄悄压掉。

## 噪音基线

246 条里 **225 条不值得改**，逐类原因如下。认出这些类别，可以在跑完 ruff 后直接跳过：

| 规则 | 条数 | 原因 |
| --- | --- | --- |
| UP031 + UP032 | 168 | `%`-formatting → f-string 现代化，零缺陷信号；148/246 集中于 `axml/__init__.py` |
| UP004 / UP020 / UP012 | 7 | 风格现代化（`object` 基类、`io.open`→`open`、多余 encode） |
| RUF100 | 15 | ruff 默认集自相矛盾：RUF100 启用而 E501 未启用，于是 `# noqa: E501` 被判为死指令。`src` 里确有 92 行 >100 字符，这些 noqa 仍在标注「这行超长是有意的」 |
| RUF059 | 9 | 变量名是布局文档（ZIP64 尾记录的 `reloff` / `sz` / `create_version` / `read_version`，AXML chunk 头的 `attributeStart` / `dataType`）。改 `_` 行为不变，文档消失 |
| SIM117 / SIM102 / SIM201 | 11 | 嵌套写法，可读性偏好 |
| PIE808 / PIE790 | 6 | `range(0, n)` 的冗余 `start`、冗余 `pass` |
| RUF015 / RUF022 / RUF023 / RUF007 | 6 | 切片取首元素、`__all__` 排序、`zip` 换 `pairwise` |
| C408 / C417 | 2 | `dict()` 改字面量、`map()` 改生成器 |

另有一条**排除规则集本身**的理由：ruff 的默认规则集随版本漂移，0.17.0 是 407 条。「跑一下 ruff」不是一个可复现的基线——真要比较，必须显式钉住规则集。

## 顺带说明

本次审计（ruff 0.17.0，246 条）已全部分类，只改了两条真正的死代码：`examples/manifest.py` 的未使用 `import json`，以及 `axml/__init__.py` 里被删掉的 sanity check 残留 `is_string_pool = True`。另有 4 条触及 public surface（`TRY002` ×2、`TRY004`、`PLR1704`），改动成本不在代码里而在兼容承诺里，需要独立评审——已记录在 issue tracker，未在本页展开。

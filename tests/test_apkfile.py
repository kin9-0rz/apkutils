"""apkfile（vendored zipfile fork）容忍规则的 characterization tests。

把散落在「注释掉的 stdlib diff」里的容忍规则钉成显式契约：每条规则对应
一个用 patch 过的内存 zip 验证现状行为的 test。裁剪 `_apkfile.py` 时这些
测试必须保持绿。

规则清单（对应 `_apkfile` 模块 docstring）：
1. 假设归档无前置拼接数据（concat=0；前提，无独立正向测试）
2. 忽略解压版本检查
3. 读时不校验 CRC
4. local header 与 central directory 文件名不一致不报错
5. 忽略加密 / patched-data flag
6. 解压时跳过超长路径
7. testzip 跳过超长文件名
"""

import io
import struct
import zipfile

import pytest

from apkutils import _apkfile

SIG_LOCAL = b"PK\x03\x04"
SIG_CENTRAL = b"PK\x01\x02"


def make_zip(entries):
    """用 stdlib 生成内存 zip（STORE，无压缩）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return buf.getvalue()


def central_header(blob):
    """返回第一个 central directory entry 的 (offset, 字段 dict)。

    structCentralDir 布局：sig(4) ver_made(2) ver_need(2) flags(2) comp(2)
    mtime(2) mdate(2) crc(4) csize(4) usize(4) fnlen(2) extlen(2) comlen(2)
    disk(2) iattr(2) eattr(4) lho(4)。
    """
    pos = blob.index(SIG_CENTRAL)
    fmt = "<4s6H3I5H2I"
    keys = [
        "sig",
        "ver_made",
        "ver_need",
        "flags",
        "comp",
        "mtime",
        "mdate",
        "crc",
        "csize",
        "usize",
        "fnlen",
        "extlen",
        "comlen",
        "disk",
        "iattr",
        "eattr",
        "lho",
    ]
    fields = struct.unpack(fmt, blob[pos : pos + struct.calcsize(fmt)])
    return pos, dict(zip(keys, fields))


def local_header(blob):
    """返回第一个 local header 的 (offset, 字段 dict)。

    structFileHeader 布局：sig(4) ver_need(2) flags(2) comp(2) mtime(2)
    mdate(2) crc(4) csize(4) usize(4) fnlen(2) extlen(2)，文件名从 offset 30 起。
    """
    pos = blob.index(SIG_LOCAL)
    fmt = "<4s5H3I2H"
    keys = [
        "sig",
        "ver_need",
        "flags",
        "comp",
        "mtime",
        "mdate",
        "crc",
        "csize",
        "usize",
        "fnlen",
        "extlen",
    ]
    fields = struct.unpack(fmt, blob[pos : pos + struct.calcsize(fmt)])
    return pos, dict(zip(keys, fields))


def open_blob(blob):
    return _apkfile.ZipFile(io.BytesIO(blob), "r")


def test_read_namelist_getinfo():
    blob = make_zip([("a.txt", b"hello"), ("b/c.txt", b"world")])
    zf = open_blob(blob)
    assert zf.namelist() == ["a.txt", "b/c.txt"]
    assert zf.read("a.txt") == b"hello"
    info = zf.getinfo("b/c.txt")
    assert (info.file_size, info.compress_size) == (5, 5)


def test_ignores_extract_version():
    """规则 2：extract_version 抬高到 99 仍能读。"""
    blob = bytearray(make_zip([("a.txt", b"hello")]))
    pos, hdr = central_header(blob)
    assert hdr["ver_need"] < 63  # 正常值远小于 MAX_EXTRACT_VERSION
    blob[pos + 6 : pos + 8] = struct.pack("<H", 99)
    zf = open_blob(bytes(blob))
    assert zf.read("a.txt") == b"hello"


def test_read_does_not_verify_crc():
    """规则 3：central directory 的 CRC 抹掉后 read 仍返回数据。"""
    blob = bytearray(make_zip([("a.txt", b"hello")]))
    pos, hdr = central_header(blob)
    assert hdr["crc"] != 0
    blob[pos + 16 : pos + 20] = b"\x00\x00\x00\x00"
    zf = open_blob(bytes(blob))
    assert zf.read("a.txt") == b"hello"


def test_ignores_name_mismatch():
    """规则 4：local header 文件名与 central directory 不一致仍能读。"""
    blob = bytearray(make_zip([("a.txt", b"hello")]))
    pos, hdr = local_header(blob)
    assert hdr["fnlen"] == 5
    name_start = pos + 30
    assert blob[name_start : name_start + 5] == b"a.txt"
    blob[name_start : name_start + 5] = b"b.txt"
    zf = open_blob(bytes(blob))
    assert zf.read("a.txt") == b"hello"


@pytest.mark.parametrize("flag", [0x20, 0x40])
def test_ignores_encryption_flags(flag):
    """规则 5：patched-data(0x20) / strong-encryption(0x40) flag 被忽略。"""
    blob = bytearray(make_zip([("a.txt", b"hello")]))
    pos, hdr = central_header(blob)
    blob[pos + 8 : pos + 10] = struct.pack("<H", hdr["flags"] | flag)
    zf = open_blob(bytes(blob))
    assert zf.read("a.txt") == b"hello"


def test_extract_skips_overlong_path(tmp_path):
    """规则 6：路径分隔符超过 255 个的条目在解压时被跳过。"""
    deep = "a/" * 256 + "f.txt"
    blob = make_zip([("normal.txt", b"n"), (deep, b"d")])
    zf = open_blob(blob)
    zf.extractall(str(tmp_path))
    assert (tmp_path / "normal.txt").read_bytes() == b"n"
    assert not (tmp_path / "a").exists()


def test_testzip_skips_overlong_name():
    """规则 7：单段文件名超过 255 字符的条目在 testzip 时被跳过。"""
    long_name = "x" * 300 + ".txt"
    blob = make_zip([(long_name, b"data"), ("ok.txt", b"ok")])
    zf = open_blob(blob)
    assert zf.testzip() is None


def test_zip_with_trailing_garbage():
    """尾部追加垃圾字节后仍能解析（EOCD 向后扫描；规则 1 的前提是「无前置数据」）。"""
    blob = make_zip([("a.txt", b"hello")])
    zf = open_blob(blob + b"\x00" * 64)
    assert zf.namelist() == ["a.txt"]
    assert zf.read("a.txt") == b"hello"

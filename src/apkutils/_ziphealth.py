"""ZIP 结构层对抗：字节级解析、体检与修复。

回答一个问题：**标准 ZIP 工具能不能信任这个文件？**

``_apkfile`` 对下列手法一律容忍（见其模块 docstring 的容忍规则），因此对 APK
照常可读——本模块反过来，专做「标准工具会不会拒绝」的判定：

    1. 伪造加密标志       通用位标志 bit0=1（数据实为明文）
    2. patched data       bit5=1，标准库抛 NotImplementedError
    3. strong encryption  bit6=1，标准库抛 NotImplementedError
    4. CRC 清零/篡改      标准库校验失败抛 BadZipFile
    5. 抬高所需版本号     标准库按 extract_version 拒绝
    6. CD 与 LFH 名字不一致
    7. 无 EOCD / CD 损坏

bit3（数据描述符）是合法流式写入，只统计数量、不判对抗。

体检结论（``check``）：``ok`` / ``has_flags`` / ``cd_damaged`` / ``not_a_zip``。
修复（``repair``）：清 CDFH/LFH 的对抗标志位、把异常版本号归一化，产出干净副本，
并以**标准库** zipfile 验证；不涉及密码学破解。

归属：检测与修复规则移植自 android-reverse-maid unpacking 技能的 zip_health.py，
宽容读取器移植自同技能的 zip_decrypt.py（后者本就是在 ``_apkfile`` 的宽容化改造
基础上写的）。本模块是迁入后的唯一编辑点。
"""

import hashlib
import logging
import os
import struct
import zipfile
import zlib
from collections import namedtuple

log = logging.getLogger("apkutils")

# ---------------------------------------------------------------------------
# 常量：ZIP 结构
# ---------------------------------------------------------------------------
EOCD_SIGNATURE = b"PK\x05\x06"                # End of Central Directory
ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"          # Zip64 EOCD
ZIP64_EOCD_LOCATOR_SIGNATURE = b"PK\x06\x07"  # Zip64 EOCD Locator
CDFH_SIGNATURE = b"PK\x01\x02"                # Central Directory File Header
LFH_SIGNATURE = b"PK\x03\x04"                 # Local File Header
DATA_DESCRIPTOR_SIGNATURE = b"PK\x07\x08"     # Data Descriptor

EOCD_MIN_SIZE = 22                            # EOCD 固定部分长度
MAX_COMMENT_SIZE = 0xFFFF                     # ZIP 注释最长 64KiB
CDFH_MIN_SIZE = 46                            # CDFH 固定部分长度
LFH_MIN_SIZE = 30                             # LFH 固定部分长度
ZIP64_EXTRA_ID = 0x0001                       # Zip64 扩展字段 ID

# 对抗性通用位标志：bit0 加密 / bit5 patched data / bit6 strong encryption
ANTI_ANALYSIS_FLAG_MASK = 0x0001 | 0x0020 | 0x0040
# bit3 = 数据描述符（合法流式写入，不计对抗）
DATA_DESCRIPTOR_FLAG_BIT = 0x0008

# 常规 zip 条目合理版本上限（45 = zip64 之前的最高值）；超过且非法才视为异常
SANE_VERSION_LIMIT = 45
# 超过上限却合法的所需版本：46 = bzip2（stdlib BZIP2_VERSION）、63 = lzma（LZMA_VERSION）
LEGITIMATE_HIGH_VERSIONS = frozenset({46, 63})
# 版本号归一化后的落点
DEFAULT_VERSION = 20

# 压缩方式
ZIP_STORED = 0
ZIP_DEFLATED = 8

# struct 格式（与 stdlib zipfile 保持一致）
_STRUCT_CDFH = "<4s4B4HL2L5H2L"  # 中央目录文件头，19 字段
_STRUCT_LFH = "<4s2B4HL2L2H"     # 本地文件头，12 字段
_STRUCT_EOCD = "<4s4H2LH"        # EOCD，8 字段

# CDFH 字段索引
_CD_FLAG_BITS = 5
_CD_COMPRESS_TYPE = 6
_CD_CRC = 9
_CD_COMPRESSED_SIZE = 10
_CD_UNCOMPRESSED_SIZE = 11
_CD_FILENAME_LENGTH = 12
_CD_EXTRA_FIELD_LENGTH = 13
_CD_COMMENT_LENGTH = 14
_CD_LOCAL_HEADER_OFFSET = 18

# LFH 字段索引
_FH_COMPRESSION_METHOD = 4
_FH_COMPRESSED_SIZE = 8
_FH_UNCOMPRESSED_SIZE = 9
_FH_FILENAME_LENGTH = 10
_FH_EXTRA_FIELD_LENGTH = 11


class BadZipError(Exception):
    """宽容读取过程中的致命错误。"""


CentralEntry = namedtuple(
    "CentralEntry",
    [
        "filename",         # str（已按 flag 解码）
        "filename_raw",     # bytes（原始编码，用于精确匹配）
        "flag_bits",        # int
        "compress_type",    # int
        "crc",              # int
        "compress_size",    # int
        "file_size",        # int
        "header_offset",    # int（LFH 绝对偏移）
        "extract_version",  # int（version needed to extract）
        "extra",            # bytes
    ],
)


# ---------------------------------------------------------------------------
# 基础 I/O
# ---------------------------------------------------------------------------
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_file_fully(file_path):
    """读取整个文件为字节串。"""
    with open(file_path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# EOCD / 中央目录定位
# ---------------------------------------------------------------------------
def find_eocd(data):
    """从文件末尾向前搜索 EOCD，返回起始偏移；找不到返回 -1。

    先试「注释长度与文件尾严格吻合」的精确匹配；失败再退化为「注释长度落在
    文件范围内」的宽松匹配（应对 EOCD 后有额外数据）。
    """
    search_start = max(0, len(data) - (EOCD_MIN_SIZE + MAX_COMMENT_SIZE))
    relaxed = -1

    for i in range(len(data) - EOCD_MIN_SIZE, search_start - 1, -1):
        if data[i:i + 4] != EOCD_SIGNATURE:
            continue
        comment_len = struct.unpack_from("<H", data, i + 20)[0]
        if i + EOCD_MIN_SIZE + comment_len == len(data):
            return i
        if relaxed == -1 and i + EOCD_MIN_SIZE + comment_len <= len(data):
            relaxed = i

    return relaxed


def locate_central_directory(data, eocd_offset):
    """读取 EOCD，返回 (条目总数, 中央目录起始偏移)；自动处理 Zip64。"""
    endrec = struct.unpack_from(_STRUCT_EOCD, data, eocd_offset)
    total = endrec[4]      # _ECD_ENTRIES_TOTAL
    cd_offset = endrec[6]  # _ECD_OFFSET

    if total != 0xFFFF and cd_offset != 0xFFFFFFFF:
        return total, cd_offset

    locator = eocd_offset - 20
    if locator >= 0 and data[locator:locator + 4] == ZIP64_EOCD_LOCATOR_SIGNATURE:
        z64_offset = struct.unpack_from("<Q", data, locator + 8)[0]
        if (0 <= z64_offset <= len(data) - 56
                and data[z64_offset:z64_offset + 4] == ZIP64_EOCD_SIGNATURE):
            total = struct.unpack_from("<Q", data, z64_offset + 32)[0]
            cd_offset = struct.unpack_from("<Q", data, z64_offset + 48)[0]

    return total, cd_offset


def _decode_filename(raw, flag_bits):
    """按通用位标志 bit11 判断文件名编码，尽量宽容地解码。"""
    if flag_bits & 0x800:
        return raw.decode("utf-8", errors="replace")
    try:
        return raw.decode("cp437")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _apply_zip64(entry_fields, extra):
    """解析 Zip64 扩展字段（tag 0x0001），还原被写成 0xFFFFFFFF 的字段。"""
    pos = 0
    while pos + 4 <= len(extra):
        tag, size = struct.unpack_from("<HH", extra, pos)
        body = extra[pos + 4:pos + 4 + size]
        if tag == ZIP64_EXTRA_ID:
            p = 0
            if entry_fields["file_size"] == 0xFFFFFFFF and p + 8 <= len(body):
                entry_fields["file_size"] = struct.unpack_from("<Q", body, p)[0]
                p += 8
            if entry_fields["compress_size"] == 0xFFFFFFFF and p + 8 <= len(body):
                entry_fields["compress_size"] = struct.unpack_from("<Q", body, p)[0]
                p += 8
            if entry_fields["header_offset"] == 0xFFFFFFFF and p + 8 <= len(body):
                entry_fields["header_offset"] = struct.unpack_from("<Q", body, p)[0]
                p += 8
            break
        pos += 4 + size
    return entry_fields


def parse_central_directory(data):
    """解析中央目录，返回 CentralEntry 列表；依据 EOCD 精确定位，不暴力扫描。"""
    eocd_offset = find_eocd(data)
    if eocd_offset == -1:
        return []

    total, pos = locate_central_directory(data, eocd_offset)
    entries = []

    for _ in range(total):
        if pos + CDFH_MIN_SIZE > len(data):
            break
        if data[pos:pos + 4] != CDFH_SIGNATURE:
            break

        fields = struct.unpack_from(_STRUCT_CDFH, data, pos)
        name_len = fields[_CD_FILENAME_LENGTH]
        extra_len = fields[_CD_EXTRA_FIELD_LENGTH]
        comment_len = fields[_CD_COMMENT_LENGTH]

        name_raw = data[pos + CDFH_MIN_SIZE:pos + CDFH_MIN_SIZE + name_len]
        extra = data[pos + CDFH_MIN_SIZE + name_len:
                     pos + CDFH_MIN_SIZE + name_len + extra_len]

        info = {
            "flag_bits": fields[_CD_FLAG_BITS],
            "compress_type": fields[_CD_COMPRESS_TYPE],
            "crc": fields[_CD_CRC],
            "compress_size": fields[_CD_COMPRESSED_SIZE],
            "file_size": fields[_CD_UNCOMPRESSED_SIZE],
            "header_offset": fields[_CD_LOCAL_HEADER_OFFSET],
        }
        info = _apply_zip64(info, extra)

        entries.append(CentralEntry(
            filename=_decode_filename(name_raw, info["flag_bits"]),
            filename_raw=name_raw,
            flag_bits=info["flag_bits"],
            compress_type=info["compress_type"],
            crc=info["crc"],
            compress_size=info["compress_size"],
            file_size=info["file_size"],
            header_offset=info["header_offset"],
            extract_version=struct.unpack_from("<H", data, pos + 6)[0],
            extra=extra,
        ))

        pos += CDFH_MIN_SIZE + name_len + extra_len + comment_len

    return entries


def iter_cdfh_offsets(data):
    """返回中央目录中各 CDFH 的起始偏移列表。"""
    eocd_offset = find_eocd(data)
    if eocd_offset == -1:
        return []
    total, pos = locate_central_directory(data, eocd_offset)
    offsets = []
    for _ in range(total):
        if pos + CDFH_MIN_SIZE > len(data) or data[pos:pos + 4] != CDFH_SIGNATURE:
            break
        offsets.append(pos)
        name_len = struct.unpack_from("<H", data, pos + 28)[0]
        extra_len = struct.unpack_from("<H", data, pos + 30)[0]
        comment_len = struct.unpack_from("<H", data, pos + 32)[0]
        pos += CDFH_MIN_SIZE + name_len + extra_len + comment_len
    return offsets


# ---------------------------------------------------------------------------
# 宽容读取器（绕开标准库的严格校验）
# ---------------------------------------------------------------------------
def _inflate(blob):
    """解压 deflate 数据流：先按 ZIP 规范用 raw deflate，失败再试 zlib/gzip 包装。"""
    errors = []
    for wbits in (-15, 15, 31):
        try:
            decomp = zlib.decompressobj(wbits)
            out = decomp.decompress(blob) + decomp.flush()
        except zlib.error as e:
            errors.append(str(e))
            continue
        if out:
            return out
    raise BadZipError("deflate 解压失败: %s" % "; ".join(errors))


def _parse_local_header(data, lfh_offset):
    """解析本地文件头，返回 (字段元组, 数据区起始偏移, 文件名 bytes)。"""
    if lfh_offset < 0 or lfh_offset + LFH_MIN_SIZE > len(data):
        raise BadZipError("本地文件头偏移越界: %d" % lfh_offset)
    if data[lfh_offset:lfh_offset + 4] != LFH_SIGNATURE:
        raise BadZipError("本地文件头签名无效 @ %d" % lfh_offset)

    fields = struct.unpack_from(_STRUCT_LFH, data, lfh_offset)
    name_len = fields[_FH_FILENAME_LENGTH]
    extra_len = fields[_FH_EXTRA_FIELD_LENGTH]

    name = data[lfh_offset + LFH_MIN_SIZE:
                lfh_offset + LFH_MIN_SIZE + name_len]
    data_start = lfh_offset + LFH_MIN_SIZE + name_len + extra_len
    return fields, data_start, name


def _decompress_entry(data, data_start, compress_type, compress_size, file_size, limit):
    """按压缩方式还原条目数据；忽略 CRC 校验。"""
    if data_start > len(data):
        raise BadZipError("数据区起始偏移越界")

    if compress_type == ZIP_STORED:
        size = file_size if file_size not in (0, 0xFFFFFFFF) else compress_size
        if size in (0, 0xFFFFFFFF):
            end = len(data) if limit <= 0 else min(limit, len(data))
            return bytes(data[data_start:end])
        return bytes(data[data_start:data_start + size])

    if compress_type == ZIP_DEFLATED:
        # deflate 流自带结束标记，无需按「下一个 LFH」截断（压缩数据中可能恰好出现该签名）
        return _inflate(data[data_start:])

    raise BadZipError("暂不支持的压缩方式: %d" % compress_type)


def _find_data_limit(data, lfh_offset):
    """估算当前条目数据区的结束位置（下一条目 LFH 或中央目录起点）。"""
    cd_offset = -1
    eocd = find_eocd(data)
    if eocd != -1:
        _, cd_offset = locate_central_directory(data, eocd)

    next_lfh = data.find(LFH_SIGNATURE, lfh_offset + LFH_MIN_SIZE)
    if next_lfh == -1:
        next_lfh = len(data)

    candidates = [next_lfh]
    if cd_offset > 0:
        candidates.append(cd_offset)
    return min(candidates)


def extract_entry_from_data(data, entry):
    """依据中央目录条目，宽松地取出该条目数据（不校验 CRC/标志/版本/文件名）。"""
    fields, data_start, _lfh_name = _parse_local_header(data, entry.header_offset)

    compress_type = entry.compress_type
    if compress_type not in (ZIP_STORED, ZIP_DEFLATED):
        compress_type = fields[_FH_COMPRESSION_METHOD]

    limit = _find_data_limit(data, entry.header_offset)

    return _decompress_entry(
        data, data_start, compress_type,
        entry.compress_size, entry.file_size, limit,
    )


def find_local_entries(data):
    """直接扫描本地文件头（不依赖中央目录），返回 (name_bytes, lfh_offset)。

    作为 EOCD / 中央目录损坏时的兜底方案。
    """
    start = 0
    while True:
        off = data.find(LFH_SIGNATURE, start)
        if off == -1:
            return
        start = off + 4
        if off + LFH_MIN_SIZE > len(data):
            continue
        name_len = struct.unpack_from("<H", data, off + 26)[0]
        if off + LFH_MIN_SIZE + name_len > len(data):
            continue
        name = data[off + LFH_MIN_SIZE:off + LFH_MIN_SIZE + name_len]
        yield name, off


def _read_by_local_header(data, lfh_offset):
    """仅凭本地文件头读取条目（中央目录不可用时使用）。"""
    fields, data_start, _name = _parse_local_header(data, lfh_offset)
    compress_type = fields[_FH_COMPRESSION_METHOD]
    compress_size = fields[_FH_COMPRESSED_SIZE]
    file_size = fields[_FH_UNCOMPRESSED_SIZE]
    limit = _find_data_limit(data, lfh_offset)
    return _decompress_entry(
        data, data_start, compress_type, compress_size, file_size, limit
    )


def list_entries(file_path):
    """列出 APK/ZIP 中的条目名（优先中央目录，失败则扫描本地头）。"""
    data = read_file_fully(file_path)
    entries = parse_central_directory(data)
    if entries:
        return [e.filename for e in entries]
    return [name.decode("utf-8", errors="replace")
            for name, _ in find_local_entries(data)]


def extract_entry(file_path, name="classes.dex"):
    """从 APK/ZIP 中提取指定条目（默认 classes.dex），全程宽松处理。"""
    data = read_file_fully(file_path)
    target = name.encode("utf-8")

    for entry in parse_central_directory(data):
        if entry.filename_raw == target or entry.filename == name:
            return extract_entry_from_data(data, entry)

    for lfh_name, lfh_offset in find_local_entries(data):
        if lfh_name == target:
            return _read_by_local_header(data, lfh_offset)

    raise BadZipError("未找到条目: %s" % name)


def get_dex_data(file_path):
    """提取 classes.dex 的字节内容；失败返回空字节串（方便调用方判断）。"""
    try:
        return extract_entry(file_path, "classes.dex")
    except (BadZipError, OSError) as e:
        log.error("get_dex_data 失败: %s", e)
        return b""


# ---------------------------------------------------------------------------
# 标志位清除与版本归一化
# ---------------------------------------------------------------------------
def clear_encryption_bit(data, offset, field_offset, mask=ANTI_ANALYSIS_FLAG_MASK):
    """清除指定记录中通用位标志里的对抗位（默认 bit0/5/6），返回是否改动。"""
    if offset + field_offset + 2 > len(data):
        return False

    flag = struct.unpack_from("<H", data, offset + field_offset)[0]
    if not (flag & mask):
        return False

    struct.pack_into("<H", data, offset + field_offset, flag & ~mask)
    return True


def _version_is_odd(ver):
    """Required version 是否异常：超过上限且不属于合法高位值（bzip2/lzma）。"""
    return ver > SANE_VERSION_LIMIT and ver not in LEGITIMATE_HIGH_VERSIONS


def _repair_bytes(path):
    """字节级修复：清对抗标志位 + 归一化异常版本号，返回 (data, n_flags, n_versions)。

    原文件不动；CD 不可用（cd_damaged）时两处修复都无从定位，返回原样字节。
    """
    data = bytearray(read_file_fully(path))
    n_flags = 0
    for pos in iter_cdfh_offsets(data):
        if clear_encryption_bit(data, pos, 8):
            n_flags += 1
        lfh = struct.unpack_from("<I", data, pos + 42)[0]
        if (lfh + LFH_MIN_SIZE <= len(data)
                and data[lfh:lfh + 4] == LFH_SIGNATURE):
            if clear_encryption_bit(data, lfh, 6):
                n_flags += 1

    n_versions = 0
    for pos in iter_cdfh_offsets(data):
        if pos + CDFH_MIN_SIZE > len(data):
            break
        if _version_is_odd(struct.unpack_from("<H", data, pos + 6)[0]):
            struct.pack_into("<H", data, pos + 6, DEFAULT_VERSION)
            n_versions += 1
        lfh = struct.unpack_from("<I", data, pos + 42)[0]
        if (lfh + LFH_MIN_SIZE <= len(data)
                and data[lfh:lfh + 4] == LFH_SIGNATURE):
            if _version_is_odd(struct.unpack_from("<H", data, lfh + 4)[0]):
                struct.pack_into("<H", data, lfh + 4, DEFAULT_VERSION)
                n_versions += 1
    return data, n_flags, n_versions


# ---------------------------------------------------------------------------
# 体检
# ---------------------------------------------------------------------------
def check(path):
    """体检单个文件，返回报告 dict（含 verdict / findings / info / sha256 / size）。"""
    report = {"path": path, "verdict": "ok", "findings": []}

    if not os.path.exists(path):
        report["verdict"] = "error"
        report["findings"].append({"type": "io_error", "detail": "file not found"})
        return report
    report["sha256"] = sha256_of(path)
    report["size"] = os.path.getsize(path)

    data = read_file_fully(path)
    if len(data) < 4 or data[:4] not in (
        LFH_SIGNATURE, EOCD_SIGNATURE, ZIP64_EOCD_SIGNATURE,
        DATA_DESCRIPTOR_SIGNATURE, CDFH_SIGNATURE,
    ):
        report["verdict"] = "not_a_zip"
        report["findings"].append({
            "type": "not_a_zip",
            "detail": "文件头无 PK 签名（纯密文载荷或非 zip），头 8 字节: %s" % data[:8].hex(),
        })
        return report

    entries = parse_central_directory(data)
    if not entries:
        local = list(find_local_entries(data))
        if local:
            report["verdict"] = "cd_damaged"
            report["findings"].append({
                "type": "cd_damaged",
                "detail": "中央目录不可解析，LFH 扫描到 %d 个条目（标准工具按 CD 索引会失败）" % len(local),
            })
        else:
            report["verdict"] = "not_a_zip"
            report["findings"].append({
                "type": "not_a_zip",
                "detail": "有 PK 签名但 CD 与 LFH 均无有效条目",
            })
        return report

    flagged = []
    for e in entries:
        hits = []
        if e.flag_bits & ANTI_ANALYSIS_FLAG_MASK:
            bits = [n for n, b in (("bit0加密", 0x1), ("bit5_patched", 0x20), ("bit6强加密", 0x40))
                    if e.flag_bits & b]
            hits.append("对抗标志位 %s (flag=0x%04x)" % ("/".join(bits), e.flag_bits))
        if e.crc == 0 and e.file_size > 0:
            hits.append("CRC 清零但 file_size=%d（标准库解压校验会失败）" % e.file_size)
        if hits:
            flagged.append({"entry": e.filename, "issues": hits})

    name_mismatch, lfh_flagged, version_odd, dd_count = [], [], [], 0
    for e in entries:
        lfh = e.header_offset
        if lfh + LFH_MIN_SIZE > len(data) or data[lfh:lfh + 4] != LFH_SIGNATURE:
            name_mismatch.append(e.filename)
            continue
        lfh_flag = struct.unpack_from("<H", data, lfh + 6)[0]
        if lfh_flag & ANTI_ANALYSIS_FLAG_MASK:
            lfh_flagged.append(e.filename)
        name_len = struct.unpack_from("<H", data, lfh + 26)[0]
        lfh_name = data[lfh + LFH_MIN_SIZE:lfh + LFH_MIN_SIZE + name_len]
        if lfh_name != e.filename_raw:
            name_mismatch.append(e.filename)
        if lfh_flag & DATA_DESCRIPTOR_FLAG_BIT:
            dd_count += 1
        if _version_is_odd(e.extract_version):
            version_odd.append("%s (need_version=%d)" % (e.filename, e.extract_version))

    for f in flagged:
        report["findings"].append({"type": "has_flags", "entry": f["entry"], "detail": "; ".join(f["issues"])})
    for nm in lfh_flagged:
        report["findings"].append({"type": "has_flags", "entry": nm, "detail": "LFH 侧对抗标志位"})
    for nm in name_mismatch:
        report["findings"].append({"type": "has_flags", "entry": nm, "detail": "CD 与 LFH 文件名不一致"})
    for nm in version_odd:
        report["findings"].append({"type": "has_flags", "entry": nm.split(" ")[0], "detail": "所需版本号异常: " + nm})

    report["info"] = {"entries": len(entries), "data_descriptor_entries": dd_count}
    if report["findings"]:
        report["verdict"] = "has_flags"
    return report


# ---------------------------------------------------------------------------
# 修复
# ---------------------------------------------------------------------------
def repair(path, repair_dir):
    """修复：清对抗标志位 + 归一化版本号，产干净副本并以标准库 zipfile 验证。"""
    try:
        orig_sha = sha256_of(path)
        data, n_flags, n_versions = _repair_bytes(path)
    except Exception as ex:
        return {"applied": False, "status": "repair_failed", "detail": str(ex)}

    new_sha = hashlib.sha256(bytes(data)).hexdigest()
    if new_sha == orig_sha:
        return {"applied": False, "status": "no_change",
                "detail": "清位/版本归一化后字节不变（对抗可能在别处）"}

    os.makedirs(repair_dir, exist_ok=True)
    dest = os.path.join(repair_dir, orig_sha[:12] + ".apk")
    with open(dest, "wb") as out:
        out.write(bytes(data))

    result = {
        "applied": True,
        "status": "repaired",
        "repaired_sha256": new_sha,
        "clean_path": dest.replace("\\", "/"),
        "fixed": {"flag_bits": n_flags, "versions": n_versions},
    }
    # 验证判据：标准库 testzip 通过才算 verified（不用宽容的 _apkfile）
    try:
        with zipfile.ZipFile(dest) as z:
            bad = z.testzip()
            if bad is not None:
                result["status"] = "repair_failed"
                result["detail"] = "修复后 testzip 仍在 %s 处失败" % bad
            else:
                result["status"] = "repaired_verified"
                result["verified"] = "testzip"
    except Exception as ex:
        result["status"] = "repair_failed"
        result["detail"] = "修复副本标准库仍拒开: %s" % ex
    if result["status"] == "repair_failed":
        result["likely_real_encryption"] = True
    return result

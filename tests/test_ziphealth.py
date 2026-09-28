"""apkutils.ziphealth：ZIP 结构层体检、修复与宽容读取。"""

import json
import struct
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from apkutils import _ziphealth as zh
from apkutils.cli import main

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _patch(tmp_path, src, fn):
    """复制夹具、对字节做局部修改后写入临时目录，返回临时路径。"""
    data = bytearray((FIXTURES / src).read_bytes())
    fn(data)
    dest = tmp_path / ("synthetic-" + src)
    dest.write_bytes(bytes(data))
    return dest


def _first_cdfh_offset(data):
    eocd = data.rfind(b"PK\x05\x06")
    return struct.unpack_from("<I", data, eocd + 16)[0]


# ---------------------------------------------------------------------------
# 现成夹具
# ---------------------------------------------------------------------------

def test_fake_pwd_is_flagged():
    """test_zip_fake_pwd：bit0 假加密（flag 0x801）必须命中 has_flags。"""
    rep = zh.check(str(FIXTURES / "test_zip_fake_pwd"))
    assert rep["verdict"] == "has_flags"
    assert rep["info"]["entries"] > 0
    details = [f["detail"] for f in rep["findings"] if f["type"] == "has_flags"]
    assert any("bit0加密" in d for d in details)


def test_data_descriptor_entries_not_flagged():
    """test.zip / youtube.zip：flag 0x808（bit3 数据描述符）是合法流式写入，不误报。"""
    for name in ("test.zip", "youtube.zip"):
        rep = zh.check(str(FIXTURES / name))
        assert rep["verdict"] == "ok", (name, rep["findings"])
        assert rep["info"]["data_descriptor_entries"] > 0


def test_i15_ok():
    rep = zh.check(str(FIXTURES / "i15.zip"))
    assert rep["verdict"] == "ok", rep["findings"]


def test_missing_file_error():
    rep = zh.check(str(FIXTURES / "no_such_file"))
    assert rep["verdict"] == "error"


def test_not_a_zip(tmp_path):
    p = tmp_path / "not_a_zip"
    p.write_bytes(b"\x00" * 64)
    rep = zh.check(str(p))
    assert rep["verdict"] == "not_a_zip"


# ---------------------------------------------------------------------------
# 合成对抗样本
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bit", [0x0001, 0x0020, 0x0040])
def test_flag_bits_flagged(tmp_path, bit):
    def fn(data):
        struct.pack_into("<H", data, _first_cdfh_offset(data) + 8,
                         struct.unpack_from("<H", data, _first_cdfh_offset(data) + 8)[0] | bit)
    tmp = _patch(tmp_path, "test.zip", fn)
    rep = zh.check(str(tmp))
    assert rep["verdict"] == "has_flags", rep["findings"]
    assert any("对抗标志位" in f["detail"] for f in rep["findings"])


def test_crc_zero_flagged(tmp_path):
    def fn(data):
        cd_off = _first_cdfh_offset(data)
        data[cd_off + 16:cd_off + 20] = b"\x00" * 4
    tmp = _patch(tmp_path, "test.zip", fn)
    rep = zh.check(str(tmp))
    assert rep["verdict"] == "has_flags"
    assert any("CRC" in f["detail"] for f in rep["findings"])


def test_version_raised_flagged_and_repaired(tmp_path):
    """版本号抬高（非 46/63）命中；repair 归一化为 20 且 stdlib 可读。"""
    def fn(data):
        struct.pack_into("<H", data, _first_cdfh_offset(data) + 6, 99)
    tmp = _patch(tmp_path, "test.zip", fn)
    rep = zh.check(str(tmp))
    assert rep["verdict"] == "has_flags"
    assert any("版本号" in f["detail"] for f in rep["findings"])

    r = zh.repair(str(tmp), str(tmp_path))
    assert r["applied"] is True
    assert r["status"] == "repaired_verified", r
    assert r["fixed"]["versions"] >= 1
    with zipfile.ZipFile(r["clean_path"]) as z:
        assert z.testzip() is None
    assert zh.check(r["clean_path"])["verdict"] == "ok"


@pytest.mark.parametrize("ver", [46, 63])
def test_legit_high_version_not_flagged_nor_repaired(tmp_path, ver):
    """46（bzip2）/63（lzma）是合法所需版本：不误报，也不被 repair 改动。"""
    def fn(data):
        struct.pack_into("<H", data, _first_cdfh_offset(data) + 6, ver)
    tmp = _patch(tmp_path, "test.zip", fn)
    rep = zh.check(str(tmp))
    assert rep["verdict"] == "ok", (ver, rep["findings"])
    r = zh.repair(str(tmp), str(tmp_path))
    assert r["applied"] is False
    assert r["status"] == "no_change"


def test_name_mismatch_flagged(tmp_path):
    """CD 与 LFH 文件名不一致必须命中。"""
    def fn(data):
        cd_off = _first_cdfh_offset(data)
        struct.pack_into("<H", data, cd_off + 28,
                         struct.unpack_from("<H", data, cd_off + 28)[0] - 1)
    tmp = _patch(tmp_path, "test.zip", fn)
    rep = zh.check(str(tmp))
    assert rep["verdict"] == "has_flags"
    assert any("不一致" in f["detail"] for f in rep["findings"])


def test_cd_damaged_detected(tmp_path):
    """EOCD 指向的中央目录不可用、但 LFH 可扫描 → cd_damaged。"""
    def fn(data):
        eocd = data.rfind(b"PK\x05\x06")
        struct.pack_into("<I", data, eocd + 16, 1)  # 偏移 1 处不是 CDFH
    tmp = _patch(tmp_path, "test.zip", fn)
    rep = zh.check(str(tmp))
    assert rep["verdict"] == "cd_damaged", rep["findings"]


def test_repair_flags_repaired_verified(tmp_path):
    """伪加密样本（数据为明文）清位后应能通过标准库验证。"""
    def fn(data):
        cd_off = _first_cdfh_offset(data)
        struct.pack_into("<H", data, cd_off + 8,
                         struct.unpack_from("<H", data, cd_off + 8)[0] | 0x0040)
    tmp = _patch(tmp_path, "test.zip", fn)
    r = zh.repair(str(tmp), str(tmp_path))
    assert r["status"] == "repaired_verified", r
    assert r["fixed"]["flag_bits"] >= 1
    assert zh.check(r["clean_path"])["verdict"] == "ok"


def test_repair_no_change_when_clean():
    path = FIXTURES / "test.zip"
    r = zh.repair(str(path), str(FIXTURES))
    assert r["applied"] is False
    assert r["status"] == "no_change"


# ---------------------------------------------------------------------------
# 宽容读取
# ---------------------------------------------------------------------------

def test_tolerant_list_and_extract_on_fake_pwd():
    path = str(FIXTURES / "test_zip_fake_pwd")
    names = zh.list_entries(path)
    assert "AndroidManifest.xml" in names
    assert len(zh.extract_entry(path, "AndroidManifest.xml")) > 0


def test_get_dex_data_missing_returns_empty(tmp_path):
    """不含 classes.dex 时 get_dex_data 返回 b''（兼容 jiagu_unpacker）。"""
    p = tmp_path / "no-dex.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("AndroidManifest.xml", b"x")
    assert zh.get_dex_data(str(p)) == b""


def test_get_dex_data_reads_classes_dex():
    blob = zh.get_dex_data(str(FIXTURES / "test.zip"))
    assert blob[:4] == b"dex\n"


def test_parse_central_directory_has_extract_version():
    entries = zh.parse_central_directory((FIXTURES / "test.zip").read_bytes())
    assert entries
    e = entries[0]
    assert isinstance(e.extract_version, int)
    assert e.filename and e.file_size > 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_health_json_ok():
    r = CliRunner().invoke(main, ["zip", "health", str(FIXTURES / "test.zip"), "--json"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["verdict"] == "ok"


def test_cli_health_flagged_exit_2():
    r = CliRunner().invoke(main, ["zip", "health", str(FIXTURES / "test_zip_fake_pwd"), "--json"])
    assert r.exit_code == 2
    assert json.loads(r.output)["verdict"] == "has_flags"


def test_cli_health_human_output():
    r = CliRunner().invoke(main, ["zip", "health", str(FIXTURES / "test_zip_fake_pwd")])
    assert r.exit_code == 2
    assert "HAS_FLAGS" in r.output
    assert "sha256" in r.output


def test_cli_repair_writes_clean_copy(tmp_path):
    r = CliRunner().invoke(main, [
        "zip", "repair", str(FIXTURES / "test_zip_fake_pwd"), "-o", str(tmp_path),
    ])
    assert r.exit_code == 0, r.output
    out_files = list(tmp_path.iterdir())
    assert len(out_files) == 1
    with zipfile.ZipFile(out_files[0]) as z:
        assert z.testzip() is None


def test_cli_zip_group_lists_subcommands():
    r = CliRunner().invoke(main, ["zip", "--help"])
    assert r.exit_code == 0
    for name in ("unzip", "health", "repair"):
        assert name in r.output


def test_top_level_unzip_removed():
    """unzip 已移入 zip 组，顶层不再提供（3.0 破坏性变更）。"""
    r = CliRunner().invoke(main, ["unzip", str(FIXTURES / "test.zip")])
    assert r.exit_code != 0

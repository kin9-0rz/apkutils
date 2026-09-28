"""ZIP 结构层对抗体检、修复与宽容读取（公开 API）。

回答一个问题：**标准 ZIP 工具能不能信任这个文件？**

- ``check(path)``：体检单文件，返回 ``{path, verdict, findings, info, sha256, size}``。
  ``verdict`` 取值 ``ok`` / ``has_flags`` / ``cd_damaged`` / ``not_a_zip`` / ``error``。
- ``repair(path, repair_dir)``：清对抗标志位（bit0/5/6）+ 归一化异常版本号，
  产出干净副本并以标准库 zipfile 验证；不破解密码学。
- 宽容读取：``read_file_fully`` / ``parse_central_directory`` / ``find_local_entries`` /
  ``list_entries`` / ``extract_entry`` / ``get_dex_data`` —— 对结构层对抗样本
  照常读出内容（与 ``_apkfile`` 同一哲学，独立实现）。

实现见私有模块 ``apkutils._ziphealth``；本模块只承诺上述入口。
"""

import json

from apkutils._ziphealth import (
    BadZipError,
    CentralEntry,
    check,
    extract_entry,
    find_local_entries,
    get_dex_data,
    list_entries,
    parse_central_directory,
    read_file_fully,
    repair,
)

__all__ = [
    "BadZipError",
    "CentralEntry",
    "check",
    "repair",
    "human",
    "read_file_fully",
    "parse_central_directory",
    "find_local_entries",
    "list_entries",
    "extract_entry",
    "get_dex_data",
]


def human(report):
    """把 check()/repair 的报告渲染成人类可读文本（CLI 默认输出格式）。"""
    lines = ["[%s] %s" % (report["verdict"].upper(), report["path"]),
             "  sha256: %s  size: %d" % (report["sha256"], report["size"])]
    info = report.get("info") or {}
    lines.append("  info: entries=%s, 数据描述符条目=%s" % (
        info.get("entries", "?"), info.get("data_descriptor_entries", "?")))
    if report["verdict"] == "ok":
        lines.append("  无 ZIP 结构层对抗迹象，标准工具可直接消费")
    for f in report["findings"]:
        entry = (" @ " + f["entry"]) if f.get("entry") else ""
        lines.append("  - %s%s: %s" % (f["type"], entry, f["detail"]))
    r = report.get("zip_repair")
    if r:
        lines.append("  repair: %s %s" % (r["status"], json.dumps(
            {k: v for k, v in r.items() if k != "status"}, ensure_ascii=False)))
    return "\n".join(lines)
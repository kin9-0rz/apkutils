"""APK 子文件清单。

`Subfiles` 的 interface 吃一个归档句柄，吐出 ``{name, type, time, crc}`` 列表。

逐个文件的 MIME 嗅探、时间字符串格式化、CRC 补零，
以及"某个文件读不出来就跳过"的容错，都藏在这里。
"""

import pyftype


class Subfiles:
    """列出归档里的每个子文件及其类型、时间、CRC。"""

    def __init__(self, archive):
        self.items = []
        self._read(archive)

    def _read(self, archive):
        for name in archive.namelist():
            try:
                data = archive.read(name)
                mime = pyftype.guess(data).MIME
                info = archive.getinfo(name)
            except Exception as ex:
                print(name, ex)
                continue

            self.items.append(
                {
                    "name": name,
                    "type": mime,
                    "time": "%d%02d%02d%02d%02d%02d" % info.date_time,
                    "crc": _crc_hex(info.CRC),
                }
            )


def _crc_hex(crc):
    text = str(hex(crc)).upper()[2:]
    return "0" * (8 - len(text)) + text

"""
from https://github.com/python/cpython/tree/3.6/Lib/zipfile.py

CPython 3.6 zipfile 的只读 fork，供 apkutils 读取 APK 归档。

与 stdlib 的差异是一组刻意的「容忍规则」，让 packed / 被加固过的 APK
（CRC 被抹、版本字段抬高、local header 与 central directory 文件名不一致、
加密 flag 声明但未真加密、超长路径）仍能读出。每条规则见代码内注释，
除规则 1 外，行为由 tests/test_apkfile.py 锁定：

1. 假设归档无前置拼接数据（concat 恒 0；对 APK 恒成立，无独立正向测试）。
2. 忽略解压版本检查。
3. 读时不校验 CRC。
4. local header 与 central directory 文件名不一致不报错。
5. 忽略加密（flag bit 6）与 patched-data（flag bit 5）flag。
6. 解压时跳过路径分隔符超过 255 个的条目。
7. testzip 跳过单段文件名超过 255 字符的条目。
"""

import binascii
import io
import logging
import os
import re
import shutil
import stat
import struct
import sys

try:
    import threading
except ImportError:
    import dummy_threading as threading

try:
    import zlib  # We may need its compression method

    crc32 = zlib.crc32
except ImportError:
    zlib = None
    crc32 = binascii.crc32

try:
    import bz2  # We may need its compression method
except ImportError:
    bz2 = None

try:
    import lzma  # We may need its compression method
except ImportError:
    lzma = None

__all__ = [
    "BadZipFile",
    "BadZipfile",
    "error",
    "ZIP_STORED",
    "ZIP_DEFLATED",
    "ZIP_BZIP2",
    "ZIP_LZMA",
    "is_zipfile",
    "ZipInfo",
    "ZipFile",
    "LargeZipFile",
]


log = logging.getLogger("apkutils")

# 容忍规则相关的显式阈值（对应模块 docstring 的规则编号）
_MAX_EXTRACT_PATH_SEPARATORS = 255  # 规则 6
_MAX_FILENAME_LENGTH = 255  # 规则 7


class BadZipFile(Exception):
    pass


class LargeZipFile(Exception):
    """
    Raised when writing a zipfile, the zipfile requires ZIP64 extensions
    and those extensions are disabled.
    """


error = BadZipfile = BadZipFile  # Pre-3.2 compatibility names


ZIP64_LIMIT = (1 << 31) - 1
ZIP_FILECOUNT_LIMIT = (1 << 16) - 1
ZIP_MAX_COMMENT = (1 << 16) - 1

# constants for Zip file compression methods
ZIP_STORED = 0
ZIP_DEFLATED = 8
ZIP_BZIP2 = 12
ZIP_LZMA = 14
# Other ZIP compression methods not supported

DEFAULT_VERSION = 20
ZIP64_VERSION = 45
BZIP2_VERSION = 46
LZMA_VERSION = 63
# we recognize (but not necessarily support) all features up to that version
MAX_EXTRACT_VERSION = 63

# Below are some formats and associated data for reading/writing headers using
# the struct module.  The names and structures of headers/records are those used
# in the PKWARE description of the ZIP file format:
#     http://www.pkware.com/documents/casestudies/APPNOTE.TXT
# (URL valid as of January 2008)

# The "end of central directory" structure, magic number, size, and indices
# (section V.I in the format document)
structEndArchive = b"<4s4H2LH"
stringEndArchive = b"PK\005\006"
sizeEndCentDir = struct.calcsize(structEndArchive)

_ECD_SIGNATURE = 0
_ECD_DISK_NUMBER = 1
_ECD_DISK_START = 2
_ECD_ENTRIES_THIS_DISK = 3
_ECD_ENTRIES_TOTAL = 4
_ECD_SIZE = 5
_ECD_OFFSET = 6
_ECD_COMMENT_SIZE = 7
# These last two indices are not part of the structure as defined in the
# spec, but they are used internally by this module as a convenience
_ECD_COMMENT = 8
_ECD_LOCATION = 9

# The "central directory" structure, magic number, size, and indices
# of entries in the structure (section V.F in the format document)
structCentralDir = "<4s4B4HL2L5H2L"
stringCentralDir = b"PK\001\002"
sizeCentralDir = struct.calcsize(structCentralDir)

# indexes of entries in the central directory structure
_CD_SIGNATURE = 0
_CD_CREATE_VERSION = 1
_CD_CREATE_SYSTEM = 2
_CD_EXTRACT_VERSION = 3
_CD_EXTRACT_SYSTEM = 4
_CD_FLAG_BITS = 5
_CD_COMPRESS_TYPE = 6
_CD_TIME = 7
_CD_DATE = 8
_CD_CRC = 9
_CD_COMPRESSED_SIZE = 10
_CD_UNCOMPRESSED_SIZE = 11
_CD_FILENAME_LENGTH = 12
_CD_EXTRA_FIELD_LENGTH = 13
_CD_COMMENT_LENGTH = 14
_CD_DISK_NUMBER_START = 15
_CD_INTERNAL_FILE_ATTRIBUTES = 16
_CD_EXTERNAL_FILE_ATTRIBUTES = 17
_CD_LOCAL_HEADER_OFFSET = 18

# The "local file header" structure, magic number, size, and indices
# (section V.A in the format document)
structFileHeader = "<4s2B4HL2L2H"
stringFileHeader = b"PK\003\004"
sizeFileHeader = struct.calcsize(structFileHeader)

_FH_SIGNATURE = 0
_FH_EXTRACT_VERSION = 1
_FH_EXTRACT_SYSTEM = 2
_FH_GENERAL_PURPOSE_FLAG_BITS = 3
_FH_COMPRESSION_METHOD = 4
_FH_LAST_MOD_TIME = 5
_FH_LAST_MOD_DATE = 6
_FH_CRC = 7
_FH_COMPRESSED_SIZE = 8
_FH_UNCOMPRESSED_SIZE = 9
_FH_FILENAME_LENGTH = 10
_FH_EXTRA_FIELD_LENGTH = 11

# The "Zip64 end of central directory locator" structure, magic number,
# and size
structEndArchive64Locator = "<4sLQL"
stringEndArchive64Locator = b"PK\x06\x07"
sizeEndCentDir64Locator = struct.calcsize(structEndArchive64Locator)

# The "Zip64 end of central directory" record, magic number, size, and indices
# (section V.G in the format document)
structEndArchive64 = "<4sQ2H2L4Q"
stringEndArchive64 = b"PK\x06\x06"
sizeEndCentDir64 = struct.calcsize(structEndArchive64)

_CD64_SIGNATURE = 0
_CD64_DIRECTORY_RECSIZE = 1
_CD64_CREATE_VERSION = 2
_CD64_EXTRACT_VERSION = 3
_CD64_DISK_NUMBER = 4
_CD64_DISK_NUMBER_START = 5
_CD64_NUMBER_ENTRIES_THIS_DISK = 6
_CD64_NUMBER_ENTRIES_TOTAL = 7
_CD64_DIRECTORY_SIZE = 8
_CD64_OFFSET_START_CENTDIR = 9


def _check_zipfile(fp):
    try:
        if _EndRecData(fp):
            return True  # file has correct magic number
    except OSError:
        pass
    return False


def is_zipfile(filename):
    """Quickly see if a file is a ZIP file by checking the magic number.

    The filename argument may be a file or file-like object too.
    """
    result = False
    try:
        if hasattr(filename, "read"):
            result = _check_zipfile(fp=filename)
        else:
            with open(filename, "rb") as fp:
                result = _check_zipfile(fp)
    except OSError:
        pass
    return result


def _EndRecData64(fpin, offset, endrec):
    """
    Read the ZIP64 end-of-archive records and use that to update endrec
    """
    try:
        fpin.seek(offset - sizeEndCentDir64Locator, 2)
    except OSError:
        # If the seek fails, the file is not large enough to contain a ZIP64
        # end-of-archive record, so just return the end record we were given.
        return endrec

    data = fpin.read(sizeEndCentDir64Locator)
    if len(data) != sizeEndCentDir64Locator:
        return endrec
    sig, diskno, reloff, disks = struct.unpack(structEndArchive64Locator, data)
    if sig != stringEndArchive64Locator:
        return endrec

    if diskno != 0 or disks != 1:
        raise BadZipFile("zipfiles that span multiple disks are not supported")

    # Assume no 'zip64 extensible data'
    fpin.seek(offset - sizeEndCentDir64Locator - sizeEndCentDir64, 2)
    data = fpin.read(sizeEndCentDir64)
    if len(data) != sizeEndCentDir64:
        return endrec
    (
        sig,
        sz,
        create_version,
        read_version,
        disk_num,
        disk_dir,
        dircount,
        dircount2,
        dirsize,
        diroffset,
    ) = struct.unpack(structEndArchive64, data)
    if sig != stringEndArchive64:
        return endrec

    # Update the original endrec using data from the ZIP64 record
    endrec[_ECD_SIGNATURE] = sig
    endrec[_ECD_DISK_NUMBER] = disk_num
    endrec[_ECD_DISK_START] = disk_dir
    endrec[_ECD_ENTRIES_THIS_DISK] = dircount
    endrec[_ECD_ENTRIES_TOTAL] = dircount2
    endrec[_ECD_SIZE] = dirsize
    endrec[_ECD_OFFSET] = diroffset
    return endrec


def _EndRecData(fpin):
    """Return data from the "End of Central Directory" record, or None.

    The data is a list of the nine items in the ZIP "End of central dir"
    record followed by a tenth item, the file seek offset of this record."""

    # Determine file size。
    fpin.seek(0, 2)
    filesize = fpin.tell()

    # Check to see if this is ZIP file with no archive comment (the
    # "end of central directory" structure should be the last item in the
    # file if this is the case).
    try:
        fpin.seek(-sizeEndCentDir, 2)
    except OSError:
        return None
    data = fpin.read()
    if (
        len(data) == sizeEndCentDir
        and data[0:4] == stringEndArchive
        and data[-2:] == b"\000\000"
    ):
        # the signature is correct and there's no comment, unpack structure
        endrec = struct.unpack(structEndArchive, data)
        endrec = list(endrec)

        # Append a blank comment and record start offset
        endrec.append(b"")
        endrec.append(filesize - sizeEndCentDir)

        # Try to read the "Zip64 end of central directory" structure
        return _EndRecData64(fpin, -sizeEndCentDir, endrec)

    # Either this is not a ZIP file, or it is a ZIP file with an archive
    # comment.  Search the end of the file for the "end of central directory"
    # record signature. The comment is the last item in the ZIP file and may be
    # up to 64K long.  It is assumed that the "end of central directory" magic
    # number does not appear in the comment.
    maxCommentStart = max(filesize - (1 << 16) - sizeEndCentDir, 0)
    fpin.seek(maxCommentStart, 0)
    data = fpin.read()
    start = data.rfind(stringEndArchive)
    if start >= 0:
        # found the magic number; attempt to unpack and interpret
        recData = data[start : start + sizeEndCentDir]
        if len(recData) != sizeEndCentDir:
            # Zip file is corrupted.
            return None
        endrec = list(struct.unpack(structEndArchive, recData))
        commentSize = endrec[_ECD_COMMENT_SIZE]  # as claimed by the zip file
        comment = data[start + sizeEndCentDir : start + sizeEndCentDir + commentSize]
        endrec.append(comment)
        endrec.append(maxCommentStart + start)

        # Try to read the "Zip64 end of central directory" structure
        return _EndRecData64(fpin, maxCommentStart + start - filesize, endrec)

    # Unable to find a valid end of central directory structure
    return None


class ZipInfo(object):
    """Class with attributes describing each file in the ZIP archive."""

    __slots__ = (
        "orig_filename",
        "filename",
        "date_time",
        "compress_type",
        "comment",
        "extra",
        "create_system",
        "create_version",
        "extract_version",
        "reserved",
        "flag_bits",
        "volume",
        "internal_attr",
        "external_attr",
        "header_offset",
        "CRC",
        "compress_size",
        "file_size",
        "_raw_time",
    )

    def __init__(self, filename="NoName", date_time=(1980, 1, 1, 0, 0, 0)):
        self.orig_filename = filename  # Original file name in archive

        # Terminate the file name at the first null byte.  Null bytes in file
        # names are used as tricks by viruses in archives.
        null_byte = filename.find(chr(0))
        if null_byte >= 0:
            filename = filename[0:null_byte]
        # This is used to ensure paths in generated ZIP files always use
        # forward slashes as the directory separator, as required by the
        # ZIP format specification.
        if os.sep != "/" and os.sep in filename:
            filename = filename.replace(os.sep, "/")

        self.filename = filename  # Normalized file name
        self.date_time = date_time  # year, month, day, hour, min, sec

        if date_time[0] < 1980:
            raise ValueError("ZIP does not support timestamps before 1980")

        # Standard values:
        self.compress_type = ZIP_STORED  # Type of compression for the file
        self.comment = b""  # Comment for each file
        self.extra = b""  # ZIP extra data
        if sys.platform == "win32":
            self.create_system = 0  # System which created ZIP archive
        else:
            # Assume everything else is unix-y
            self.create_system = 3  # System which created ZIP archive
        self.create_version = DEFAULT_VERSION  # Version which created ZIP archive
        self.extract_version = DEFAULT_VERSION  # Version needed to extract archive
        self.reserved = 0  # Must be zero
        self.flag_bits = 0  # ZIP flag bits
        self.volume = 0  # Volume number of file header
        self.internal_attr = 0  # Internal attributes
        self.external_attr = 0  # External file attributes
        # Other attributes are set by class ZipFile:
        # header_offset         Byte offset to the file header
        # CRC                   CRC-32 of the uncompressed file
        # compress_size         Size of the compressed file
        # file_size             Size of the uncompressed file

    def __repr__(self):
        result = ["<%s filename=%r" % (self.__class__.__name__, self.filename)]
        if self.compress_type != ZIP_STORED:
            result.append(
                " compress_type=%s"
                % compressor_names.get(self.compress_type, self.compress_type)
            )
        hi = self.external_attr >> 16
        lo = self.external_attr & 0xFFFF
        if hi:
            result.append(" filemode=%r" % stat.filemode(hi))
        if lo:
            result.append(" external_attr=%#x" % lo)
        isdir = self.filename[-1:] == "/"
        if not isdir or self.file_size:
            result.append(" file_size=%r" % self.file_size)
        if (not isdir or self.compress_size) and (
            self.compress_type != ZIP_STORED or self.file_size != self.compress_size
        ):
            result.append(" compress_size=%r" % self.compress_size)
        result.append(">")
        return "".join(result)

    def _decodeExtra(self):
        # Try to decode the extra field.
        extra = self.extra
        unpack = struct.unpack
        while len(extra) >= 4:
            tp, ln = unpack("<HH", extra[:4])
            if tp == 1:
                if ln >= 24:
                    counts = unpack("<QQQ", extra[4:28])
                elif ln == 16:
                    counts = unpack("<QQ", extra[4:20])
                elif ln == 8:
                    counts = unpack("<Q", extra[4:12])
                elif ln == 0:
                    counts = ()
                else:
                    raise RuntimeError("Corrupt extra field %s" % (ln,))

                idx = 0

                # ZIP64 extension (large files and/or large archives)
                if self.file_size in (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFF):
                    self.file_size = counts[idx]
                    idx += 1

                if self.compress_size == 0xFFFFFFFF:
                    self.compress_size = counts[idx]
                    idx += 1

                if self.header_offset == 0xFFFFFFFF:
                    # old = self.header_offset
                    self.header_offset = counts[idx]
                    idx += 1

            extra = extra[ln + 4 :]


class LZMADecompressor:
    def __init__(self):
        self._decomp = None
        self._unconsumed = b""
        self.eof = False

    def decompress(self, data):
        if self._decomp is None:
            self._unconsumed += data
            if len(self._unconsumed) <= 4:
                return b""
            (psize,) = struct.unpack("<H", self._unconsumed[2:4])
            if len(self._unconsumed) <= 4 + psize:
                return b""

            self._decomp = lzma.LZMADecompressor(
                lzma.FORMAT_RAW,
                filters=[
                    lzma._decode_filter_properties(
                        lzma.FILTER_LZMA1, self._unconsumed[4 : 4 + psize]
                    )
                ],
            )
            data = self._unconsumed[4 + psize :]
            del self._unconsumed

        result = self._decomp.decompress(data)
        self.eof = self._decomp.eof
        return result


compressor_names = {
    0: "store",
    1: "shrink",
    2: "reduce",
    3: "reduce",
    4: "reduce",
    5: "reduce",
    6: "implode",
    7: "tokenize",
    8: "deflate",
    9: "deflate64",
    10: "implode",
    12: "bzip2",
    14: "lzma",
    18: "terse",
    19: "lz77",
    97: "wavpack",
    98: "ppmd",
}


def _check_compression(compression):
    if compression == ZIP_STORED:
        pass
    elif compression == ZIP_DEFLATED:
        if not zlib:
            raise RuntimeError("Compression requires the (missing) zlib module")
    elif compression == ZIP_BZIP2:
        if not bz2:
            raise RuntimeError("Compression requires the (missing) bz2 module")
    elif compression == ZIP_LZMA:
        if not lzma:
            raise RuntimeError("Compression requires the (missing) lzma module")
    else:
        raise RuntimeError("That compression method is not supported")


def _get_decompressor(compress_type):
    if compress_type == ZIP_STORED:
        return None
    elif compress_type == ZIP_DEFLATED:
        return zlib.decompressobj(-15)
    elif compress_type == ZIP_BZIP2:
        return bz2.BZ2Decompressor()
    elif compress_type == ZIP_LZMA:
        return LZMADecompressor()
    else:
        descr = compressor_names.get(compress_type)
        if descr:
            raise NotImplementedError(
                "compression type %d (%s)" % (compress_type, descr)
            )
        else:
            raise NotImplementedError("compression type %d" % (compress_type,))


class _SharedFile:
    def __init__(self, file, pos, close, lock):
        self._file = file
        self._pos = pos
        self._close = close
        self._lock = lock

    def read(self, n=-1):
        with self._lock:
            self._file.seek(self._pos)
            data = self._file.read(n)
            self._pos = self._file.tell()
            return data

    def close(self):
        if self._file is not None:
            fileobj = self._file
            self._file = None
            self._close(fileobj)


class ZipExtFile(io.BufferedIOBase):
    """File-like object for reading an archive member.
    Is returned by ZipFile.open().
    """

    # Max size supported by decompressor.
    MAX_N = 1 << 31 - 1

    # Read from compressed files in 4k blocks.
    MIN_READ_SIZE = 4096

    # Search for universal newlines or line chunks.
    PATTERN = re.compile(rb"^(?P<chunk>[^\r\n]+)|(?P<newline>\n|\r\n?)")

    def __init__(self, fileobj, mode, zipinfo, decrypter=None, close_fileobj=False):
        self._fileobj = fileobj
        self._close_fileobj = close_fileobj

        self._compress_type = zipinfo.compress_type
        self._compress_left = zipinfo.compress_size
        self._left = zipinfo.file_size

        if self._compress_type not in {ZIP_STORED, ZIP_DEFLATED, ZIP_BZIP2, ZIP_LZMA}:
            self._compress_type = ZIP_STORED
        self._decompressor = _get_decompressor(self._compress_type)

        self._eof = False
        self._readbuffer = b""
        self._offset = 0

        self._universal = "U" in mode
        self.newlines = None

        self.mode = mode
        self.name = zipinfo.filename

    def __repr__(self):
        result = ["<%s.%s" % (self.__class__.__module__, self.__class__.__qualname__)]
        if not self.closed:
            result.append(" name=%r mode=%r" % (self.name, self.mode))
            if self._compress_type != ZIP_STORED:
                result.append(
                    " compress_type=%s"
                    % compressor_names.get(self._compress_type, self._compress_type)
                )
        else:
            result.append(" [closed]")
        result.append(">")
        return "".join(result)

    def readline(self, limit=-1):
        """Read and return a line from the stream.

        If limit is specified, at most limit bytes will be read.
        """

        if not self._universal and limit < 0:
            # Shortcut common case - newline found in buffer.
            i = self._readbuffer.find(b"\n", self._offset) + 1
            if i > 0:
                line = self._readbuffer[self._offset : i]
                self._offset = i
                return line

        if not self._universal:
            return io.BufferedIOBase.readline(self, limit)

        line = b""
        while limit < 0 or len(line) < limit:
            readahead = self.peek(2)
            if readahead == b"":
                return line

            #
            # Search for universal newlines or line chunks.
            #
            # The pattern returns either a line chunk or a newline, but not
            # both. Combined with peek(2), we are assured that the sequence
            # '\r\n' is always retrieved completely and never split into
            # separate newlines - '\r', '\n' due to coincidental readaheads.
            #
            match = self.PATTERN.search(readahead)
            newline = match.group("newline")
            if newline is not None:
                if self.newlines is None:
                    self.newlines = []
                if newline not in self.newlines:
                    self.newlines.append(newline)
                self._offset += len(newline)
                return line + b"\n"

            chunk = match.group("chunk")
            if limit >= 0:
                chunk = chunk[: limit - len(line)]

            self._offset += len(chunk)
            line += chunk

        return line

    def peek(self, n=1):
        """Returns buffered bytes without advancing the position."""
        if n > len(self._readbuffer) - self._offset:
            chunk = self.read(n)
            if len(chunk) > self._offset:
                self._readbuffer = chunk + self._readbuffer[self._offset :]
                self._offset = 0
            else:
                self._offset -= len(chunk)

        # Return up to 512 bytes to reduce allocation overhead for tight loops.
        return self._readbuffer[self._offset : self._offset + 512]

    def readable(self):
        return True

    def read(self, n=-1):
        """Read and return up to n bytes.
        If the argument is omitted, None, or negative, data is read and returned until EOF is reached..
        """
        if n is None or n < 0:
            buf = self._readbuffer[self._offset :]
            self._readbuffer = b""
            self._offset = 0
            while not self._eof:
                buf += self._read1(self.MAX_N)
            return buf

        end = n + self._offset
        if end < len(self._readbuffer):
            buf = self._readbuffer[self._offset : end]
            self._offset = end
            return buf

        n = end - len(self._readbuffer)
        buf = self._readbuffer[self._offset :]
        self._readbuffer = b""
        self._offset = 0
        while n > 0 and not self._eof:
            data = self._read1(n)
            if n < len(data):
                self._readbuffer = data
                self._offset = n
                buf += data[:n]
                break
            buf += data
            n -= len(data)
        return buf

    def read1(self, n):
        """Read up to n bytes with at most one read() system call."""

        if n is None or n < 0:
            buf = self._readbuffer[self._offset :]
            self._readbuffer = b""
            self._offset = 0
            while not self._eof:
                data = self._read1(self.MAX_N)
                if data:
                    buf += data
                    break
            return buf

        end = n + self._offset
        if end < len(self._readbuffer):
            buf = self._readbuffer[self._offset : end]
            self._offset = end
            return buf

        n = end - len(self._readbuffer)
        buf = self._readbuffer[self._offset :]
        self._readbuffer = b""
        self._offset = 0
        if n > 0:
            while not self._eof:
                data = self._read1(n)
                if n < len(data):
                    self._readbuffer = data
                    self._offset = n
                    buf += data[:n]
                    break
                if data:
                    buf += data
                    break
        return buf

    def _read1(self, n):
        # Read up to n compressed bytes with at most one read() system call,
        # decrypt and decompress them.
        if self._eof or n <= 0:
            return b""

        # Read from file.
        if self._compress_type == ZIP_DEFLATED:
            # Handle unconsumed data.
            data = self._decompressor.unconsumed_tail
            if n > len(data):
                data += self._read2(n - len(data))
        else:
            data = self._read2(n)

        if self._compress_type == ZIP_STORED:
            self._eof = self._compress_left <= 0
        elif self._compress_type == ZIP_DEFLATED:
            n = max(n, self.MIN_READ_SIZE)
            data = self._decompressor.decompress(data, n)
            self._eof = (
                self._decompressor.eof
                or self._compress_left <= 0
                and not self._decompressor.unconsumed_tail
            )
            if self._eof:
                data += self._decompressor.flush()
        else:
            data = self._decompressor.decompress(data)
            self._eof = self._decompressor.eof or self._compress_left <= 0

        data = data[: self._left]
        self._left -= len(data)
        if self._left <= 0:
            self._eof = True
        # 容忍规则 3：刻意不校验 CRC（部分 APK 抹掉 CRC 字段，见模块 docstring）。
        return data

    def _read2(self, n):
        if self._compress_left <= 0:
            return b""

        n = max(n, self.MIN_READ_SIZE)
        n = min(n, self._compress_left)

        data = self._fileobj.read(n)
        self._compress_left -= len(data)
        if not data:
            raise EOFError

        return data

    def close(self):
        try:
            if self._close_fileobj:
                self._fileobj.close()
        finally:
            super().close()


class ZipFile:
    """Class with methods to open, read, write, close, list zip files.

    z = ZipFile(file, mode="r", compression=ZIP_STORED, allowZip64=True)

    file: Either the path to the file, or a file-like object.
          If it is a path, the file will be opened and closed by ZipFile.
    mode: The mode can be either read 'r', write 'w', exclusive create 'x',
          or append 'a'.
    compression: ZIP_STORED (no compression), ZIP_DEFLATED (requires zlib),
                 ZIP_BZIP2 (requires bz2) or ZIP_LZMA (requires lzma).
    allowZip64: if True ZipFile will create files with ZIP64 extensions when
                needed, otherwise it will raise an exception when this would
                be necessary.

    """

    fp = None  # Set here since __del__ checks it
    _windows_illegal_name_trans_table = None

    def __init__(self, file, mode="r", compression=ZIP_STORED, allowZip64=True):
        """以只读模式打开 ZIP 归档。"""
        if mode != "r":
            raise RuntimeError("_apkfile.ZipFile 是只读 fork，仅支持 mode='r'")

        _check_compression(compression)

        self._allowZip64 = allowZip64
        self._didModify = False
        self.NameToInfo = {}  # Find file info given name
        self.filelist = []  # List of ZipInfo instances for archive
        self.compression = compression  # Method of compression
        self.mode = mode
        self.pwd = None
        self._comment = b""

        # Check if we were passed a file-like object
        if isinstance(file, str):
            self._filePassed = 0
            self.filename = file
            self.fp = io.open(file, "rb")
        else:
            self._filePassed = 1
            self.fp = file
            self.filename = getattr(file, "name", None)
        self._fileRefCnt = 1
        self._lock = threading.RLock()

        try:
            self._RealGetContents()
        except Exception:
            fp = self.fp
            self.fp = None
            self._fpclose(fp)
            raise

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def __repr__(self):
        result = ["<%s.%s" % (self.__class__.__module__, self.__class__.__qualname__)]
        if self.fp is not None:
            if self._filePassed:
                result.append(" file=%r" % self.fp)
            elif self.filename is not None:
                result.append(" filename=%r" % self.filename)
            result.append(" mode=%r" % self.mode)
        else:
            result.append(" [closed]")
        result.append(">")
        return "".join(result)

    def _RealGetContents(self):
        """Read in the table of contents for the ZIP file."""
        fp = self.fp
        try:
            endrec = _EndRecData(fp)
        except OSError:
            raise BadZipFile("File is not a zip file")
        if not endrec:
            raise BadZipFile("File is not a zip file")
        size_cd = endrec[_ECD_SIZE]  # bytes in central directory
        offset_cd = endrec[_ECD_OFFSET]  # offset of central directory
        self._comment = endrec[_ECD_COMMENT]  # archive comment

        # 容忍规则 1：假设归档无前置拼接数据（APK 不会 concat）。
        # stdlib 此处计算 concat 偏移并累加到 header_offset；对 APK 恒为 0。
        concat = 0

        # self.start_dir:  Position of start of central directory
        self.start_dir = offset_cd + concat
        fp.seek(self.start_dir, 0)
        data = fp.read(size_cd)
        fp = io.BytesIO(data)
        total = 0
        while total < size_cd:
            centdir = fp.read(sizeCentralDir)
            if len(centdir) != sizeCentralDir:
                raise BadZipFile("Truncated central directory")
            centdir = struct.unpack(structCentralDir, centdir)
            if centdir[_CD_SIGNATURE] != stringCentralDir:
                raise BadZipFile("Bad magic number for central directory")
            filename = fp.read(centdir[_CD_FILENAME_LENGTH])
            flags = centdir[5]
            if flags & 0x800:
                # UTF-8 file names extension
                filename = filename.decode("utf-8")
            else:
                # Historical ZIP filename encoding
                filename = filename.decode("cp437")
            # Create ZipInfo instance to store file information
            x = ZipInfo(filename)
            x.extra = fp.read(centdir[_CD_EXTRA_FIELD_LENGTH])
            x.comment = fp.read(centdir[_CD_COMMENT_LENGTH])
            x.header_offset = centdir[_CD_LOCAL_HEADER_OFFSET]
            (
                x.create_version,
                x.create_system,
                x.extract_version,
                x.reserved,
                x.flag_bits,
                x.compress_type,
                t,
                d,
                x.CRC,
                x.compress_size,
                x.file_size,
            ) = centdir[1:12]

            # 容忍规则 2：忽略解压版本检查——部分 APK 抬高版本字段对抗解压软件。
            # if x.extract_version > MAX_EXTRACT_VERSION:
            #     raise NotImplementedError(
            #         "zip file version %.1f" % (x.extract_version / 10)
            #     )

            x.volume, x.internal_attr, x.external_attr = centdir[15:18]
            # Convert date/time code to (year, month, day, hour, min, sec)
            x._raw_time = t
            x.date_time = (
                (d >> 9) + 1980,
                (d >> 5) & 0xF,
                d & 0x1F,
                t >> 11,
                (t >> 5) & 0x3F,
                (t & 0x1F) * 2,
            )

            x._decodeExtra()
            # x.header_offset = x.header_offset + concat
            self.filelist.append(x)
            self.NameToInfo[x.filename] = x

            # update total bytes read from central directory
            total = (
                total
                + sizeCentralDir
                + centdir[_CD_FILENAME_LENGTH]
                + centdir[_CD_EXTRA_FIELD_LENGTH]
                + centdir[_CD_COMMENT_LENGTH]
            )

    def namelist(self):
        """Return a list of file names in the archive."""
        return [data.filename for data in self.filelist]

    def infolist(self):
        """Return a list of class ZipInfo instances for files in the
        archive."""
        return self.filelist

    def testzip(self):
        """读一遍所有文件；坏文件返回其文件名，否则返回 None。

        注意：CRC 校验已按容忍规则 3 关闭，这里只验证「能读完」，
        不验证数据完整性。
        """
        chunk_size = 2**20
        for zinfo in self.filelist:
            try:
                # Read by chunks, to avoid an OverflowError or a
                # MemoryError with very large embedded files.
                with self.open(zinfo.filename, "r") as f:
                    name = zinfo.filename.split(os.path.sep)[-1]
                    # 容忍规则 7：单段文件名超过阈值（255）的条目跳过。
                    if len(name) > _MAX_FILENAME_LENGTH:
                        log.warning("存在超过255个字符串的文件名，跳过: %s", zinfo.filename)
                        continue
                    while f.read(chunk_size):  # Check CRC-32
                        pass
            except BadZipFile:
                return zinfo.filename

    def getinfo(self, name):
        """Return the instance of ZipInfo given 'name'."""
        info = self.NameToInfo.get(name)
        if info is None:
            raise KeyError("There is no item named %r in the archive" % name)

        return info

    def setpassword(self, pwd):
        """Set default password for encrypted files."""
        if pwd and not isinstance(pwd, bytes):
            raise TypeError("pwd: expected bytes, got %s" % type(pwd))
        if pwd:
            self.pwd = pwd
        else:
            self.pwd = None

    @property
    def comment(self):
        """The comment text associated with the ZIP file."""
        return self._comment

    @comment.setter
    def comment(self, comment):
        if not isinstance(comment, bytes):
            raise TypeError("comment: expected bytes, got %s" % type(comment))
        # check for valid comment length
        if len(comment) > ZIP_MAX_COMMENT:
            import warnings

            warnings.warn(
                "Archive comment is too long; truncating to %d bytes" % ZIP_MAX_COMMENT,
                stacklevel=2,
            )
            comment = comment[:ZIP_MAX_COMMENT]
        self._comment = comment
        self._didModify = True

    def read(self, name, pwd=None):
        """Return file bytes (as a string) for name."""
        with self.open(name, "r", pwd) as fp:
            return fp.read()

    def open(self, name, mode="r", pwd=None):
        """Return file-like object for 'name'."""
        if mode not in ("r", "U", "rU"):
            raise RuntimeError('open() requires mode "r", "U", or "rU"')
        if "U" in mode:
            import warnings

            warnings.warn("'U' mode is deprecated", DeprecationWarning, 2)
        if pwd and not isinstance(pwd, bytes):
            raise TypeError("pwd: expected bytes, got %s" % type(pwd))
        if not self.fp:
            raise RuntimeError("Attempt to read ZIP archive that was already closed")

        # Make sure we have an info object
        if isinstance(name, ZipInfo):
            # 'name' is already an info object
            zinfo = name
        else:
            # Get info object for name
            zinfo = self.getinfo(name)

        self._fileRefCnt += 1

        zef_file = _SharedFile(self.fp, zinfo.header_offset, self._fpclose, self._lock)

        try:
            # Skip the file header:
            fheader = zef_file.read(sizeFileHeader)

            if len(fheader) != sizeFileHeader:
                raise BadZipFile("Truncated file header")

            fheader = struct.unpack(structFileHeader, fheader)

            if fheader[_FH_SIGNATURE] != stringFileHeader:
                raise BadZipFile("Bad magic number for file header")

            # 容忍规则 4：不保留 local header 文件名，也不与 central directory
            # 的文件名比较——部分 APK 两者不一致，而文件名本就无用。
            # fname = zef_file.read(fheader[_FH_FILENAME_LENGTH])
            zef_file.read(fheader[_FH_FILENAME_LENGTH])

            if fheader[_FH_EXTRA_FIELD_LENGTH]:
                zef_file.read(fheader[_FH_EXTRA_FIELD_LENGTH])

            # 容忍规则 5：忽略 patched-data(bit 5) / strong-encryption(bit 6)
            # flag——部分 APK 声明这些 flag 但并未真加密。
            # if zinfo.flag_bits & 0x20:
            #     raise NotImplementedError("compressed patched data (flag bit 5)")
            # if zinfo.flag_bits & 0x40:
            #     raise NotImplementedError("strong encryption (flag bit 6)")

            return ZipExtFile(zef_file, mode, zinfo, None, True)
        except Exception:
            zef_file.close()
            raise

    def extract(self, member, path=None, pwd=None):
        """Extract a member from the archive to the current working directory,
        using its full name. Its file information is extracted as accurately
        as possible. `member' may be a filename or a ZipInfo object. You can
        specify a different directory using `path'.
        """
        if not isinstance(member, ZipInfo):
            member = self.getinfo(member)

        if path is None:
            path = os.getcwd()

        return self._extract_member(member, path, pwd)

    def extractall(self, path=None, members=None, pwd=None):
        """Extract all members from the archive to the current working
        directory. `path' specifies a different directory to extract to.
        `members' is optional and must be a subset of the list returned
        by namelist().
        """
        if members is None:
            members = self.namelist()

        for zipinfo in members:
            self.extract(zipinfo, path, pwd)

    @classmethod
    def _sanitize_windows_name(cls, arcname, pathsep):
        """Replace bad characters and remove trailing dots from parts."""
        table = cls._windows_illegal_name_trans_table
        if not table:
            illegal = ':<>|"?*'
            table = str.maketrans(illegal, "_" * len(illegal))
            cls._windows_illegal_name_trans_table = table
        arcname = arcname.translate(table)
        # remove trailing dots
        arcname = (x.rstrip(".") for x in arcname.split(pathsep))
        # rejoin, removing empty parts.
        arcname = pathsep.join(x for x in arcname if x)
        return arcname

    def _extract_member(self, member, targetpath, pwd):
        """Extract the ZipInfo object 'member' to a physical
        file on the path targetpath.
        """
        # build the destination pathname, replacing
        # forward slashes to platform specific separators.
        arcname = member.filename.replace("/", os.path.sep)

        if os.path.altsep:
            arcname = arcname.replace(os.path.altsep, os.path.sep)
        # interpret absolute pathname as relative, remove drive letter or
        # UNC path, redundant separators, "." and ".." components.
        arcname = os.path.splitdrive(arcname)[1]
        invalid_path_parts = ("", os.path.curdir, os.path.pardir)
        arcname = os.path.sep.join(
            x for x in arcname.split(os.path.sep) if x not in invalid_path_parts
        )
        if os.path.sep == "\\":
            # filter illegal characters on Windows
            arcname = self._sanitize_windows_name(arcname, os.path.sep)

        targetpath = os.path.join(targetpath, arcname)
        targetpath = os.path.normpath(targetpath)

        # 容忍规则 6：路径分隔符超过阈值（255）的条目在解压时跳过。
        sep_size = targetpath.count(os.path.sep)
        if sep_size > _MAX_EXTRACT_PATH_SEPARATORS:
            log.warning("跳过(路径过长): %s", targetpath)
            return

        # Create all upper directories if necessary.
        upperdirs = os.path.dirname(targetpath)
        if upperdirs and not os.path.exists(upperdirs):
            os.makedirs(upperdirs)

        if member.filename[-1] == "/":
            if not os.path.isdir(targetpath):
                os.mkdir(targetpath)
            return targetpath

        with self.open(member, pwd=pwd) as source, open(targetpath, "wb") as target:
            shutil.copyfileobj(source, target)

        return targetpath

    def __del__(self):
        """Call the "close()" method in case the user forgot."""
        self.close()

    def close(self):
        """Close the file."""
        if self.fp is None:
            return

        fp = self.fp
        self.fp = None
        self._fpclose(fp)


    def _fpclose(self, fp):
        assert self._fileRefCnt > 0
        self._fileRefCnt -= 1
        if not self._fileRefCnt and not self._filePassed:
            fp.close()

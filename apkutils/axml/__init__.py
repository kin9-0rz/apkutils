import binascii
import collections
import logging
import re
from collections import defaultdict
from enum import Enum
from struct import pack, unpack
from xml.sax.saxutils import escape

from lxml import etree

from apkutils.axml import bytecode, public

log = logging.getLogger("axml")
log.setLevel(logging.CRITICAL)

# log.setLevel(logging.DEBUG)
# handler = logging.FileHandler("axml.log")
# handler.setFormatter(
#     logging.Formatter("%(levelname)s[%(name)s][%(lineno)d]: %(message)s")
# )
# log.addHandler(handler)

# ---------------------------------------------------------------------------- #

# ------------------------------- ResourceTypes ------------------------------ #
# See http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#258
# 资源块中值的类型
TYPE_NULL = 0x00  # 数据只有0或1
# The 'data' holds a ResTable_ref, a reference to another resource table entry.
TYPE_REFERENCE = 0x01
# The 'data' holds an attribute resource identifier.
TYPE_ATTRIBUTE = 0x02
# “data”保存了包含资源表的全局值字符串池的索引。
TYPE_STRING = 0x03
# The 'data' holds a single-precision floating point number.
TYPE_FLOAT = 0x04
# The 'data' holds a complex number encoding a dimension value
# such as "100in".
TYPE_DIMENSION = 0x05
# The 'data' holds a complex number encoding a fraction of a
# container.
TYPE_FRACTION = 0x06
# The 'data' holds a dynamic ResTable_ref, which needs to be
# resolved before it can be used like a TYPE_REFERENCE.
TYPE_DYNAMIC_REFERENCE = 0x07
# The 'data' holds an attribute resource identifier, which needs to be resolved
# before it can be used like a TYPE_ATTRIBUTE.
TYPE_DYNAMIC_ATTRIBUTE = 0x08
# Beginning of integer flavors...
TYPE_FIRST_INT = 0x10
# The 'data' is a raw integer value of the form n..n.
TYPE_INT_DEC = 0x10
# The 'data' is a raw integer value of the form 0xn..n.
TYPE_INT_HEX = 0x11
# The 'data' is either 0 or 1, for input "false" or "true" respectively.
TYPE_INT_BOOLEAN = 0x12
# Beginning of color integer flavors...
TYPE_FIRST_COLOR_INT = 0x1C
# The 'data' is a raw integer value of the form #aarrggbb.
TYPE_INT_COLOR_ARGB8 = 0x1C
# The 'data' is a raw integer value of the form #rrggbb.
TYPE_INT_COLOR_RGB8 = 0x1D
# The 'data' is a raw integer value of the form #argb.
TYPE_INT_COLOR_ARGB4 = 0x1E
# The 'data' is a raw integer value of the form #rgb.
TYPE_INT_COLOR_RGB4 = 0x1F
# ...end of integer flavors.
TYPE_LAST_COLOR_INT = 0x1F
# ...end of integer flavors.
TYPE_LAST_INT = 0x1F

# ------------------------- 头部格式定义 ------------------------- #
# http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#193
# ---------------------------------------------------------------------------- #
RES_NULL_TYPE = 0x0000
RES_STRING_POOL_TYPE = 0x0001
RES_TABLE_TYPE = 0x0002

RES_XML_TYPE = 0x0003

RES_XML_FIRST_CHUNK_TYPE = 0x0100
RES_XML_START_NAMESPACE_TYPE = 0x0100
RES_XML_END_NAMESPACE_TYPE = 0x0101
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
RES_XML_CDATA_TYPE = 0x0104
RES_XML_LAST_CHUNK_TYPE = 0x017F

RES_XML_RESOURCE_MAP_TYPE = 0x0180

RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_TYPE = 0x0201
RES_TABLE_TYPE_SPEC_TYPE = 0x0202
RES_TABLE_LIBRARY_TYPE = 0x0203


class RES_CHUNK_TYPE(Enum):
    RES_NULL_TYPE = 0x0000

    RES_STRING_POOL_TYPE = 0x0001
    RES_TABLE_TYPE = 0x0002
    RES_XML_TYPE = 0x0003

    RES_XML_START_NAMESPACE_TYPE = 0x0100
    RES_XML_END_NAMESPACE_TYPE = 0x0101
    RES_XML_START_ELEMENT_TYPE = 0x0102
    RES_XML_END_ELEMENT_TYPE = 0x0103
    RES_XML_CDATA_TYPE = 0x0104

    RES_XML_RESOURCE_MAP_TYPE = 0x0180

    RES_TABLE_PACKAGE_TYPE = 0x0200
    RES_TABLE_TYPE_TYPE = 0x0201
    RES_TABLE_TYPE_SPEC_TYPE = 0x0202
    RES_TABLE_LIBRARY_TYPE = 0x0203

    RES_UNVALID_TYPE = 0xFFFF


def get_res_type(value: int) -> str:
    for v in RES_CHUNK_TYPE:
        if v.value == value:
            return v.name
    return RES_CHUNK_TYPE.RES_UNVALID_TYPE.name
    # try:
    #     return RES_CHUNK_TYPE(value).name
    # except Exception:
    #     return RES_CHUNK_TYPE.RES_UNVALID_TYPE.name


DEFAULT_HEADER_SIZES = {
    RES_XML_TYPE: 8,
    RES_STRING_POOL_TYPE: 28,
    RES_TABLE_TYPE: 12,
    RES_XML_RESOURCE_MAP_TYPE: 8,
    RES_XML_START_ELEMENT_TYPE: 16,
    RES_XML_END_ELEMENT_TYPE: 16,
    RES_XML_START_NAMESPACE_TYPE: 16,
    RES_XML_END_NAMESPACE_TYPE: 16,
    RES_TABLE_PACKAGE_TYPE: 288,
    RES_TABLE_TYPE_SPEC_TYPE: 16,
}


def verify_chunk_header_size(ctype: int, header_size: int):
    default_size = DEFAULT_HEADER_SIZES.get(ctype, -1)
    if default_size != -1:
        if default_size > header_size:
            msg = "[Verify] header size 小于默认值 {} !".format(default_size)
            log.error(msg)
            raise ResParserError(msg)

        if default_size < header_size:
            n = header_size - default_size
            log.warning(
                "[Verify] header size {} 大于默认值 {}".format(
                    header_size, default_size
                )
            )
            log.warning("[Verify] 头部后面可能存在多余的数据，数量为 {}".format(n))
            return n  # NOTE 需要根据这个值跳过填充数据
    else:
        # TODO 不存在该类型
        return -1

    return 0


class ResChunkHeader:
    """
    ResChunk_header 一共8个字节
    uint16_t type;
    uint16_t headerSize;
    uint32_t size;

    通过头的类型来判断是一个什么类型的ResChunk。
    然后，再决定使用什么方式去解析数据。

    See http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#196
    :raises: ResParserError
    """  # noqa: E501

    HEADER_SIZE = 2 + 2 + 4

    def __init__(self, buff: bytecode.BuffHandle, expected_type=None, force=False):
        """
        :param buff: the buffer set to the position where the header starts.
        :param int expected_type: the type of the header which is expected.
        """
        self.start = buff.get_idx()
        if buff.size() < self.start + self.HEADER_SIZE:
            raise ResParserError(
                "Can not read over the buffer size! Offset={}".format(self.start)
            )

        self._type, self._header_size, self._size = unpack(
            "<HHL", buff.read(self.HEADER_SIZE)
        )

        log.info(
            "[ResChunk] type={} start={}, header_size={}, size={}, end={}".format(
                get_res_type(self._type),
                self.start,
                self.header_size,
                self._size,
                self.end,
            )
        )

        if expected_type and self._type != expected_type:
            if force:
                "[ResChunk] 解析 AndroidManifest 类型不对，直接修复。"
                self._type = expected_type
            else:
                raise ResParserError(
                    "[ResChunk] 目标类型不对: Got 0x{:04x}, wanted 0x{:04x}".format(
                        self._type, expected_type
                    )
                )

        # chunk size 小于 8，这种情况不可能存在。
        if self._size < self.HEADER_SIZE:
            raise ResParserError(
                "chunk size 小于 header size {}! Offset={}".format(
                    self.HEADER_SIZE, self.start
                )
            )

        # chunk size 比 头还小，这不可能存在。
        if self._size < self._header_size:
            log.error(
                "[ResChunk] size={} < header size={}".format(
                    self._size, self._header_size
                )
            )
            raise ResParserError(
                "declared chunk size ({}) is smaller than header size ({})! Offset={}".format(  # noqa: E501
                    self._size, self._header_size, self.start
                )
            )

    @property
    def type(self):
        """
        Type identifier for this chunk
        """
        return self._type

    def fix_type(self, _type):
        self._type = _type

    @property
    def header_size(self):
        """
        Size of the chunk header (in bytes).  Adding this value to
        the address of the chunk allows you to find its associated data
        (if any).
        """
        return self._header_size

    @property
    def size(self):
        """
        Total size of this chunk (in bytes).  This is the chunkSize plus
        the size of any data associated with the chunk.  Adding this value
        to the chunk allows you to completely skip its contents (including
        any child chunks).  If this value is the same as chunkSize, there is
        no data associated with the chunk.
        """
        return self._size

    @property
    def end(self):
        """
        Get the absolute offset inside the file, where the chunk ends.
        This is equal to `ARSCHeader.start + ARSCHeader.size`.
        下一个Chunk的开始地址。
        """
        return self.start + self.size

    def __repr__(self):
        return (
            "<ARSCHeader idx='0x{:08x}' type='{}' header_size='{}' size='{}'>".format(
                self.start, self.type, self.header_size, self.size
            )
        )


# Flags in the STRING Section
SORTED_FLAG = 1 << 0
UTF8_FLAG = 1 << 8

# Position of the fields inside an attribute
ATTRIBUTE_IX_NAMESPACE_URI = 0
ATTRIBUTE_IX_NAME = 1
ATTRIBUTE_IX_VALUE_STRING = 2
ATTRIBUTE_IX_VALUE_TYPE = 3
ATTRIBUTE_IX_VALUE_DATA = 4
ATTRIBUTE_LENGHT = 5  # 5个字节

# Table used to lookup functions to determine the value representation in ARSCParser
TYPE_TABLE = {
    TYPE_ATTRIBUTE: "attribute",
    TYPE_DIMENSION: "dimension",
    TYPE_FLOAT: "float",
    TYPE_FRACTION: "fraction",
    TYPE_INT_BOOLEAN: "int_boolean",
    TYPE_INT_COLOR_ARGB4: "int_color_argb4",
    TYPE_INT_COLOR_ARGB8: "int_color_argb8",
    TYPE_INT_COLOR_RGB4: "int_color_rgb4",
    TYPE_INT_COLOR_RGB8: "int_color_rgb8",
    TYPE_INT_DEC: "int_dec",
    TYPE_INT_HEX: "int_hex",
    TYPE_NULL: "null",
    TYPE_REFERENCE: "reference",
    TYPE_STRING: "string",
}

RADIX_MULTS = [0.00390625, 3.051758e-005, 1.192093e-007, 4.656613e-010]
DIMENSION_UNITS = ["px", "dip", "sp", "pt", "in", "mm"]
FRACTION_UNITS = ["%", "%p"]

COMPLEX_UNIT_MASK = 0x0F


class ResParserError(Exception):
    """Exception for the parsers"""

    pass


def complexToFloat(xcomplex):
    """
    Convert a complex unit into float
    """
    return float(xcomplex & 0xFFFFFF00) * RADIX_MULTS[(xcomplex >> 4) & 3]


def print_nrange(alist: list, n: int):
    for b in [alist[i : i + n] for i in range(0, len(alist), n)]:
        print(b)


class ResStringPoolHeader:
    """
    StringBlock is a CHUNK inside an AXML File: `ResStringPool_header`
    It contains all strings, which are used by referecing to ID's

    See http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#436
    """

    def __init__(self, buff, header, is_android_manifest=False):
        """
        :param buff: buffer which holds the string block
        :param header: a instance of :class:`~ARSCHeader`
        """
        log.info("解析StringBlock, is_android_manifest: {}".format(is_android_manifest))
        self._cache = {}

        self.header = header
        self.stringCount = unpack("<I", buff.read(4))[0]
        log.info("字符串数量: {}".format(self.stringCount))

        self.styleCount = 0
        if is_android_manifest:
            buff.read(4)
        else:
            self.styleCount = unpack("<I", buff.read(4))[0]
        log.info("样式数量: {}".format(self.stringCount))

        # flags is_utf8
        self.flags = unpack("<I", buff.read(4))[0]
        self.m_isUTF8 = (self.flags & UTF8_FLAG) != 0

        # stringsStart 字符串数据开始的位置
        # string_pool_offset
        # The string offset is counted from the beginning of the string section
        self.stringsOffset = unpack("<I", buff.read(4))[0]

        # The styles offset is counted as well from the beginning of the string section
        self.stylesOffset = 0
        if is_android_manifest:
            buff.read(4)
        else:
            self.stylesOffset = unpack("<I", buff.read(4))[0]

        # Check if they supplied a stylesOffset even if the count is 0:
        if self.styleCount == 0 and self.stylesOffset > 0:
            log.info(
                "Styles Offset given, but styleCount is zero. "
                "This is not a problem but could indicate packers."
            )

        self.m_stringOffsets = []
        self.m_styleOffsets = []
        self.m_charbuff = ""
        self.m_styles = []

        # 字符串池与字符串偏移数组的差，这个是一个固定值
        N = 6  # NOTE resource.arsc
        if is_android_manifest:
            N = 8  # NOTE AndroidManifest.xml
        for i in range(self.stringCount):
            offset = unpack("<I", buff.read(4))[0]
            self.m_stringOffsets.append(offset)

            # 通常情况，不会执行这个，只有 stringCount 伪造一个超大的值才会执行到这里
            if self.stringsOffset + N == buff.get_idx():
                self.stringCount = i
                buff.set_idx(buff.get_idx())
                break

        # And a list of styles
        # again, a list of offsets
        for i in range(self.styleCount):
            self.m_styleOffsets.append(unpack("<I", buff.read(4))[0])

        size = self.header.size - self.stringsOffset

        # if there are styles as well, we do not want to read them too.
        # Only read them, if no
        if self.stylesOffset != 0 and self.styleCount != 0:
            size = self.stylesOffset - self.stringsOffset

        if (size % 4) != 0:
            log.warning("Size of strings is not aligned by four bytes.")

        self.m_charbuff = buff.read(size)

        if self.stylesOffset != 0 and self.styleCount != 0:
            size = self.header.size - self.stylesOffset

            if (size % 4) != 0:
                log.warning("Size of styles is not aligned by four bytes.")

            for i in range(0, size // 4):
                self.m_styles.append(unpack("<I", buff.read(4))[0])

        # self.show()

    def __repr__(self):
        return "<StringPool #strings={}, #styles={}, UTF8={}>".format(
            self.stringCount, self.styleCount, self.m_isUTF8
        )

    def __getitem__(self, idx):
        """
        Returns the string at the index in the string table
        """
        return self.getString(idx)

    def __len__(self):
        """
        Get the number of strings stored in this table
        """
        return self.stringCount

    def __iter__(self):
        """
        Iterable over all strings
        """
        for i in range(self.stringCount):
            yield self.getString(i)

    def getString(self, idx):
        """
        Return the string at the index in the string table

        :param idx: index in the string table
        :return: str
        """
        if idx in self._cache:
            return self._cache[idx]

        if idx < 0 or not self.m_stringOffsets or idx > self.stringCount:
            return ""

        offset = self.m_stringOffsets[idx]

        if self.m_isUTF8:
            self._cache[idx] = self._decode8(offset)
        else:
            self._cache[idx] = self._decode16(offset)

        return self._cache[idx]

    def getStyle(self, idx):
        """
        Return the style associated with the index

        :param idx: index of the style
        :return:
        """
        return self.m_styles[idx]

    def _decode8(self, offset):
        """
        Decode an UTF-8 String at the given offset

        :param offset: offset of the string inside the data
        :return: str
        """
        # UTF-8 Strings contain two lengths, as they might differ:
        # 1) the UTF-16 length
        str_len, skip = self._decode_length(offset, 1)
        offset += skip

        # 2) the utf-8 string length
        encoded_bytes, skip = self._decode_length(offset, 1)
        offset += skip

        data = self.m_charbuff[offset : offset + encoded_bytes]

        if self.m_charbuff[offset + encoded_bytes] != 0:
            raise ResParserError(
                "UTF-8 String is not null terminated! At offset={}".format(offset)
            )

        return self._decode_bytes(data, "utf-8", str_len)

    def _decode16(self, offset):
        """
        Decode an UTF-16 String at the given offset

        :param offset: offset of the string inside the data
        :return: str
        """
        str_len, skip = self._decode_length(offset, 2)
        offset += skip

        # The len is the string len in utf-16 units
        encoded_bytes = str_len * 2

        data = self.m_charbuff[offset : offset + encoded_bytes]

        if (
            self.m_charbuff[offset + encoded_bytes : offset + encoded_bytes + 2]
            != b"\x00\x00"
        ):
            # raise ResParserError(
            #     "UTF-16 String is not null terminated! At offset={}".format(offset)
            # )
            # NOTE 清单被混淆，暂时使用这个做替换，这种处理方式，不大好
            return "android"

        return self._decode_bytes(data, "utf-16", str_len)

    @staticmethod
    def _decode_bytes(data, encoding, str_len):
        """
        Generic decoding with length check.
        The string is decoded from bytes with the given encoding, then the length
        of the string is checked.
        The string is decoded using the "replace" method.

        :param data: bytes
        :param encoding: encoding name ("utf-8" or "utf-16")
        :param str_len: length of the decoded string
        :return: str
        """
        # string = data.decode(encoding, 'replace')
        # NOTE 直接忽略，避免乱码
        string = data.decode(encoding, "ignore")
        # NOTE 移除日志，没有必要输出
        # if len(string) != str_len:
        #     log.warning("invalid decoded string length")
        return string

    def _decode_length(self, offset, sizeof_char):
        """
        Generic Length Decoding at offset of string

        The method works for both 8 and 16 bit Strings.
        Length checks are enforced:
        * 8 bit strings: maximum of 0x7FFF bytes (See
        http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/ResourceTypes.cpp#692)
        * 16 bit strings: maximum of 0x7FFFFFF bytes (See
        http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/ResourceTypes.cpp#670)

        :param offset: offset into the string data section of the beginning of
        the string
        :param sizeof_char: number of bytes per char (1 = 8bit, 2 = 16bit)
        :returns: tuple of (length, read bytes)
        """
        sizeof_2chars = sizeof_char << 1
        fmt = "<2{}".format("B" if sizeof_char == 1 else "H")
        highbit = 0x80 << (8 * (sizeof_char - 1))

        length1, length2 = unpack(
            fmt, self.m_charbuff[offset : (offset + sizeof_2chars)]
        )

        if (length1 & highbit) != 0:
            length = ((length1 & ~highbit) << (8 * sizeof_char)) | length2
            size = sizeof_2chars
        else:
            length = length1
            size = sizeof_char

        # These are true asserts, as the size should never be less than the values
        if sizeof_char == 1:
            assert (
                length <= 0x7FFF
            ), "length of UTF-8 string is too large! At offset={}".format(offset)
        else:
            assert (
                length <= 0x7FFFFFFF
            ), "length of UTF-16 string is too large!  At offset={}".format(offset)

        return length, size

    def show(self):
        """
        Print some information on stdout about the string table
        """
        print(
            "StringBlock(stringsCount=0x%x, "
            "stringsOffset=0x%x, "
            "stylesCount=0x%x, "
            "stylesOffset=0x%x, "
            "flags=0x%x"
            ")"
            % (
                self.stringCount,
                self.stringsOffset,
                self.styleCount,
                self.stylesOffset,
                self.flags,
            )
        )

        if self.stringCount > 0:
            print()
            print("String Table: ")
            for i, s in enumerate(self):
                print("{:08d} {}".format(i, repr(s)))

        if self.styleCount > 0:
            print()
            print("Styles Table: ")
            for i in range(self.styleCount):
                print("{:08d} {}".format(i, repr(self.getStyle(i))))


# AXMLParser 专用事件
START_DOCUMENT = 0
END_DOCUMENT = 1
START_TAG = 2
END_TAG = 3
TEXT = 4


class AXMLParser:
    """
    AXMLParser reads through all chunks in the AXML file
    and implements a state machine to return information about
    the current chunk, which can then be read by :class:`~AXMLPrinter`.

    An AXML file is a file which contains multiple chunks of data, defined
    by the `ResChunk_header`.
    There is no real file magic but as the size of the first header is fixed
    and the `type` of the `ResChunk_header` is set to `RES_XML_TYPE`, a file
    will usually start with `0x03000800`.
    But there are several examples where the `type` is set to something
    else, probably in order to fool parsers.

    Typically the AXMLParser is used in a loop which terminates if `m_event` is set to `END_DOCUMENT`.
    You can use the `next()` function to get the next chunk.
    Note that not all chunk types are yielded from the iterator! Some chunks are processed in
    the AXMLParser only.
    The parser will set `is_valid()` to False if it parses something not valid.
    Messages what is wrong are logged.

    See http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#563
    """

    def __init__(self, raw_buff, is_android_manifest=False):
        self._reset()

        log.info(
            "------------------------- 解析 AndroidManifest.xml 文件 ------------------------"
        )  # noqa: E501
        self._valid = True
        self.axml_tampered = False
        self.buff = bytecode.BuffHandle(raw_buff)

        if self.buff.size() < 8:
            self._valid = False
            return

        if self.buff.size() > 0xFFFFFFFF:
            self._valid = False
            return

        # 解析AXML头，4个字节是类型，4个字节是文件大小
        try:
            axml_header = ResChunkHeader(
                self.buff, expected_type=RES_XML_TYPE, force=True
            )  # noqa: E501
        except ResParserError as e:
            log.error("Error parsing first resource header: %s", e)
            self._valid = False
            return

        verify_chunk_header_size(RES_XML_TYPE, axml_header.header_size)

        self.filesize = axml_header.size

        if axml_header.header_size != 8:
            self._valid = False
            return

        if self.filesize > self.buff.size():
            self._valid = False
            return

        if self.filesize < self.buff.size():
            self.axml_tampered = True

        # NOTE 判断是否是AXML文件，没啥用
        if axml_header.type != RES_XML_TYPE:
            self.axml_tampered = True

        # 解析下一个头 - String Pool Chunk
        try:
            header = ResChunkHeader(self.buff, expected_type=RES_STRING_POOL_TYPE)
        except ResParserError as e:
            log.error("Error parsing resource header of string pool: %s", e)
            self._valid = False
            return

        if header.header_size != 0x1C:
            self._valid = False
            return

        self.sb = ResStringPoolHeader(self.buff, header, is_android_manifest)

        # Stores resource ID mappings, if any
        self.m_resourceIDs = []

        # Store a list of prefix/uri mappings encountered
        self.namespaces = []

    def is_valid(self):
        """
        Get the state of the AXMLPrinter.
        if an error happend somewhere in the process of parsing the file,
        this flag is set to False.
        """
        return self._valid

    def _reset(self):
        self.m_event = -1
        self.m_lineNumber = -1
        self.m_name = -1
        self.m_namespaceUri = -1
        self.m_attributes = []
        self.m_idAttribute = -1
        self.m_classAttribute = -1
        self.m_styleAttribute = -1

    def __next__(self):
        self._do_next()
        return self.m_event

    def _do_next(self):
        if self.m_event == END_DOCUMENT:
            return

        self._reset()
        while self._valid:
            # Stop at the declared filesize or at the end of the file
            if self.buff.end() or self.buff.get_idx() == self.filesize:
                self.m_event = END_DOCUMENT
                break

            # Again, we read an ARSCHeader
            try:
                h = ResChunkHeader(self.buff)
            except ResParserError as e:
                log.error("Error parsing resource header: %s", e)
                self._valid = False
                return

            # Special chunk: Resource Map.
            if h.type == RES_XML_RESOURCE_MAP_TYPE:
                # Check size: < 8 bytes mean that the chunk is not complete
                # Should be aligned to 4 bytes.
                if h.size < 8 or (h.size % 4) != 0:
                    log.error("Invalid chunk size in chunk XML_RESOURCE_MAP")
                    self._valid = False
                    return

                for i in range((h.size - h.header_size) // 4):
                    self.m_resourceIDs.append(unpack("<L", self.buff.read(4))[0])
                continue

            # Parse now the XML chunks.
            if h.type < RES_XML_FIRST_CHUNK_TYPE or h.type > RES_XML_LAST_CHUNK_TYPE:
                # h.size is the size of the whole chunk including the header.
                # We read already 8 bytes of the header, thus we need to subtract them.
                log.error(
                    "Not a XML resource chunk type: 0x{:04x}. Skipping {} bytes, end={}".format(  # noqa: E501
                        h.type, h.size, h.end
                    )
                )
                self.buff.set_idx(h.end)
                continue

            # Check that we read a correct header
            if h.header_size != 0x10:
                log.error(
                    "XML Resource Type Chunk header size does not match 16! "
                    "At chunk type 0x{:04x}, declared header size={}, chunk size={}".format(
                        h.type, h.header_size, h.size
                    )
                )
                self._valid = False
                return

            # Line Number of the source file, only used as meta information
            (self.m_lineNumber,) = unpack("<L", self.buff.read(4))

            # Comment_Index (usually 0xFFFFFFFF)
            (self.m_comment_index,) = unpack("<L", self.buff.read(4))

            if self.m_comment_index != 0xFFFFFFFF and h.type in [
                RES_XML_START_NAMESPACE_TYPE,
                RES_XML_END_NAMESPACE_TYPE,
            ]:
                log.warning(
                    "Unhandled Comment at namespace chunk: '{}'".format(
                        self.sb[self.m_comment_index]
                    )
                )

            if h.type == RES_XML_START_NAMESPACE_TYPE:
                log.debug("解析 RES_XML_START_NAMESPACE_TYPE")
                (prefix,) = unpack("<L", self.buff.read(4))
                (uri,) = unpack("<L", self.buff.read(4))

                s_prefix = self.sb[prefix]
                s_uri = self.sb[uri]

                log.debug("'{}' --> {}'".format(s_prefix, s_uri))

                if s_uri == "":
                    log.warning(
                        "Namespace prefix '{}' resolves to empty URI. "
                        "This might be a packer.".format(s_prefix)
                    )

                if (prefix, uri) in self.namespaces:
                    log.info(
                        "Namespace mapping ({}, {}) already seen! "
                        "This is usually not a problem but could indicate packers or broken AXML compilers.".format(
                            prefix, uri
                        )
                    )
                self.namespaces.append((prefix, uri))

                # We can continue with the next chunk, as we store the namespace
                # mappings for each tag
                continue

            if h.type == RES_XML_END_NAMESPACE_TYPE:
                (prefix,) = unpack("<L", self.buff.read(4))
                (uri,) = unpack("<L", self.buff.read(4))

                # We remove the last namespace mapping matching
                if (prefix, uri) in self.namespaces:
                    self.namespaces.remove((prefix, uri))
                else:
                    log.warning(
                        "Reached a NAMESPACE_END without having the namespace stored before? "
                        "Prefix ID: {}, URI ID: {}".format(prefix, uri)
                    )

                # We can continue with the next chunk, as we store the namespace
                # mappings for each tag
                continue

            # START_TAG is the start of a new tag.
            if h.type == RES_XML_START_ELEMENT_TYPE:
                # * (chunk_size, line_number, comment_index - we read before)
                # * namespace_uri
                # * name
                # * flags
                # * attribute_count
                # * class_attribute
                # * 后

                verify_chunk_header_size(RES_XML_START_ELEMENT_TYPE, h.header_size)

                # Namespace URI (String ID)
                (self.m_namespaceUri,) = unpack("<L", self.buff.read(4))
                # Name of the Tag (String ID)
                (self.m_name,) = unpack("<L", self.buff.read(4))

                # 属性结构体的开始偏移量
                (attributeStart,) = unpack("<H", self.buff.read(2))
                # 属性结构体的大小
                (attributeSize,) = unpack("<H", self.buff.read(2))

                (attributeCount,) = unpack("<H", self.buff.read(2))
                (idIndex,) = unpack("<H", self.buff.read(2))
                (classIndex,) = unpack("<H", self.buff.read(2))
                (styleIndex,) = unpack("<H", self.buff.read(2))

                self.m_attribute_count = attributeCount
                self.m_idAttribute = idIndex
                self.m_classAttribute = classIndex
                self.m_styleAttribute = styleIndex

                # 结构体的字节数
                nbytes = int(attributeSize / 4)  # 一次读4个字节
                # 一次nop的数量，至少要4个字节，一次可以nop 4*n个字节。
                nop_num = attributeSize - 20
                skip_n = int(nop_num / 4)
                max_n = 5 + skip_n

                if nop_num > 0:
                    log.warning(
                        "[RES_XML_START_ELEMENT_TYPE] Attribute Chunk，填充{}位".format(
                            nop_num
                        )
                    )  # noqa: E501

                counter = 0
                for i in range(0, (self.m_attribute_count * nbytes)):  # noqa: E501
                    counter += 1
                    # ! nop_num > 0 是必须的，针对没有nop的情况。
                    if nop_num > 0 and counter == max_n:
                        self.buff.read(nop_num)
                        counter = 0
                        continue

                    if nop_num > 0 and counter >= 6:
                        self.buff.read(nop_num)
                        continue

                    # 属性结构默认是20，但是，可以根据 attributeSize 填充其他数据。
                    # * Namespace URI (String ID)
                    # * Name (String ID)
                    # * Value
                    # * Type
                    # * Data
                    self.m_attributes.append(unpack("<L", self.buff.read(4))[0])

                # Then there are class_attributes
                for i in range(
                    ATTRIBUTE_IX_VALUE_TYPE, len(self.m_attributes), ATTRIBUTE_LENGHT
                ):
                    self.m_attributes[i] = self.m_attributes[i] >> 24

                self.m_event = START_TAG
                break

            if h.type == RES_XML_END_ELEMENT_TYPE:
                (self.m_namespaceUri,) = unpack("<L", self.buff.read(4))
                (self.m_name,) = unpack("<L", self.buff.read(4))
                self.m_event = END_TAG
                break

            if h.type == RES_XML_CDATA_TYPE:
                # The CDATA field is like an attribute.
                # It contains an index into the String pool
                # as well as a typed value.
                # usually, this typed value is set to UNDEFINED

                # ResStringPool_ref data --> uint32_t index
                (self.m_name,) = unpack("<L", self.buff.read(4))
                # Res_value typedData:
                # uint16_t size
                # uint8_t res0 -> always zero
                # uint8_t dataType
                # uint32_t data
                # For now, we ingore these values
                size, res0, dataType, data = unpack("<HBBL", self.buff.read(8))
                self.m_event = TEXT
                break

            log.warning(
                "Unknown XML Chunk: 0x{:04x}, skipping {} bytes.".format(h.type, h.size)
            )
            self.buff.set_idx(h.end)

    @property
    def name(self):
        """
        Return the String assosciated with the tag name
        """
        if self.m_name == -1 or (self.m_event != START_TAG and self.m_event != END_TAG):
            return ""

        return self.sb[self.m_name]

    @property
    def comment(self):
        """
        Return the comment at the current position or None if no comment is given

        This works only for Tags, as the comments of Namespaces are silently dropped.
        Currently, there is no way of retrieving comments of namespaces.
        """
        if self.m_comment_index == 0xFFFFFFFF:
            return None

        return self.sb[self.m_comment_index]

    @property
    def namespace(self):
        """
        Return the Namespace URI (if any) as a String for the current tag
        """
        if self.m_name == -1 or (self.m_event != START_TAG and self.m_event != END_TAG):
            return ""

        # No Namespace
        if self.m_namespaceUri == 0xFFFFFFFF:
            return ""

        return self.sb[self.m_namespaceUri]

    @property
    def nsmap(self):
        """
        Returns the current namespace mapping as a dictionary

        there are several problems with the map and we try to guess a few
        things here:

        1) a URI can be mapped by many prefixes, so it is to decide which one to take
        2) a prefix might map to an empty string (some packers)
        3) uri+prefix mappings might be included several times
        4) prefix might be empty
        """

        NSMAP = dict()
        # solve 3) by using a set
        for k, v in set(self.namespaces):
            s_prefix = self.sb[k]
            s_uri = self.sb[v]
            # Solve 2) & 4) by not including
            if s_uri != "" and s_prefix != "":
                # solve 1) by using the last one in the list
                NSMAP[s_prefix] = s_uri

        return NSMAP

    @property
    def text(self):
        """
        Return the String assosicated with the current text
        """
        if self.m_name == -1 or self.m_event != TEXT:
            return ""

        return self.sb[self.m_name]

    def getName(self):
        """
        Legacy only!
        use :py:attr:`~androguard.core.bytecodes.AXMLParser.name` instead
        """
        return self.name

    def getText(self):
        """
        Legacy only!
        use :py:attr:`~androguard.core.bytecodes.AXMLParser.text` instead
        """
        return self.text

    def getPrefix(self):
        """
        Legacy only!
        use :py:attr:`~androguard.core.bytecodes.AXMLParser.namespace` instead
        """
        return self.namespace

    def _get_attribute_offset(self, index):
        """
        Return the start inside the m_attributes array for a given attribute
        """
        if self.m_event != START_TAG:
            log.warning("Current event is not START_TAG.")

        offset = index * ATTRIBUTE_LENGHT
        if offset >= len(self.m_attributes):
            log.warning("Invalid attribute index")

        return offset

    def getAttributeCount(self):
        """
        Return the number of Attributes for a Tag
        or -1 if not in a tag
        """
        if self.m_event != START_TAG:
            return -1

        return self.m_attribute_count

    def getAttributeUri(self, index):
        """
        Returns the numeric ID for the namespace URI of an attribute
        """
        offset = self._get_attribute_offset(index)
        uri = self.m_attributes[offset + ATTRIBUTE_IX_NAMESPACE_URI]

        return uri

    def getAttributeNamespace(self, index):
        """
        Return the Namespace URI (if any) for the attribute
        """
        uri = self.getAttributeUri(index)

        # No Namespace
        if uri == 0xFFFFFFFF:
            return ""

        return self.sb[uri]

    def getAttributeName(self, index):
        """
        获取属性名
        """
        offset = self._get_attribute_offset(index)
        name = self.m_attributes[offset + ATTRIBUTE_IX_NAME]
        res = self.sb[name]
        # 如果能够从字符串池中获取到属性名，那么直接返回。

        if not res or res == ":":
            attr = self.m_resourceIDs[name]
            if attr in public.SYSTEM_RESOURCES["attributes"]["inverse"]:
                res = (
                    "android:" + public.SYSTEM_RESOURCES["attributes"]["inverse"][attr]
                )
            else:
                # Attach the HEX Number, so for multiple missing attributes we do not run
                # into problems.
                res = "android:UNKNOWN_SYSTEM_ATTRIBUTE_{:08x}".format(attr)

        return res

    def getAttributeValueType(self, index):
        """
        Return the type of the attribute at the given index

        :param index: index of the attribute
        """
        offset = self._get_attribute_offset(index)
        return self.m_attributes[offset + ATTRIBUTE_IX_VALUE_TYPE]

    def getAttributeValueData(self, index):
        """
        Return the data of the attribute at the given index

        :param index: index of the attribute
        """
        offset = self._get_attribute_offset(index)
        return self.m_attributes[offset + ATTRIBUTE_IX_VALUE_DATA]

    def getAttributeValue(self, index):
        """
        This function is only used to look up strings
        All other work is done by
        :func:`~androguard.core.bytecodes.axml.format_value`
        # FIXME should unite those functions
        :param index: index of the attribute
        :return:
        """
        offset = self._get_attribute_offset(index)
        valueType = self.m_attributes[offset + ATTRIBUTE_IX_VALUE_TYPE]
        if valueType == TYPE_STRING:
            valueString = self.m_attributes[offset + ATTRIBUTE_IX_VALUE_STRING]
            return self.sb[valueString]
        return ""


def format_value(_type, _data, lookup_string=lambda ix: "<string>"):
    """
    Format a value based on type and data.
    By default, no strings are looked up and "<string>" is returned.
    You need to define `lookup_string` in order to actually lookup strings from
    the string table.

    :param _type: The numeric type of the value
    :param _data: The numeric data of the value
    :param lookup_string: A function how to resolve strings from integer IDs
    """

    # Function to prepend android prefix for attributes/references from the
    # android library
    def fmt_package(x):
        return "android:" if x >> 24 == 1 else ""

    # Function to represent integers
    def fmt_int(x):
        return (2147483647 & x) - 2147483648 if x > 2147483647 else x

    if _type == TYPE_STRING:
        return lookup_string(_data)

    elif _type == TYPE_ATTRIBUTE:
        return "?{}{:08X}".format(fmt_package(_data), _data)

    elif _type == TYPE_REFERENCE:
        return "@{}{:08X}".format(fmt_package(_data), _data)

    elif _type == TYPE_FLOAT:
        return "%f" % unpack("=f", pack("=L", _data))[0]

    elif _type == TYPE_INT_HEX:
        return "0x%08X" % _data

    elif _type == TYPE_INT_BOOLEAN:
        if _data == 0:
            return "false"
        return "true"

    elif _type == TYPE_DIMENSION:
        return "{:f}{}".format(
            complexToFloat(_data), DIMENSION_UNITS[_data & COMPLEX_UNIT_MASK]
        )

    elif _type == TYPE_FRACTION:
        return "{:f}{}".format(
            complexToFloat(_data) * 100, FRACTION_UNITS[_data & COMPLEX_UNIT_MASK]
        )

    elif TYPE_FIRST_COLOR_INT <= _type <= TYPE_LAST_COLOR_INT:
        return "#%08X" % _data

    elif TYPE_FIRST_INT <= _type <= TYPE_LAST_INT:
        return "%d" % fmt_int(_data)

    return "<0x{:X}, type 0x{:02X}>".format(_data, _type)


class AXMLPrinter:
    """
    Converter for AXML Files into a lxml ElementTree, which can easily be
    converted into XML.

    A Reference Implementation can be found at http://androidxref.com/9.0.0_r3/xref/frameworks/base/tools/aapt/XMLNode.cpp
    """

    __charrange = None
    __replacement = None

    def __init__(self, raw_buff, is_android_manifest=False):
        self.axml = AXMLParser(raw_buff, is_android_manifest)

        self.root = None
        self.packerwarning = False
        cur = []

        while self.axml.is_valid():
            _type = next(self.axml)
            if _type == START_TAG:
                uri = self._print_namespace(self.axml.namespace)
                uri, name = self._fix_name(uri, self.axml.name)
                tag = "{}{}".format(uri, name)

                comment = self.axml.comment
                if comment:
                    if self.root is None:
                        log.warning(
                            "Can not attach comment with content '{}' without root!".format(  # noqa: E501
                                comment
                            )
                        )
                    else:
                        cur[-1].append(etree.Comment(comment))

                elem = etree.Element(tag, nsmap=self.axml.nsmap)
                for i in range(self.axml.getAttributeCount()):
                    uri = self._print_namespace(self.axml.getAttributeNamespace(i))
                    attribute_name = self.axml.getAttributeName(i)
                    uri, name = self._fix_name(uri, attribute_name)
                    value = self._fix_value(self._get_attribute_value(i))

                    if "{}{}".format(uri, name) in elem.attrib:
                        log.warning(
                            "Duplicate attribute '{}{}'! Will overwrite!".format(
                                uri, name
                            )
                        )
                    elem.set("{}{}".format(uri, name), value)

                if self.root is None:
                    self.root = elem
                else:
                    if not cur:
                        # looks like we lost the root?
                        log.error(
                            "No more elements available to attach to! Is the XML malformed?"
                        )
                        break
                    cur[-1].append(elem)
                cur.append(elem)

            if _type == END_TAG:
                if not cur:
                    log.warning(
                        "Too many END_TAG! No more elements available to attach to!"
                    )

                name = self.axml.name
                uri = self._print_namespace(self.axml.namespace)
                tag = "{}{}".format(uri, name)
                if cur[-1].tag != tag:
                    log.warning(
                        "Closing tag '{}' does not match current stack! At line number: {}. Is the XML malformed?".format(
                            self.axml.name, self.axml.m_lineNumber
                        )
                    )
                cur.pop()
            if _type == TEXT:
                log.debug("TEXT for {}".format(cur[-1]))
                cur[-1].text = self.axml.text
            if _type == END_DOCUMENT:
                # Check if all namespace mappings are closed
                if len(self.axml.namespaces) > 0:
                    log.warning(
                        "Not all namespace mappings were closed! Malformed AXML?"
                    )
                break

    def get_buff(self):
        """
        Returns the raw XML file without prettification applied.

        :returns: bytes, encoded as UTF-8
        """
        return self.get_xml(pretty=False)

    def get_xml(self, pretty=True):
        """
        Get the XML as an UTF-8 string

        :returns: bytes encoded as UTF-8
        """
        return etree.tostring(self.root, encoding="utf-8", pretty_print=pretty)

    def get_xml_obj(self):
        """
        Get the XML as an ElementTree object

        :returns: :class:`lxml.etree.Element`
        """
        return self.root

    def is_valid(self):
        """
        Return the state of the AXMLParser.
        If this flag is set to False, the parsing has failed, thus
        the resulting XML will not work or will even be empty.
        """
        return self.axml.is_valid()

    def is_packed(self):
        """
        Returns True if the AXML is likely to be packed

        Packers do some weird stuff and we try to detect it.
        Sometimes the files are not packed but simply broken or compiled with
        some broken version of a tool.
        Some file corruption might also be appear to be a packed file.

        :returns: True if packer detected, False otherwise
        """
        return self.packerwarning

    def _get_attribute_value(self, index):
        """
        Wrapper function for format_value to resolve the actual value of an attribute in a tag
        :param index: index of the current attribute
        :return: formatted value
        """
        _type = self.axml.getAttributeValueType(index)
        _data = self.axml.getAttributeValueData(index)

        return format_value(_type, _data, lambda _: self.axml.getAttributeValue(index))

    def _fix_name(self, prefix, name):
        """
        Apply some fixes to element named and attribute names.
        Try to get conform to:
        > Like element names, attribute names are case-sensitive and must start with a letter or underscore.
        > The rest of the name can contain letters, digits, hyphens, underscores, and periods.
        See: https://msdn.microsoft.com/en-us/library/ms256152(v=vs.110).aspx

        This function tries to fix some broken namespace mappings.
        In some cases, the namespace prefix is inside the name and not in the prefix field.
        Then, the tag name will usually look like 'android:foobar'.
        If and only if the namespace prefix is inside the namespace mapping and the actual prefix field is empty,
        we will strip the prefix from the attribute name and return the fixed prefix URI instead.
        Otherwise replacement rules will be applied.

        The replacement rules work in that way, that all unwanted characters are replaced by underscores.
        In other words, all characters except the ones listed above are replaced.

        :param name: Name of the attribute or tag
        :param prefix: The existing prefix uri as found in the AXML chunk
        :return: a fixed version of prefix and name
        :rtype: tuple
        """
        if not name[0].isalpha() and name[0] != "_":
            log.warning(
                "Invalid start for name '{}'. "
                "XML name must start with a letter.".format(name)
            )
            self.packerwarning = True
            name = "_{}".format(name)
        if (
            name.startswith("android:")
            and prefix == ""
            and "android" in self.axml.nsmap
        ):
            # Seems be a common thing...
            log.info(
                "Name '{}' starts with 'android:' prefix but 'android' is a known prefix. Replacing prefix.".format(
                    name
                )
            )
            prefix = self._print_namespace(self.axml.nsmap["android"])
            name = name[len("android:") :]
            # It looks like this is some kind of packer... Not sure though.
            self.packerwarning = True
        elif ":" in name and prefix == "":
            self.packerwarning = True
            embedded_prefix, new_name = name.split(":", 1)
            if embedded_prefix in self.axml.nsmap:
                log.info(
                    "Prefix '{}' is in namespace mapping, assume that it is a prefix."
                )
                prefix = self._print_namespace(self.axml.nsmap[embedded_prefix])
                name = new_name
            else:
                # Print out an extra warning
                log.warning(
                    "Confused: name contains a unknown namespace prefix: '{}'. "
                    "This is either a broken AXML file or some attempt to break stuff.".format(  # noqa: E501
                        name
                    )
                )
        if not re.match(r"^[a-zA-Z0-9._-]*$", name):
            log.warning("Name '{}' contains invalid characters!".format(name))
            self.packerwarning = True
            name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)

        return prefix, name

    def _fix_value(self, value):
        """
        Return a cleaned version of a value
        according to the specification:
        > Char	   ::=   	#x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]

        See https://www.w3.org/TR/xml/#charsets

        :param value: a value to clean
        :return: the cleaned value
        """
        if not self.__charrange or not self.__replacement:
            self.__charrange = re.compile(
                "^[\u0020-\uD7FF\u0009\u000A\u000D\uE000-\uFFFD\U00010000-\U0010FFFF]*$"
            )
            self.__replacement = re.compile(
                "[^\u0020-\uD7FF\u0009\u000A\u000D\uE000-\uFFFD\U00010000-\U0010FFFF]"
            )

        # Reading string until \x00. This is the same as aapt does.
        if "\x00" in value:
            self.packerwarning = True
            log.warning(
                "Null byte found in attribute value at position {}: "
                "Value(hex): '{}'".format(
                    value.find("\x00"), binascii.hexlify(value.encode("utf-8"))
                )
            )
            value = value[: value.find("\x00")]

        if not self.__charrange.match(value):
            log.warning("Invalid character in value found. Replacing with '_'.")
            self.packerwarning = True
            value = self.__replacement.sub("_", value)
        return value

    def _print_namespace(self, uri):
        if uri != "":
            uri = "{{{}}}".format(uri)
        return uri


ACONFIGURATION_MCC = 0x0001
ACONFIGURATION_MNC = 0x0002
ACONFIGURATION_LOCALE = 0x0004
ACONFIGURATION_TOUCHSCREEN = 0x0008
ACONFIGURATION_KEYBOARD = 0x0010
ACONFIGURATION_KEYBOARD_HIDDEN = 0x0020
ACONFIGURATION_NAVIGATION = 0x0040
ACONFIGURATION_ORIENTATION = 0x0080
ACONFIGURATION_DENSITY = 0x0100
ACONFIGURATION_SCREEN_SIZE = 0x0200
ACONFIGURATION_VERSION = 0x0400
ACONFIGURATION_SCREEN_LAYOUT = 0x0800
ACONFIGURATION_UI_MODE = 0x1000
ACONFIGURATION_LAYOUTDIR_ANY = 0x00
ACONFIGURATION_LAYOUTDIR_LTR = 0x01
ACONFIGURATION_LAYOUTDIR_RTL = 0x02
ACONFIGURATION_SCREENSIZE_ANY = 0x00
ACONFIGURATION_SCREENSIZE_SMALL = 0x01
ACONFIGURATION_SCREENSIZE_NORMAL = 0x02
ACONFIGURATION_SCREENSIZE_LARGE = 0x03
ACONFIGURATION_SCREENSIZE_XLARGE = 0x04
ACONFIGURATION_SCREENLONG_ANY = 0x00
ACONFIGURATION_SCREENLONG_NO = 0x1
ACONFIGURATION_SCREENLONG_YES = 0x2
ACONFIGURATION_TOUCHSCREEN_ANY = 0x0000
ACONFIGURATION_TOUCHSCREEN_NOTOUCH = 0x0001
ACONFIGURATION_TOUCHSCREEN_STYLUS = 0x0002
ACONFIGURATION_TOUCHSCREEN_FINGER = 0x0003
ACONFIGURATION_DENSITY_DEFAULT = 0
ACONFIGURATION_DENSITY_LOW = 120
ACONFIGURATION_DENSITY_MEDIUM = 160
ACONFIGURATION_DENSITY_TV = 213
ACONFIGURATION_DENSITY_HIGH = 240
ACONFIGURATION_DENSITY_XHIGH = 320
ACONFIGURATION_DENSITY_XXHIGH = 480
ACONFIGURATION_DENSITY_XXXHIGH = 640
ACONFIGURATION_DENSITY_ANY = 0xFFFE
ACONFIGURATION_DENSITY_NONE = 0xFFFF
MASK_LAYOUTDIR = 0xC0
MASK_SCREENSIZE = 0x0F
MASK_SCREENLONG = 0x30
SHIFT_LAYOUTDIR = 6
SHIFT_SCREENLONG = 4
LAYOUTDIR_ANY = ACONFIGURATION_LAYOUTDIR_ANY << SHIFT_LAYOUTDIR
LAYOUTDIR_LTR = ACONFIGURATION_LAYOUTDIR_LTR << SHIFT_LAYOUTDIR
LAYOUTDIR_RTL = ACONFIGURATION_LAYOUTDIR_RTL << SHIFT_LAYOUTDIR
SCREENSIZE_ANY = ACONFIGURATION_SCREENSIZE_ANY
SCREENSIZE_SMALL = ACONFIGURATION_SCREENSIZE_SMALL
SCREENSIZE_NORMAL = ACONFIGURATION_SCREENSIZE_NORMAL
SCREENSIZE_LARGE = ACONFIGURATION_SCREENSIZE_LARGE
SCREENSIZE_XLARGE = ACONFIGURATION_SCREENSIZE_XLARGE
SCREENLONG_ANY = ACONFIGURATION_SCREENLONG_ANY << SHIFT_SCREENLONG
SCREENLONG_NO = ACONFIGURATION_SCREENLONG_NO << SHIFT_SCREENLONG
SCREENLONG_YES = ACONFIGURATION_SCREENLONG_YES << SHIFT_SCREENLONG
DENSITY_DEFAULT = ACONFIGURATION_DENSITY_DEFAULT
DENSITY_LOW = ACONFIGURATION_DENSITY_LOW
DENSITY_MEDIUM = ACONFIGURATION_DENSITY_MEDIUM
DENSITY_TV = ACONFIGURATION_DENSITY_TV
DENSITY_HIGH = ACONFIGURATION_DENSITY_HIGH
DENSITY_XHIGH = ACONFIGURATION_DENSITY_XHIGH
DENSITY_XXHIGH = ACONFIGURATION_DENSITY_XXHIGH
DENSITY_XXXHIGH = ACONFIGURATION_DENSITY_XXXHIGH
DENSITY_ANY = ACONFIGURATION_DENSITY_ANY
DENSITY_NONE = ACONFIGURATION_DENSITY_NONE
TOUCHSCREEN_ANY = ACONFIGURATION_TOUCHSCREEN_ANY
TOUCHSCREEN_NOTOUCH = ACONFIGURATION_TOUCHSCREEN_NOTOUCH
TOUCHSCREEN_STYLUS = ACONFIGURATION_TOUCHSCREEN_STYLUS
TOUCHSCREEN_FINGER = ACONFIGURATION_TOUCHSCREEN_FINGER


class ARSCParser:
    """
    Parser for resource.arsc files

    The ARSC File is, like the binary XML format, a chunk based format.
    Both formats are actually identical but use different chunks in order to store the data.

    The most outer chunk in the ARSC file is a chunk of type RES_TABLE_TYPE.
    Inside this chunk is a StringPool and at least one package.

    Each package is a chunk of type RES_TABLE_PACKAGE_TYPE.
    It contains again many more chunks.
    """

    def __init__(self, raw_buff):
        """
        :param bytes raw_buff: the raw bytes of the file
        """
        log.info(
            "---------------------------- 解析 resource.arsc 文件 ---------------------------"
        )  # noqa: E501
        self.buff = bytecode.BuffHandle(raw_buff)

        if self.buff.size() < 8 or self.buff.size() > 0xFFFFFFFF:
            raise ResParserError(
                "Invalid file size {} for a resources.arsc file!".format(
                    self.buff.size()
                )
            )

        self.analyzed = False
        self._resolved_strings = None
        self.packages = defaultdict(list)
        self.values = {}
        self.resource_values = defaultdict(defaultdict)
        self.resource_configs = defaultdict(lambda: defaultdict(set))
        self.resource_keys = defaultdict(lambda: defaultdict(defaultdict))
        self.stringpool_main = None

        # First, there is a ResTable_header.
        log.info("解析ARSC - ResTable_header.ResChunk_header")
        self.header = ResChunkHeader(self.buff, expected_type=RES_TABLE_TYPE)
        verify_chunk_header_size(RES_TABLE_TYPE, self.header.header_size)

        # More sanity checks...
        if self.header.header_size != 12:
            log.warning(
                "header.header_size 不是12个字节，而是 {}.".format(
                    self.header.header_size
                )
            )

        if self.header.size > self.buff.size():
            raise ResParserError(
                "ResTable_header.size = {}，实际大小为 {}；定义文件大小异常，不解析。".format(
                    self.header.size,
                    self.buff.size(),
                )
            )

        if self.header.size < self.buff.size():
            log.warning(
                "The Resource file seems to have data appended to it. Filesize: {}, declared size: {}".format(
                    self.buff.size(), self.header.size
                )
            )

        # The ResTable_header contains the packageCount, i.e. the number of ResTable_package
        self.packageCount = unpack("<I", self.buff.read(4))[0]
        log.info(
            "解析ARSC - ResTable_header.packageCount = {}".format(self.packageCount)
        )

        # Even more sanity checks...
        if self.packageCount < 1:
            log.warning("至少要有一个包!")

        # 解析完毕之后，下一个一定是一个字符串池
        is_string_pool = True

        # 直接跳到后面数据块的开头，一般情况下，这个值是12。
        self.buff.set_idx(self.header.start + self.header.header_size)
        log.info("当前的地址是: {}".format(self.buff.get_idx()))

        # 后面是
        # ResStringPool_header
        # ResTable_package
        while self.buff.get_idx() <= self.header.end - ResChunkHeader.HEADER_SIZE:
            res_header = ResChunkHeader(self.buff)
            # if res_header.end > self.header.end:
            #     # this inner chunk crosses the boundary of the table chunk
            #     log.warning(
            #         "Invalid chunk found! It is larger than the outer chunk: %s",
            #         res_header,
            #     )
            #     break
            if res_header.type == RES_NULL_TYPE:
                log.warning("[RES_NULL_TYPE] - 跳过{}个填充位".format(res_header.size))
                self.buff.set_idx(
                    self.buff.get_idx() - res_header.header_size + res_header.size
                )  # noqa: E501
                continue

            if res_header.type not in {RES_STRING_POOL_TYPE, RES_TABLE_PACKAGE_TYPE}:
                addr = self.buff.get_idx()
                log.info("未知Chunk跳过，当前的地址是: {} = {}".format(addr, hex(addr)))
                continue

            if res_header.type == RES_STRING_POOL_TYPE:
                log.info("开始解析字符串池 RES_STRING_POOL_TYPE")
                if self.stringpool_main:
                    raise ResParserError(
                        "There can be only one StringPool per resource table!"
                    )
                else:
                    self.stringpool_main = ResStringPoolHeader(self.buff, res_header)
                log.debug("找到一个字符串池 {}".format(self.stringpool_main))

            elif res_header.type == RES_TABLE_PACKAGE_TYPE:
                if len(self.packages) > self.packageCount:
                    raise ResParserError(
                        "Got more packages ({}) than expected ({})".format(
                            len(self.packages), self.packageCount
                        )
                    )

                current_package = ResTablePackage(self.buff, res_header)
                package_name = current_package.get_name()
                log.debug("Parsing package {}".format(package_name))
                # After the Header, we have the resource type symbol table
                self.buff.set_idx(
                    current_package.header.start + current_package.typeStrings
                )
                type_sp_header = ResChunkHeader(
                    self.buff, expected_type=RES_STRING_POOL_TYPE
                )
                mTableStrings = ResStringPoolHeader(self.buff, type_sp_header)

                # Next, we should have the resource key symbol table
                self.buff.set_idx(
                    current_package.header.start + current_package.keyStrings
                )
                key_sp_header = ResChunkHeader(
                    self.buff, expected_type=RES_STRING_POOL_TYPE
                )
                mKeyStrings = ResStringPoolHeader(self.buff, key_sp_header)

                # Add them to the dict of read packages
                self.packages[package_name].append(current_package)
                self.packages[package_name].append(mTableStrings)
                self.packages[package_name].append(mKeyStrings)

                pc = PackageContext(
                    current_package, self.stringpool_main, mTableStrings, mKeyStrings
                )
                # log.debug("Constructed a PackageContext: %s", pc)

                # skip to the first header in this table package chunk
                # FIXME is this correct? We have already read the first two sections!
                # self.buff.set_idx(res_header.start + res_header.header_size)
                # this looks more like we want: (???)
                # FIXME
                # 看起来我们读到的两个字符串池可能不会相互连接，因此跳转到大小的和可能是不正确的…
                next_idx = (
                    res_header.start
                    + res_header.header_size
                    + type_sp_header.size
                    + key_sp_header.size
                )

                if next_idx != self.buff.tell():
                    # If this happens, we have a testfile ;)
                    log.error("This looks like an odd resources.arsc file!")
                    log.error(
                        "Please report this error including the file you have parsed!"
                    )
                    log.error(
                        "next_idx = {}, current buffer position = {}".format(
                            next_idx, self.buff.tell()
                        )
                    )
                    log.error(
                        "Please open a issue at https://github.com/androguard/androguard/issues"
                    )
                    log.error("Thank you!")

                self.buff.set_idx(next_idx)

                # Read all other headers
                while (
                    self.buff.get_idx() <= res_header.end - ResChunkHeader.HEADER_SIZE
                ):
                    pkg_chunk_header = ResChunkHeader(self.buff)
                    if pkg_chunk_header.start + pkg_chunk_header.size > res_header.end:
                        # we are way off the package chunk; bail out
                        break

                    self.packages[package_name].append(pkg_chunk_header)

                    if pkg_chunk_header.type == RES_TABLE_TYPE_SPEC_TYPE:
                        self.packages[package_name].append(
                            ResTableTypeSpec(self.buff, pc)
                        )

                    elif pkg_chunk_header.type == RES_TABLE_TYPE_TYPE:
                        a_res_type = ResTableType(pkg_chunk_header, self.buff, pc)

                        self.packages[package_name].append(a_res_type)
                        self.resource_configs[package_name][a_res_type].add(
                            a_res_type.config
                        )

                        log.debug(
                            "a_res_type.entryCount = {}".format(a_res_type.entryCount)
                        )
                        entries = []
                        for i in range(0, a_res_type.entryCount):
                            current_package.mResId = (
                                current_package.mResId & 0xFFFF0000 | i
                            )
                            entries.append(
                                (
                                    unpack("<i", self.buff.read(4))[0],
                                    current_package.mResId,
                                )
                            )
                        log.debug("entries num: {}".format(len(entries)))
                        self.packages[package_name].append(entries)
                        log.debug("idx - {}".format(self.buff.get_idx()))

                        for entry, res_id in entries:
                            if self.buff.end():
                                break

                            if entry != -1:
                                ate = ResTableEntry(
                                    pkg_chunk_header.end, self.buff, res_id, pc
                                )
                                self.packages[package_name].append(ate)
                                if ate.is_weak():
                                    # FIXME we are not sure how to implement the FLAG_WEAK!
                                    # We saw the following: There is just a single Res_value after the ARSCResTableEntry
                                    # and then comes the next ARSCHeader.
                                    # Therefore we think this means all entries are somehow replicated?
                                    # So we do some kind of hack here. We set the idx to the entry again...
                                    # Now we will read all entries!
                                    # Not sure if this is a good solution though
                                    self.buff.set_idx(ate.start)
                    elif pkg_chunk_header.type == RES_TABLE_LIBRARY_TYPE:
                        log.warning("RES_TABLE_LIBRARY_TYPE chunk is not supported")
                    else:
                        # Unknown / not-handled chunk type
                        log.warning(
                            (
                                "Unknown chunk type encountered inside "
                                "RES_TABLE_PACKAGE: {}"
                            ).format(pkg_chunk_header)
                        )

                    # skip to the next chunk
                    self.buff.set_idx(pkg_chunk_header.end)
            else:
                # Unknown / not-handled chunk type
                log.warning(
                    "非 RES_STRING_POOL_TYPE 和 RES_TABLE_PACKAGE_TYPE 类型的chunk"
                )
                log.warning("Unknown chunk type encountered: %s", res_header)

            log.info("move to the next resource chunk: {}".format(res_header.end))
            # move to the next resource chunk
            self.buff.set_idx(res_header.end)

    def _analyse(self):
        if self.analyzed:
            return

        self.analyzed = True

        for package_name in self.packages:
            self.values[package_name] = {}

            nb = 3
            while nb < len(self.packages[package_name]):
                header = self.packages[package_name][nb]
                if isinstance(header, ResChunkHeader):
                    if header.type == RES_TABLE_TYPE_TYPE:
                        a_res_type = self.packages[package_name][nb + 1]

                        locale = a_res_type.config.get_language_and_region()

                        c_value = self.values[package_name].setdefault(
                            locale, {"public": []}
                        )

                        entries = self.packages[package_name][nb + 2]
                        nb_i = 0
                        for entry, res_id in entries:
                            if entry != -1:
                                ate = self.packages[package_name][nb + 3 + nb_i]

                                self.resource_values[ate.mResId][
                                    a_res_type.config
                                ] = ate
                                self.resource_keys[package_name][a_res_type.get_type()][
                                    ate.get_value()
                                ] = ate.mResId

                                if ate.get_index() != -1:
                                    c_value["public"].append(
                                        (
                                            a_res_type.get_type(),
                                            ate.get_value(),
                                            ate.mResId,
                                        )
                                    )

                                if a_res_type.get_type() not in c_value:
                                    c_value[a_res_type.get_type()] = []

                                if a_res_type.get_type() == "string":
                                    c_value["string"].append(
                                        self.get_resource_string(ate)
                                    )

                                elif a_res_type.get_type() == "id":
                                    if not ate.is_complex():
                                        c_value["id"].append(self.get_resource_id(ate))

                                elif a_res_type.get_type() == "bool":
                                    if not ate.is_complex():
                                        c_value["bool"].append(
                                            self.get_resource_bool(ate)
                                        )

                                elif a_res_type.get_type() == "integer":
                                    c_value["integer"].append(
                                        self.get_resource_integer(ate)
                                    )

                                elif a_res_type.get_type() == "color":
                                    c_value["color"].append(
                                        self.get_resource_color(ate)
                                    )

                                elif a_res_type.get_type() == "dimen":
                                    c_value["dimen"].append(
                                        self.get_resource_dimen(ate)
                                    )

                                nb_i += 1
                        nb += (
                            3 + nb_i - 1
                        )  # -1 to account for the nb+=1 on the next line
                nb += 1

    def get_resource_string(self, ate):
        return [ate.get_value(), ate.get_key_data()]

    def get_resource_id(self, ate):
        x = [ate.get_value()]
        if ate.key.get_data() == 0:
            x.append("false")
        elif ate.key.get_data() == 1:
            x.append("true")
        return x

    def get_resource_bool(self, ate):
        x = [ate.get_value()]
        if ate.key.get_data() == 0:
            x.append("false")
        elif ate.key.get_data() == -1:
            x.append("true")
        return x

    def get_resource_integer(self, ate):
        return [ate.get_value(), ate.key.get_data()]

    def get_resource_color(self, ate):
        entry_data = ate.key.get_data()
        return [
            ate.get_value(),
            "#{:02x}{:02x}{:02x}{:02x}".format(
                ((entry_data >> 24) & 0xFF),
                ((entry_data >> 16) & 0xFF),
                ((entry_data >> 8) & 0xFF),
                (entry_data & 0xFF),
            ),
        ]

    def get_resource_dimen(self, ate):
        data = ate.key.get_data()
        if len(DIMENSION_UNITS) < (data & COMPLEX_UNIT_MASK):
            return [ate.get_value(), data]
        else:
            return [
                ate.get_value(),
                "{}{}".format(
                    complexToFloat(data),
                    DIMENSION_UNITS[data & COMPLEX_UNIT_MASK],
                ),
            ]

    def get_resource_style(self, ate):
        return ["", ""]

    def get_packages_names(self):
        """
        Retrieve a list of all package names, which are available
        in the given resources.arsc.
        """
        return list(self.packages.keys())

    def get_locales(self, package_name):
        """
        Retrieve a list of all available locales in a given packagename.

        :param package_name: the package name to get locales of
        """
        self._analyse()
        return list(self.values[package_name].keys())

    def get_types(self, package_name, locale="\x00\x00"):
        """
        Retrieve a list of all types which are available in the given
        package and locale.

        :param package_name: the package name to get types of
        :param locale: the locale to get types of (default: '\x00\x00')
        """
        self._analyse()
        return list(self.values[package_name][locale].keys())

    def get_public_resources(self, package_name, locale="\x00\x00"):
        """
        Get the XML (as string) of all resources of type 'public'.

        The public resources table contains the IDs for each item.

        :param package_name: the package name to get the resources for
        :param locale: the locale to get the resources for (default: '\x00\x00')
        """

        self._analyse()

        buff = '<?xml version="1.0" encoding="utf-8"?>\n'
        buff += "<resources>\n"

        try:
            for i in self.values[package_name][locale]["public"]:
                buff += '<public type="{}" name="{}" id="0x{:08x}" />\n'.format(
                    i[0], i[1], i[2]
                )
        except KeyError:
            pass

        buff += "</resources>\n"

        return buff.encode("utf-8")

    def get_string_resources(self, package_name, locale="\x00\x00"):
        """
        Get the XML (as string) of all resources of type 'string'.

        Read more about string resources:
        https://developer.android.com/guide/topics/resources/string-resource.html

        :param package_name: the package name to get the resources for
        :param locale: the locale to get the resources for (default: '\x00\x00')
        """
        self._analyse()

        buff = '<?xml version="1.0" encoding="utf-8"?>\n'
        buff += "<resources>\n"

        try:
            for i in self.values[package_name][locale]["string"]:
                if any(map(i[1].__contains__, "<&>")):
                    value = "<![CDATA[%s]]>" % i[1]
                else:
                    value = i[1]
                buff += '<string name="{}">{}</string>\n'.format(i[0], value)
        except KeyError:
            pass

        buff += "</resources>\n"

        return buff.encode("utf-8")

    def get_strings_resources(self):
        """
        Get the XML (as string) of all resources of type 'string'.
        This is a combined variant, which has all locales and all package names
        stored.
        """
        self._analyse()

        buff = '<?xml version="1.0" encoding="utf-8"?>\n'

        buff += "<packages>\n"
        for package_name in self.get_packages_names():
            buff += '<package name="%s">\n' % package_name

            for locale in self.get_locales(package_name):
                buff += "<locale value=%s>\n" % repr(locale)

                buff += "<resources>\n"
                try:
                    for i in self.values[package_name][locale]["string"]:
                        buff += '<string name="{}">{}</string>\n'.format(
                            i[0], escape(i[1])
                        )
                except KeyError:
                    pass

                buff += "</resources>\n"
                buff += "</locale>\n"

            buff += "</package>\n"

        buff += "</packages>\n"

        return buff.encode("utf-8")

    def get_id_resources(self, package_name, locale="\x00\x00"):
        """
        Get the XML (as string) of all resources of type 'id'.

        Read more about ID resources:
        https://developer.android.com/guide/topics/resources/more-resources.html#Id

        :param package_name: the package name to get the resources for
        :param locale: the locale to get the resources for (default: '\x00\x00')
        """
        self._analyse()

        buff = '<?xml version="1.0" encoding="utf-8"?>\n'
        buff += "<resources>\n"

        try:
            for i in self.values[package_name][locale]["id"]:
                if len(i) == 1:
                    buff += '<item type="id" name="%s"/>\n' % (i[0])
                else:
                    buff += '<item type="id" name="{}">{}</item>\n'.format(
                        i[0], escape(i[1])
                    )
        except KeyError:
            pass

        buff += "</resources>\n"

        return buff.encode("utf-8")

    def get_bool_resources(self, package_name, locale="\x00\x00"):
        """
        Get the XML (as string) of all resources of type 'bool'.

        Read more about bool resources:
        https://developer.android.com/guide/topics/resources/more-resources.html#Bool

        :param package_name: the package name to get the resources for
        :param locale: the locale to get the resources for (default: '\x00\x00')
        """
        self._analyse()

        buff = '<?xml version="1.0" encoding="utf-8"?>\n'
        buff += "<resources>\n"

        try:
            for i in self.values[package_name][locale]["bool"]:
                if len(i) == 1:
                    log.warning("[get_bool_resources][bool] item size=1")
                    buff += '<bool name="{}">{}</bool>\n'.format(i[0], "false")
                else:
                    buff += '<bool name="{}">{}</bool>\n'.format(i[0], i[1])
        except KeyError:
            pass

        buff += "</resources>\n"

        return buff.encode("utf-8")

    def get_integer_resources(self, package_name, locale="\x00\x00"):
        """
        Get the XML (as string) of all resources of type 'integer'.

        Read more about integer resources:
        https://developer.android.com/guide/topics/resources/more-resources.html#Integer

        :param package_name: the package name to get the resources for
        :param locale: the locale to get the resources for (default: '\x00\x00')
        """
        self._analyse()

        buff = '<?xml version="1.0" encoding="utf-8"?>\n'
        buff += "<resources>\n"

        try:
            for i in self.values[package_name][locale]["integer"]:
                buff += '<integer name="{}">{}</integer>\n'.format(i[0], i[1])
        except KeyError:
            pass

        buff += "</resources>\n"

        return buff.encode("utf-8")

    def get_color_resources(self, package_name, locale="\x00\x00"):
        """
        Get the XML (as string) of all resources of type 'color'.

        Read more about color resources:
        https://developer.android.com/guide/topics/resources/more-resources.html#Color

        :param package_name: the package name to get the resources for
        :param locale: the locale to get the resources for (default: '\x00\x00')
        """
        self._analyse()

        buff = '<?xml version="1.0" encoding="utf-8"?>\n'
        buff += "<resources>\n"

        try:
            for i in self.values[package_name][locale]["color"]:
                buff += '<color name="{}">{}</color>\n'.format(i[0], i[1])
        except KeyError:
            pass

        buff += "</resources>\n"

        return buff.encode("utf-8")

    def get_dimen_resources(self, package_name, locale="\x00\x00"):
        """
        Get the XML (as string) of all resources of type 'dimen'.

        Read more about Dimension resources:
        https://developer.android.com/guide/topics/resources/more-resources.html#Dimension

        :param package_name: the package name to get the resources for
        :param locale: the locale to get the resources for (default: '\x00\x00')
        """
        self._analyse()

        buff = '<?xml version="1.0" encoding="utf-8"?>\n'
        buff += "<resources>\n"

        try:
            for i in self.values[package_name][locale]["dimen"]:
                buff += '<dimen name="{}">{}</dimen>\n'.format(i[0], i[1])
        except KeyError:
            pass

        buff += "</resources>\n"

        return buff.encode("utf-8")

    def get_id(self, package_name, rid, locale="\x00\x00"):
        """
        Returns the tuple (resource_type, resource_name, resource_id)
        for the given resource_id.

        :param package_name: package name to query
        :param rid: the resource_id
        :param locale: specific locale
        :return: tuple of (resource_type, resource_name, resource_id)
        """
        self._analyse()

        try:
            for i in self.values[package_name][locale]["public"]:
                if i[2] == rid:
                    return i
        except KeyError:
            pass
        return None, None, None

    class ResourceResolver:
        """
        Resolves resources by ID and configuration.
        This resolver deals with complex resources as well as with references.
        """

        def __init__(self, android_resources, config=None):
            """
            :param ARSCParser android_resources: A resource parser
            :param ARSCResTableConfig config: The desired configuration or None to resolve all.
            """
            self.resources = android_resources
            self.wanted_config = config

        def resolve(self, res_id):
            """
            the given ID into the Resource and returns a list of matching resources.

            :param int res_id: numerical ID of the resource
            :return: a list of tuples of (ARSCResTableConfig, str)
            """
            result = []
            self._resolve_into_result(result, res_id, self.wanted_config)
            return result

        def _resolve_into_result(self, result, res_id, config):
            # First: Get all candidates
            configs = self.resources.get_res_configs(res_id, config)

            for config, ate in configs:
                # deconstruct them and check if more candidates are generated
                self.put_ate_value(result, ate, config)

        def put_ate_value(self, result, ate, config):
            """
            Put a ResTableEntry into the list of results
            :param list result: results array
            :param ARSCResTableEntry ate:
            :param ARSCResTableConfig config:
            :return:
            """
            if ate.is_complex():
                complex_array = []
                result.append((config, complex_array))
                for _, item in ate.item.items:
                    self.put_item_value(complex_array, item, config, ate, complex_=True)
            else:
                self.put_item_value(result, ate.key, config, ate, complex_=False)

        def put_item_value(self, result, item, config, parent, complex_):
            """
            Put the tuple (ARSCResTableConfig, resolved string) into the result set

            :param list result: the result set
            :param ARSCResStringPoolRef item:
            :param ARSCResTableConfig config:
            :param ARSCResTableEntry parent: the originating entry
            :param bool complex_: True if the originating :class:`ARSCResTableEntry` was complex
            :return:
            """
            if item.is_reference():
                res_id = item.get_data()
                if res_id:
                    # Infinite loop detection:
                    # TODO should this stay here or should be detect the loop much earlier?
                    if res_id == parent.mResId:
                        log.warning(
                            "Infinite loop detected at resource item {}. It references itself!".format(
                                parent
                            )
                        )
                        return

                    self._resolve_into_result(
                        result, item.get_data(), self.wanted_config
                    )
            else:
                if complex_:
                    result.append(item.format_value())
                else:
                    result.append((config, item.format_value()))

    def get_resolved_res_configs(self, rid, config=None):
        """
        Return a list of resolved resource IDs with their corresponding configuration.
        It has a similar return type as :meth:`get_res_configs` but also handles complex entries
        and references.
        Also instead of returning :class:`ARSCResTableEntry` in the tuple, the actual values are resolved.

        This is the preferred way of resolving resource IDs to their resources.

        :param int rid: the numerical ID of the resource
        :param ARSCTableResConfig config: the desired configuration or None to retrieve all
        :return: A list of tuples of (ARSCResTableConfig, str)
        """
        # resolver = ARSCParser.ResourceResolver(self, config)
        # return resolver.resolve(rid)
        return

    def get_resolved_strings(self):
        self._analyse()
        if self._resolved_strings:
            return self._resolved_strings

        r = {}
        for package_name in self.get_packages_names():
            r[package_name] = {}
            k = {}

            for locale in self.values[package_name]:
                v_locale = locale
                if v_locale == "\x00\x00":
                    v_locale = "DEFAULT"

                r[package_name][v_locale] = {}

                try:
                    for i in self.values[package_name][locale]["public"]:
                        if i[0] == "string":
                            r[package_name][v_locale][i[2]] = None
                            k[i[1]] = i[2]
                except KeyError:
                    pass

                try:
                    for i in self.values[package_name][locale]["string"]:
                        if i[0] in k:
                            r[package_name][v_locale][k[i[0]]] = i[1]
                except KeyError:
                    pass

        self._resolved_strings = r
        return r

    def get_res_configs(self, rid, config=None, fallback=True):
        """
        Return the resources found with the ID `rid` and select
        the right one based on the configuration, or return all if no configuration was set.

        But we try to be generous here and at least try to resolve something:
        This method uses a fallback to return at least one resource (the first one in the list)
        if more than one items are found and the default config is used and no default entry could be found.

        This is usually a bad sign (i.e. the developer did not follow the android documentation:
        https://developer.android.com/guide/topics/resources/localization.html#failing2)
        In practise an app might just be designed to run on a single locale and thus only has those locales set.

        You can disable this fallback behaviour, to just return exactly the given result.

        :param rid: resource id as int
        :param config: a config to resolve from, or None to get all results
        :param fallback: Enable the fallback for resolving default configuration (default: True)
        :return: a list of ARSCResTableConfig: ARSCResTableEntry
        """
        self._analyse()

        if not rid:
            raise ValueError("'rid' should be set")
        if not isinstance(rid, int):
            raise ValueError("'rid' must be an int")

        if rid not in self.resource_values:
            log.warning(
                "The requested rid '0x{:08x}' could not be found in the list of resources.".format(
                    rid
                )
            )
            return []

        res_options = self.resource_values[rid]
        if len(res_options) > 1 and config:
            if config in res_options:
                return [(config, res_options[config])]
            elif fallback and config == ResTableConfig.default_config():
                log.warning(
                    "No default resource config could be found for the given rid '0x{:08x}', using fallback!".format(
                        rid
                    )
                )
                return [list(self.resource_values[rid].items())[0]]
            else:
                return []
        else:
            return list(res_options.items())

    def get_string(self, package_name, name, locale="\x00\x00"):
        self._analyse()

        try:
            for i in self.values[package_name][locale]["string"]:
                if i[0] == name:
                    return i
        except KeyError:
            return None

    def get_res_id_by_key(self, package_name, resource_type, key):
        try:
            return self.resource_keys[package_name][resource_type][key]
        except KeyError:
            return None

    def get_items(self, package_name):
        self._analyse()
        return self.packages[package_name]

    def get_type_configs(self, package_name, type_name=None):
        if package_name is None:
            package_name = self.get_packages_names()[0]
        result = collections.defaultdict(list)

        for res_type, configs in list(self.resource_configs[package_name].items()):
            if res_type.get_package_name() == package_name and (
                type_name is None or res_type.get_type() == type_name
            ):
                result[res_type.get_type()].extend(configs)

        return result

    @staticmethod
    def parse_id(name):
        """
        Resolves an id from a binary XML file in the form "@[package:]DEADBEEF"
        and returns a tuple of package name and resource id.
        If no package name was given, i.e. the ID has the form "@DEADBEEF",
        the package name is set to None.

        Raises a ValueError if the id is malformed.

        :param name: the string of the resource, as in the binary XML file
        :return: a tuple of (resource_id, package_name).
        """

        if not name.startswith("@"):
            raise ValueError(
                "Not a valid resource ID, must start with @: '{}'".format(name)
            )

        # remove @
        name = name[1:]

        package = None
        if ":" in name:
            package, res_id = name.split(":", 1)
        else:
            res_id = name

        if len(res_id) != 8:
            raise ValueError(
                "Numerical ID is not 8 characters long: '{}'".format(res_id)
            )

        try:
            return int(res_id, 16), package
        except ValueError:
            raise ValueError("ID is not a hex ID: '{}'".format(res_id))

    def get_resource_xml_name(self, r_id, package=None):
        """
        Returns the XML name for a resource, including the package name if package is None.
        A full name might look like `@com.example:string/foobar`
        Otherwise the name is only looked up in the specified package and is returned without
        the package name.
        The same example from about without the package name will read as `@string/foobar`.

        If the ID could not be found, `None` is returned.

        A description of the XML name can be found here:
        https://developer.android.com/guide/topics/resources/providing-resources#ResourcesFromXml

        :param r_id: numerical ID if the resource
        :param package: package name
        :return: XML name identifier
        """
        if package:
            resource, name, i_id = self.get_id(package, r_id)
            if not i_id:
                return None
            return "@{}/{}".format(resource, name)
        else:
            for p in self.get_packages_names():
                r, n, i_id = self.get_id(p, r_id)
                if i_id:
                    # found the resource in this package
                    package = p
                    resource = r
                    name = n
                    break
            if not package:
                return None
            else:
                return "@{}:{}/{}".format(package, resource, name)


class PackageContext:
    def __init__(self, current_package, stringpool_main, mTableStrings, mKeyStrings):
        """
        :param ARSCResTablePackage current_package:
        :param StringBlock stringpool_main:
        :param StringBlock mTableStrings:
        :param StringBlock mKeyStrings:
        """
        self.stringpool_main = stringpool_main
        self.mTableStrings = mTableStrings
        self.mKeyStrings = mKeyStrings
        self.current_package = current_package

    def get_mResId(self):
        return self.current_package.mResId

    def set_mResId(self, mResId):
        self.current_package.mResId = mResId

    def get_package_name(self):
        return self.current_package.get_name()

    def __repr__(self):
        return "<PackageContext {}, {}, {}, {}>".format(
            self.current_package,
            self.stringpool_main,
            self.mTableStrings,
            self.mKeyStrings,
        )


class ResTablePackage:
    """
    A `ResTable_package`

    See http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#861
    """

    def __init__(self, buff, header):
        self.header = header
        self.start = buff.get_idx()
        self.id = unpack("<I", buff.read(4))[0]
        # 128 times 16bit -> read 256 bytes
        # TODO why not read a null terminated string in buffer
        # (like the meth name suggests) instead of parsing it later in get_name()?
        self.name = buff.readNullString(256)
        self.typeStrings = unpack("<I", buff.read(4))[0]
        self.lastPublicType = unpack("<I", buff.read(4))[0]
        self.keyStrings = unpack("<I", buff.read(4))[0]
        self.lastPublicKey = unpack("<I", buff.read(4))[0]
        self.mResId = self.id << 24

        log.info(
            "[ResTablePackage] start={}, rsize={}".format(
                self.start, buff.get_idx() - self.start
            )
        )  # noqa: E501

    def get_name(self):
        name = self.name.decode("utf-16", "replace")
        name = name[: name.find("\x00")]
        return name


class ResTableTypeSpec:
    """ResTable_typeSpec

    See http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#1327
    """  # noqa: E501

    def __init__(self, buff, parent=None):
        log.info("ResTable_typeSpec")
        self.start = buff.get_idx()
        self.parent = parent
        self.id = unpack("<B", buff.read(1))[0]
        self.res0 = unpack("<B", buff.read(1))[0]
        self.res1 = unpack("<H", buff.read(2))[0]

        if self.res0 != 0:
            raise ResParserError("res0 must be zero!")
        if self.res1 != 0:
            raise ResParserError("res1 must be zero!")

        self.entryCount = unpack("<I", buff.read(4))[0]

        self.typespec_entries = []
        for i in range(0, self.entryCount):
            self.typespec_entries.append(unpack("<I", buff.read(4))[0])

        log.debug(
            " -> [ResTableTypeSpec] start={},end={},rsize={}".format(
                self.start, buff.get_idx(), buff.get_idx() - self.start
            )
        )


class ResTableType:
    """
    ! This is a `ResTable_type` without it's `ResChunk_header`.
    It contains a `ResTable_config`
    FIXME ResTableType 不是应该带有一个ResChunk_header么？

    See http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#1364
    """

    def __init__(self, chunk_header, buff, parent=None):
        self.start = buff.get_idx()
        self.parent = parent

        self.id = unpack("<B", buff.read(1))[0]
        # TODO there is now FLAG_SPARSE: http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#1401
        (self.flags,) = unpack("<B", buff.read(1))
        self.reserved = unpack("<H", buff.read(2))[0]
        if self.reserved != 0:
            raise ResParserError("reserved must be zero!")
        self.entryCount = unpack("<I", buff.read(4))[0]
        self.entriesStart = unpack("<I", buff.read(4))[0]

        self.mResId = (0xFF000000 & self.parent.get_mResId()) | self.id << 16
        self.parent.set_mResId(self.mResId)

        self.config = ResTableConfig(buff)
        log.info(
            " -> [ResTableType] start={}, end={}, real_size={}".format(
                self.start, buff.get_idx(), buff.get_idx() - self.start
            )
        )
        log.info(
            "   -> [ResTableType] entryCount={}, entriesStart={} [资源开始地址], ".format(
                self.entryCount, chunk_header.start + self.entriesStart
            )
        )
        log.info(
            " -> ResTableType.chunk_header.start + entriesStart = ResTableEntry的起始位置"
        )  # noqa: E501

    def get_type(self):
        return self.parent.mTableStrings.getString(self.id - 1)

    def get_package_name(self):
        return self.parent.get_package_name()

    def __repr__(self):
        return (
            "<ARSCResType(start=0x%x, id=0x%x, flags=0x%x, ",
            "entryCount=%d, entriesStart=0x%x, mResId=0x%x, %s)>",
        ) % (
            self.start,
            self.id,
            self.flags,
            self.entryCount,
            self.entriesStart,
            self.mResId,
            "table:" + self.parent.mTableStrings.getString(self.id - 1),
        )


class ResTableConfig:
    """
    ARSCResTableConfig contains the configuration for specific resource selection.
    This is used on the device to determine which resources should be loaded
    based on different properties of the device like locale or displaysize.

    See the definition of `ResTable_config` in
    http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#911
    """

    @classmethod
    def default_config(cls):
        if not hasattr(cls, "DEFAULT"):
            cls.DEFAULT = ResTableConfig(None)
        return cls.DEFAULT

    def __init__(self, buff: bytecode.BuffHandle = None, **kwargs):
        self.input = (
            ((kwargs.pop("keyboard", 0) & 0xFF) << 0)
            + ((kwargs.pop("navigation", 0) & 0xFF) << 8)
            + ((kwargs.pop("inputFlags", 0) & 0xFF) << 16)
            + ((kwargs.pop("inputPad0", 0) & 0xFF) << 24)
        )

        self.screenSize = ((kwargs.pop("screenWidth", 0) & 0xFFFF) << 0) + (
            (kwargs.pop("screenHeight", 0) & 0xFFFF) << 16
        )

        self.version = ((kwargs.pop("sdkVersion", 0) & 0xFFFF) << 0) + (
            (kwargs.pop("minorVersion", 0) & 0xFFFF) << 16
        )

        self.screenConfig = (
            ((kwargs.pop("screenLayout", 0) & 0xFF) << 0)
            + ((kwargs.pop("uiMode", 0) & 0xFF) << 8)
            + ((kwargs.pop("smallestScreenWidthDp", 0) & 0xFFFF) << 16)
        )

        self.screenSizeDp = ((kwargs.pop("screenWidthDp", 0) & 0xFFFF) << 0) + (
            (kwargs.pop("screenHeightDp", 0) & 0xFFFF) << 16
        )

        self.screenConfig2 = 0
        self.exceedingSize = 0

        if buff is not None:
            self.start = buff.get_idx()

            # 结构体大小
            self.size = unpack("<I", buff.read(4))[0]

            # union: uint16_t mcc, uint16_t mnc
            # mcc 移动国家代码(来自SIM卡)。0表示“任意”。
            # mnc 移动网络代码(来自SIM卡)。0表示“任意”。
            self.imsi = unpack("<I", buff.read(4))[0]

            # char language[2];
            # char country[2];
            self.locale = unpack("<I", buff.read(4))[0]

            # uint8_t orientation
            # uint8_t touchscreen
            # uint16_t density
            self.screenType = unpack("<I", buff.read(4))[0]

            if self.size > 20:
                # struct of
                # uint8_t keyboard
                # uint8_t navigation
                # uint8_t inputFlags
                # uint8_t inputPad0
                self.input = unpack("<I", buff.read(4))[0]

            if self.size > 24:
                # struct of
                # uint16_t screenWidth
                # uint16_t screenHeight
                self.screenSize = unpack("<I", buff.read(4))[0]

            if self.size > 28:
                # struct of
                # uint16_t sdkVersion
                # uint16_t minorVersion，它应该总是0，因为含义没有定义
                self.version = unpack("<I", buff.read(4))[0]

            # The next three fields seems to be optional
            if self.size >= 32:
                # struct of
                # uint8_t screenLayout
                # uint8_t uiMode
                # uint16_t smallestScreenWidthDp
                (self.screenConfig,) = unpack("<I", buff.read(4))

            if self.size >= 36:
                # struct of
                # uint16_t screenWidthDp
                # uint16_t screenHeightDp
                (self.screenSizeDp,) = unpack("<I", buff.read(4))

            if self.size >= 40:
                # struct of
                # uint8_t screenLayout2
                # uint8_t colorMode
                # uint16_t screenConfigPad2
                (self.screenConfig2,) = unpack("<I", buff.read(4))

            self.exceedingSize = self.size - (buff.tell() - self.start)
            if self.exceedingSize > 0:
                log.debug("Skipping padding bytes!")
                self.padding = buff.read(self.exceedingSize)
        else:
            self.start = 0
            self.size = 0
            self.imsi = ((kwargs.pop("mcc", 0) & 0xFFFF) << 0) + (
                (kwargs.pop("mnc", 0) & 0xFFFF) << 16
            )

            self.locale = 0
            for char_ix, char in kwargs.pop("locale", "")[0:4]:
                self.locale += ord(char) << (char_ix * 8)

            self.screenType = (
                ((kwargs.pop("orientation", 0) & 0xFF) << 0)
                + ((kwargs.pop("touchscreen", 0) & 0xFF) << 8)
                + ((kwargs.pop("density", 0) & 0xFFFF) << 16)
            )

        log.info(
            " -> [ResTableType][ResTableConfig] start={},end={},size={},rsize={}".format(  # noqa: E501
                self.start, buff.get_idx(), self.size, buff.get_idx() - self.start
            )
        )

    def _unpack_language_or_region(self, char_in, char_base):
        char_out = ""
        if char_in[0] & 0x80:
            first = char_in[1] & 0x1F
            second = ((char_in[1] & 0xE0) >> 5) + ((char_in[0] & 0x03) << 3)
            third = (char_in[0] & 0x7C) >> 2
            char_out += chr(first + char_base)
            char_out += chr(second + char_base)
            char_out += chr(third + char_base)
        else:
            if char_in[0]:
                char_out += chr(char_in[0])
            if char_in[1]:
                char_out += chr(char_in[1])
        return char_out

    def get_language_and_region(self):
        """
        Returns the combined language+region string or \x00\x00 for the default locale
        :return:
        """
        if self.locale != 0:
            _language = self._unpack_language_or_region(
                [
                    self.locale & 0xFF,
                    (self.locale & 0xFF00) >> 8,
                ],
                ord("a"),
            )
            _region = self._unpack_language_or_region(
                [
                    (self.locale & 0xFF0000) >> 16,
                    (self.locale & 0xFF000000) >> 24,
                ],
                ord("0"),
            )
            return (_language + "-r" + _region) if _region else _language
        return "\x00\x00"

    def get_config_name_friendly(self):
        """
        Here for legacy reasons.

        use :meth:`~get_qualifier` instead.
        """
        return self.get_qualifier()

    def get_qualifier(self):
        """
        Return resource name qualifier for the current configuration.
        for example
        * `ldpi-v4`
        * `hdpi-v4`

        All possible qualifiers are listed in table 2 of https://developer.android.com/guide/topics/resources/providing-resources

        ..todo:: This name might not have all properties set! Therefore returned values might not reflect the true qualifier name!
        :return: str
        """
        res = []

        mcc = self.imsi & 0xFFFF
        mnc = (self.imsi & 0xFFFF0000) >> 16
        if mcc != 0:
            res.append("mcc%d" % mcc)
        if mnc != 0:
            res.append("mnc%d" % mnc)

        if self.locale != 0:
            res.append(self.get_language_and_region())

        screenLayout = self.screenConfig & 0xFF
        if (screenLayout & MASK_LAYOUTDIR) != 0:
            if screenLayout & MASK_LAYOUTDIR == LAYOUTDIR_LTR:
                res.append("ldltr")
            elif screenLayout & MASK_LAYOUTDIR == LAYOUTDIR_RTL:
                res.append("ldrtl")
            else:
                res.append("layoutDir_%d" % (screenLayout & MASK_LAYOUTDIR))

        smallestScreenWidthDp = (self.screenConfig & 0xFFFF0000) >> 16
        if smallestScreenWidthDp != 0:
            res.append("sw%ddp" % smallestScreenWidthDp)

        screenWidthDp = self.screenSizeDp & 0xFFFF
        screenHeightDp = (self.screenSizeDp & 0xFFFF0000) >> 16
        if screenWidthDp != 0:
            res.append("w%ddp" % screenWidthDp)
        if screenHeightDp != 0:
            res.append("h%ddp" % screenHeightDp)

        if (screenLayout & MASK_SCREENSIZE) != SCREENSIZE_ANY:
            if screenLayout & MASK_SCREENSIZE == SCREENSIZE_SMALL:
                res.append("small")
            elif screenLayout & MASK_SCREENSIZE == SCREENSIZE_NORMAL:
                res.append("normal")
            elif screenLayout & MASK_SCREENSIZE == SCREENSIZE_LARGE:
                res.append("large")
            elif screenLayout & MASK_SCREENSIZE == SCREENSIZE_XLARGE:
                res.append("xlarge")
            else:
                res.append("screenLayoutSize_%d" % (screenLayout & MASK_SCREENSIZE))
        if (screenLayout & MASK_SCREENLONG) != 0:
            if screenLayout & MASK_SCREENLONG == SCREENLONG_NO:
                res.append("notlong")
            elif screenLayout & MASK_SCREENLONG == SCREENLONG_YES:
                res.append("long")
            else:
                res.append("screenLayoutLong_%d" % (screenLayout & MASK_SCREENLONG))

        density = (self.screenType & 0xFFFF0000) >> 16
        if density != DENSITY_DEFAULT:
            if density == DENSITY_LOW:
                res.append("ldpi")
            elif density == DENSITY_MEDIUM:
                res.append("mdpi")
            elif density == DENSITY_TV:
                res.append("tvdpi")
            elif density == DENSITY_HIGH:
                res.append("hdpi")
            elif density == DENSITY_XHIGH:
                res.append("xhdpi")
            elif density == DENSITY_XXHIGH:
                res.append("xxhdpi")
            elif density == DENSITY_XXXHIGH:
                res.append("xxxhdpi")
            elif density == DENSITY_NONE:
                res.append("nodpi")
            elif density == DENSITY_ANY:
                res.append("anydpi")
            else:
                res.append("%ddpi" % (density))

        touchscreen = (self.screenType & 0xFF00) >> 8
        if touchscreen != TOUCHSCREEN_ANY:
            if touchscreen == TOUCHSCREEN_NOTOUCH:
                res.append("notouch")
            elif touchscreen == TOUCHSCREEN_FINGER:
                res.append("finger")
            elif touchscreen == TOUCHSCREEN_STYLUS:
                res.append("stylus")
            else:
                res.append("touchscreen_%d" % touchscreen)

        screenSize = self.screenSize
        if screenSize != 0:
            screenWidth = self.screenSize & 0xFFFF
            screenHeight = (self.screenSize & 0xFFFF0000) >> 16
            res.append("%dx%d" % (screenWidth, screenHeight))

        version = self.version
        if version != 0:
            sdkVersion = self.version & 0xFFFF
            minorVersion = (self.version & 0xFFFF0000) >> 16
            res.append("v%d" % sdkVersion)
            if minorVersion != 0:
                res.append(".%d" % minorVersion)

        return "-".join(res)

    def get_language(self):
        x = self.locale & 0x0000FFFF
        return chr(x & 0x00FF) + chr((x & 0xFF00) >> 8)

    def get_country(self):
        x = (self.locale & 0xFFFF0000) >> 16
        return chr(x & 0x00FF) + chr((x & 0xFF00) >> 8)

    def get_density(self):
        x = (self.screenType >> 16) & 0xFFFF
        return x

    def is_default(self):
        """
        Test if this is a default resource, which matches all

        This is indicated that all fields are zero.
        :return: True if default, False otherwise
        """
        return all(map(lambda x: x == 0, self._get_tuple()))

    def _get_tuple(self):
        return (
            self.imsi,
            self.locale,
            self.screenType,
            self.input,
            self.screenSize,
            self.version,
            self.screenConfig,
            self.screenSizeDp,
            self.screenConfig2,
        )

    def __hash__(self):
        return hash(self._get_tuple())

    def __eq__(self, other):
        return self._get_tuple() == other._get_tuple()

    def __repr__(self):
        return "<ARSCResTableConfig '{}'={}>".format(
            self.get_qualifier(), repr(self._get_tuple())
        )


class ResTableEntry:
    """
    A `ResTable_entry`.

    See http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#1458
    """

    # If set, this is a complex entry, holding a set of name/value
    # mappings.  It is followed by an array of ResTable_map structures.
    FLAG_COMPLEX = 1

    # If set, this resource has been declared public, so libraries
    # are allowed to reference it.
    FLAG_PUBLIC = 2

    # If set, this is a weak resource and may be overriden by strong
    # resources of the same name/type. This is only useful during
    # linking with other resource tables.
    FLAG_WEAK = 4

    def __init__(self, chunk_end, buff, mResId, parent=None):
        self.start = buff.get_idx()
        self.mResId = mResId
        self.parent = parent  # ResTable_ref
        # 0xpptteeee

        self.size = unpack("<H", buff.read(2))[0]
        self.flags = unpack("<H", buff.read(2))[0]
        self.index = unpack("<I", buff.read(4))[0]  # ResStringPool_ref

        log.info(
            " -> [ResTableEntry] flags={}, start={},end={},size={},rsize={}".format(
                self.flags,
                self.start,
                buff.get_idx(),
                self.size,
                buff.get_idx() - self.start,  # noqa: E501
            )
        )

        # NOTE 注意，强制修复，效果未知
        if self.size == 0xFFFF:
            self.size = 8
            log.info("  -> [ResTableEntry] fix size = 8")

        # NOTE 注意，强制修复，效果未知
        if self.flags > 7:
            self.flags = 0
            log.info("  -> [ResTableEntry] fix flags = 0")

        if self.is_complex():
            log.info("  -> [ResTableEntry] is_complex")
            self.tmp = ResTableMapEntry(chunk_end, buff, parent)
        else:
            self.key = ResValue(buff, self.parent)

    def get_index(self):
        return self.index

    def get_value(self):
        return self.parent.mKeyStrings.getString(self.index)

    def get_key_data(self):
        return self.key.get_data_value()

    def is_public(self):
        return (self.flags & self.FLAG_PUBLIC) != 0

    def is_complex(self):
        return (self.flags & self.FLAG_COMPLEX) != 0

    def is_weak(self):
        return (self.flags & self.FLAG_WEAK) != 0

    def __repr__(self):
        return (
            "<ARSCResTableEntry idx='0x{:08x}' mResId='0x{:08x}' size='{}' ",
            "flags='0x{:02x}' index='0x{:x}' holding={}>",
        ).format(
            self.start,
            self.mResId,
            self.size,
            self.flags,
            self.index,
            self.item if self.is_complex() else self.key,
        )


class ResTableMapEntry:
    """
    This is actually a `ResTable_map_entry`

    It contains a set of {name: value} mappings, which are of type `ResTable_map`.
    A `ResTable_map` contains two items: `ResTable_ref` and `Res_value`.

    See http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#1485 for `ResTable_map_entry`
    and http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#1498 for `ResTable_map`
    """

    def __init__(self, chunk_end, buff, parent=None):
        self.start = buff.get_idx()
        self.parent = parent

        self.id_parent = unpack("<I", buff.read(4))[0]
        self.count = unpack("<I", buff.read(4))[0]

        self.items = []
        # unpack requires a buffer of 4 bytes
        # Parse self.count number of `ResTable_map`
        # these are structs of ResTable_ref and Res_value
        # ResTable_ref is a uint32_t.
        for i in range(0, self.count):
            # NOTE 当前位置不能超过chunk大小
            if buff.tell() + 4 > chunk_end:
                break

            if buff.get_idx() + 4 > buff.size():
                log.error("Invalid ResTable_map_entry 溢出")
                raise Exception("Invalid ResTable_map_entry 溢出")

            self.items.append(
                (unpack("<I", buff.read(4))[0], ResValue(buff, self.parent))
            )

        log.info(
            " -> [ResTableMapEntry] start={},end={},rsize={}".format(
                self.start, buff.get_idx(), buff.get_idx() - self.start
            )
        )

    def __repr__(self):
        return "<ARSCComplex idx='0x{:08x}' parent='{}' count='{}'>".format(
            self.start, self.id_parent, self.count
        )


class ResValue:
    """
    This is actually a `Res_value`
    It holds information about the stored resource value

    See: http://androidxref.com/9.0.0_r3/xref/frameworks/base/libs/androidfw/include/androidfw/ResourceTypes.h#262
    """

    def __init__(self, buff, parent=None):
        self.start = buff.get_idx()
        self.parent = parent

        (self.size,) = unpack("<H", buff.read(2))
        (self.res0,) = unpack("<B", buff.read(1))
        # if self.res0 != 0:
        #     log.warning("res0 must be always zero!")
        # raise ResParserError("res0 must be always zero!")
        # NOTE 跳过，这个值一般是0，如果不是，说明 arsc 文件可能有异常。
        # buff.read(1)

        self.data_type = unpack("<B", buff.read(1))[0]
        # data is interpreted according to data_type
        self.data = unpack("<I", buff.read(4))[0]

        # NOTE 只能是8，不能是其他值
        if self.size != 8:
            log.warning(" -> [ResValue] size={}, 不是8，强制赋予8.".format(self.size))
            self.size = 8

        log.info(
            "      -> [ResValue] start={},end={},size={},rsize={}".format(
                self.start, buff.get_idx(), self.size, buff.get_idx() - self.start
            )
        )

    def get_data_value(self):
        return self.parent.stringpool_main.getString(self.data)

    def get_data(self):
        return self.data

    def get_data_type(self):
        return self.data_type

    def get_data_type_string(self):
        return TYPE_TABLE[self.data_type]

    def format_value(self):
        """
        Return the formatted (interpreted) data according to `data_type`.
        """
        return format_value(
            self.data_type, self.data, self.parent.stringpool_main.getString
        )

    def is_reference(self):
        """
        Returns True if the Res_value is actually a reference to another resource
        """
        return self.data_type == TYPE_REFERENCE

    def __repr__(self):
        return "<ARSCResStringPoolRef idx='0x{:08x}' size='{}' type='{}' data='0x{:08x}'>".format(
            self.start,
            self.size,
            TYPE_TABLE.get(self.data_type, "0x%x" % self.data_type),
            self.data,
        )


def get_arsc_info(arscobj):
    """
    返回一个字符串，包含按包名、地区和类型排序的所有资源包。

    :param arscobj: :class:`~ARSCParser`
    :return: a string
    """
    buff = ""
    for package in arscobj.get_packages_names():
        buff += package + ":\n"
        for locale in arscobj.get_locales(package):
            buff += "\t" + repr(locale) + ":\n"
            for ttype in arscobj.get_types(package, locale):
                buff += "\t\t" + ttype + ":\n"
                try:
                    tmp_buff = (
                        getattr(arscobj, "get_" + ttype + "_resources")(package, locale)
                        .decode("utf-8", "replace")
                        .split("\n")
                    )
                    for i in tmp_buff:
                        buff += "\t\t\t" + i + "\n"
                except AttributeError:
                    pass
    return buff

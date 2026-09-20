import os
import zipfile

from apkutils._dex import DexReader, convert_proto_string

FIXTURES = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))
MAIN_ACTIVITY = "com/example/hellojni/MainActivity"


def _dex_blobs(fixture):
    with zipfile.ZipFile(os.path.join(FIXTURES, fixture)) as zf:
        names = [
            name
            for name in zf.namelist()
            if name.startswith("classes") and name.endswith(".dex")
        ]
        return [zf.read(name) for name in names]


def test_empty_reader():
    reader = DexReader([])

    assert reader.files() == []
    assert reader.classes() == []
    assert reader.strings() == []
    assert reader.opcodes_list() == []


def test_reads_classes_and_strings():
    reader = DexReader(_dex_blobs("test.zip"))

    assert len(reader.files()) == 1
    assert b"com/example/hellojni/MainActivity" in reader.classes()
    assert len(reader.strings()) == 8594
    assert len(reader.hex_strings()) == 8594
    assert b"hellojni" in reader.strings()


def test_opcodes_for_a_method():
    reader = DexReader(_dex_blobs("test.zip"))

    item = next(
        item
        for item in reader.opcodes_list()
        if item["class_name"] == MAIN_ACTIVITY and item["method_name"] == "onCreate"
    )

    assert item["super_class"] == "android/app/Activity"
    assert item["method_desc"] == "(Landroid/os/Bundle;)V"
    assert item["proto"] == "VL"
    assert item["opcodes"] == "6F156E0E"


def test_strings_refx_index():
    reader = DexReader(_dex_blobs("test.zip"))

    index = reader.strings_refx_index()

    assert b"hellojni" in index[MAIN_ACTIVITY]["<clinit>"]


def test_convert_proto_string():
    assert convert_proto_string(b"V", []) == "V"
    assert convert_proto_string(b"[I", [b"I"]) == "LI"
    assert convert_proto_string(b"V", [b"I", b"Ljava/lang/String;"]) == "VIL"


def test_methods_returns_real_set():
    reader = DexReader(_dex_blobs("test.zip"))

    methods = reader.methods()

    assert isinstance(methods, set)
    assert MAIN_ACTIVITY + "/onCreate" in methods


def test_methods_refx_index_returns_real_dict():
    reader = DexReader(_dex_blobs("test.zip"))

    index = reader.methods_refx_index()

    assert b"android/app/Activity-><init>" in index[MAIN_ACTIVITY]["<init>"]


def test_each_view_traverses_the_skeleton_once(monkeypatch):
    reader = DexReader(_dex_blobs("test.zip"))
    calls = []
    original = reader._iter_parsed_classes

    def spy():
        calls.append(1)
        return original()

    monkeypatch.setattr(reader, "_iter_parsed_classes", spy)

    reader.methods()
    reader.methods()
    assert len(calls) == 1

    reader.opcodes_list()
    reader.opcodes_list()
    assert len(calls) == 2

    reader.strings_refx_index()
    reader.methods_refx_index()
    assert len(calls) == 4


def test_targeted_queries_do_not_traverse(monkeypatch):
    reader = DexReader(_dex_blobs("test.zip"))
    calls = []
    monkeypatch.setattr(reader, "_iter_parsed_classes", lambda: calls.append(1))

    reader.method_strings(MAIN_ACTIVITY + "->onCreate(Landroid/os/Bundle;)V")
    reader.xref(MAIN_ACTIVITY + "->onCreate(Landroid/os/Bundle;)V")

    assert calls == []


def test_bad_blob_is_skipped_without_losing_the_rest():
    reader = DexReader([b"not a dex"] + _dex_blobs("test.zip"))

    assert len(reader.files()) == 1
    assert len(reader.skipped) == 1
    assert b"com/example/hellojni/MainActivity" in reader.classes()

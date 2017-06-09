# Test sample from : https://github.com/googlesamples/android-ndk/tree/master/hello-jni
import json

from apkutils import apk

if __name__ == "__main__":
    apk_path = "E:\\samples\\base.apk"

    # Test get files
    infos = apk.get_files(apk_path)
    buff = json.dumps(infos, indent=4)
    with open("file.json", "w") as fd:
        fd.write(buff)

    # Test get manifest infos
    infos = apk.get_manifest(apk_path)
    buff = json.dumps(infos, indent=4)
    with open("manifset.json", "w") as fd:
        fd.write(buff)

    # Test get dex strings
    infos = apk.get_dex_infos(apk_path, opcodes_flag=False)
    buff = json.dumps(infos, indent=4)
    with open("dex_strings.json", "w") as fd:
        fd.write(buff)

    # Test get dex opcodes
    infos = apk.get_dex_infos(apk_path, string_flag=False)
    buff = json.dumps(infos, indent=4)
    with open("dex_opcodes.json", "w") as fd:
        fd.write(buff)

    # Test get dex infos
    infos = apk.get_dex_infos(apk_path)
    buff = json.dumps(infos, indent=4)
    with open("dex.json", "w") as fd:
        fd.write(buff)

    # Test get elf infos
    infos = apk.get_elf_infos(apk_path)
    buff = json.dumps(infos, indent=4)
    with open("elf.json", "w") as fd:
        fd.write(buff)

    # # Test get elf infos
    infos = apk.get_resource_infos(apk_path)
    buff = json.dumps(infos, indent=4)
    with open("resource_string.json", "w") as fd:
        fd.write(buff)

from apkutils import APK

path = "/Users/lyb/Sources/apkutils/bf3e8b04dfb8ee429e4eee006daa511c.apk"
apk = APK.from_file(path)
print(apk.get_manifest())

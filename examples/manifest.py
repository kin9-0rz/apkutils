import json
import os

from apkutils import APK

file_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", 'data', 'test'))
apk = APK.from_file(file_path)

m_xml = apk.get_org_manifest()
print(m_xml)

m_dict = apk.get_manifest()
print(json.dumps(m_dict, indent=1))

# get any item you want from dict
print('package:', m_dict['@package'])
print('android:versionName:', m_dict['@android:versionName'])
